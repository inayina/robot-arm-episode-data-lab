#!/usr/bin/env python3
"""Compare two Panda episode datasets as Sim2Sim distribution evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.io.upstream_episode import (
    dataset_root,
    list_episode_indices,
    sidecar_meta_path,
    video_episode_path,
)
from training.scripts.inspect_dataset import load_rows


FIELDS = (
    "observation.state",
    "observation.ee_pose",
    "observation.object_pose",
    "observation.ft",
    "observation.gripper",
    "action",
)
SCENE_KEY = "observation.images.scene"


def _finite_matrix(rows: list[dict[str, Any]], key: str) -> tuple[np.ndarray, float]:
    """Return a 2-D finite matrix and the original non-finite value rate."""
    available = [row[key] for row in rows if key in row]
    if not available:
        return np.empty((0, 0), dtype=np.float64), 1.0
    values = np.asarray(available, dtype=np.float64)
    if values.ndim == 1:
        values = values[:, None]
    if values.ndim != 2:
        raise ValueError(f"{key} must be a scalar/vector field; observed {values.shape}")
    finite = np.isfinite(values)
    nonfinite_rate = 1.0 - float(np.count_nonzero(finite)) / float(finite.size)
    complete_rows = values[np.all(finite, axis=1)]
    return complete_rows, nonfinite_rate


def _per_dimension(values: np.ndarray) -> dict[str, list[float]]:
    """Summarize a non-empty numeric matrix by dimension."""
    return {
        "mean": np.mean(values, axis=0).astype(float).tolist(),
        "std": np.std(values, axis=0).astype(float).tolist(),
        "min": np.min(values, axis=0).astype(float).tolist(),
        "p05": np.quantile(values, 0.05, axis=0).astype(float).tolist(),
        "p50": np.quantile(values, 0.50, axis=0).astype(float).tolist(),
        "p95": np.quantile(values, 0.95, axis=0).astype(float).tolist(),
        "max": np.max(values, axis=0).astype(float).tolist(),
    }


def _empirical_wasserstein(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    max_quantiles: int = 1024,
) -> list[float]:
    """Approximate per-axis empirical W1 with a bounded shared quantile grid."""
    count = min(max(len(reference), len(candidate), 2), max_quantiles)
    quantiles = np.linspace(0.0, 1.0, count)
    ref_q = np.quantile(reference, quantiles, axis=0)
    cand_q = np.quantile(candidate, quantiles, axis=0)
    return np.mean(np.abs(ref_q - cand_q), axis=0).astype(float).tolist()


def _normalized_trajectory(values: np.ndarray, points: int = 101) -> np.ndarray:
    """Interpolate a trajectory over normalized episode progress."""
    if not len(values):
        return np.empty((0, values.shape[1] if values.ndim == 2 else 0))
    if len(values) == 1:
        return np.repeat(values, points, axis=0)
    source = np.linspace(0.0, 1.0, len(values))
    target = np.linspace(0.0, 1.0, points)
    return np.column_stack([
        np.interp(target, source, values[:, axis])
        for axis in range(values.shape[1])
    ])


def compare_field(reference: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    """Compare equally shaped vector fields without assuming equal frame counts."""
    if reference.shape[1:] != candidate.shape[1:]:
        raise ValueError(
            f"field dimension mismatch: {reference.shape[1:]} != {candidate.shape[1:]}"
        )
    ref_mean = np.mean(reference, axis=0)
    cand_mean = np.mean(candidate, axis=0)
    ref_std = np.std(reference, axis=0)
    cand_std = np.std(candidate, axis=0)
    pooled_std = np.sqrt((np.square(ref_std) + np.square(cand_std)) / 2.0)
    standardized = np.divide(
        cand_mean - ref_mean,
        pooled_std,
        out=np.zeros_like(ref_mean),
        where=pooled_std > 1e-12,
    )
    ref_trajectory = _normalized_trajectory(reference)
    cand_trajectory = _normalized_trajectory(candidate)
    trajectory_error = cand_trajectory - ref_trajectory
    return {
        "dimension": int(reference.shape[1]),
        "reference": _per_dimension(reference),
        "candidate": _per_dimension(candidate),
        "mean_shift": (cand_mean - ref_mean).astype(float).tolist(),
        "standardized_mean_shift": standardized.astype(float).tolist(),
        "wasserstein_1": _empirical_wasserstein(reference, candidate),
        "normalized_trajectory_rmse": np.sqrt(
            np.mean(np.square(trajectory_error), axis=0)
        ).astype(float).tolist(),
        "normalized_trajectory_l2_rmse": float(
            np.sqrt(np.mean(np.sum(np.square(trajectory_error), axis=1)))
        ),
        "endpoint_delta": (
            candidate[-1] - reference[-1]
        ).astype(float).tolist(),
    }


def _episode_meta(root: Path) -> list[dict[str, Any]]:
    resolved = dataset_root(root)
    result = []
    for index in list_episode_indices(resolved):
        path = sidecar_meta_path(resolved, index)
        if path.is_file():
            result.append(json.loads(path.read_text(encoding="utf-8")))
    return result


def _timing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    timestamps = np.asarray([row["timestamp"] for row in rows], dtype=np.float64)
    dt = np.diff(timestamps)
    positive = dt[dt > 0.0]
    duration = float(timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 0.0
    return {
        "duration_s": duration,
        "effective_fps": float((len(rows) - 1) / duration) if duration > 0.0 else None,
        "timestamp_strictly_increasing": bool(np.all(dt > 0.0)),
        "dt_ms": ({
            "mean": float(np.mean(positive) * 1000.0),
            "std": float(np.std(positive) * 1000.0),
            "p95": float(np.quantile(positive, 0.95) * 1000.0),
            "max": float(np.max(positive) * 1000.0),
        } if len(positive) else None),
    }


def dataset_summary(path: Path, label: str) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Load one raw/adapted dataset and summarize comparable numeric fields."""
    rows = load_rows(path)
    if not rows:
        raise ValueError(f"{label} dataset contains no rows: {path}")
    rows.sort(key=lambda row: (int(row["episode_index"]), int(row["frame_index"])))
    meta = _episode_meta(path)
    matrices: dict[str, np.ndarray] = {}
    fields: dict[str, Any] = {}
    for key in FIELDS:
        values, nonfinite_rate = _finite_matrix(rows, key)
        missing_rate = 1.0 - sum(key in row for row in rows) / len(rows)
        if values.size:
            matrices[key] = values
        fields[key] = {
            "present": bool(values.size),
            "shape": list(values.shape),
            "missing_rate": float(missing_rate),
            "nonfinite_rate": float(nonfinite_rate),
            "summary": _per_dimension(values) if values.size else None,
        }
    provenance_keys = ("simulator_backend", "simulator_version", "scene_id")
    provenance = {
        key: sorted({str(item[key]) for item in meta if item.get(key) not in (None, "")})
        for key in provenance_keys
    }
    return ({
        "label": label,
        "path": str(path.resolve()),
        "num_episodes": len({int(row["episode_index"]) for row in rows}),
        "num_frames": len(rows),
        "tasks": sorted({str(row.get("task", "")) for row in rows}),
        "action_semantics": sorted({
            str(item.get("action_semantics", "")) for item in meta
            if item.get("action_semantics")
        }),
        "provenance": provenance,
        "timing": _timing(rows),
        "fields": fields,
    }, matrices)


def _decode_scene_video(path: Path, sample_fps: float) -> np.ndarray:
    """Decode sampled RGB frames using the repository's existing ffmpeg dependency."""
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", str(path),
    ], text=True))
    stream = probe["streams"][0]
    width, height = int(stream["width"]), int(stream["height"])
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(path),
        "-vf", f"fps={sample_fps}", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
    ])
    frame_bytes = height * width * 3
    if not raw or len(raw) % frame_bytes:
        raise ValueError(f"unexpected decoded video size for {path}")
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, height, width, 3)


def scene_distribution(path: Path, sample_fps: float) -> tuple[dict[str, Any], np.ndarray | None]:
    """Summarize scene RGB pixels from all discovered episode videos."""
    root = dataset_root(path)
    videos = [
        video_episode_path(root, SCENE_KEY, index)
        for index in list_episode_indices(root)
    ]
    videos = [video for video in videos if video.is_file()]
    if not videos:
        return {"present": False, "videos": []}, None
    frames = [_decode_scene_video(video, sample_fps) for video in videos]
    shapes = [list(frame.shape[1:]) for frame in frames]
    pixels = np.concatenate([frame.reshape(-1, 3) for frame in frames], axis=0).astype(
        np.float64
    ) / 255.0
    luminance = pixels @ np.asarray([0.2126, 0.7152, 0.0722])
    return ({
        "present": True,
        "videos": [str(video) for video in videos],
        "sample_fps": float(sample_fps),
        "sampled_frames": int(sum(len(frame) for frame in frames)),
        "frame_shapes": shapes,
        "rgb_mean": np.mean(pixels, axis=0).astype(float).tolist(),
        "rgb_std": np.std(pixels, axis=0).astype(float).tolist(),
        "luminance_mean": float(np.mean(luminance)),
        "luminance_std": float(np.std(luminance)),
    }, pixels)


def compare_datasets(
    reference_path: Path,
    candidate_path: Path,
    *,
    reference_label: str = "mujoco",
    candidate_label: str = "isaac",
    video_sample_fps: float = 1.0,
) -> dict[str, Any]:
    """Build an evidence-only Sim2Sim comparison report."""
    reference, ref_values = dataset_summary(reference_path, reference_label)
    candidate, cand_values = dataset_summary(candidate_path, candidate_label)
    common = sorted(set(ref_values) & set(cand_values))
    fields = {
        key: compare_field(ref_values[key], cand_values[key])
        for key in common
    }
    ref_scene, ref_pixels = scene_distribution(reference_path, video_sample_fps)
    cand_scene, cand_pixels = scene_distribution(candidate_path, video_sample_fps)
    scene_comparison = None
    if ref_pixels is not None and cand_pixels is not None:
        scene_comparison = {
            "rgb_mean_shift": (
                np.mean(cand_pixels, axis=0) - np.mean(ref_pixels, axis=0)
            ).astype(float).tolist(),
            "rgb_wasserstein_1": _empirical_wasserstein(ref_pixels, cand_pixels),
        }
    warnings = []
    if reference["num_episodes"] < 5 or candidate["num_episodes"] < 5:
        warnings.append(
            "fewer than 5 episodes per backend; do not treat this as a calibrated gate"
        )
    if reference["tasks"] != candidate["tasks"]:
        warnings.append("task labels differ between datasets")
    if reference["action_semantics"] != candidate["action_semantics"]:
        warnings.append("action semantics differ or are missing")
    shared_scene_id = (
        reference["provenance"]["scene_id"]
        and reference["provenance"]["scene_id"]
        == candidate["provenance"]["scene_id"]
    )
    return {
        "report_type": "sim2sim_distribution_evidence_v1",
        "status": "EVIDENCE_ONLY",
        "method": {
            "wasserstein_1": "shared quantile approximation, at most 1024 points",
            "trajectory_alignment": "101 points over normalized episode progress",
            "scene_rgb_sampling_fps": float(video_sample_fps),
        },
        "reference": reference,
        "candidate": candidate,
        "comparability": {
            "task_labels_equal": reference["tasks"] == candidate["tasks"],
            "action_semantics_equal": (
                reference["action_semantics"] == candidate["action_semantics"]
            ),
            "frame_counts_equal": reference["num_frames"] == candidate["num_frames"],
            "declared_scene_ids_equal": bool(shared_scene_id),
            "raw_action_distribution_equal": bool(
                "action" in fields
                and np.max(np.abs(fields["action"]["wasserstein_1"])) < 1e-12
            ),
        },
        "common_fields": common,
        "field_comparisons": fields,
        "scene_rgb": {
            "reference": ref_scene,
            "candidate": cand_scene,
            "comparison": scene_comparison,
        },
        "warnings": warnings,
        "interpretation_limits": [
            "not a task-success or grasp-success metric",
            "not evidence of real-robot or Sim2Real performance",
            "thresholds require a multi-episode baseline before use as a gate",
            "matching scene_id strings do not prove matching physical initial state",
            "force/torque values require aligned sensor frames and semantics before gating",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render a compact human-readable companion to the JSON evidence."""
    ref, cand = report["reference"], report["candidate"]
    lines = [
        "# Sim2Sim Distribution Evidence",
        "",
        f"Status: **{report['status']}**",
        "",
        "| Dataset | Backend | Episodes | Frames | Duration (s) | Effective FPS |",
        "|---|---|---:|---:|---:|---:|",
        (
            f"| Reference | {ref['label']} | {ref['num_episodes']} | "
            f"{ref['num_frames']} | {ref['timing']['duration_s']:.4f} | "
            f"{_format_number(ref['timing']['effective_fps'])} |"
        ),
        (
            f"| Candidate | {cand['label']} | {cand['num_episodes']} | "
            f"{cand['num_frames']} | {cand['timing']['duration_s']:.4f} | "
            f"{_format_number(cand['timing']['effective_fps'])} |"
        ),
        "",
        "| Field | Dim | Trajectory L2 RMSE | Mean W1 | Max abs mean shift |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, comparison in report["field_comparisons"].items():
        lines.append(
            f"| `{key}` | {comparison['dimension']} | "
            f"{comparison['normalized_trajectory_l2_rmse']:.6g} | "
            f"{float(np.mean(comparison['wasserstein_1'])):.6g} | "
            f"{float(np.max(np.abs(comparison['mean_shift']))):.6g} |"
        )
    scene = report["scene_rgb"]
    if scene["comparison"] is not None:
        ref_scene = scene["reference"]
        cand_scene = scene["candidate"]
        lines.extend([
            "",
            "## Scene RGB (sampled)",
            "",
            "| Dataset | Frames | Luminance mean | Luminance std | RGB mean |",
            "|---|---:|---:|---:|---|",
            (
                f"| Reference | {ref_scene['sampled_frames']} | "
                f"{ref_scene['luminance_mean']:.6g} | "
                f"{ref_scene['luminance_std']:.6g} | "
                f"{_format_vector(ref_scene['rgb_mean'])} |"
            ),
            (
                f"| Candidate | {cand_scene['sampled_frames']} | "
                f"{cand_scene['luminance_mean']:.6g} | "
                f"{cand_scene['luminance_std']:.6g} | "
                f"{_format_vector(cand_scene['rgb_mean'])} |"
            ),
            "",
            (
                "RGB Wasserstein-1: "
                f"{_format_vector(scene['comparison']['rgb_wasserstein_1'])}."
            ),
        ])
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {item}" for item in report["interpretation_limits"])
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in report["warnings"])
    return "\n".join(lines) + "\n"


def _format_number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _format_vector(values: list[float]) -> str:
    return "[" + ", ".join(f"{value:.6g}" for value in values) + "]"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--reference-label", default="mujoco")
    parser.add_argument("--candidate-label", default="isaac")
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument("--video-sample-fps", type=float, default=1.0)
    args = parser.parse_args()
    if args.video_sample_fps <= 0.0:
        raise ValueError("video-sample-fps must be positive")
    report = compare_datasets(
        args.reference,
        args.candidate,
        reference_label=args.reference_label,
        candidate_label=args.candidate_label,
        video_sample_fps=args.video_sample_fps,
    )
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote Sim2Sim JSON evidence to {args.json_output}")
    if args.markdown_output is not None:
        print(f"Wrote Sim2Sim Markdown evidence to {args.markdown_output}")
    print("Status: EVIDENCE_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
