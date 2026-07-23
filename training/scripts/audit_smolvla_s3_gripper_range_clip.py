#!/usr/bin/env python3
"""Audit SmolVLA Recovery gripper range, clipping, and normalization.

This is a CPU-only, saved-prediction audit. It never runs policy inference,
changes a checkpoint, or reclassifies the frozen eval_gate_v1 result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANONICAL = (
    ROOT
    / "runs"
    / "smolvla_s3"
    / "openloop_recovery_v3_20260723T142240Z"
    / "s3_open_loop_report.json"
)
DEFAULT_QUEUED = (
    ROOT
    / "runs"
    / "smolvla_s3"
    / "openloop_recovery_v3_k5_20260723T151853Z_retry1"
    / "s3_open_loop_report.json"
)
DEFAULT_CHECKPOINT = (
    ROOT
    / "runs"
    / "smolvla_s3"
    / "recovery_v3_lora_20260723T125632Z"
    / "lerobot_run"
    / "checkpoints"
    / "005705"
    / "pretrained_model"
)
DEFAULT_RELEASE_STATS = (
    ROOT
    / "data"
    / "releases"
    / "smolvla_s3_panda_abs_eef_scene_v3_phaseaware50"
    / "norm_stats.json"
)
DEFAULT_GATE_V1 = ROOT / "configs" / "smolvla_s3" / "eval_gate.yaml"
DEFAULT_GATE_V2 = ROOT / "configs" / "smolvla_s3" / "eval_gate_v2.yaml"

GRIPPER_INDEX = 7
GRIPPER_MIN = 0.0
GRIPPER_MAX = 1.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _finite_float(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"non-finite value: {value!r}")
    return result


def _read_safetensors_f32(path: Path) -> dict[str, np.ndarray]:
    """Read the F32 tensors needed by this audit without a torch dependency."""
    payload = path.read_bytes()
    if len(payload) < 8:
        raise ValueError(f"invalid safetensors file: {path}")
    header_size = struct.unpack("<Q", payload[:8])[0]
    header_end = 8 + header_size
    header = json.loads(payload[8:header_end])
    tensors: dict[str, np.ndarray] = {}
    for name, meta in header.items():
        if name == "__metadata__":
            continue
        if meta["dtype"] != "F32":
            raise ValueError(f"{path}: unsupported dtype for {name}: {meta['dtype']}")
        start, end = (int(x) for x in meta["data_offsets"])
        shape = tuple(int(x) for x in meta["shape"])
        array = np.frombuffer(
            payload[header_end + start : header_end + end], dtype="<f4"
        ).copy()
        tensors[name] = array.reshape(shape)
    return tensors


def _first_close(values: Sequence[float], *, threshold: float, debounce: int) -> int | None:
    closed = [float(value) <= threshold for value in values]
    for index in range(len(closed) - debounce + 1):
        if all(closed[index : index + debounce]):
            return index
    return None


def _quantiles(values: np.ndarray) -> dict[str, float]:
    return {
        f"p{int(q * 100):02d}": float(np.quantile(values, q))
        for q in (0.0, 0.01, 0.05, 0.5, 0.95, 0.99, 1.0)
    }


def _normalization_contract(
    checkpoint: Path, release_stats_path: Path
) -> dict[str, Any]:
    preprocessor_path = checkpoint / "policy_preprocessor.json"
    postprocessor_path = checkpoint / "policy_postprocessor.json"
    preprocessor = _json(preprocessor_path)
    postprocessor = _json(postprocessor_path)

    pre_step = next(
        step
        for step in preprocessor["steps"]
        if step.get("registry_name") == "normalizer_processor"
    )
    post_step = next(
        step
        for step in postprocessor["steps"]
        if step.get("registry_name") == "unnormalizer_processor"
    )
    pre_state_path = checkpoint / str(pre_step["state_file"])
    post_state_path = checkpoint / str(post_step["state_file"])
    pre_tensors = _read_safetensors_f32(pre_state_path)
    post_tensors = _read_safetensors_f32(post_state_path)
    release_stats = _json(release_stats_path)["action8"]

    names = list(release_stats["names"])
    if names[GRIPPER_INDEX] != "gripper_cmd":
        raise ValueError(f"release action index 7 is not gripper_cmd: {names}")
    pre_mean = pre_tensors["action.mean"].astype(np.float64)
    pre_std = pre_tensors["action.std"].astype(np.float64)
    pre_min = pre_tensors["action.min"].astype(np.float64)
    pre_max = pre_tensors["action.max"].astype(np.float64)
    post_mean = post_tensors["action.mean"].astype(np.float64)
    post_std = post_tensors["action.std"].astype(np.float64)
    release_mean = np.asarray(release_stats["mean"], dtype=np.float64)
    release_std = np.asarray(release_stats["std"], dtype=np.float64)

    checks = {
        "preprocessor_action_norm_is_mean_std": (
            pre_step["config"]["norm_map"].get("ACTION") == "MEAN_STD"
        ),
        "postprocessor_action_norm_is_mean_std": (
            post_step["config"]["norm_map"].get("ACTION") == "MEAN_STD"
        ),
        "pre_and_post_mean_identical": bool(np.array_equal(pre_mean, post_mean)),
        "pre_and_post_std_identical": bool(np.array_equal(pre_std, post_std)),
        "checkpoint_mean_matches_release": bool(
            np.allclose(pre_mean, release_mean, rtol=1e-6, atol=1e-6)
        ),
        "checkpoint_std_matches_release": bool(
            np.allclose(pre_std, release_std, rtol=1e-6, atol=1e-6)
        ),
        "checkpoint_gripper_min_is_zero": bool(
            math.isclose(pre_min[GRIPPER_INDEX], GRIPPER_MIN, abs_tol=1e-7)
        ),
        "checkpoint_gripper_max_is_one": bool(
            math.isclose(pre_max[GRIPPER_INDEX], GRIPPER_MAX, abs_tol=1e-7)
        ),
    }
    grip_mean = float(pre_mean[GRIPPER_INDEX])
    grip_std = float(pre_std[GRIPPER_INDEX])
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "action_normalization": "MEAN_STD",
        "postprocessor_behavior": "unnormalize_only_no_range_clamp",
        "gripper_index": GRIPPER_INDEX,
        "gripper_train_physical_range": [GRIPPER_MIN, GRIPPER_MAX],
        "gripper_mean": grip_mean,
        "gripper_std": grip_std,
        "gripper_normalized_train_range": [
            (GRIPPER_MIN - grip_mean) / grip_std,
            (GRIPPER_MAX - grip_mean) / grip_std,
        ],
        "source_files": {
            "preprocessor_json": str(preprocessor_path),
            "postprocessor_json": str(postprocessor_path),
            "preprocessor_state": str(pre_state_path),
            "postprocessor_state": str(post_state_path),
            "release_norm_stats": str(release_stats_path),
        },
    }


def audit_report_lane(
    report: Mapping[str, Any],
    *,
    normalization: Mapping[str, Any],
    severity_epsilon: float,
    thresholds: Mapping[str, Any],
) -> dict[str, Any]:
    episodes = report["per_episode_raw_results"]["lora"]
    raw_values: list[float] = []
    mapped_values: list[float] = []
    expert_values: list[float] = []
    raw_clip_close_deltas: list[int] = []

    for episode in episodes:
        episode_raw: list[float] = []
        episode_clipped: list[float] = []
        for frame in episode["frame_logs"]:
            raw = _finite_float(frame["raw_pred"][GRIPPER_INDEX])
            mapped = _finite_float(frame["pred_gripper_cmd"])
            expert = _finite_float(frame["expert_gripper_cmd"])
            clipped = float(np.clip(raw, GRIPPER_MIN, GRIPPER_MAX))
            raw_values.append(raw)
            mapped_values.append(mapped)
            expert_values.append(expert)
            episode_raw.append(raw)
            episode_clipped.append(clipped)
        raw_close = _first_close(episode_raw, threshold=0.5, debounce=3)
        clipped_close = _first_close(episode_clipped, threshold=0.5, debounce=3)
        if raw_close is not None and clipped_close is not None:
            raw_clip_close_deltas.append(clipped_close - raw_close)
        elif raw_close != clipped_close:
            raw_clip_close_deltas.append(999)

    raw = np.asarray(raw_values, dtype=np.float64)
    mapped = np.asarray(mapped_values, dtype=np.float64)
    expert = np.asarray(expert_values, dtype=np.float64)
    if not raw.size:
        raise ValueError("report has no LoRA frame logs")
    clipped = np.clip(raw, GRIPPER_MIN, GRIPPER_MAX)
    clip_delta = clipped - raw
    below = raw[raw < GRIPPER_MIN]
    above = raw[raw > GRIPPER_MAX]
    raw_closed = raw <= 0.5
    clipped_closed = clipped <= 0.5
    mapped_matches_clip_max_abs = float(np.max(np.abs(mapped - clipped)))
    normalized = (
        raw - float(normalization["gripper_mean"])
    ) / float(normalization["gripper_std"])

    severity = {
        "epsilon": severity_epsilon,
        "oob_beyond_epsilon_ratio": float(
            np.mean(
                (raw < GRIPPER_MIN - severity_epsilon)
                | (raw > GRIPPER_MAX + severity_epsilon)
            )
        ),
        "clip_adjustment_mae": float(np.mean(np.abs(clip_delta))),
        "clip_adjustment_rmse": float(np.sqrt(np.mean(np.square(clip_delta)))),
        "clip_adjustment_max_abs": float(np.max(np.abs(clip_delta))),
        "clip_classification_change_ratio": float(
            np.mean(raw_closed != clipped_closed)
        ),
        "clip_close_timing_change_frames_max_abs": int(
            max((abs(value) for value in raw_clip_close_deltas), default=0)
        ),
    }
    severity_checks = {
        "oob_beyond_epsilon_ratio": (
            severity["oob_beyond_epsilon_ratio"]
            <= float(thresholds["oob_beyond_epsilon_ratio_max"])
        ),
        "clip_adjustment_mae": (
            severity["clip_adjustment_mae"]
            <= float(thresholds["clip_adjustment_mae_max"])
        ),
        "clip_adjustment_max_abs": (
            severity["clip_adjustment_max_abs"]
            <= float(thresholds["clip_adjustment_max_abs_max"])
        ),
        "raw_min": float(raw.min()) >= float(thresholds["raw_gripper_min"]),
        "raw_max": float(raw.max()) <= float(thresholds["raw_gripper_max"]),
        "clip_classification_invariant": (
            severity["clip_classification_change_ratio"]
            <= float(thresholds["clip_classification_change_ratio_max"])
        ),
        "clip_close_timing_invariant": (
            severity["clip_close_timing_change_frames_max_abs"]
            <= int(thresholds["clip_close_timing_change_frames_max"])
        ),
        "mapped_command_matches_clip": mapped_matches_clip_max_abs <= 1e-7,
        "mapped_command_in_range": bool(
            np.all((mapped >= GRIPPER_MIN) & (mapped <= GRIPPER_MAX))
        ),
    }
    epsilon_ratios = {
        f"outside_0_1_by_more_than_{epsilon:g}": float(
            np.mean((raw < -epsilon) | (raw > 1.0 + epsilon))
        )
        for epsilon in (0.0, 0.01, 0.02, 0.05, 0.10)
    }
    return {
        "passed": all(severity_checks.values()),
        "inference_mode": report["sampling_contract"]["inference_mode"],
        "executes_action_chunk_queue": bool(
            report["sampling_contract"]["executes_action_chunk_queue"]
        ),
        "num_episodes": len(episodes),
        "num_frames": int(raw.size),
        "raw_gripper": {
            "range": [float(raw.min()), float(raw.max())],
            "quantiles": _quantiles(raw),
            "below_zero_ratio": float(np.mean(raw < 0.0)),
            "above_one_ratio": float(np.mean(raw > 1.0)),
            "raw_oob_ratio": float(np.mean((raw < 0.0) | (raw > 1.0))),
            "below_zero_mean_excess": float(np.mean(-below)) if below.size else 0.0,
            "above_one_mean_excess": (
                float(np.mean(above - 1.0)) if above.size else 0.0
            ),
            "epsilon_oob_ratios": epsilon_ratios,
        },
        "normalized_gripper_prediction": {
            "range": [float(normalized.min()), float(normalized.max())],
            "quantiles": _quantiles(normalized),
        },
        "clip": {
            **severity,
            "mapped_command_matches_clip_max_abs": mapped_matches_clip_max_abs,
            "mapped_command_range": [float(mapped.min()), float(mapped.max())],
            "mapped_command_all_in_0_1": bool(
                np.all((mapped >= 0.0) & (mapped <= 1.0))
            ),
            "expert_command_range": [float(expert.min()), float(expert.max())],
        },
        "severity_thresholds": dict(thresholds),
        "severity_checks": severity_checks,
        "severity_contract_passed": all(severity_checks.values()),
    }


def run_audit(
    *,
    canonical_report: Path,
    queued_report: Path,
    checkpoint: Path,
    release_stats: Path,
    gate_v1: Path,
    gate_v2: Path,
) -> dict[str, Any]:
    source_paths = {
        "canonical_report": canonical_report,
        "queued_report": queued_report,
        "release_stats": release_stats,
        "gate_v1": gate_v1,
        "gate_v2": gate_v2,
        "checkpoint_preprocessor": checkpoint / "policy_preprocessor.json",
        "checkpoint_postprocessor": checkpoint / "policy_postprocessor.json",
        "checkpoint_preprocessor_state": checkpoint
        / "policy_preprocessor_step_5_normalizer_processor.safetensors",
        "checkpoint_postprocessor_state": checkpoint
        / "policy_postprocessor_step_0_unnormalizer_processor.safetensors",
    }
    missing = [str(path) for path in source_paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing audit inputs: {missing}")

    v1 = yaml.safe_load(gate_v1.read_text(encoding="utf-8"))
    v2 = yaml.safe_load(gate_v2.read_text(encoding="utf-8"))
    canonical = _json(canonical_report)
    queued = _json(queued_report)
    normalization = _normalization_contract(checkpoint, release_stats)
    severity_contract = v2["gripper_range_severity_contract"]
    thresholds = severity_contract["thresholds"]
    epsilon = float(severity_contract["epsilon"])
    canonical_lane = audit_report_lane(
        canonical,
        normalization=normalization,
        severity_epsilon=epsilon,
        thresholds=thresholds,
    )
    queued_lane = audit_report_lane(
        queued,
        normalization=normalization,
        severity_epsilon=epsilon,
        thresholds=thresholds,
    )

    contract_checks = {
        "v1_is_unchanged_parent_contract": (
            v1["contract_version"] == "smolvla_s3_eval_gate_v1"
        ),
        "v2_is_independent_approved_frozen": (
            v2["contract_version"] == "smolvla_s3_eval_gate_v2"
            and v2["status"] == "approved_frozen"
            and v2["thresholds_frozen"] is True
            and v2["parent_gate_sha256"] == _sha256(gate_v1)
        ),
        "v2_cannot_retroactively_reclassify_v1": bool(
            v2["prospective_evaluation_contract"][
                "forbid_saved_report_reclassification"
            ]
        ),
        "queued_still_not_gate_eligible": (
            v2["sampling_contract"]["queued_diagnostic_gate_eligible"] is False
            and queued["sampling_contract"]["temporal_metrics_gate_eligible"] is False
        ),
        "canonical_report_was_v1_hold": (
            canonical.get("gate_decision") == "hold"
        ),
        "queued_report_was_diagnostic_hold": (
            queued.get("gate_decision") == "hold"
        ),
    }
    passed = (
        normalization["passed"]
        and canonical_lane["passed"]
        and queued_lane["passed"]
        and all(contract_checks.values())
    )
    return {
        "contract_version": "smolvla_s3_gripper_range_clip_audit_v1",
        "artifact_type": "cpu_saved_prediction_audit",
        "passed": passed,
        "claims_task_success": False,
        "ran_policy_inference": False,
        "ran_training": False,
        "ran_isaac": False,
        "canonical_v1_decision_remains": canonical.get("gate_decision"),
        "v2_gate_status": v2["status"],
        "v2_current_result": "not_evaluated_prospectively",
        "source_hashes": {
            name: {"path": str(path), "sha256": _sha256(path)}
            for name, path in source_paths.items()
        },
        "normalization_contract": normalization,
        "canonical_first_action": canonical_lane,
        "queued_k5": queued_lane,
        "comparison_k5_minus_canonical": {
            "raw_oob_ratio": (
                queued_lane["raw_gripper"]["raw_oob_ratio"]
                - canonical_lane["raw_gripper"]["raw_oob_ratio"]
            ),
            "clip_adjustment_mae": (
                queued_lane["clip"]["clip_adjustment_mae"]
                - canonical_lane["clip"]["clip_adjustment_mae"]
            ),
            "oob_beyond_epsilon_ratio": (
                queued_lane["clip"]["oob_beyond_epsilon_ratio"]
                - canonical_lane["clip"]["oob_beyond_epsilon_ratio"]
            ),
        },
        "contract_checks": contract_checks,
        "finding": (
            "Raw OOB frequency is high under the exact [0,1] count, but the "
            "magnitude is bounded and clipping is classification/timing invariant. "
            "This supports the approved/frozen prospective severity-aware v2 gate; "
            "it does not change the frozen v1 Hold."
        ),
    }


def _markdown(report: Mapping[str, Any]) -> str:
    canonical = report["canonical_first_action"]
    queued = report["queued_k5"]
    normalization = report["normalization_contract"]
    rows = []
    for label, lane in (("canonical", canonical), ("queued K5", queued)):
        rows.append(
            "| "
            + " | ".join(
                [
                    label,
                    f"{lane['raw_gripper']['raw_oob_ratio']:.6f}",
                    f"{lane['clip']['oob_beyond_epsilon_ratio']:.6f}",
                    f"{lane['clip']['clip_adjustment_mae']:.6f}",
                    f"{lane['clip']['clip_adjustment_max_abs']:.6f}",
                    f"{lane['clip']['clip_classification_change_ratio']:.6f}",
                    str(lane["clip"]["clip_close_timing_change_frames_max_abs"]),
                ]
            )
            + " |"
        )
    return "\n".join(
        [
            "# SmolVLA S3 Recovery gripper range / clip / normalization audit",
            "",
            f"- Audit passed: `{str(report['passed']).lower()}`",
            f"- Frozen eval_gate_v1 decision remains: `{report['canonical_v1_decision_remains']}`",
            f"- eval_gate_v2 status: `{report['v2_gate_status']}`; "
            "no retrospective promotion",
            f"- Action normalization: `{normalization['action_normalization']}`",
            f"- Gripper mean/std: `{normalization['gripper_mean']:.9f}` / "
            f"`{normalization['gripper_std']:.9f}`",
            "",
            "| lane | exact OOB ratio | OOB beyond ε=0.05 | clip MAE | "
            "clip max | class change | timing change frames |",
            "|---|---:|---:|---:|---:|---:|---:|",
            *rows,
            "",
            "Conclusion: exact-bound OOB is dominated by small regression overshoot. "
            "The Panda mapping clips to `[0,1]` without changing open/close "
            "classification or close timing. This is evidence for a prospective "
            "severity-aware gate, not permission to rewrite the v1 Hold or enter Isaac.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-report", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--queued-report", type=Path, default=DEFAULT_QUEUED)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--release-stats", type=Path, default=DEFAULT_RELEASE_STATS)
    parser.add_argument("--gate-v1", type=Path, default=DEFAULT_GATE_V1)
    parser.add_argument("--gate-v2", type=Path, default=DEFAULT_GATE_V2)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args(argv)

    report = run_audit(
        canonical_report=args.canonical_report.resolve(),
        queued_report=args.queued_report.resolve(),
        checkpoint=args.checkpoint.resolve(),
        release_stats=args.release_stats.resolve(),
        gate_v1=args.gate_v1.resolve(),
        gate_v2=args.gate_v2.resolve(),
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    args.markdown_out.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
