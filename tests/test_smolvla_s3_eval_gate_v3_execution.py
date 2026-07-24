"""Contract tests for eval-gate-v3 (execution-semantics severity revision).

v3 is a human-approved revision of the frozen v2 gate: execution-clip
invariants and the contact-risk close edge stay gated; open-edge raw
overshoot becomes report-only diagnostics inside a [-0.5, 1.5] sanity
envelope. Historical v2 decisions are not reclassified.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from training.smolvla_s3.eval_gate_v3 import (
    GATE_CONTRACT_VERSION_V3,
    SEVERITY_GATE_CONTRACT_VERSIONS,
    compute_gripper_severity_metrics,
    decide_gate_v3,
    validate_prospective_context,
)


ROOT = Path(__file__).resolve().parents[1]
GATE_V2_PATH = ROOT / "configs" / "smolvla_s3" / "eval_gate_v2.yaml"
GATE_V3_PATH = ROOT / "configs" / "smolvla_s3" / "eval_gate_v3.yaml"
LOCK_V3_PATH = ROOT / "configs" / "smolvla_s3" / "eval_gate_v3.lock.json"


def _gate_v2() -> dict:
    return yaml.safe_load(GATE_V2_PATH.read_text(encoding="utf-8"))


def _gate_v3() -> dict:
    return yaml.safe_load(GATE_V3_PATH.read_text(encoding="utf-8"))


def _threshold_digest(gate: dict) -> str:
    payload = {
        "gripper_range_severity_contract": gate[
            "gripper_range_severity_contract"
        ],
        "thresholds": gate["thresholds"],
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _measured_prospective_metrics(*, prospective: bool) -> dict:
    """Measured 2026-07-24 v2 prospective Hold numbers (retry1 report)."""
    return {
        "ee_position_rmse_m": 0.025967761453333616,
        "quaternion_angular_error_rad": 0.01,
        "gripper_balanced_accuracy": 0.9931396967255146,
        "gripper_close_timing_error_frames": 1.9,
        "action_smoothness_ee_step_l2_p90": 0.02983534771757356,
        "home_no_close_detected_rate": 0.0,
        "temporal_metrics_gate_eligible": True,
        "raw_gripper_oob_ratio": 0.4373363262252151,
        "raw_gripper_oob_beyond_epsilon_ratio": 0.01870557426112982,
        "raw_gripper_oob_beyond_epsilon_open_edge_ratio": 43 / 2673,
        "raw_gripper_oob_beyond_epsilon_close_edge_ratio": 7 / 2673,
        "gripper_clip_adjustment_mae": 0.006957991735078046,
        "gripper_clip_adjustment_max_abs": 0.2153458595275879,
        "raw_gripper_min": -0.06957733631134033,
        "raw_gripper_max": 1.215345859527588,
        "gripper_clip_classification_change_ratio": 0.0,
        "gripper_clip_close_timing_change_frames_max_abs": 0,
        "mapped_gripper_command_in_range": True,
        "mapped_gripper_matches_clip_max_abs": 0.0,
        "prospective_eval_eligible": prospective,
        "gripper_nonfinite_any": False,
    }


def test_v3_gate_and_lock_match_exact_bytes() -> None:
    gate = _gate_v3()
    lock = json.loads(LOCK_V3_PATH.read_text(encoding="utf-8"))
    assert gate["contract_version"] == GATE_CONTRACT_VERSION_V3
    assert GATE_CONTRACT_VERSION_V3 in SEVERITY_GATE_CONTRACT_VERSIONS
    assert gate["status"] == "approved_frozen"
    assert gate["thresholds_frozen"] is True
    assert gate["authorized_isaac"] is False
    assert gate["historical_v2_decisions_unchanged"] is True
    assert (
        lock["gate_sha256"]
        == hashlib.sha256(GATE_V3_PATH.read_bytes()).hexdigest()
    )
    assert lock["threshold_payload_sha256"] == _threshold_digest(gate)


def test_v3_design_refs_include_the_v2_prospective_ten() -> None:
    refs = _gate_v3()["prospective_evaluation_contract"][
        "threshold_design_episode_refs"
    ]
    v2_prospective = [ref for ref in refs if "_v3_prospective_" in ref]
    assert len(v2_prospective) == 10
    # And the original 14 v2 design episodes stay quarantined too.
    assert len(refs) == 24


def test_side_split_metrics_computed_from_frame_logs() -> None:
    values = [-0.2, -0.02, 0.5, 1.02, 1.2, 1.3]
    episode = {
        "frame_logs": [
            {
                "raw_pred": [0.0] * 7 + [value],
                "pred_gripper_cmd": min(1.0, max(0.0, value)),
            }
            for value in values
        ]
    }
    metrics = compute_gripper_severity_metrics(
        [episode], grip_idx=7, epsilon=0.05
    )
    assert metrics[
        "raw_gripper_oob_beyond_epsilon_open_edge_ratio"
    ] == pytest.approx(2 / 6)
    assert metrics[
        "raw_gripper_oob_beyond_epsilon_close_edge_ratio"
    ] == pytest.approx(1 / 6)
    assert metrics["raw_gripper_oob_beyond_epsilon_ratio"] == pytest.approx(
        3 / 6
    )


def test_measured_v2_hold_numbers_pass_under_v3_execution_semantics() -> None:
    metrics = _measured_prospective_metrics(prospective=True)
    v2 = decide_gate_v3(
        _gate_v2(),
        metrics,
        s2_ee=_gate_v2()["baselines"]["s2_ee_rmse_m"],
        prospective_context={"eligible": True},
    )
    assert v2["gate_decision"] == "hold"
    assert set(v2["pass_failures"]) == {
        "gripper_oob_severity",
        "gripper_clip_max",
        "raw_gripper_max",
    }
    v3 = decide_gate_v3(
        _gate_v3(),
        metrics,
        s2_ee=_gate_v3()["baselines"]["s2_ee_rmse_m"],
        prospective_context={"eligible": True},
    )
    assert v3["gate_decision"] == "pass"
    assert v3["isaac_ready_candidate"] is True
    assert v3["isaac_authorized"] is False


def test_v3_cannot_pass_without_prospective_eligibility() -> None:
    result = decide_gate_v3(
        _gate_v3(),
        _measured_prospective_metrics(prospective=False),
        s2_ee=_gate_v3()["baselines"]["s2_ee_rmse_m"],
        prospective_context={"eligible": False},
    )
    assert result["gate_decision"] == "hold"
    assert "prospective_eligibility" in result["pass_failures"]


def test_v3_close_edge_overshoot_beyond_threshold_is_hold() -> None:
    metrics = _measured_prospective_metrics(prospective=True)
    metrics["raw_gripper_oob_beyond_epsilon_close_edge_ratio"] = 0.02
    result = decide_gate_v3(
        _gate_v3(),
        metrics,
        s2_ee=_gate_v3()["baselines"]["s2_ee_rmse_m"],
        prospective_context={"eligible": True},
    )
    assert result["gate_decision"] == "hold"
    assert "gripper_close_edge_oob" in result["pass_failures"]


def test_v3_raw_outside_sanity_envelope_is_no_go() -> None:
    for key, value in (
        ("raw_gripper_max", 1.6),
        ("raw_gripper_min", -0.6),
    ):
        metrics = _measured_prospective_metrics(prospective=True)
        metrics[key] = value
        result = decide_gate_v3(
            _gate_v3(),
            metrics,
            s2_ee=_gate_v3()["baselines"]["s2_ee_rmse_m"],
            prospective_context={"eligible": True},
        )
        assert result["gate_decision"] == "no_go"
        assert "raw_gripper_outside_sanity_envelope" in result["reasons"]


def test_v3_keeps_execution_clip_invariants_as_no_go() -> None:
    metrics = _measured_prospective_metrics(prospective=True)
    metrics["gripper_clip_classification_change_ratio"] = 0.001
    result = decide_gate_v3(
        _gate_v3(),
        metrics,
        s2_ee=_gate_v3()["baselines"]["s2_ee_rmse_m"],
        prospective_context={"eligible": True},
    )
    assert result["gate_decision"] == "no_go"
    assert "clip_classification_change" in result["reasons"]


def test_v3_prospective_context_rejects_design_contaminated_episodes() -> None:
    gate = _gate_v3()
    gate_sha = hashlib.sha256(GATE_V3_PATH.read_bytes()).hexdigest()
    contaminated = (
        "e2_red_500hz_seed65_v3_prospective_P0_eval2_20260724/episode_000000"
    )
    manifest = {
        "contract_version": "smolvla_s3_prospective_eval_manifest_v1",
        "evaluation_id": "v3_fixture",
        "created_at_utc": "2026-07-24T07:00:00Z",
        "human_authorized_run": True,
        "thresholds_frozen_before_evaluation": True,
        "gate_sha256": gate_sha,
        "release_splits_sha256": "fixture-splits-sha",
        "evaluation_episode_refs": [contaminated],
    }
    invalid = validate_prospective_context(
        gate,
        manifest,
        gate_sha256=gate_sha,
        release_splits_sha256="fixture-splits-sha",
        evaluation_episode_refs=[contaminated],
        train_episode_refs=[],
        stride=1,
        max_frames_per_episode=0,
        inference_mode="canonical_first_action",
    )
    assert invalid["eligible"] is False
    assert "threshold_design_overlap" in invalid["errors"]

    fresh = ["fresh_eval_only_source/episode_000000"]
    manifest["evaluation_episode_refs"] = fresh
    valid = validate_prospective_context(
        gate,
        manifest,
        gate_sha256=gate_sha,
        release_splits_sha256="fixture-splits-sha",
        evaluation_episode_refs=fresh,
        train_episode_refs=["train/episode_000000"],
        stride=1,
        max_frames_per_episode=0,
        inference_mode="canonical_first_action",
    )
    assert valid["eligible"] is True
    assert valid["errors"] == []
