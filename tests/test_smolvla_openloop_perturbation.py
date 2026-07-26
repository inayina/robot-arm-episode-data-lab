"""CPU tests for open-loop perturbation helpers (no GPU / no SmolVLA load)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from training.smolvla_s3.nuisance_perturbations import (
    apply_nuisance_bgr,
    condition_seed,
)
from training.smolvla_s3.stage_anchors import (
    STAGE_NAMES,
    build_episode_plan,
    close_window_indices,
    first_close_frame,
    select_stage_anchors,
)

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "configs" / "smolvla_s3" / "openloop_perturbation.yaml"


def test_perturbation_config_contract() -> None:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    assert cfg["gate_eligible"] is False
    assert cfg["claims_task_success"] is False
    assert cfg["inference_mode"] == "canonical_first_action"
    assert cfg["horizon"] == 1
    assert set(cfg["layers"]["stage_anchors"]["stages"]) == set(STAGE_NAMES)
    assert cfg["layers"]["stage_anchors"]["expected_inferences"] == 240
    assert "state_ee_noise" in cfg["excluded_from_main_table"]


def test_first_close_debounce() -> None:
    # open ... brief blip ... sustained close
    cmds = [1.0] * 10 + [0.0, 1.0] + [0.0] * 5
    assert first_close_frame(cmds, debounce=3) == 12
    assert first_close_frame(cmds, debounce=1) == 10


def test_close_window_clamped() -> None:
    assert close_window_indices(20, 2, before=10, after=10) == list(range(0, 13))
    assert close_window_indices(21, 10, before=10, after=10) == list(range(0, 21))
    assert len(close_window_indices(300, 180, before=10, after=10)) == 21


def test_stage_anchors_cover_six_and_order() -> None:
    n = 250
    # Descend then close around 180, then lift.
    z = np.linspace(0.45, 0.12, 180).tolist() + np.linspace(0.12, 0.40, 70).tolist()
    g = [1.0] * 180 + [0.0] * 70
    selected = select_stage_anchors(ee_z=z, gripper_cmds=g, close_debounce=3)
    anchors = selected["anchors"]
    assert set(anchors) == set(STAGE_NAMES)
    assert anchors["hover_approach"] < anchors["descend_mid"] <= anchors["pre_close"]
    assert anchors["pre_close"] <= anchors["close_transition"]
    assert anchors["close_transition"] <= anchors["early_lift"] <= anchors["late_lift"]
    assert selected["close_idx"] == 180


def test_build_episode_plan_window_len() -> None:
    z = np.linspace(0.4, 0.1, 200).tolist()
    g = [1.0] * 150 + [0.0] * 50
    plan = build_episode_plan(
        {"ref": "ep/episode_000000"},
        ee_z=z,
        gripper_cmds=g,
        window_before=10,
        window_after=10,
    )
    assert plan["close_window_len"] == 21
    assert plan["close_idx"] in plan["close_window_indices"]


def test_nuisance_clean_is_identity() -> None:
    rng = np.random.default_rng(0)
    frame = rng.integers(0, 255, size=(48, 64, 3), dtype=np.uint8)
    out = apply_nuisance_bgr(
        frame,
        {"brightness_scale": 1.0, "gaussian_blur_ksize": 0, "gaussian_noise_std": 0.0},
    )
    assert np.array_equal(out, frame)


def test_nuisance_heavy_changes_pixels_and_seed_stable() -> None:
    frame = np.full((32, 32, 3), 120, dtype=np.uint8)
    spec = {"brightness_scale": 0.55, "gaussian_blur_ksize": 7, "gaussian_noise_std": 28.0}
    s = condition_seed("ep/episode_000000", 42, "heavy")
    a = apply_nuisance_bgr(frame, spec, rng=np.random.default_rng(s))
    b = apply_nuisance_bgr(frame, spec, rng=np.random.default_rng(s))
    assert np.array_equal(a, b)
    assert not np.array_equal(a, frame)
