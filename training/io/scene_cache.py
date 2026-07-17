"""Deterministic release-scoped cache for random scene-frame access."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


SCENE_KEY = "observation.images.scene"


def default_cache_root() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "robot_arm_episode_data_lab" / "scene_frames"


def release_cache_key(dataset: Path, manifest: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(manifest, sort_keys=True).encode("utf-8"))
    for relative in sorted(
        (manifest.get("video_files") or {}).get(SCENE_KEY, {}).values()
    ):
        path = dataset / str(relative)
        stat = path.stat()
        digest.update(str(relative).encode("utf-8"))
        digest.update(str(stat.st_size).encode("ascii"))
    return digest.hexdigest()[:20]


class SceneFrameCache:
    def __init__(
        self,
        dataset: Path,
        manifest: dict[str, Any],
        *,
        cache_root: Path | None = None,
    ) -> None:
        self.dataset = dataset.resolve()
        self.manifest = manifest
        self.video_map = {
            int(key): str(value)
            for key, value in (
                (manifest.get("video_files") or {}).get(SCENE_KEY, {})
            ).items()
        }
        if not self.video_map:
            raise ValueError("release has no scene video mapping")
        self.cache_key = release_cache_key(self.dataset, manifest)
        self.root = (cache_root or default_cache_root()) / self.cache_key

    def prepare(self, expected_counts: dict[int, int]) -> Path:
        metadata_path = self.root / "cache.json"
        expected = {
            "cache_key": self.cache_key,
            "expected_counts": {
                str(key): int(value) for key, value in sorted(expected_counts.items())
            },
        }
        if metadata_path.is_file():
            try:
                current = json.loads(metadata_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                current = {}
            if current == expected and self._all_frames_exist(expected_counts):
                return self.root
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True)
        for episode_index, expected_count in sorted(expected_counts.items()):
            video_relative = self.video_map.get(episode_index)
            if not video_relative:
                raise ValueError(
                    f"missing scene video for episode {episode_index}")
            video = self.dataset / video_relative
            if not video.is_file():
                raise FileNotFoundError(video)
            episode_dir = self.root / f"episode_{episode_index:06d}"
            episode_dir.mkdir(parents=True)
            subprocess.run(
                [
                    "ffmpeg", "-v", "error", "-i", str(video),
                    "-vsync", "0", str(episode_dir / "%06d.png"),
                ],
                check=True,
            )
            observed = len(list(episode_dir.glob("*.png")))
            if observed != int(expected_count):
                raise ValueError(
                    f"episode {episode_index} decoded frames {observed} "
                    f"!= expected {expected_count}"
                )
        metadata_path.write_text(
            json.dumps(expected, indent=2, sort_keys=True), encoding="utf-8")
        return self.root

    def frame_path(self, episode_index: int, frame_index: int) -> Path:
        # ffmpeg numbering starts at one; frame_index is zero based.
        return (
            self.root
            / f"episode_{int(episode_index):06d}"
            / f"{int(frame_index) + 1:06d}.png"
        )

    def _all_frames_exist(self, expected_counts: dict[int, int]) -> bool:
        return all(
            len(list((self.root / f"episode_{episode:06d}").glob("*.png")))
            == int(count)
            for episode, count in expected_counts.items()
        )
