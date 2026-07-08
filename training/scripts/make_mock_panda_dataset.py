#!/usr/bin/env python3
"""Generate a tiny schema-compatible Panda dataset for smoke tests."""

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

DEFAULT_SCHEMA = REPO_ROOT / "configs" / "robot_schemas" / "panda.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Output dataset directory.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Panda schema YAML.")
    parser.add_argument("--episodes", type=int, default=2, help="Number of mock episodes.")
    parser.add_argument("--frames-per-episode", type=int, default=5, help="Frames per episode.")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic RNG seed.")
    parser.add_argument(
        "--action-type",
        default=None,
        help="Action type to generate. Defaults to schema action.default_type.",
    )
    return parser.parse_args()


def load_schema(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def make_rows(
    schema: dict[str, Any],
    *,
    episodes: int,
    frames_per_episode: int,
    seed: int,
    action_type: str | None,
) -> list[dict[str, Any]]:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    if frames_per_episode <= 0:
        raise ValueError("frames-per-episode must be positive")

    rng = np.random.default_rng(seed)
    selected_action_type = action_type or schema["action"]["default_type"]
    action_dim = int(schema["action"][selected_action_type]["dim"])
    state_dim = int(schema["observation"]["state"]["dim"])
    ee_dim = int(schema["observation"]["ee_pose"]["dim"])
    object_dim = int(schema["observation"]["object_pose"]["dim"])
    ft_dim = int(schema["observation"]["ft"]["dim"])

    rows: list[dict[str, Any]] = []
    fps = 30.0
    include_language = "language_instruction" in schema
    for episode_index in range(episodes):
        base_state = rng.normal(0.0, 0.05, size=state_dim)
        instruction = _language_instruction_for_episode(episode_index)
        for frame_index in range(frames_per_episode):
            t = frame_index / fps
            state = base_state + rng.normal(0.0, 0.005, size=state_dim)
            state[-1] = float(np.clip(0.8 - 0.1 * frame_index, 0.0, 1.0))
            action = rng.normal(0.0, 0.01, size=action_dim)
            action[-1] = 1.0 if frame_index < frames_per_episode // 2 else 0.0
            row = {
                "observation.state": state.astype(np.float32).tolist(),
                "observation.ee_pose": _unit_pose(ee_dim, z=0.35 + 0.002 * frame_index),
                "observation.object_pose": _unit_pose(object_dim, z=0.05),
                "observation.ft": rng.normal(0.0, 0.01, size=ft_dim).astype(np.float32).tolist(),
                "action": action.astype(np.float32).tolist(),
                "timestamp": float(episode_index * frames_per_episode + frame_index) / fps,
                "frame_index": frame_index,
                "episode_index": episode_index,
                "task": "mock_panda_pick",
            }
            if include_language:
                row["task"] = "mock_panda_sorting"
                row["language_instruction"] = instruction
            rows.append(row)
    return rows


def _unit_pose(dim: int, *, z: float) -> list[float]:
    if dim != 7:
        raise ValueError(f"expected pose dim 7, got {dim}")
    return [0.4, 0.0, float(z), 0.0, 0.0, 0.0, 1.0]


def _language_instruction_for_episode(episode_index: int) -> str:
    instructions = (
        "pick up the red box and place it in the left bin",
        "pick up the blue cylinder and place it in the right bin",
        "pick up the green sphere and place it in the left bin",
    )
    return instructions[episode_index % len(instructions)]


def write_dataset(
    output: Path,
    schema: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    action_type: str,
    seed: int,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    frames_path = output / "frames.jsonl"
    with frames_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    manifest = {
        "dataset_format": "panda_jsonl_v0",
        "schema_id": schema["schema_id"],
        "robot": schema["robot"],
        "action_type": action_type,
        "num_episodes": len({row["episode_index"] for row in rows}),
        "num_frames": len(rows),
        "seed": seed,
        "source": "mock_generator",
        "frames": "frames.jsonl",
    }
    if "language_instruction" in schema:
        manifest["has_language_instruction"] = all(
            str(row.get("language_instruction", "")).strip() for row in rows
        )
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    schema = load_schema(args.schema)
    action_type = args.action_type or schema["action"]["default_type"]
    rows = make_rows(
        schema,
        episodes=args.episodes,
        frames_per_episode=args.frames_per_episode,
        seed=args.seed,
        action_type=action_type,
    )
    write_dataset(args.output, schema, rows, action_type=action_type, seed=args.seed)
    print(f"Wrote mock Panda dataset: {args.output}")
    print(f"Frames: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
