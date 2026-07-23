#!/usr/bin/env python3
"""Audit upstream abs-EEF+RGB demonstrations for SmolVLA grip-timing repair.

This tool is read-only. It does not prepare a release, train a policy, or launch
ROS/Isaac.  ``structural`` verifies provenance and physical-gate evidence;
``round2`` additionally applies the frozen late-close/smooth-label targets.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np
import pyarrow.parquet as pq


@dataclass(frozen=True)
class Round2Thresholds:
    close_threshold: float = 0.5
    debounce_frames: int = 3
    pick_xy_tolerance_m: float = 0.02
    pick_z_relative_max_m: float = 0.03
    descent_z_relative_max_m: float = 0.22
    # Calibrated above the Round-1 maximum (27 frames); the validated
    # high-open-descent smoke produced 33 frames.
    min_open_descent_frames: int = 30
    min_stable_open_seconds: float = 4.5
    max_ee_step_l2_p90_m: float = 0.008
    min_accept_rate: float = 0.90


def _first_sustained(
    values: Sequence[float],
    *,
    predicate,
    debounce: int,
) -> int | None:
    flags = [bool(predicate(float(value))) for value in values]
    for index in range(0, len(flags) - debounce + 1):
        if all(flags[index : index + debounce]):
            return index
    return None


def _hysteresis_edges(
    values: Sequence[float],
    *,
    closed_le: float = 0.4,
    open_ge: float = 0.6,
) -> tuple[int, int]:
    """Return open→closed and closed→open edge counts, ignoring the ramp band."""
    state: str | None = None
    closes = 0
    reopens = 0
    for raw in values:
        value = float(raw)
        new_state = "closed" if value <= closed_le else "open" if value >= open_ge else None
        if new_state is None:
            continue
        if state == "open" and new_state == "closed":
            closes += 1
        elif state == "closed" and new_state == "open":
            reopens += 1
        state = new_state
    return closes, reopens


def analyze_episode_arrays(
    *,
    action: np.ndarray,
    ee_pose: np.ndarray,
    object_pose: np.ndarray,
    timestamps: np.ndarray,
    thresholds: Round2Thresholds,
) -> dict[str, Any]:
    """Compute geometry-relative timing and label-quality metrics."""
    if action.ndim != 2 or action.shape[1] != 8:
        raise ValueError(f"expected action[N,8], got {action.shape}")
    if ee_pose.ndim != 2 or ee_pose.shape[1] < 3:
        raise ValueError(f"expected observation.ee_pose[N,>=3], got {ee_pose.shape}")
    if object_pose.ndim != 2 or object_pose.shape[1] < 3:
        raise ValueError(
            f"expected observation.object_pose[N,>=3], got {object_pose.shape}"
        )
    if not (len(action) == len(ee_pose) == len(object_pose) == len(timestamps)):
        raise ValueError("episode columns have inconsistent lengths")
    if len(action) < thresholds.debounce_frames:
        raise ValueError("episode is too short for debounce")

    grip = action[:, 7]
    first_close = _first_sustained(
        grip,
        predicate=lambda value: value <= thresholds.close_threshold,
        debounce=thresholds.debounce_frames,
    )
    xy_error = np.linalg.norm(ee_pose[:, :2] - object_pose[:, :2], axis=1)
    z_relative = ee_pose[:, 2] - object_pose[:, 2]
    open_mask = grip > thresholds.close_threshold
    before_close = np.arange(len(action)) < (
        first_close if first_close is not None else len(action)
    )
    stable_pick_open = (
        before_close
        & open_mask
        & (xy_error <= thresholds.pick_xy_tolerance_m)
        & (z_relative <= thresholds.pick_z_relative_max_m)
    )

    stable_start = None
    stable_open_seconds = 0.0
    stable_open_frames = 0
    if first_close is not None:
        cursor = first_close - 1
        while cursor >= 0 and bool(stable_pick_open[cursor]):
            cursor -= 1
        stable_start = cursor + 1
        stable_open_frames = first_close - stable_start
        if stable_open_frames > 0:
            stable_open_seconds = float(
                timestamps[first_close] - timestamps[stable_start]
            )

    open_descent = (
        before_close
        & open_mask
        & (z_relative > thresholds.pick_z_relative_max_m)
        & (z_relative <= thresholds.descent_z_relative_max_m)
    )
    step_l2 = np.linalg.norm(np.diff(action[:, :3], axis=0), axis=1)
    close_edges, reopen_edges = _hysteresis_edges(grip)
    intermediate = (grip > 1e-6) & (grip < 1.0 - 1e-6)

    close_xy_error = (
        float(xy_error[first_close]) if first_close is not None else None
    )
    close_z_relative = (
        float(z_relative[first_close]) if first_close is not None else None
    )
    close_geometry_ok = bool(
        first_close is not None
        and close_xy_error is not None
        and close_z_relative is not None
        and close_xy_error <= thresholds.pick_xy_tolerance_m
        and close_z_relative <= thresholds.pick_z_relative_max_m
    )

    return {
        "num_frames": int(len(action)),
        "duration_seconds": float(timestamps[-1] - timestamps[0]),
        "first_close_frame": first_close,
        "first_close_timestamp": (
            float(timestamps[first_close]) if first_close is not None else None
        ),
        "first_close_xy_error_m": close_xy_error,
        "first_close_z_relative_m": close_z_relative,
        "first_close_geometry_ok": close_geometry_ok,
        "stable_pick_open_start_frame": stable_start,
        "stable_pick_open_frames": stable_open_frames,
        "stable_pick_open_seconds": stable_open_seconds,
        "open_descent_frames": int(np.sum(open_descent)),
        "gripper_close_edges": close_edges,
        "gripper_reopen_edges": reopen_edges,
        "gripper_min": float(np.min(grip)),
        "gripper_max": float(np.max(grip)),
        "gripper_exact_endpoint_fraction": float(
            np.mean(np.isclose(grip, 0.0) | np.isclose(grip, 1.0))
        ),
        "gripper_intermediate_fraction": float(np.mean(intermediate)),
        "ee_step_l2_p90_m": (
            float(np.percentile(step_l2, 90)) if len(step_l2) else 0.0
        ),
        "ee_step_l2_max_m": float(np.max(step_l2)) if len(step_l2) else 0.0,
    }


def _video_frame_count(path: Path) -> int:
    capture = cv2.VideoCapture(str(path))
    try:
        return int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()


def _seed_from_name(name: str) -> int | None:
    match = re.search(r"(?:^|_)seed(\d+)(?:_|$)", name)
    return int(match.group(1)) if match else None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _episode_target_failures(
    metrics: dict[str, Any], thresholds: Round2Thresholds
) -> list[str]:
    failures: list[str] = []
    if not metrics["first_close_geometry_ok"]:
        failures.append("first_close_geometry")
    if metrics["open_descent_frames"] < thresholds.min_open_descent_frames:
        failures.append("open_descent_frames")
    if metrics["stable_pick_open_seconds"] < thresholds.min_stable_open_seconds:
        failures.append("stable_pick_open_seconds")
    if metrics["gripper_close_edges"] != 1:
        failures.append("gripper_close_edges")
    if metrics["gripper_reopen_edges"] != 0:
        failures.append("gripper_reopen_edges")
    if not (
        metrics["gripper_min"] >= 0.0 and metrics["gripper_max"] <= 1.0
    ):
        failures.append("gripper_range")
    ee_p90 = metrics["ee_step_l2_p90_m"]
    if ee_p90 > thresholds.max_ee_step_l2_p90_m and not np.isclose(
        ee_p90,
        thresholds.max_ee_step_l2_p90_m,
        rtol=1e-9,
        atol=1e-12,
    ):
        failures.append("ee_step_l2_p90")
    return failures


def audit_source(
    source: Path,
    *,
    evidence_dir: Path | None,
    thresholds: Round2Thresholds,
    apply_round2_targets: bool,
) -> dict[str, Any]:
    structural_errors: list[str] = []
    target_failures: list[str] = []
    expected_seed = _seed_from_name(source.name)

    info_path = source / "meta" / "info.json"
    if not info_path.is_file():
        return {
            "source": str(source),
            "structural_passed": False,
            "round2_targets_passed": False,
            "structural_errors": ["missing meta/info.json"],
            "target_failures": [],
            "episodes": [],
        }
    info = json.loads(info_path.read_text(encoding="utf-8"))
    expected_episodes = int(info.get("total_episodes", 0))

    runtime_path = source / "episode_results.jsonl"
    runtime_rows = _read_jsonl(runtime_path) if runtime_path.is_file() else []
    if not runtime_rows:
        structural_errors.append("missing episode_results.jsonl runtime evidence")
    runtime_successes = sum(
        bool(row.get("outcome", {}).get("success")) for row in runtime_rows
    )
    accept_rate = (
        float(runtime_successes / len(runtime_rows)) if runtime_rows else None
    )
    if runtime_successes != expected_episodes:
        structural_errors.append(
            f"runtime successful episodes {runtime_successes} != dataset episodes {expected_episodes}"
        )
    if accept_rate is not None and accept_rate < thresholds.min_accept_rate:
        structural_errors.append(
            f"runtime accept_rate {accept_rate:.3f} < {thresholds.min_accept_rate:.3f}"
        )
    runtime_seeds = sorted(
        {
            int(row["identity"]["seed"])
            for row in runtime_rows
            if row.get("identity", {}).get("seed") is not None
        }
    )
    if expected_seed is not None and runtime_seeds != [expected_seed]:
        structural_errors.append(
            f"runtime seeds {runtime_seeds} != source-name seed {expected_seed}"
        )
    for index, row in enumerate(runtime_rows):
        if row.get("execution_status") != "completed":
            structural_errors.append(f"runtime row {index}: execution not completed")
        safety = row.get("contact_safety", {})
        if safety.get("estop_triggered") is True:
            structural_errors.append(f"runtime row {index}: estop triggered")
        if row.get("fail_safe_events"):
            structural_errors.append(f"runtime row {index}: fail_safe_events present")
        if row.get("outcome", {}).get("success") and not row.get("subgoals", {}).get(
            "lift"
        ):
            structural_errors.append(f"runtime row {index}: success without lift")

    renderer_verified = None
    pre_close_holds: list[float] = []
    if evidence_dir is not None:
        full_log = evidence_dir / "full_system.log"
        renderer_verified = False
        if full_log.is_file():
            text = full_log.read_text(encoding="utf-8", errors="replace")
            # Bounded launches can report a node as "process has died" during
            # normal shutdown. Renderer startup/fallback is the evidence
            # boundary; shutdown wording is not a camera-quality failure.
            renderer_verified = bool(
                re.search(r"camera_bridge up .*MuJoCo renderer", text)
            ) and not bool(
                re.search(r"synthetic fallback|MuJoCo camera init failed", text)
            )
        if not renderer_verified:
            structural_errors.append("real MuJoCo renderer evidence missing or failed")
        for log_path in sorted(evidence_dir.glob("batch_*.log")):
            text = log_path.read_text(encoding="utf-8", errors="replace")
            pre_close_holds.extend(
                float(value)
                for value in re.findall(r"Pre-close open hold \(([0-9.]+)s\)", text)
            )

    episodes: list[dict[str, Any]] = []
    required_columns = {
        "action",
        "observation.ee_pose",
        "observation.object_pose",
        "timestamp",
    }
    for episode_index in range(expected_episodes):
        episode_name = f"episode_{episode_index:06d}"
        parquet = source / "data" / "chunk-000" / f"{episode_name}.parquet"
        video = (
            source
            / "videos"
            / "chunk-000"
            / "observation.images.scene"
            / f"{episode_name}.mp4"
        )
        meta_path = source / episode_name / "meta.json"
        episode_errors: list[str] = []
        if not parquet.is_file():
            structural_errors.append(f"{episode_name}: missing parquet")
            continue
        table = pq.read_table(parquet)
        missing = sorted(required_columns - set(table.column_names))
        if missing:
            structural_errors.append(f"{episode_name}: missing columns {missing}")
            continue
        action = np.asarray(table.column("action").to_pylist(), dtype=np.float64)
        ee_pose = np.asarray(
            table.column("observation.ee_pose").to_pylist(), dtype=np.float64
        )
        object_pose = np.asarray(
            table.column("observation.object_pose").to_pylist(), dtype=np.float64
        )
        timestamps = np.asarray(
            table.column("timestamp").to_pylist(), dtype=np.float64
        )
        if not all(
            np.all(np.isfinite(values))
            for values in (action, ee_pose, object_pose, timestamps)
        ):
            episode_errors.append("nan_or_inf")
        metrics = analyze_episode_arrays(
            action=action,
            ee_pose=ee_pose,
            object_pose=object_pose,
            timestamps=timestamps,
            thresholds=thresholds,
        )
        if not video.is_file():
            episode_errors.append("missing_scene_video")
        else:
            video_frames = _video_frame_count(video)
            metrics["video_num_frames"] = video_frames
            if video_frames != table.num_rows:
                episode_errors.append(
                    f"video_parquet_length:{video_frames}!={table.num_rows}"
                )
        if not meta_path.is_file():
            episode_errors.append("missing_episode_meta")
        else:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("success") is not True:
                episode_errors.append("meta.success_not_true")
            if meta.get("upstream_gate") != "batch_generator":
                episode_errors.append("meta.upstream_gate_not_batch_generator")
            if float(meta.get("capture_fps", meta.get("fps", 0.0))) != 10.0:
                episode_errors.append("meta.capture_fps_not_10")
            if meta.get("video_specs", {}).get("observation.images.scene") != [
                240,
                320,
                3,
            ]:
                episode_errors.append("meta.scene_shape_not_240x320x3")
        structural_errors.extend(
            f"{episode_name}: {error}" for error in episode_errors
        )
        failures = (
            _episode_target_failures(metrics, thresholds)
            if apply_round2_targets
            else []
        )
        target_failures.extend(f"{episode_name}: {failure}" for failure in failures)
        episodes.append(
            {
                "episode_index": episode_index,
                "episode_id": f"{source.name}/{episode_name}",
                "structural_errors": episode_errors,
                "round2_target_failures": failures,
                "metrics": metrics,
            }
        )

    scalar_metric_names = (
        "first_close_frame",
        "first_close_xy_error_m",
        "first_close_z_relative_m",
        "stable_pick_open_frames",
        "stable_pick_open_seconds",
        "open_descent_frames",
        "gripper_intermediate_fraction",
        "ee_step_l2_p90_m",
    )
    aggregate: dict[str, Any] = {}
    for name in scalar_metric_names:
        values = [
            float(episode["metrics"][name])
            for episode in episodes
            if episode["metrics"].get(name) is not None
        ]
        aggregate[f"{name}_mean"] = float(np.mean(values)) if values else None
        aggregate[f"{name}_min"] = float(np.min(values)) if values else None
        aggregate[f"{name}_max"] = float(np.max(values)) if values else None

    return {
        "source": str(source),
        "source_name": source.name,
        "expected_seed_from_name": expected_seed,
        "runtime_seeds": runtime_seeds,
        "expected_episodes": expected_episodes,
        "runtime_attempts": len(runtime_rows),
        "runtime_successes": runtime_successes,
        "runtime_accept_rate": accept_rate,
        "renderer_verified": renderer_verified,
        "pre_close_hold_seconds_from_log": sorted(set(pre_close_holds)),
        "structural_passed": not structural_errors,
        "round2_targets_passed": (
            not structural_errors and not target_failures
            if apply_round2_targets
            else None
        ),
        "structural_errors": structural_errors,
        "target_failures": target_failures,
        "aggregate": aggregate,
        "episodes": episodes,
    }


def audit_datasets(
    sources: list[Path],
    *,
    evidence_dirs: list[Path] | None,
    profile: str,
    thresholds: Round2Thresholds,
) -> dict[str, Any]:
    if evidence_dirs is not None and len(evidence_dirs) != len(sources):
        raise ValueError("--evidence-dir must be repeated once per --source")
    apply_targets = profile == "round2"
    results = [
        audit_source(
            source,
            evidence_dir=(evidence_dirs[index] if evidence_dirs else None),
            thresholds=thresholds,
            apply_round2_targets=apply_targets,
        )
        for index, source in enumerate(sources)
    ]
    structural_passed = all(result["structural_passed"] for result in results)
    round2_passed = (
        structural_passed
        and all(result["round2_targets_passed"] for result in results)
        if apply_targets
        else None
    )
    return {
        "artifact_type": "smolvla_griptiming_dataset_audit",
        "contract_version": "smolvla_griptiming_dataset_audit_v1",
        "profile": profile,
        "claims_task_success": False,
        "ran_training": False,
        "ran_isaac": False,
        "structural_passed": structural_passed,
        "round2_targets_passed": round2_passed,
        "thresholds": thresholds.__dict__,
        "sources": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--evidence-dir", type=Path, action="append", default=None)
    parser.add_argument(
        "--profile",
        choices=("structural", "round2"),
        default="structural",
    )
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--min-open-descent-frames", type=int, default=30)
    parser.add_argument("--min-stable-open-seconds", type=float, default=4.5)
    parser.add_argument("--max-ee-step-l2-p90-m", type=float, default=0.008)
    args = parser.parse_args()

    thresholds = Round2Thresholds(
        min_open_descent_frames=args.min_open_descent_frames,
        min_stable_open_seconds=args.min_stable_open_seconds,
        max_ee_step_l2_p90_m=args.max_ee_step_l2_p90_m,
    )
    report = audit_datasets(
        args.source,
        evidence_dirs=args.evidence_dir,
        profile=args.profile,
        thresholds=thresholds,
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["structural_passed"]:
        return 2
    if report["round2_targets_passed"] is False:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
