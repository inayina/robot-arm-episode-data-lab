#!/usr/bin/env python3
"""Prepare an immutable-ish Panda dataset release for training/evaluation."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.scripts.inspect_dataset import inspect_dataset, load_manifest

DEFAULT_SCHEMA = REPO_ROOT / "configs" / "robot_schemas" / "panda.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Inspected Panda dataset directory.")
    parser.add_argument("--output", type=Path, required=True, help="Release output directory.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Panda schema YAML.")
    parser.add_argument("--release-id", required=True, help="Stable release identifier.")
    parser.add_argument(
        "--description",
        default="",
        help="Short human-readable release note.",
    )
    return parser.parse_args()


def load_schema(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def prepare_release(
    source: Path,
    output: Path,
    schema: dict[str, Any],
    *,
    release_id: str,
    description: str = "",
) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"release output is not empty: {output}")

    report = inspect_dataset(source, schema)
    if not report.passed:
        raise ValueError("dataset inspection failed; refusing to create release")

    source_manifest = load_manifest(source)
    copied_frames = copy_frame_payload(source, output)
    inspection_report = report.to_dict()
    (output / "inspection_report.json").write_text(
        json.dumps(inspection_report, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    manifest = build_release_manifest(
        source=source,
        schema=schema,
        source_manifest=source_manifest,
        inspection_report=inspection_report,
        copied_frames=copied_frames,
        release_id=release_id,
        description=description,
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def copy_frame_payload(source: Path, output: Path) -> str:
    output.mkdir(parents=True, exist_ok=True)
    if (source / "frames.jsonl").exists():
        shutil.copy2(source / "frames.jsonl", output / "frames.jsonl")
        return "frames.jsonl"
    if (source / "frames.npz").exists():
        shutil.copy2(source / "frames.npz", output / "frames.npz")
        return "frames.npz"
    raise FileNotFoundError(
        "release preparation currently requires frames.jsonl or frames.npz input"
    )


def build_release_manifest(
    *,
    source: Path,
    schema: dict[str, Any],
    source_manifest: dict[str, Any],
    inspection_report: dict[str, Any],
    copied_frames: str,
    release_id: str,
    description: str,
) -> dict[str, Any]:
    action_type = str(inspection_report["action_type"])
    has_language_instruction = bool(source_manifest.get("has_language_instruction", False))
    training_contract = {
        "state_key": "observation.state",
        "state_dim": int(schema["observation"]["state"]["dim"]),
        "action_key": "action",
        "action_dim": int(schema["action"][action_type]["dim"]),
        "task_key": schema["task"]["key"],
    }
    if has_language_instruction:
        training_contract["language_instruction_key"] = str(
            schema.get("language_instruction", {}).get("key", "language_instruction")
        )
    return {
        "dataset_format": "panda_release_v0",
        "release_id": release_id,
        "description": description,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schema_id": schema["schema_id"],
        "schema_version": schema.get("version"),
        "robot": schema["robot"],
        "action_type": action_type,
        "num_episodes": int(inspection_report["episodes"]),
        "num_frames": int(inspection_report["frames"]),
        "has_language_instruction": has_language_instruction,
        "frames": copied_frames,
        "inspection": {
            "status": inspection_report["status"],
            "warnings": inspection_report["warnings"],
            "report": "inspection_report.json",
        },
        "source": {
            "path": str(source),
            "dataset_format": source_manifest.get("dataset_format", "unknown"),
            "schema_id": source_manifest.get("schema_id"),
            "action_type": source_manifest.get("action_type", action_type),
            "source": source_manifest.get("source"),
            "source_path": source_manifest.get("source_path"),
        },
        "filter_rules": {
            "require_success_true": True,
            "exclude_safety_estop": True,
            "exclude_drive_fault": True,
            "optional_modalities_may_be_missing": True,
            "filter_scope": str(
                source_manifest.get(
                    "filter_scope",
                    "training_split_only"
                    if source_manifest.get("physical_validation_applied")
                    else "schema_and_training",
                )
            ),
            "upstream_gate": source_manifest.get("upstream_gate"),
            "physical_validation_applied": bool(
                source_manifest.get("physical_validation_applied", False)
            ),
        },
        "training_contract": training_contract,
    }


def main() -> int:
    args = parse_args()
    schema = load_schema(args.schema)
    try:
        manifest = prepare_release(
            args.input,
            args.output,
            schema,
            release_id=args.release_id,
            description=args.description,
        )
    except Exception as exc:  # noqa: BLE001 - CLI should report release failures cleanly.
        print(f"Release: {args.output}")
        print("Status: FAIL")
        print(f"Error: {exc}")
        return 1

    print(f"Release: {args.output}")
    print(f"Release id: {manifest['release_id']}")
    print(f"Robot: {manifest['robot']}")
    print(f"Action type: {manifest['action_type']}")
    print(f"Episodes: {manifest['num_episodes']}")
    print(f"Frames: {manifest['num_frames']}")
    print("Status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
