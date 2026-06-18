"""Tests for ffmpeg-backed MP4 encoding helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from core.video_encode import encode_png_sequence_to_mp4, ffmpeg_available


@pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not available")
def test_encode_png_sequence_to_mp4(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    for index in range(3):
        Image.new("RGB", (32, 24), color=(index * 40, 80, 120)).save(
            frames_dir / f"{index:06d}.png"
        )
    output_path = tmp_path / "clip.mp4"
    encode_png_sequence_to_mp4(
        sorted(frames_dir.glob("*.png")),
        output_path,
        fps=5.0,
    )
    assert output_path.exists()
    assert output_path.stat().st_size > 0
