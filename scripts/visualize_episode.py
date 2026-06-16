#!/usr/bin/env python3
"""Create a lightweight GIF replay for a collected episode."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize a collected episode.")
    parser.add_argument("episode_dir", type=Path, help="Episode directory.")
    parser.add_argument(
        "--save-gif",
        type=Path,
        default=None,
        help="GIF path. Defaults to <episode_dir>/replay.gif.",
    )
    parser.add_argument("--fps", type=float, default=10.0, help="GIF playback FPS.")
    parser.add_argument(
        "--max-frames",
        type=int,
        default=120,
        help="Maximum frames to include in the GIF preview.",
    )
    return parser.parse_args()


def load_array(path: Path) -> np.ndarray | None:
    if not path.exists():
        return None
    return np.load(path)


def format_vector(prefix: str, values: np.ndarray | None, index: int, count: int) -> str:
    if values is None or index >= len(values):
        return f"{prefix}: n/a"
    head = values[index][:count]
    return f"{prefix}: " + ", ".join(f"{value:+.2f}" for value in head)


def annotated_frames(
    image_paths: list[Path],
    actions: np.ndarray | None,
    object_poses: np.ndarray | None,
    max_frames: int,
) -> list[Image.Image]:
    frames: list[Image.Image] = []
    for step, image_path in enumerate(image_paths[:max_frames]):
        image = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(image)
        lines = [
            f"step: {step:06d}",
            format_vector("action", actions, step, 3),
            format_vector("object_xyz", object_poses, step, 3),
        ]
        draw.rectangle((8, 8, 360, 72), fill=(0, 0, 0))
        for line_index, line in enumerate(lines):
            draw.text((16, 14 + line_index * 18), line, fill=(255, 255, 255))
        frames.append(image)
    return frames


def main() -> int:
    args = parse_args()
    episode_dir = args.episode_dir
    images_dir = episode_dir / "images"
    image_paths = sorted(images_dir.glob("*.png"))
    if not image_paths:
        print(f"No PNG frames found in {images_dir}")
        return 1
    if args.fps <= 0:
        print("--fps must be positive")
        return 1
    if args.max_frames <= 0:
        print("--max-frames must be positive")
        return 1

    actions = load_array(episode_dir / "actions.npy")
    object_poses = load_array(episode_dir / "object_poses.npy")
    frames = annotated_frames(image_paths, actions, object_poses, args.max_frames)
    output_path = args.save_gif or (episode_dir / "replay.gif")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration_ms = max(1, int(1000.0 / args.fps))
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
    )
    print(
        f"Wrote GIF replay to {output_path} "
        f"({len(frames)} of {len(image_paths)} frames)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
