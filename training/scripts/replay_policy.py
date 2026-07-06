#!/usr/bin/env python3
"""Export predicted Panda actions as neutral replay JSONL."""

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
    parser.add_argument("--output", type=Path, required=True, help="Replay JSONL output path.")
    return parser.parse_args()


def load_schema(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def export_replay(
    dataset: Path,
    checkpoint_path: Path,
    schema: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    manifest = load_manifest(dataset)
    checkpoint = load_checkpoint(checkpoint_path)
    action_type = str(manifest.get("action_type", checkpoint.action_type))
    validate_replay_contract(schema, manifest, checkpoint, action_type)

    report = inspect_dataset(dataset, schema)
    if not report.passed:
        raise ValueError("dataset inspection failed; refusing to export replay")

    rows = load_rows(dataset)
    states, _actions = rows_to_arrays(
        rows,
        state_key=checkpoint.input_key,
        action_key=checkpoint.action_key,
    )
    predicted = predict(checkpoint, states)
    expected_action_dim = int(schema["action"][action_type]["dim"])
    if predicted.ndim != 2 or predicted.shape[1] != expected_action_dim:
        raise ValueError(
            f"predicted action dim={predicted.shape[1] if predicted.ndim == 2 else predicted.shape} "
            f"does not match schema dim={expected_action_dim}"
        )
    if not np.isfinite(predicted).all():
        raise ValueError("predicted actions contain NaN or Inf")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row, action in zip(rows, predicted, strict=True):
            handle.write(
                json.dumps(
                    build_replay_row(
                        row=row,
                        action=action,
                        schema=schema,
                        manifest=manifest,
                        action_type=action_type,
                    ),
                    sort_keys=True,
                )
                + "\n"
            )

    summary = {
        "output": str(output),
        "dataset": str(dataset),
        "checkpoint": str(checkpoint_path),
        "schema_id": schema["schema_id"],
        "release_id": manifest.get("release_id"),
        "robot": schema["robot"],
        "action_type": action_type,
        "num_episodes": int(report.episodes),
        "num_frames": int(report.frames),
        "action_dim": expected_action_dim,
    }
    return summary


def validate_replay_contract(
    schema: dict[str, Any],
    manifest: dict[str, Any],
    checkpoint,
    action_type: str,
) -> None:
    if checkpoint.schema_id != schema["schema_id"]:
        raise ValueError(
            f"checkpoint schema_id={checkpoint.schema_id!r} does not match schema={schema['schema_id']!r}"
        )
    if manifest.get("schema_id") and manifest["schema_id"] != schema["schema_id"]:
        raise ValueError(
            f"dataset schema_id={manifest['schema_id']!r} does not match schema={schema['schema_id']!r}"
        )
    if action_type not in schema["action"]:
        raise ValueError(f"action_type={action_type!r} is not declared in schema")
    if checkpoint.action_type != action_type:
        raise ValueError(
            f"checkpoint action_type={checkpoint.action_type!r} does not match dataset action_type={action_type!r}"
        )

    expected_dim = int(schema["action"][action_type]["dim"])
    checkpoint_dim = int(checkpoint.action_mean.shape[0])
    if checkpoint_dim != expected_dim:
        raise ValueError(
            f"checkpoint action dim={checkpoint_dim} does not match schema dim={expected_dim}"
        )


def build_replay_row(
    *,
    row: dict[str, Any],
    action: np.ndarray,
    schema: dict[str, Any],
    manifest: dict[str, Any],
    action_type: str,
) -> dict[str, Any]:
    return {
        "timestamp": float(row["timestamp"]),
        "episode_index": int(row["episode_index"]),
        "frame_index": int(row["frame_index"]),
        "task": row.get("task"),
        "robot": schema["robot"],
        "schema_id": schema["schema_id"],
        "release_id": manifest.get("release_id"),
        "action_type": action_type,
        "action": action.astype(float).tolist(),
    }


def main() -> int:
    args = parse_args()
    schema = load_schema(args.schema)
    try:
        summary = export_replay(args.dataset, args.checkpoint, schema, args.output)
    except Exception as exc:  # noqa: BLE001 - CLI should report replay export failures cleanly.
        print(f"Replay output: {args.output}")
        print("Status: FAIL")
        print(f"Error: {exc}")
        return 1

    print(f"Replay output: {summary['output']}")
    print(f"Frames: {summary['num_frames']}")
    print(f"Action type: {summary['action_type']}")
    print(f"Action dim: {summary['action_dim']}")
    print("Status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
