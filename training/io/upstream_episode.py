"""Load upstream Panda episodes (Arrow legacy or LeRobot v2.1)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

FORMAT_ARROW = "huggingface_dataset"
FORMAT_V21 = "lerobot_v21"
FORMAT_VIDEO = FORMAT_V21

RGB_IMAGE_KEYS = (
    "observation.images.scene",
    "observation.images.wrist",
    "observation.images.tactile_left",
    "observation.images.tactile_right",
)
DEPTH_KEY = "observation.depth.scene"
CHUNK_ID = "chunk-000"


def dataset_root(path: Path) -> Path:
    path = path.resolve()
    if (path / "meta" / "info.json").is_file():
        return path
    if path.name.startswith("episode_"):
        return path.parent
    if path.name == "train" and path.parent.name.startswith("episode_"):
        return path.parent.parent
    return path


def detect_episode_format(root: Path) -> str:
    root = dataset_root(root)
    if (root / "meta" / "info.json").is_file():
        return FORMAT_V21
    if list((root / "data" / CHUNK_ID).glob("episode_*.parquet")):
        return FORMAT_V21
    return FORMAT_ARROW


def list_episode_indices(root: Path) -> list[int]:
    root = dataset_root(root)
    indices: set[int] = set()
    data_dir = root / "data" / CHUNK_ID
    if data_dir.is_dir():
        for path in data_dir.glob("episode_*.parquet"):
            indices.add(int(path.stem.split("_", 1)[1]))
    for path in root.glob("episode_*/meta.json"):
        try:
            indices.add(int(path.parent.name.split("_", 1)[1]))
        except (IndexError, ValueError):
            continue
    return sorted(indices)


def discover_episode_train_dirs(root: Path) -> list[Path]:
    root = dataset_root(root)
    if detect_episode_format(root) == FORMAT_V21:
        return [root / f"episode_{index:06d}" for index in list_episode_indices(root)]
    if root.name == "train" and root.is_dir():
        return [root]
    if root.name.startswith("episode_") and (root / "train").is_dir():
        return [root / "train"]
    return sorted(path for path in root.glob("episode_*/train") if path.is_dir())


def parquet_episode_path(root: Path, episode_index: int) -> Path:
    return root / "data" / CHUNK_ID / f"episode_{episode_index:06d}.parquet"


def video_episode_path(root: Path, camera_key: str, episode_index: int) -> Path:
    return root / "videos" / CHUNK_ID / camera_key / f"episode_{episode_index:06d}.mp4"


def sidecar_meta_path(root: Path, episode_index: int) -> Path:
    return root / f"episode_{episode_index:06d}" / "meta.json"


def load_parquet_rows(root: Path, episode_index: int) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    table = pq.read_table(parquet_episode_path(dataset_root(root), episode_index))
    return table.to_pylist()


def load_upstream_episode_rows(
    dataset: Path,
    *,
    decode_videos: bool = False,
) -> list[dict[str, Any]]:
    root = dataset_root(dataset)
    if detect_episode_format(root) != FORMAT_V21:
        train_dirs = discover_episode_train_dirs(dataset)
        if not train_dirs:
            return _load_arrow_rows(dataset)
        rows: list[dict[str, Any]] = []
        for train_dir in train_dirs:
            rows.extend(_load_arrow_rows(train_dir))
        return rows

    rows: list[dict[str, Any]] = []
    for episode_index in list_episode_indices(root):
        episode_rows = load_parquet_rows(root, episode_index)
        if decode_videos:
            episode_rows = _attach_decoded_videos(root, episode_rows, episode_index)
        rows.extend(episode_rows)
    return rows


def _load_arrow_rows(train_dir: Path) -> list[dict[str, Any]]:
    from datasets import load_from_disk

    path = train_dir
    if path.name != "train" and (path / "train").is_dir():
        path = path / "train"
    dataset = load_from_disk(str(path))
    return [dict(row) for row in dataset]


def read_episode_meta(train_dir: Path) -> dict[str, Any]:
    if train_dir.name.startswith("episode_") and (train_dir / "meta.json").is_file():
        return json.loads((train_dir / "meta.json").read_text(encoding="utf-8"))
    root = dataset_root(train_dir)
    for episode_index in reversed(list_episode_indices(root)):
        sidecar = sidecar_meta_path(root, episode_index)
        if sidecar.is_file():
            return json.loads(sidecar.read_text(encoding="utf-8"))
    return {}


def video_specs_from_meta(train_dir: Path) -> dict[str, list[int]]:
    meta = read_episode_meta(train_dir)
    specs = meta.get("video_specs")
    if isinstance(specs, dict):
        return {str(key): list(value) for key, value in specs.items()}
    return {}


def _attach_decoded_videos(
    root: Path,
    rows: list[dict[str, Any]],
    episode_index: int,
) -> list[dict[str, Any]]:
    import torchvision.io as io

    decoded: dict[str, list[np.ndarray]] = {}
    for key in RGB_IMAGE_KEYS:
        path = video_episode_path(root, key, episode_index)
        if path.is_file():
            tensor, _, _ = io.read_video(str(path), pts_unit="sec")
            decoded[key] = [np.asarray(frame, dtype=np.uint8) for frame in tensor]

    enriched: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        item = dict(row)
        for key, frames in decoded.items():
            if index < len(frames):
                item[key] = frames[index]
        enriched.append(item)
    return enriched


def ffprobe_frame_count(video_path: Path) -> int:
    output = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_packets",
            "-show_entries",
            "stream=nb_read_packets",
            "-of",
            "csv=p=0",
            str(video_path),
        ],
        text=True,
    ).strip()
    return int(output)
