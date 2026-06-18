#!/usr/bin/env python3
"""Render a ~1 minute portfolio overview MP4 from episode PNG sequences."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.video_encode import encode_png_sequence_to_mp4, ffmpeg_available
from scripts.visualize_episode import annotated_frames, load_array


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def title_card(
    title: str,
    subtitle: str,
    *,
    size: tuple[int, int] = (640, 480),
    seconds: float = 2.5,
    fps: float = 10.0,
) -> list[Image.Image]:
    width, height = size
    frame_count = max(1, int(seconds * fps))
    image = Image.new("RGB", size, "#0f172a")
    draw = ImageDraw.Draw(image)
    title_font = load_font(34)
    subtitle_font = load_font(18)
    draw.text((40, height // 2 - 48), title, fill="#f8fafc", font=title_font)
    draw.text((40, height // 2 + 8), subtitle, fill="#94a3b8", font=subtitle_font)
    return [image.copy() for _ in range(frame_count)]


def episode_segment(
    episode_dir: Path,
    *,
    max_frames: int,
    label: str,
) -> list[Image.Image]:
    image_paths = sorted((episode_dir / "images").glob("*.png"))
    actions = load_array(episode_dir / "actions.npy")
    object_poses = load_array(episode_dir / "object_poses.npy")
    frames = annotated_frames(image_paths, actions, object_poses, max_frames)
    metadata_path = episode_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    subtitle = (
        f"{label} | grasp_mode={metadata.get('grasp_mode', 'n/a')} "
        f"success={metadata.get('success', 'n/a')}"
    )
    draw_font = load_font(16)
    for frame in frames:
        draw = ImageDraw.Draw(frame)
        draw.rectangle((8, frame.height - 34, frame.width - 8, frame.height - 8), fill=(0, 0, 0))
        draw.text((16, frame.height - 28), subtitle, fill=(255, 255, 255), font=draw_font)
    return frames


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render portfolio overview MP4.")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "assets" / "videos" / "demo_overview.mp4",
        help="Output MP4 path.",
    )
    parser.add_argument("--fps", type=float, default=5.0, help="Video FPS.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not ffmpeg_available():
        print("ffmpeg not found; install ffmpeg to render portfolio video")
        return 1

    segments = [
        title_card(
            "robot-arm-episode-data-lab",
            "PyBullet pick-lift data pipeline + LeRobot export",
        ),
        episode_segment(
            REPO_ROOT / "dataset_sample" / "episode_pick_001",
            max_frames=80,
            label="Pick-Lift (constraint)",
        ),
        episode_segment(
            REPO_ROOT / "dataset_sample" / "episode_pick_gripper",
            max_frames=80,
            label="Pick-Lift (gripper_urdf)",
        ),
        episode_segment(
            REPO_ROOT / "dataset_sample" / "episode_000001",
            max_frames=60,
            label="Reach trajectory",
        ),
        title_card(
            "LeRobot v2.1 export",
            "parquet + observation.images.main MP4 per episode",
            seconds=3.0,
        ),
        title_card(
            "Reproduce locally",
            "python -m pip install -r requirements.txt && pytest -q",
            seconds=3.0,
        ),
    ]

    frames: list[Image.Image] = []
    for segment in segments:
        frames.extend(segment)

    with tempfile.TemporaryDirectory(prefix="portfolio_video_") as temp_dir:
        temp_root = Path(temp_dir)
        png_paths: list[Path] = []
        for index, frame in enumerate(frames):
            png_path = temp_root / f"{index:06d}.png"
            frame.save(png_path)
            png_paths.append(png_path)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        encode_png_sequence_to_mp4(png_paths, args.output, fps=args.fps)

    duration = len(frames) / args.fps
    print(f"Wrote portfolio video to {args.output} ({len(frames)} frames, {duration:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
