from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "training" / "scripts" / "audit_smolvla_griptiming_dataset.py"
SPEC = importlib.util.spec_from_file_location("smolvla_griptiming_audit_test", SCRIPT)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


def test_geometry_relative_timing_and_label_metrics() -> None:
    n = 10
    action = np.zeros((n, 8), dtype=np.float64)
    action[:, 2] = [0.18, 0.15, 0.12, 0.09, 0.07, 0.04, 0.04, 0.04, 0.04, 0.04]
    action[:, 7] = [1.0] * 7 + [0.0] * 3
    ee = np.zeros((n, 7), dtype=np.float64)
    ee[:, 2] = action[:, 2]
    obj = np.zeros((n, 7), dtype=np.float64)
    obj[:, 2] = 0.025
    timestamps = np.arange(n, dtype=np.float64) * 0.1
    thresholds = AUDIT.Round2Thresholds(
        min_open_descent_frames=1,
        min_stable_open_seconds=0.1,
        max_ee_step_l2_p90_m=1.0,
    )

    metrics = AUDIT.analyze_episode_arrays(
        action=action,
        ee_pose=ee,
        object_pose=obj,
        timestamps=timestamps,
        thresholds=thresholds,
    )

    assert metrics["first_close_frame"] == 7
    assert metrics["first_close_geometry_ok"] is True
    assert metrics["stable_pick_open_frames"] == 2
    assert abs(metrics["stable_pick_open_seconds"] - 0.2) < 1e-12
    assert metrics["open_descent_frames"] == 5
    assert metrics["gripper_close_edges"] == 1
    assert metrics["gripper_reopen_edges"] == 0
    assert AUDIT._episode_target_failures(metrics, thresholds) == []


def test_hysteresis_detects_reopen_but_ignores_ramp_band() -> None:
    closes, reopens = AUDIT._hysteresis_edges(
        [1.0, 0.8, 0.55, 0.45, 0.2, 0.0, 0.5, 0.7, 1.0]
    )
    assert closes == 1
    assert reopens == 1


def test_monotonic_close_ramp_is_not_a_target_failure() -> None:
    metrics = {
        "first_close_geometry_ok": True,
        "open_descent_frames": 40,
        "stable_pick_open_seconds": 4.5,
        "gripper_close_edges": 1,
        "gripper_reopen_edges": 0,
        "gripper_min": 0.0,
        "gripper_max": 1.0,
        "gripper_intermediate_fraction": 0.25,
        "ee_step_l2_p90_m": 0.008,
    }

    assert AUDIT._episode_target_failures(
        metrics, AUDIT.Round2Thresholds()
    ) == []


def test_ee_p90_boundary_ignores_float_roundoff() -> None:
    metrics = {
        "first_close_geometry_ok": True,
        "open_descent_frames": 30,
        "stable_pick_open_seconds": 4.5,
        "gripper_close_edges": 1,
        "gripper_reopen_edges": 0,
        "gripper_min": 0.0,
        "gripper_max": 1.0,
        "ee_step_l2_p90_m": 0.008000000000000007,
    }

    assert AUDIT._episode_target_failures(
        metrics, AUDIT.Round2Thresholds()
    ) == []


def test_source_seed_parser_is_explicit() -> None:
    assert (
        AUDIT._seed_from_name(
            "e2_red_500hz_seed56_griptiming_lateclose10_20260723"
        )
        == 56
    )
    assert AUDIT._seed_from_name("dataset_without_seed") is None
