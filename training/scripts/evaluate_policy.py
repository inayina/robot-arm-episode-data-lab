#!/usr/bin/env python3
"""Evaluate a smoke policy offline against a Panda dataset release."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.policies.linear_policy import load_checkpoint, predict
from training.scripts.inspect_dataset import inspect_dataset, load_manifest, load_rows
from training.scripts.train_act_smoke import rows_to_arrays

DEFAULT_SCHEMA = REPO_ROOT / "configs" / "robot_schemas" / "panda.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True, help="Panda dataset release directory.")
    parser.add_argument("--checkpoint", type=Path, required=True, help="checkpoint.npz path.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Panda schema YAML.")
    parser.add_argument("--output", type=Path, required=True, help="Evaluation JSON output path.")
    return parser.parse_args()


def load_schema(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def evaluate_policy(
    dataset: Path,
    checkpoint_path: Path,
    schema: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    manifest = load_manifest(dataset)
    checkpoint = load_checkpoint(checkpoint_path)
    action_type = str(manifest.get("action_type", checkpoint.action_type))
    if checkpoint.schema_id != schema["schema_id"]:
        raise ValueError(
            f"checkpoint schema_id={checkpoint.schema_id!r} does not match schema={schema['schema_id']!r}"
        )
    if checkpoint.action_type != action_type:
        raise ValueError(
            f"checkpoint action_type={checkpoint.action_type!r} does not match dataset action_type={action_type!r}"
        )

    report = inspect_dataset(dataset, schema)
    if not report.passed:
        raise ValueError("dataset inspection failed; refusing to evaluate")

    rows = load_rows(dataset)
    states, actions = rows_to_arrays(
        rows,
        state_key=checkpoint.input_key,
        action_key=checkpoint.action_key,
    )
    predicted = predict(checkpoint, states)
    errors = predicted - actions
    abs_errors = np.abs(errors)
    squared_errors = errors**2
    smoothness = smoothness_proxy(predicted, rows)
    success_summary = summarize_success(rows)

    result = {
        "dataset": str(dataset),
        "checkpoint": str(checkpoint_path),
        "schema_id": schema["schema_id"],
        "release_id": manifest.get("release_id"),
        "policy_type": "linear_smoke",
        "robot": report.robot,
        "action_type": action_type,
        "num_episodes": int(report.episodes),
        "num_frames": int(report.frames),
        "state_dim": int(states.shape[1]),
        "action_dim": int(actions.shape[1]),
        "mean_absolute_action_error": float(abs_errors.mean()),
        "rmse_action_error": float(np.sqrt(squared_errors.mean())),
        "per_dim_mean_absolute_action_error": abs_errors.mean(axis=0).astype(float).tolist(),
        "per_dim_rmse_action_error": np.sqrt(squared_errors.mean(axis=0)).astype(float).tolist(),
        "smoothness_proxy": smoothness,
        "success_summary": success_summary,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def smoothness_proxy(predicted_actions: np.ndarray, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if predicted_actions.shape[0] < 2:
        return {"mean_l2_delta": 0.0, "per_episode_mean_l2_delta": {}}

    by_episode: dict[int, list[int]] = {}
    for index, row in enumerate(rows):
        by_episode.setdefault(int(row["episode_index"]), []).append(index)

    per_episode: dict[str, float] = {}
    deltas: list[float] = []
    for episode_index, indices in sorted(by_episode.items()):
        if len(indices) < 2:
            per_episode[str(episode_index)] = 0.0
            continue
        episode_actions = predicted_actions[indices]
        episode_deltas = np.linalg.norm(np.diff(episode_actions, axis=0), axis=1)
        deltas.extend(float(value) for value in episode_deltas)
        per_episode[str(episode_index)] = float(episode_deltas.mean())
    mean_delta = float(np.mean(deltas)) if deltas else 0.0
    return {
        "mean_l2_delta": mean_delta,
        "per_episode_mean_l2_delta": per_episode,
    }


def summarize_success(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    labeled: dict[int, bool] = {}
    for row in rows:
        if "success" not in row:
            continue
        labeled[int(row["episode_index"])] = bool(row["success"])
    if not labeled:
        return None
    success_count = sum(1 for value in labeled.values() if value)
    total = len(labeled)
    return {
        "labeled_episodes": total,
        "success_count": success_count,
        "success_rate": success_count / total if total else 0.0,
    }


def main() -> int:
    args = parse_args()
    schema = load_schema(args.schema)
    try:
        result = evaluate_policy(args.dataset, args.checkpoint, schema, args.output)
    except Exception as exc:  # noqa: BLE001 - CLI should report evaluation failures cleanly.
        print(f"Eval output: {args.output}")
        print("Status: FAIL")
        print(f"Error: {exc}")
        return 1

    print(f"Eval output: {args.output}")
    print(f"Frames: {result['num_frames']}")
    print(f"MAE: {result['mean_absolute_action_error']:.6f}")
    print(f"RMSE: {result['rmse_action_error']:.6f}")
    print("Status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
