#!/usr/bin/env python3
"""Merge compatible adapted Panda datasets with contiguous episode indices."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


COMPATIBILITY_KEYS = (
    "dataset_format",
    "schema_id",
    "robot",
    "action_type",
    "source_action_semantics",
    "upstream_gate",
    "filter_scope",
    "video_fps",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_manifest(root: Path) -> dict:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    if len(args.input) < 2:
        raise ValueError("at least two --input datasets are required")
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite output: {args.output}")

    manifests = [load_manifest(root) for root in args.input]
    baseline = manifests[0]
    for root, manifest in zip(args.input[1:], manifests[1:]):
        for key in COMPATIBILITY_KEYS:
            if manifest.get(key) != baseline.get(key):
                raise ValueError(
                    f"incompatible {key} for {root}: "
                    f"{manifest.get(key)!r} != {baseline.get(key)!r}"
                )

    args.output.mkdir(parents=True)
    video_root = args.output / "videos" / "observation.images.scene"
    video_root.mkdir(parents=True)
    merged_video_files: dict[str, str] = {}
    next_episode = 0
    total_frames = 0

    with (args.output / "frames.jsonl").open("w", encoding="utf-8") as output:
        for root, manifest in zip(args.input, manifests):
            episode_map: dict[int, int] = {}
            with (root / "frames.jsonl").open(encoding="utf-8") as source:
                for line in source:
                    row = json.loads(line)
                    old_episode = int(row["episode_index"])
                    if old_episode not in episode_map:
                        episode_map[old_episode] = next_episode
                        next_episode += 1
                    row["episode_index"] = episode_map[old_episode]
                    output.write(json.dumps(row, sort_keys=True) + "\n")
                    total_frames += 1

            videos = manifest["video_files"]["observation.images.scene"]
            if set(map(int, videos)) != set(episode_map):
                raise ValueError(f"video/episode mismatch in {root}")
            for old_episode, new_episode in episode_map.items():
                source_video = root / videos[str(old_episode)]
                relative = Path("videos") / "observation.images.scene" / (
                    f"episode_{new_episode:06d}.mp4"
                )
                shutil.copy2(source_video, args.output / relative)
                merged_video_files[str(new_episode)] = relative.as_posix()

    merged = dict(baseline)
    merged.update(
        num_episodes=next_episode,
        num_frames=total_frames,
        source="merged_adapted_datasets",
        source_path=None,
        source_paths=[str(root.resolve()) for root in args.input],
        video_files={"observation.images.scene": merged_video_files},
    )
    (args.output / "manifest.json").write_text(
        json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        f"Merged {len(args.input)} datasets: "
        f"{next_episode} episodes, {total_frames} frames -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
