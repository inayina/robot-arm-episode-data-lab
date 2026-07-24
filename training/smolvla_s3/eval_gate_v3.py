"""Severity-aware SmolVLA S3 eval-gate-v2 implementation.

This module is CPU-only contract logic. It does not run policy inference,
training, or Isaac. Historical saved reports can be audited but are never
prospective-eligible.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import numpy as np


EVALUATOR_CONTRACT_VERSION = "smolvla_s3_open_loop_evaluator_v3"
GATE_CONTRACT_VERSION = "smolvla_s3_eval_gate_v2"
GATE_CONTRACT_VERSION_V3 = "smolvla_s3_eval_gate_v3"
SEVERITY_GATE_CONTRACT_VERSIONS = frozenset(
    {GATE_CONTRACT_VERSION, GATE_CONTRACT_VERSION_V3}
)
PROSPECTIVE_MANIFEST_CONTRACT_VERSION = "smolvla_s3_prospective_eval_manifest_v1"


def _first_close(
    values: Sequence[float], *, threshold: float, debounce: int
) -> int | None:
    closed = [float(value) <= threshold for value in values]
    for index in range(len(closed) - debounce + 1):
        if all(closed[index : index + debounce]):
            return index
    return None


def compute_gripper_severity_metrics(
    per_episode: Sequence[Mapping[str, Any]],
    *,
    grip_idx: int,
    epsilon: float,
    threshold: float = 0.5,
    debounce: int = 3,
) -> dict[str, Any]:
    """Compute raw-output and execution-clip metrics from persisted frame logs."""
    raw_values: list[float] = []
    mapped_values: list[float] = []
    timing_deltas: list[int] = []
    nonfinite = False
    for episode in per_episode:
        episode_raw: list[float] = []
        episode_clipped: list[float] = []
        for frame in episode.get("frame_logs") or []:
            try:
                raw = float(
                    np.asarray(frame["raw_pred"], dtype=np.float64).reshape(-1)[
                        grip_idx
                    ]
                )
                mapped = float(frame["pred_gripper_cmd"])
            except (IndexError, KeyError, TypeError, ValueError):
                nonfinite = True
                continue
            if not math.isfinite(raw) or not math.isfinite(mapped):
                nonfinite = True
                continue
            clipped = float(np.clip(raw, 0.0, 1.0))
            raw_values.append(raw)
            mapped_values.append(mapped)
            episode_raw.append(raw)
            episode_clipped.append(clipped)
        raw_close = _first_close(
            episode_raw, threshold=threshold, debounce=debounce
        )
        clipped_close = _first_close(
            episode_clipped, threshold=threshold, debounce=debounce
        )
        if raw_close is None and clipped_close is None:
            continue
        if raw_close is None or clipped_close is None:
            timing_deltas.append(999)
        else:
            timing_deltas.append(clipped_close - raw_close)

    if not raw_values:
        return {
            "gripper_severity_metrics_available": False,
            "gripper_nonfinite_any": True,
        }

    raw = np.asarray(raw_values, dtype=np.float64)
    mapped = np.asarray(mapped_values, dtype=np.float64)
    clipped = np.clip(raw, 0.0, 1.0)
    adjustment = clipped - raw
    return {
        "gripper_severity_metrics_available": True,
        "gripper_nonfinite_any": nonfinite,
        "raw_gripper_oob_ratio": float(
            np.mean((raw < 0.0) | (raw > 1.0))
        ),
        "raw_gripper_oob_beyond_epsilon_ratio": float(
            np.mean((raw < -epsilon) | (raw > 1.0 + epsilon))
        ),
        "raw_gripper_oob_beyond_epsilon_open_edge_ratio": float(
            np.mean(raw > 1.0 + epsilon)
        ),
        "raw_gripper_oob_beyond_epsilon_close_edge_ratio": float(
            np.mean(raw < -epsilon)
        ),
        "gripper_clip_adjustment_mae": float(np.mean(np.abs(adjustment))),
        "gripper_clip_adjustment_max_abs": float(np.max(np.abs(adjustment))),
        "raw_gripper_min": float(np.min(raw)),
        "raw_gripper_max": float(np.max(raw)),
        "gripper_clip_classification_change_ratio": float(
            np.mean((raw <= threshold) != (clipped <= threshold))
        ),
        "gripper_clip_close_timing_change_frames_max_abs": int(
            max((abs(value) for value in timing_deltas), default=0)
        ),
        "mapped_gripper_command_in_range": bool(
            np.all((mapped >= 0.0) & (mapped <= 1.0))
        ),
        "mapped_gripper_matches_clip_max_abs": float(
            np.max(np.abs(mapped - clipped))
        ),
    }


def _parse_utc(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_prospective_context(
    gate: Mapping[str, Any],
    manifest: Mapping[str, Any] | None,
    *,
    gate_sha256: str,
    release_splits_sha256: str,
    evaluation_episode_refs: Sequence[str],
    train_episode_refs: Sequence[str],
    stride: int,
    max_frames_per_episode: int,
    inference_mode: str,
) -> dict[str, Any]:
    """Validate that a v2 evaluation is prospective and independent."""
    errors: list[str] = []
    evaluation = list(evaluation_episode_refs)
    train = set(train_episode_refs)
    design = set(
        gate.get("prospective_evaluation_contract", {}).get(
            "threshold_design_episode_refs", []
        )
    )
    if gate.get("contract_version") not in SEVERITY_GATE_CONTRACT_VERSIONS:
        errors.append("gate_contract_version")
    if gate.get("status") != "approved_frozen":
        errors.append("gate_not_approved_frozen")
    if gate.get("thresholds_frozen") is not True:
        errors.append("thresholds_not_frozen")
    if manifest is None:
        errors.append("prospective_manifest_missing")
        manifest = {}
    if (
        manifest.get("contract_version")
        != PROSPECTIVE_MANIFEST_CONTRACT_VERSION
    ):
        errors.append("manifest_contract_version")
    if not str(manifest.get("evaluation_id") or "").strip():
        errors.append("evaluation_id")
    if manifest.get("human_authorized_run") is not True:
        errors.append("human_run_authorization")
    if manifest.get("thresholds_frozen_before_evaluation") is not True:
        errors.append("thresholds_frozen_before_evaluation")
    if manifest.get("gate_sha256") != gate_sha256:
        errors.append("gate_sha256")
    if manifest.get("release_splits_sha256") != release_splits_sha256:
        errors.append("release_splits_sha256")
    if sorted(manifest.get("evaluation_episode_refs") or []) != sorted(evaluation):
        errors.append("evaluation_refs_exact_match")
    if not evaluation or len(evaluation) != len(set(evaluation)):
        errors.append("evaluation_refs_empty_or_duplicate")
    train_overlap = sorted(set(evaluation) & train)
    design_overlap = sorted(set(evaluation) & design)
    if train_overlap:
        errors.append("train_overlap")
    if design_overlap:
        errors.append("threshold_design_overlap")
    if stride != 1:
        errors.append("canonical_stride")
    if max_frames_per_episode != 0:
        errors.append("full_episode_limit")
    if inference_mode != "canonical_first_action":
        errors.append("canonical_inference_mode")
    frozen_at = _parse_utc(gate.get("frozen_at_utc"))
    manifest_at = _parse_utc(manifest.get("created_at_utc"))
    if frozen_at is None or manifest_at is None or manifest_at <= frozen_at:
        errors.append("manifest_created_after_gate_freeze")
    return {
        "eligible": not errors,
        "errors": errors,
        "evaluation_id": manifest.get("evaluation_id"),
        "gate_sha256": gate_sha256,
        "release_splits_sha256": release_splits_sha256,
        "evaluation_episode_count": len(evaluation),
        "train_overlap": train_overlap,
        "threshold_design_overlap": design_overlap,
        "historical_saved_report_reclassification": False,
    }


def _finite(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return value is not None
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def decide_gate_v3(
    gate: Mapping[str, Any],
    metrics: Mapping[str, Any] | None,
    *,
    s2_ee: float,
    prospective_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Apply a frozen severity gate (v2 or v3 execution-semantics).

    Pass requires prospective eligibility in both contract versions.
    """
    if not metrics:
        return {
            "gate_decision": "no_go",
            "reasons": ["missing_lora_metrics"],
            "relative_ee_improvement_vs_s2": None,
            "isaac_authorized": False,
        }
    required = list(gate.get("metrics_required") or [])
    missing = [name for name in required if name not in metrics]
    if missing:
        return {
            "gate_decision": "no_go",
            "reasons": [f"missing_metrics:{','.join(missing)}"],
            "relative_ee_improvement_vs_s2": None,
            "isaac_authorized": False,
        }
    finite_names = [
        name
        for name in required
        if name
        not in {
            "mapped_gripper_command_in_range",
            "prospective_eval_eligible",
        }
    ]
    bad_finite = [name for name in finite_names if not _finite(metrics.get(name))]
    if bad_finite or metrics.get("gripper_nonfinite_any") is True:
        return {
            "gate_decision": "no_go",
            "reasons": [f"nan_or_inf:{','.join(bad_finite) or 'gripper'}"],
            "relative_ee_improvement_vs_s2": None,
            "isaac_authorized": False,
        }

    ee = float(metrics["ee_position_rmse_m"])
    grip = float(metrics["gripper_balanced_accuracy"])
    quat = float(metrics["quaternion_angular_error_rad"])
    timing = float(metrics["gripper_close_timing_error_frames"])
    smooth = float(metrics["action_smoothness_ee_step_l2_p90"])
    hnc = float(metrics["home_no_close_detected_rate"])
    rel = (s2_ee - ee) / s2_ee if s2_ee > 0 else None
    thresholds = gate["thresholds"]
    no_go = thresholds["no_go"]
    reasons: list[str] = []
    if ee >= float(no_go["ee_position_rmse_m_min"]):
        reasons.append("ee")
    if grip <= float(no_go["gripper_balanced_accuracy_max"]):
        reasons.append("grip")
    if hnc >= float(no_go["home_no_close_detected_min_rate"]):
        reasons.append("home_no_close")
    if smooth <= float(no_go["near_static_ee_step_l2_p90_max"]):
        reasons.append("near_static_ee")
    severity = gate["gripper_range_severity_contract"]["thresholds"]
    execution_side_aware = (
        gate.get("contract_version") == GATE_CONTRACT_VERSION_V3
    )
    if metrics["mapped_gripper_command_in_range"] is not True:
        reasons.append("mapped_gripper_out_of_range")
    if float(metrics["mapped_gripper_matches_clip_max_abs"]) > float(
        severity["mapped_gripper_matches_clip_max_abs_max"]
    ):
        reasons.append("mapped_gripper_not_equal_clip")
    if float(metrics["gripper_clip_classification_change_ratio"]) > 0.0:
        reasons.append("clip_classification_change")
    if int(metrics["gripper_clip_close_timing_change_frames_max_abs"]) > 0:
        reasons.append("clip_close_timing_change")
    if execution_side_aware and (
        float(metrics["raw_gripper_min"])
        < float(severity["raw_gripper_sanity_min"])
        or float(metrics["raw_gripper_max"])
        > float(severity["raw_gripper_sanity_max"])
    ):
        reasons.append("raw_gripper_outside_sanity_envelope")
    if reasons:
        return {
            "gate_decision": "no_go",
            "reasons": reasons,
            "relative_ee_improvement_vs_s2": rel,
            "isaac_authorized": False,
        }

    pas = thresholds["pass"]
    failures: list[str] = []
    if ee > float(pas["ee_position_rmse_m_max"]):
        failures.append("ee")
    if rel is None or rel < float(pas["relative_ee_improvement_vs_s2_min"]):
        failures.append("rel_improve")
    if quat > float(pas["quaternion_angular_error_rad_max"]):
        failures.append("quat")
    if grip < float(pas["gripper_balanced_accuracy_min"]):
        failures.append("grip")
    if timing > float(pas["gripper_close_timing_error_frames_max"]):
        failures.append("timing")
    if smooth > float(pas["action_smoothness_ee_step_l2_p90_max"]):
        failures.append("smooth")
    if hnc > float(pas["home_no_close_detected_max_rate"]):
        failures.append("hnc")
    if metrics["temporal_metrics_gate_eligible"] is not True:
        failures.append("temporal_coverage")
    if execution_side_aware:
        # v3 execution semantics: the executed command is clip(raw, 0, 1),
        # so Pass gates the contact-risk close edge and mean clip magnitude.
        # Open-edge raw overshoot is diagnostics-only inside the sanity
        # envelope enforced above as No-Go.
        if float(
            metrics["raw_gripper_oob_beyond_epsilon_close_edge_ratio"]
        ) > float(severity["close_edge_oob_beyond_epsilon_ratio_max"]):
            failures.append("gripper_close_edge_oob")
        if float(metrics["gripper_clip_adjustment_mae"]) > float(
            severity["clip_adjustment_mae_max"]
        ):
            failures.append("gripper_clip_mae")
    else:
        if float(metrics["raw_gripper_oob_beyond_epsilon_ratio"]) > float(
            severity["oob_beyond_epsilon_ratio_max"]
        ):
            failures.append("gripper_oob_severity")
        if float(metrics["gripper_clip_adjustment_mae"]) > float(
            severity["clip_adjustment_mae_max"]
        ):
            failures.append("gripper_clip_mae")
        if float(metrics["gripper_clip_adjustment_max_abs"]) > float(
            severity["clip_adjustment_max_abs_max"]
        ):
            failures.append("gripper_clip_max")
        if float(metrics["raw_gripper_min"]) < float(severity["raw_gripper_min"]):
            failures.append("raw_gripper_min")
        if float(metrics["raw_gripper_max"]) > float(severity["raw_gripper_max"]):
            failures.append("raw_gripper_max")
    prospective_eligible = bool(
        prospective_context and prospective_context.get("eligible")
    )
    if not prospective_eligible or metrics["prospective_eval_eligible"] is not True:
        failures.append("prospective_eligibility")
    if not failures:
        return {
            "gate_decision": "pass",
            "reasons": [
                "all_frozen_v3_execution_semantics_thresholds_and_prospective_contract"
                if execution_side_aware
                else "all_frozen_v2_thresholds_and_prospective_contract"
            ],
            "relative_ee_improvement_vs_s2": rel,
            "pass_failures": [],
            "isaac_ready_candidate": True,
            "isaac_authorized": False,
        }

    hold = thresholds["hold"]
    hold_failures: list[str] = []
    if ee > float(hold["ee_position_rmse_m_max"]):
        hold_failures.append("ee")
    if rel is None or rel < float(hold["relative_ee_improvement_vs_s2_min"]):
        hold_failures.append("rel_improve")
    if quat > float(hold["quaternion_angular_error_rad_max"]):
        hold_failures.append("quat")
    if grip < float(hold["gripper_balanced_accuracy_min"]):
        hold_failures.append("grip")
    if hnc > float(hold["home_no_close_detected_max_rate"]):
        hold_failures.append("hnc")
    if not hold_failures:
        return {
            "gate_decision": "hold",
            "reasons": [f"pass_failed:{','.join(failures)}", "within_hold_band"],
            "relative_ee_improvement_vs_s2": rel,
            "pass_failures": failures,
            "isaac_ready_candidate": False,
            "isaac_authorized": False,
        }
    return {
        "gate_decision": "no_go",
        "reasons": [
            f"below_hold:{','.join(hold_failures)}",
            f"pass_failed:{','.join(failures)}",
        ],
        "relative_ee_improvement_vs_s2": rel,
        "pass_failures": failures,
        "hold_failures": hold_failures,
        "isaac_ready_candidate": False,
        "isaac_authorized": False,
    }
