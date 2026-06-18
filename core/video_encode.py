"""Encode PNG frame sequences to MP4 via ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def encode_png_sequence_to_mp4(
    image_paths: list[Path],
    output_path: Path,
    *,
    fps: float,
) -> None:
    if not image_paths:
        raise ValueError("No PNG frames provided for video encoding")
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg not found on PATH; install ffmpeg to export MP4 videos")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            str(fps),
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-i",
            "-",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ],
        stdin=subprocess.PIPE,
    ) as process:
        assert process.stdin is not None
        for image_path in image_paths:
            process.stdin.write(image_path.read_bytes())
        process.stdin.close()
        return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"ffmpeg failed with exit code {return_code}")
