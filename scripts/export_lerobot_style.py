#!/usr/bin/env python3
"""Reserved helper for future LeRobot-style exports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a lightweight mapping manifest toward a future "
            "LeRobot-style dataset export."
        )
    )
    parser.add_argument("episode_dir", type=Path, help="Source episode directory.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional manifest JSON path. If omitted, only prints the mapping.",
    )
    return parser.parse_args()


def build_manifest(episode_dir: Path) -> dict[str, object]:
    return {
        "status": "reserved",
        "source_episode": str(episode_dir),
        "note": (
            "This project keeps V1 focused on PyBullet episode collection. "
            "A later version can map these fields into LeRobot conventions."
        ),
        "field_mapping": {
            "images/*.png": "observation.images.fixed_rgb",
            "states.npy": "observation.state",
            "actions.npy": "action",
            "ee_poses.npy": "observation.ee_pose",
            "object_poses.npy": "observation.object_pose",
            "metadata.json": "episode metadata",
        },
    }


def main() -> int:
    args = parse_args()
    manifest = build_manifest(args.episode_dir)
    text = json.dumps(manifest, indent=2)
    if args.output is None:
        print(text)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote LeRobot-style export manifest to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
