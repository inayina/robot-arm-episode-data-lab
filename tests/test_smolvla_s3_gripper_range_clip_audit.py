"""Regression tests for the Recovery gripper range/clip audit and v2 proposal."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "training" / "scripts" / "audit_smolvla_s3_gripper_range_clip.py"
SPEC = importlib.util.spec_from_file_location("smolvla_gripper_range_audit", SCRIPT)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

GATE_V1 = ROOT / "configs" / "smolvla_s3" / "eval_gate.yaml"
GATE_V2_PROPOSAL = (
    ROOT / "configs" / "smolvla_s3" / "eval_gate_v2_proposal.yaml"
)
GATE_V2 = ROOT / "configs" / "smolvla_s3" / "eval_gate_v2.yaml"


def _fixture_report(raw_values: list[float]) -> dict:
    frames = [
        {
            "raw_pred": [0.0] * 7 + [value],
            "pred_gripper_cmd": min(1.0, max(0.0, value)),
            "expert_gripper_cmd": 0.0 if value <= 0.5 else 1.0,
        }
        for value in raw_values
    ]
    return {
        "sampling_contract": {
            "inference_mode": "canonical_first_action",
            "executes_action_chunk_queue": False,
        },
        "per_episode_raw_results": {"lora": [{"frame_logs": frames}]},
    }


def _thresholds() -> dict:
    return {
        "oob_beyond_epsilon_ratio_max": 0.01,
        "clip_adjustment_mae_max": 0.01,
        "clip_adjustment_max_abs_max": 0.10,
        "raw_gripper_min": -0.10,
        "raw_gripper_max": 1.10,
        "clip_classification_change_ratio_max": 0.0,
        "clip_close_timing_change_frames_max": 0,
    }


def test_small_boundary_overshoot_is_measured_without_changing_behavior() -> None:
    lane = AUDIT.audit_report_lane(
        _fixture_report([-0.02, 0.10, 0.20, 0.90, 1.02, 1.01]),
        normalization={"gripper_mean": 0.7, "gripper_std": 0.45},
        severity_epsilon=0.05,
        thresholds=_thresholds(),
    )
    assert lane["raw_gripper"]["raw_oob_ratio"] == pytest.approx(0.5)
    assert lane["clip"]["oob_beyond_epsilon_ratio"] == 0.0
    assert lane["clip"]["clip_adjustment_mae"] == pytest.approx(0.05 / 6)
    assert lane["clip"]["clip_classification_change_ratio"] == 0.0
    assert lane["clip"]["clip_close_timing_change_frames_max_abs"] == 0
    assert lane["severity_checks"]["mapped_command_in_range"] is True
    assert lane["severity_contract_passed"] is True


def test_v2_keeps_proposal_history_and_freezes_approved_gate() -> None:
    proposal = yaml.safe_load(GATE_V2_PROPOSAL.read_text(encoding="utf-8"))
    v2 = yaml.safe_load(GATE_V2.read_text(encoding="utf-8"))
    v1_sha = hashlib.sha256(GATE_V1.read_bytes()).hexdigest()
    assert proposal["contract_version"] == "smolvla_s3_eval_gate_v2_proposal"
    assert proposal["status"] == "proposal_not_approved"
    assert v2["contract_version"] == "smolvla_s3_eval_gate_v2"
    assert v2["status"] == "approved_frozen"
    assert v2["thresholds_frozen"] is True
    assert v2["parent_gate"] == "configs/smolvla_s3/eval_gate.yaml"
    assert v2["parent_gate_sha256"] == v1_sha
    assert (
        v2["prospective_evaluation_contract"][
            "forbid_saved_report_reclassification"
        ]
        is True
    )
    assert v2["sampling_contract"]["queued_diagnostic_gate_eligible"] is False
    assert v2["evaluator_contract_version"].endswith("_evaluator_v3")
    assert v2["ran_isaac"] is False
    assert v2["authorized_isaac"] is False


def test_real_saved_prediction_audit_when_artifacts_are_present() -> None:
    required = [
        AUDIT.DEFAULT_CANONICAL,
        AUDIT.DEFAULT_QUEUED,
        AUDIT.DEFAULT_RELEASE_STATS,
        AUDIT.DEFAULT_GATE_V1,
        AUDIT.DEFAULT_GATE_V2,
        AUDIT.DEFAULT_CHECKPOINT / "policy_preprocessor.json",
        AUDIT.DEFAULT_CHECKPOINT / "policy_postprocessor.json",
    ]
    if not all(path.is_file() for path in required):
        pytest.skip("local Recovery audit artifacts are not available")
    report = AUDIT.run_audit(
        canonical_report=AUDIT.DEFAULT_CANONICAL,
        queued_report=AUDIT.DEFAULT_QUEUED,
        checkpoint=AUDIT.DEFAULT_CHECKPOINT,
        release_stats=AUDIT.DEFAULT_RELEASE_STATS,
        gate_v1=AUDIT.DEFAULT_GATE_V1,
        gate_v2=AUDIT.DEFAULT_GATE_V2,
    )
    assert report["passed"] is True
    assert report["normalization_contract"]["passed"] is True
    assert report["canonical_v1_decision_remains"] == "hold"
    assert report["v2_gate_status"] == "approved_frozen"
    assert report["v2_current_result"] == "not_evaluated_prospectively"
    assert report["canonical_first_action"]["raw_gripper"]["raw_oob_ratio"] > 0.30
    assert (
        report["canonical_first_action"]["clip"]["oob_beyond_epsilon_ratio"]
        < 0.01
    )
    assert (
        report["canonical_first_action"]["clip"][
            "clip_close_timing_change_frames_max_abs"
        ]
        == 0
    )
