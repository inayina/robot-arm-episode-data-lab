#!/usr/bin/env python3
"""Package a Panda replay JSONL with checks for downstream bridge handoff."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.scripts.inspect_dataset import load_manifest

DEFAULT_SCHEMA = REPO_ROOT / "configs" / "robot_schemas" / "panda.yaml"


@dataclass
class ReplayCheck:
    replay_path: str
    robot: str
    schema_id: str
    release_id: str | None
    action_type: str
    action_dim: int
    frames: int
    episodes: int
    action_min: list[float] = field(default_factory=list)
    action_max: list[float] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "replay_path": self.replay_path,
            "robot": self.robot,
            "schema_id": self.schema_id,
            "release_id": self.release_id,
            "action_type": self.action_type,
            "action_dim": self.action_dim,
            "frames": self.frames,
            "episodes": self.episodes,
            "action_min": self.action_min,
            "action_max": self.action_max,
            "warnings": self.warnings,
            "errors": self.errors,
            "status": "PASS" if self.passed else "FAIL",
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True, help="Panda dataset release directory.")
    parser.add_argument("--replay", type=Path, required=True, help="predicted_actions.jsonl path.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Panda schema YAML.")
    parser.add_argument("--output", type=Path, required=True, help="Bridge handoff bundle directory.")
    parser.add_argument("--handoff-id", default="", help="Optional stable handoff identifier.")
    return parser.parse_args()


def load_schema(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def prepare_bridge_handoff(
    dataset: Path,
    replay: Path,
    schema: dict[str, Any],
    output: Path,
    *,
    handoff_id: str = "",
) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"handoff output is not empty: {output}")
    if not replay.exists():
        raise FileNotFoundError(f"replay JSONL does not exist: {replay}")

    dataset_manifest = load_manifest(dataset)
    check = inspect_replay_for_handoff(replay, schema, dataset_manifest)
    if not check.passed:
        raise ValueError("replay handoff check failed; refusing to package bundle")

    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(replay, output / "predicted_actions.jsonl")
    if (dataset / "manifest.json").exists():
        shutil.copy2(dataset / "manifest.json", output / "dataset_manifest.json")
    if (dataset / "inspection_report.json").exists():
        shutil.copy2(dataset / "inspection_report.json", output / "dataset_inspection_report.json")

    (output / "replay_check.json").write_text(
        json.dumps(check.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest = build_handoff_manifest(
        dataset=dataset,
        replay=replay,
        schema=schema,
        dataset_manifest=dataset_manifest,
        check=check,
        handoff_id=handoff_id,
    )
    (output / "handoff_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def inspect_replay_for_handoff(
    replay: Path,
    schema: dict[str, Any],
    dataset_manifest: dict[str, Any],
) -> ReplayCheck:
    rows = load_replay_rows(replay)
    action_type = str(dataset_manifest.get("action_type", schema["action"]["default_type"]))
    action_dim = int(schema["action"][action_type]["dim"]) if action_type in schema["action"] else -1
    check = ReplayCheck(
        replay_path=str(replay),
        robot=schema["robot"],
        schema_id=schema["schema_id"],
        release_id=dataset_manifest.get("release_id"),
        action_type=action_type,
        action_dim=action_dim,
        frames=len(rows),
        episodes=len({row.get("episode_index") for row in rows if "episode_index" in row}),
    )

    if not rows:
        check.errors.append("replay contains no frames")
        return check
    if action_type not in schema["action"]:
        check.errors.append(f"action_type={action_type!r} is not declared in schema")
        return check

    actions: list[list[float]] = []
    previous_timestamp_by_episode: dict[int, float] = {}
    required_keys = {"timestamp", "robot", "schema_id", "action_type", "action"}
    for index, row in enumerate(rows):
        missing = sorted(required_keys - set(row))
        if missing:
            check.errors.append(f"line {index + 1}: missing keys {missing}")
            continue
        validate_identity_fields(row, schema, action_type, index, check)
        action = np.asarray(row["action"], dtype=np.float64)
        if action.shape != (action_dim,):
            check.errors.append(
                f"line {index + 1}: action shape {tuple(action.shape)} does not match [{action_dim}]"
            )
            continue
        if not np.isfinite(action).all():
            check.errors.append(f"line {index + 1}: action contains NaN or Inf")
            continue
        actions.append(action.astype(float).tolist())
        validate_timestamp_order(row, index, previous_timestamp_by_episode, check)

    if actions:
        action_array = np.asarray(actions, dtype=np.float64)
        check.action_min = action_array.min(axis=0).astype(float).tolist()
        check.action_max = action_array.max(axis=0).astype(float).tolist()
        add_range_warnings(check, schema, action_array)

    expected_frames = dataset_manifest.get("num_frames")
    if expected_frames is not None and int(expected_frames) != check.frames:
        check.errors.append(
            f"replay frames={check.frames} does not match dataset num_frames={expected_frames}"
        )
    return check


def load_replay_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: replay row must be a JSON object")
            rows.append(row)
    return rows


def validate_identity_fields(
    row: dict[str, Any],
    schema: dict[str, Any],
    action_type: str,
    index: int,
    check: ReplayCheck,
) -> None:
    if row["robot"] != schema["robot"]:
        check.errors.append(f"line {index + 1}: robot={row['robot']!r} does not match schema")
    if row["schema_id"] != schema["schema_id"]:
        check.errors.append(f"line {index + 1}: schema_id={row['schema_id']!r} does not match schema")
    if row["action_type"] != action_type:
        check.errors.append(
            f"line {index + 1}: action_type={row['action_type']!r} does not match dataset"
        )


def validate_timestamp_order(
    row: dict[str, Any],
    index: int,
    previous_timestamp_by_episode: dict[int, float],
    check: ReplayCheck,
) -> None:
    if "episode_index" not in row:
        return
    episode_index = int(row["episode_index"])
    timestamp = float(row["timestamp"])
    previous = previous_timestamp_by_episode.get(episode_index)
    if previous is not None and timestamp < previous:
        check.errors.append(f"line {index + 1}: timestamp decreased within episode {episode_index}")
    previous_timestamp_by_episode[episode_index] = timestamp


def add_range_warnings(check: ReplayCheck, schema: dict[str, Any], actions: np.ndarray) -> None:
    gripper_range = schema.get("gripper", {}).get("command_range")
    if gripper_range is None or actions.shape[1] == 0:
        return
    lower, upper = float(gripper_range[0]), float(gripper_range[1])
    gripper = actions[:, -1]
    outside = int(np.count_nonzero((gripper < lower) | (gripper > upper)))
    if outside:
        check.warnings.append(
            f"{outside} gripper commands are outside declared range [{lower}, {upper}]; "
            "bridge must clamp or reject before execution"
        )


def build_handoff_manifest(
    *,
    dataset: Path,
    replay: Path,
    schema: dict[str, Any],
    dataset_manifest: dict[str, Any],
    check: ReplayCheck,
    handoff_id: str,
) -> dict[str, Any]:
    return {
        "handoff_format": "panda_bridge_handoff_v0",
        "handoff_id": handoff_id or f"{dataset_manifest.get('release_id', 'panda')}_bridge_handoff",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "producer_repo": "robot-arm-episode-data-lab",
        "consumer_repo": "ros2-moveit-pybullet-bridge",
        "dataset": str(dataset),
        "source_replay": str(replay),
        "files": {
            "replay": "predicted_actions.jsonl",
            "dataset_manifest": "dataset_manifest.json",
            "dataset_inspection_report": "dataset_inspection_report.json",
            "replay_check": "replay_check.json",
        },
        "schema_id": schema["schema_id"],
        "robot": schema["robot"],
        "release_id": dataset_manifest.get("release_id"),
        "action_type": check.action_type,
        "action_dim": check.action_dim,
        "frames": check.frames,
        "episodes": check.episodes,
        "status": "PASS" if check.passed else "FAIL",
        "bridge_contract": {
            "runtime_owner": "ros2-moveit-pybullet-bridge",
            "first_consumer": "JsonlActionReplayPolicy",
            "input_action_semantics": "ee delta xyz/rpy plus gripper command",
            "must_validate": [
                "robot",
                "schema_id",
                "action_type",
                "action_dim",
                "finite action values",
                "runtime limits before execution",
            ],
        },
    }


def main() -> int:
    args = parse_args()
    schema = load_schema(args.schema)
    try:
        manifest = prepare_bridge_handoff(
            args.dataset,
            args.replay,
            schema,
            args.output,
            handoff_id=args.handoff_id,
        )
    except Exception as exc:  # noqa: BLE001 - CLI should report handoff failures cleanly.
        print(f"Handoff output: {args.output}")
        print("Status: FAIL")
        print(f"Error: {exc}")
        return 1

    print(f"Handoff output: {args.output}")
    print(f"Handoff id: {manifest['handoff_id']}")
    print(f"Frames: {manifest['frames']}")
    print(f"Action type: {manifest['action_type']}")
    print("Status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
