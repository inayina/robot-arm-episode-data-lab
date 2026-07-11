#!/usr/bin/env python3
"""Generate episode-level EDA for state-only Panda behavioral cloning data."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.scripts.inspect_dataset import load_rows


def trajectory_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_episode: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_episode[int(row["episode_index"])].append(row)

    episodes = []
    for episode_id, episode_rows in sorted(by_episode.items()):
        episode_rows.sort(key=lambda row: int(row["frame_index"]))
        timestamps = np.asarray([row["timestamp"] for row in episode_rows], dtype=np.float64)
        states = np.asarray([row["observation.state"] for row in episode_rows], dtype=np.float64)
        actions = np.asarray([row["action"] for row in episode_rows], dtype=np.float64)
        dt = np.diff(timestamps)
        joint_step = np.diff(states[:, :7], axis=0)
        velocity = joint_step / dt[:, None] if len(dt) else np.empty((0, 7))
        reversals = (
            (joint_step[1:] * joint_step[:-1] < 0.0)
            & (np.abs(joint_step[1:]) > 0.003)
            & (np.abs(joint_step[:-1]) > 0.003)
        )
        reversal_by_axis = np.sum(reversals, axis=0).astype(int)
        reversal_denominator = max(1, len(joint_step) - 1)
        episodes.append({
            "episode_index": episode_id,
            "frames": len(episode_rows),
            "timestamp_strictly_increasing": bool(np.all(dt > 0.0)),
            "dt_ms": _summary(dt * 1000.0),
            "joint_abs_step_rad": _summary(np.abs(joint_step)),
            "joint_abs_velocity_rad_s": _summary(np.abs(velocity)),
            "joint_reversal_count": int(np.sum(reversals)),
            "joint_reversal_count_by_axis": reversal_by_axis.tolist(),
            "joint_reversal_rate_by_axis": (reversal_by_axis / reversal_denominator).astype(float).tolist(),
            "action_abs_step": _summary(np.abs(np.diff(actions, axis=0))),
        })

    states = np.asarray([row["observation.state"] for row in rows], dtype=np.float64)
    actions = np.asarray([row["action"] for row in rows], dtype=np.float64)
    return {
        "num_episodes": len(episodes),
        "num_frames": len(rows),
        "state": _per_dimension(states),
        "action": _per_dimension(actions),
        "episodes": episodes,
    }


def quality_gate(
    report: dict[str, Any], *, max_p99_joint_step_rad: float = 0.02,
    max_axis_reversal_rate: float = 0.10,
) -> dict[str, Any]:
    rejected = []
    for episode in report["episodes"]:
        reasons = []
        if not episode["timestamp_strictly_increasing"]:
            reasons.append("timestamp is not strictly increasing")
        p99 = episode["joint_abs_step_rad"]["p99"]
        if p99 is not None and p99 > max_p99_joint_step_rad:
            reasons.append(f"joint step p99 {p99:.6f} > {max_p99_joint_step_rad:.6f} rad")
        max_reversal = max(episode["joint_reversal_rate_by_axis"], default=0.0)
        if max_reversal > max_axis_reversal_rate:
            reasons.append(
                f"axis reversal rate {max_reversal:.6f} > {max_axis_reversal_rate:.6f}"
            )
        if reasons:
            rejected.append({"episode_index": episode["episode_index"], "reasons": reasons})
    return {
        "passed": not rejected,
        "accepted_episodes": report["num_episodes"] - len(rejected),
        "rejected_episodes": rejected,
        "thresholds": {
            "max_p99_joint_step_rad": max_p99_joint_step_rad,
            "max_axis_reversal_rate": max_axis_reversal_rate,
        },
    }


def _summary(values: np.ndarray) -> dict[str, float | None]:
    flat = np.asarray(values, dtype=np.float64).reshape(-1)
    if not len(flat):
        return {"median": None, "p95": None, "p99": None, "max": None}
    return {
        "median": float(np.median(flat)),
        "p95": float(np.quantile(flat, 0.95)),
        "p99": float(np.quantile(flat, 0.99)),
        "max": float(np.max(flat)),
    }


def _per_dimension(values: np.ndarray) -> dict[str, list[float]]:
    return {
        "mean": np.mean(values, axis=0).astype(float).tolist(),
        "std": np.std(values, axis=0).astype(float).tolist(),
        "min": np.min(values, axis=0).astype(float).tolist(),
        "max": np.max(values, axis=0).astype(float).tolist(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = load_rows(args.dataset)
    if not rows:
        raise ValueError("dataset contains no rows")
    report = trajectory_metrics(rows)
    report["quality_gate"] = quality_gate(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote low-dimensional EDA to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
