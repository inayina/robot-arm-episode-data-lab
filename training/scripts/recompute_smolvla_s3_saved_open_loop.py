#!/usr/bin/env python3
"""Recompute corrected S3 gripper/temporal metrics from a saved open-loop report.

This is a CPU-only evaluator audit. It does not load a policy, run inference,
train, mutate the checkpoint, or replace the source report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.vla_contract.smolvla_panda_s2 import write_json  # noqa: E402
from training.scripts.run_smolvla_s3_open_loop import (  # noqa: E402
    EVALUATOR_CONTRACT_VERSION,
    GRIPPER_TOLERANCE,
    _binary_gripper_metrics,
    _episode_extra_metrics,
    decide_gate,
)
from training.smolvla_s3.eval_gate_v3 import (  # noqa: E402
    compute_gripper_severity_metrics,
)

DEFAULT_GATE = ROOT / "configs" / "smolvla_s3" / "eval_gate_v2.yaml"


def _mean(values: list[Any]) -> float | None:
    finite = [float(v) for v in values if v is not None]
    return float(np.mean(finite)) if finite else None


def recompute_lane(
    lane: dict[str, Any],
    per_episode: list[dict[str, Any]],
    *,
    stride: int,
    max_frames_per_episode: int,
) -> dict[str, Any]:
    """Recompute evaluator-v1 diagnostics from persisted frame logs."""
    expert: list[float] = []
    predicted: list[float] = []
    raw_gripper_oob: list[float] = []
    extras: list[dict[str, Any]] = []
    for episode in per_episode:
        logs = episode.get("frame_logs") or []
        grip_idx = 5 if episode.get("protocol") == "s2_libero6" else 7
        extra = _episode_extra_metrics(logs, grip_idx=grip_idx)
        extras.append(extra)
        expert.extend(float(row["expert_gripper_cmd"]) for row in logs)
        predicted.extend(float(row["pred_gripper_cmd"]) for row in logs)
        for row in logs:
            if row.get("raw_pred") is None:
                continue
            raw_gripper = float(
                np.asarray(row["raw_pred"], dtype=np.float64).reshape(-1)[grip_idx]
            )
            raw_gripper_oob.append(
                1.0 if raw_gripper < 0.0 or raw_gripper > 1.0 else 0.0
            )

    binary = _binary_gripper_metrics(expert, predicted)
    e = np.asarray(expert, dtype=np.float64)
    p = np.asarray(predicted, dtype=np.float64)
    metrics = dict(lane.get("metrics") or {})
    metrics["gripper_accuracy_legacy_tolerance"] = metrics.get("gripper_accuracy")
    metrics["gripper_tolerance_accuracy"] = (
        float(np.mean(np.abs(p - e) <= GRIPPER_TOLERANCE)) if len(e) else None
    )
    metrics.update(binary)
    metrics["gripper_accuracy"] = binary["gripper_balanced_accuracy"]
    timing_missing_count = sum(
        x.get("gripper_close_timing_status") != "matched" for x in extras
    )
    metrics["gripper_close_missing_count"] = timing_missing_count
    metrics["gripper_close_timing_error_frames"] = (
        999.0
        if timing_missing_count
        else _mean([x.get("gripper_close_timing_error_frames") for x in extras])
    )
    metrics["gripper_close_timing_offset_frames_signed"] = _mean(
        [x.get("gripper_close_timing_offset_frames_signed") for x in extras]
    )
    metrics["gripper_close_timing_offset_seconds_signed"] = _mean(
        [x.get("gripper_close_timing_offset_seconds_signed") for x in extras]
    )
    metrics["gripper_binary_transition_count"] = _mean(
        [x.get("gripper_binary_transition_count") for x in extras]
    )
    metrics["action_smoothness_ee_step_l2_p90"] = _mean(
        [x.get("action_smoothness_ee_step_l2_p90") for x in extras]
    )
    metrics["expert_smoothness_ee_step_l2_p90"] = _mean(
        [x.get("expert_smoothness_ee_step_l2_p90") for x in extras]
    )
    metrics["raw_gripper_oob_ratio"] = _mean(raw_gripper_oob)
    metrics["saturation_or_clip_ratio"] = metrics["raw_gripper_oob_ratio"]
    lane_grip_idx = 5 if lane.get("protocol") == "s2_libero6" else 7
    metrics.update(
        compute_gripper_severity_metrics(
            per_episode,
            grip_idx=lane_grip_idx,
            epsilon=0.05,
        )
    )
    metrics["home_no_close_detected_rate"] = _mean(
        [1.0 if x.get("home_no_close_detected") else 0.0 for x in extras]
    )
    metrics["sampling_stride_frames"] = stride
    metrics["full_episode_coverage"] = bool(
        stride == 1
        and max_frames_per_episode == 0
        and per_episode
        and all(bool(ep.get("full_episode_coverage")) for ep in per_episode)
    )
    metrics["temporal_metrics_gate_eligible"] = metrics["full_episode_coverage"]
    metrics["inference_mode"] = "teacher_forced_first_action_policy_reset_each_frame"
    metrics["executes_action_chunk_queue"] = False
    # Saved predictions may be audited but can never satisfy the prospective
    # contract of the frozen v2 gate.
    metrics["prospective_eval_eligible"] = False

    return {
        "protocol": lane.get("protocol"),
        "metrics": metrics,
        "per_episode_extra_v1": [
            {
                "episode_ref": ep.get("episode_ref"),
                "slice": ep.get("slice"),
                "extra": extra,
            }
            for ep, extra in zip(per_episode, extras, strict=True)
        ],
    }


def recompute_report(report: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    stride = int(report.get("stride", 1))
    max_frames = int(report.get("max_frames_per_episode", 0))
    per = report.get("per_episode_raw_results") or {}
    base = recompute_lane(
        report.get("base") or {},
        per.get("base") or [],
        stride=stride,
        max_frames_per_episode=max_frames,
    )
    lora = recompute_lane(
        report.get("lora") or {},
        per.get("lora") or [],
        stride=stride,
        max_frames_per_episode=max_frames,
    )
    s2_ee = float(gate["baselines"]["s2_ee_rmse_m"])
    prospective_context = {
        "eligible": False,
        "errors": ["historical_saved_report_reclassification_forbidden"],
        "historical_saved_report_reclassification": True,
    }
    decision = decide_gate(
        gate,
        lora["metrics"],
        s2_ee=s2_ee,
        prospective_context=prospective_context,
    )
    return {
        "artifact_type": "smolvla_s3_saved_open_loop_recompute",
        "evaluator_contract_version": EVALUATOR_CONTRACT_VERSION,
        "source_report_gate_decision": report.get("gate_decision"),
        "source_report_stride": stride,
        "source_report_max_frames_per_episode": max_frames,
        "claims_task_success": False,
        "ran_inference": False,
        "ran_training": False,
        "ran_isaac": False,
        "prospective_evaluation": prospective_context,
        "base": base,
        "lora": lora,
        "gate_decision": decision,
        "canonical_status": (
            "diagnostic_only_noncanonical_sampling"
            if not lora["metrics"]["temporal_metrics_gate_eligible"]
            else "canonical_sampling"
        ),
        "note": (
            "Saved predictions can be re-audited, but missing full-episode predictions "
            "cannot be reconstructed without an evaluator-only inference rerun."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--eval-gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    gate = yaml.safe_load(args.eval_gate.read_text(encoding="utf-8"))
    result = recompute_report(report, gate)
    write_json(args.output, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
