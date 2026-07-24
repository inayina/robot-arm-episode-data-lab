"""Contract tests for frozen eval-gate-v2 and evaluator-v3."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from training.smolvla_s3.eval_gate_v3 import (
    EVALUATOR_CONTRACT_VERSION,
    compute_gripper_severity_metrics,
    decide_gate_v3,
    validate_prospective_context,
)


ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = ROOT / "configs" / "smolvla_s3" / "eval_gate_v2.yaml"
LOCK_PATH = ROOT / "configs" / "smolvla_s3" / "eval_gate_v2.lock.json"


def _gate() -> dict:
    return yaml.safe_load(GATE_PATH.read_text(encoding="utf-8"))


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


def _pass_metrics(*, prospective: bool) -> dict:
    return {
        "ee_position_rmse_m": 0.04,
        "quaternion_angular_error_rad": 0.01,
        "gripper_balanced_accuracy": 0.99,
        "gripper_close_timing_error_frames": 2.0,
        "action_smoothness_ee_step_l2_p90": 0.03,
        "home_no_close_detected_rate": 0.0,
        "temporal_metrics_gate_eligible": True,
        # Exact OOB is intentionally high; v2 gates on severity and invariants.
        "raw_gripper_oob_ratio": 0.33,
        "raw_gripper_oob_beyond_epsilon_ratio": 0.007,
        "gripper_clip_adjustment_mae": 0.004,
        "gripper_clip_adjustment_max_abs": 0.08,
        "raw_gripper_min": -0.06,
        "raw_gripper_max": 1.08,
        "gripper_clip_classification_change_ratio": 0.0,
        "gripper_clip_close_timing_change_frames_max_abs": 0,
        "mapped_gripper_command_in_range": True,
        "mapped_gripper_matches_clip_max_abs": 0.0,
        "prospective_eval_eligible": prospective,
        "gripper_nonfinite_any": False,
    }


def test_frozen_gate_and_threshold_lock_match_exact_bytes() -> None:
    gate = _gate()
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    assert gate["contract_version"] == "smolvla_s3_eval_gate_v2"
    assert gate["evaluator_contract_version"] == EVALUATOR_CONTRACT_VERSION
    assert gate["status"] == "approved_frozen"
    assert gate["thresholds_frozen"] is True
    assert gate["authorized_isaac"] is False
    assert lock["gate_sha256"] == hashlib.sha256(GATE_PATH.read_bytes()).hexdigest()
    assert lock["threshold_payload_sha256"] == _threshold_digest(gate)


def test_severity_metrics_measure_clip_without_changing_close() -> None:
    values = [-0.02, 0.1, 0.2, 0.9, 1.02, 1.01]
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
    assert metrics["raw_gripper_oob_ratio"] == pytest.approx(0.5)
    assert metrics["raw_gripper_oob_beyond_epsilon_ratio"] == 0.0
    assert metrics["gripper_clip_adjustment_mae"] == pytest.approx(0.05 / 6)
    assert metrics["gripper_clip_classification_change_ratio"] == 0.0
    assert metrics["gripper_clip_close_timing_change_frames_max_abs"] == 0
    assert metrics["mapped_gripper_command_in_range"] is True


def test_v2_cannot_pass_without_prospective_eligibility() -> None:
    gate = _gate()
    result = decide_gate_v3(
        gate,
        _pass_metrics(prospective=False),
        s2_ee=gate["baselines"]["s2_ee_rmse_m"],
        prospective_context={"eligible": False},
    )
    assert result["gate_decision"] == "hold"
    assert "prospective_eligibility" in result["pass_failures"]
    assert result["isaac_authorized"] is False


def test_v2_can_pass_only_with_frozen_thresholds_and_prospective_context() -> None:
    gate = _gate()
    result = decide_gate_v3(
        gate,
        _pass_metrics(prospective=True),
        s2_ee=gate["baselines"]["s2_ee_rmse_m"],
        prospective_context={"eligible": True},
    )
    assert result["gate_decision"] == "pass"
    assert result["isaac_ready_candidate"] is True
    assert result["isaac_authorized"] is False


def test_execution_clip_invariant_violation_is_no_go() -> None:
    gate = _gate()
    metrics = _pass_metrics(prospective=True)
    metrics["mapped_gripper_command_in_range"] = False
    result = decide_gate_v3(
        gate,
        metrics,
        s2_ee=gate["baselines"]["s2_ee_rmse_m"],
        prospective_context={"eligible": True},
    )
    assert result["gate_decision"] == "no_go"
    assert "mapped_gripper_out_of_range" in result["reasons"]


def test_prospective_manifest_checks_hash_refs_time_and_overlap() -> None:
    gate = _gate()
    gate_sha = hashlib.sha256(GATE_PATH.read_bytes()).hexdigest()
    evaluation_refs = ["new_locked_set/episode_000000"]
    manifest = {
        "contract_version": "smolvla_s3_prospective_eval_manifest_v1",
        "evaluation_id": "prospective_fixture",
        "created_at_utc": "2026-07-23T16:00:00Z",
        "human_authorized_run": True,
        "thresholds_frozen_before_evaluation": True,
        "gate_sha256": gate_sha,
        "release_splits_sha256": "fixture-splits-sha",
        "evaluation_episode_refs": evaluation_refs,
    }
    valid = validate_prospective_context(
        gate,
        manifest,
        gate_sha256=gate_sha,
        release_splits_sha256="fixture-splits-sha",
        evaluation_episode_refs=evaluation_refs,
        train_episode_refs=["train/episode_000000"],
        stride=1,
        max_frames_per_episode=0,
        inference_mode="canonical_first_action",
    )
    assert valid["eligible"] is True
    assert valid["errors"] == []

    contaminated_ref = gate["prospective_evaluation_contract"][
        "threshold_design_episode_refs"
    ][0]
    manifest["evaluation_episode_refs"] = [contaminated_ref]
    invalid = validate_prospective_context(
        gate,
        manifest,
        gate_sha256=gate_sha,
        release_splits_sha256="fixture-splits-sha",
        evaluation_episode_refs=[contaminated_ref],
        train_episode_refs=[],
        stride=1,
        max_frames_per_episode=0,
        inference_mode="canonical_first_action",
    )
    assert invalid["eligible"] is False
    assert "threshold_design_overlap" in invalid["errors"]


GATE_V3_PATH = ROOT / "configs" / "smolvla_s3" / "eval_gate_v3.yaml"
LOCK_V3_PATH = ROOT / "configs" / "smolvla_s3" / "eval_gate_v3.lock.json"


def _gate_v3() -> dict:
    return yaml.safe_load(GATE_V3_PATH.read_text(encoding="utf-8"))


def _v3_pass_metrics(*, prospective: bool) -> dict:
    # Numbers mirror the 2026-07-24 v2 prospective Hold result, which fails
    # v2 on open-edge severity but must Pass under execution-semantics v3.
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
        "raw_gripper_oob_beyond_epsilon_open_edge_ratio": 0.016086793864571642,
        "raw_gripper_oob_beyond_epsilon_close_edge_ratio": 0.002618780396558174,
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


def test_frozen_gate_v3_and_threshold_lock_match_exact_bytes() -> None:
    gate = _gate_v3()
    lock = json.loads(LOCK_V3_PATH.read_text(encoding="utf-8"))
    assert gate["contract_version"] == "smolvla_s3_eval_gate_v3"
    assert gate["evaluator_contract_version"] == EVALUATOR_CONTRACT_VERSION
    assert gate["status"] == "approved_frozen"
    assert gate["thresholds_frozen"] is True
    assert gate["authorized_isaac"] is False
    assert gate["historical_v2_decisions_unchanged"] is True
    assert lock["gate_sha256"] == hashlib.sha256(GATE_V3_PATH.read_bytes()).hexdigest()
    assert lock["threshold_payload_sha256"] == _threshold_digest(gate)


def test_v3_passes_open_edge_overshoot_that_holds_v2() -> None:
    gate_v2 = _gate()
    gate_v3 = _gate_v3()
    metrics_v2 = _pass_metrics(prospective=True)
    # Inject the measured open-edge Hold numbers into the v2 metric set.
    metrics_v2.update(
        {
            "raw_gripper_oob_beyond_epsilon_ratio": 0.01870557426112982,
            "gripper_clip_adjustment_max_abs": 0.2153458595275879,
            "raw_gripper_max": 1.215345859527588,
            "raw_gripper_min": -0.06957733631134033,
            "gripper_clip_adjustment_mae": 0.006957991735078046,
            "ee_position_rmse_m": 0.025967761453333616,
            "gripper_balanced_accuracy": 0.9931396967255146,
            "gripper_close_timing_error_frames": 1.9,
            "action_smoothness_ee_step_l2_p90": 0.02983534771757356,
        }
    )
    v2 = decide_gate_v3(
        gate_v2,
        metrics_v2,
        s2_ee=gate_v2["baselines"]["s2_ee_rmse_m"],
        prospective_context={"eligible": True},
    )
    assert v2["gate_decision"] == "hold"
    assert "gripper_oob_severity" in v2["pass_failures"]
    assert "gripper_clip_max" in v2["pass_failures"]
    assert "raw_gripper_max" in v2["pass_failures"]

    v3 = decide_gate_v3(
        gate_v3,
        _v3_pass_metrics(prospective=True),
        s2_ee=gate_v3["baselines"]["s2_ee_rmse_m"],
        prospective_context={"eligible": True},
    )
    assert v3["gate_decision"] == "pass"
    assert v3["isaac_ready_candidate"] is True
    assert v3["isaac_authorized"] is False


def test_v3_holds_when_close_edge_beyond_epsilon_exceeds_one_percent() -> None:
    gate = _gate_v3()
    metrics = _v3_pass_metrics(prospective=True)
    metrics["raw_gripper_oob_beyond_epsilon_close_edge_ratio"] = 0.02
    result = decide_gate_v3(
        gate,
        metrics,
        s2_ee=gate["baselines"]["s2_ee_rmse_m"],
        prospective_context={"eligible": True},
    )
    assert result["gate_decision"] == "hold"
    assert "gripper_close_edge_oob" in result["pass_failures"]


def test_v3_no_go_when_raw_outside_sanity_envelope() -> None:
    gate = _gate_v3()
    metrics = _v3_pass_metrics(prospective=True)
    metrics["raw_gripper_max"] = 1.6
    result = decide_gate_v3(
        gate,
        metrics,
        s2_ee=gate["baselines"]["s2_ee_rmse_m"],
        prospective_context={"eligible": True},
    )
    assert result["gate_decision"] == "no_go"
    assert "raw_gripper_outside_sanity_envelope" in result["reasons"]


def test_severity_metrics_report_open_and_close_edges() -> None:
    values = [-0.06, 0.1, 0.2, 0.9, 1.06, 1.01]
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
    assert metrics["raw_gripper_oob_beyond_epsilon_open_edge_ratio"] == pytest.approx(
        1.0 / 6.0
    )
    assert metrics["raw_gripper_oob_beyond_epsilon_close_edge_ratio"] == pytest.approx(
        1.0 / 6.0
    )


def test_v3_prospective_rejects_v2_prospective_design_episodes() -> None:
    gate = _gate_v3()
    gate_sha = hashlib.sha256(GATE_V3_PATH.read_bytes()).hexdigest()
    contaminated = gate["prospective_evaluation_contract"][
        "threshold_design_episode_refs"
    ][-1]
    manifest = {
        "contract_version": "smolvla_s3_prospective_eval_manifest_v1",
        "evaluation_id": "prospective_v3_fixture",
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
