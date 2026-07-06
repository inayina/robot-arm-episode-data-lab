#!/usr/bin/env python3
"""Adapt ros2-arm-teleoperation-suite M6 Panda datasets to the local schema."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.adapters.upstream_m6 import adapt_rows, write_adapted_dataset
from training.scripts.inspect_dataset import inspect_dataset, load_rows

DEFAULT_SCHEMA = REPO_ROOT / "configs" / "robot_schemas" / "panda.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Upstream dataset directory.")
    parser.add_argument("--output", type=Path, required=True, help="Adapted output directory.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Panda schema YAML.")
    parser.add_argument(
        "--derive-ee-delta-action",
        action="store_true",
        help="Convert upstream ee_pose_gripper[8] actions to ee_delta_gripper[7].",
    )
    parser.add_argument(
        "--inspect",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Inspect the adapted dataset before returning.",
    )
    return parser.parse_args()


def load_schema(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    schema = load_schema(args.schema)
    rows = load_rows(args.input)
    adapted_rows, action_type = adapt_rows(
        rows,
        schema,
        derive_ee_delta_action=args.derive_ee_delta_action,
    )
    write_adapted_dataset(
        args.output,
        adapted_rows,
        schema,
        action_type=action_type,
        source=args.input,
        derive_ee_delta_action=args.derive_ee_delta_action,
    )

    print(f"Adapted upstream Panda dataset: {args.output}")
    print(f"Frames: {len(adapted_rows)}")
    print(f"Action type: {action_type}")
    if args.inspect:
        report = inspect_dataset(args.output, schema)
        print(f"Inspection: {'PASS' if report.passed else 'FAIL'}")
        if report.errors:
            for error in report.errors:
                print(f"  - {error}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
