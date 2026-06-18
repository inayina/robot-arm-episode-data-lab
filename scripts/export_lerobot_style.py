#!/usr/bin/env python3
"""将本地 episode 数据集导出为 LeRobot v2.1 兼容布局。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.video_encode import encode_png_sequence_to_mp4, ffmpeg_available

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:  # pragma: no cover - exercised only without deps.
    pa = None
    pq = None


CODEBASE_VERSION = "v2.1"
DEFAULT_FPS = 10.0
DEFAULT_CAMERA_KEY = "observation.images.main"
JOINT_NAMES = [f"joint_{index}" for index in range(7)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a dataset directory to LeRobot v2.1-compatible files."
    )
    parser.add_argument(
        "dataset_dir",
        type=Path,
        help="Dataset root or single episode directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Export directory. Defaults to <dataset_dir>/lerobot_export.",
    )
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS, help="Dataset FPS.")
    parser.add_argument(
        "--export-videos",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Encode episode PNG sequences to MP4 under videos/ (requires ffmpeg).",
    )
    parser.add_argument(
        "--camera-key",
        default=DEFAULT_CAMERA_KEY,
        help="LeRobot video feature key for the fixed RGB camera.",
    )
    return parser.parse_args()


def is_episode_dir(path: Path) -> bool:
    return (path / "metadata.json").exists() and (path / "states.npy").exists()


def discover_episode_dirs(dataset_dir: Path) -> list[Path]:
    if is_episode_dir(dataset_dir):
        return [dataset_dir]
    episodes = [
        child
        for child in sorted(dataset_dir.iterdir())
        if child.is_dir() and is_episode_dir(child)
    ]
    if not episodes:
        raise FileNotFoundError(f"No episode directories found under {dataset_dir}")
    return episodes


def load_episode_arrays(episode_dir: Path) -> dict[str, Any]:
    metadata = json.loads((episode_dir / "metadata.json").read_text(encoding="utf-8"))
    return {
        "metadata": metadata,
        "states": np.load(episode_dir / "states.npy"),
        "actions": np.load(episode_dir / "actions.npy"),
        "ee_poses": np.load(episode_dir / "ee_poses.npy"),
        "object_poses": np.load(episode_dir / "object_poses.npy"),
    }


def build_features(
    state_dim: int,
    action_dim: int,
    *,
    export_videos: bool,
    camera_key: str,
    image_shape: tuple[int, int, int] | None,
    fps: float,
) -> dict[str, dict[str, Any]]:
    features: dict[str, dict[str, Any]] = {
        "observation.state": {
            "dtype": "float32",
            "shape": [state_dim],
            "names": JOINT_NAMES[:state_dim],
        },
        "action": {
            "dtype": "float32",
            "shape": [action_dim],
            "names": JOINT_NAMES[:action_dim],
        },
        "observation.ee_pose": {
            "dtype": "float32",
            "shape": [7],
            "names": ["x", "y", "z", "qx", "qy", "qz", "qw"],
        },
        "observation.object_pose": {
            "dtype": "float32",
            "shape": [7],
            "names": ["x", "y", "z", "qx", "qy", "qz", "qw"],
        },
    }
    if export_videos and image_shape is not None:
        height, width, channels = image_shape
        features[camera_key] = {
            "dtype": "video",
            "shape": [height, width, channels],
            "names": ["height", "width", "channel"],
            "info": {
                "video.height": height,
                "video.width": width,
                "video.codec": "h264",
                "video.pix_fmt": "yuv420p",
                "video.fps": fps,
                "video.channels": channels,
                "video.is_depth_map": False,
            },
        }
    return features


def discover_image_paths(episode_dir: Path) -> list[Path]:
    return sorted((episode_dir / "images").glob("*.png"))


def probe_image_shape(episode_dir: Path) -> tuple[int, int, int]:
    from PIL import Image

    image_paths = discover_image_paths(episode_dir)
    if not image_paths:
        raise FileNotFoundError(f"No PNG frames found in {episode_dir / 'images'}")
    with Image.open(image_paths[0]) as image:
        width, height = image.size
    return height, width, 3


def compute_feature_stats(
    episodes: list[dict[str, Any]],
    feature_key: str,
    array_key: str,
) -> dict[str, list[float]]:
    stacked = np.concatenate([episode[array_key] for episode in episodes], axis=0)
    return {
        "mean": stacked.mean(axis=0).astype(np.float32).tolist(),
        "std": stacked.std(axis=0).astype(np.float32).tolist(),
        "min": stacked.min(axis=0).astype(np.float32).tolist(),
        "max": stacked.max(axis=0).astype(np.float32).tolist(),
    }


def episode_to_table(
    episode: dict[str, Any],
    *,
    episode_index: int,
    global_index_start: int,
    fps: float,
) -> pa.Table:
    if pa is None or pq is None:
        raise RuntimeError(
            "Missing dependency: pyarrow. Install dependencies with "
            "`python -m pip install -r requirements.txt`."
        )

    states = episode["states"]
    actions = episode["actions"]
    ee_poses = episode["ee_poses"]
    object_poses = episode["object_poses"]
    num_frames = states.shape[0]
    metadata = episode["metadata"]
    task_index = 0
    language_instruction = metadata.get("language_instruction", metadata.get("task_name", ""))

    rows = {
        "index": list(range(global_index_start, global_index_start + num_frames)),
        "episode_index": [episode_index] * num_frames,
        "frame_index": list(range(num_frames)),
        "timestamp": [frame_index / fps for frame_index in range(num_frames)],
        "task_index": [task_index] * num_frames,
        "next.done": [False] * (num_frames - 1) + [True],
        "next.reward": [0.0] * num_frames,
        "observation.state": [row.astype(np.float32).tolist() for row in states],
        "action": [row.astype(np.float32).tolist() for row in actions],
        "observation.ee_pose": [row.astype(np.float32).tolist() for row in ee_poses],
        "observation.object_pose": [
            row.astype(np.float32).tolist() for row in object_poses
        ],
        "language_instruction": [str(language_instruction)] * num_frames,
        "success": [bool(metadata.get("success", False))] * num_frames,
    }
    return pa.Table.from_pydict(rows)


def export_dataset(
    dataset_dir: Path,
    output_dir: Path,
    fps: float,
    *,
    export_videos: bool = True,
    camera_key: str = DEFAULT_CAMERA_KEY,
) -> dict[str, Any]:
    episode_dirs = discover_episode_dirs(dataset_dir)
    episodes = [load_episode_arrays(path) for path in episode_dirs]

    state_dim = int(episodes[0]["states"].shape[1])
    action_dim = int(episodes[0]["actions"].shape[1])
    image_shape = probe_image_shape(episode_dirs[0]) if export_videos else None
    if export_videos and not ffmpeg_available():
        raise RuntimeError(
            "Video export requested but ffmpeg was not found on PATH. "
            "Install ffmpeg or pass --no-export-videos."
        )
    features = build_features(
        state_dim,
        action_dim,
        export_videos=export_videos,
        camera_key=camera_key,
        image_shape=image_shape,
        fps=fps,
    )

    data_chunk_dir = output_dir / "data" / "chunk-000"
    meta_dir = output_dir / "meta"
    video_chunk_dir = output_dir / "videos" / "chunk-000" / camera_key
    data_chunk_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)
    if export_videos:
        video_chunk_dir.mkdir(parents=True, exist_ok=True)

    episode_records: list[dict[str, Any]] = []
    global_index = 0
    for episode_index, (episode_dir, episode) in enumerate(zip(episode_dirs, episodes)):
        table = episode_to_table(
            episode,
            episode_index=episode_index,
            global_index_start=global_index,
            fps=fps,
        )
        parquet_path = data_chunk_dir / f"episode_{episode_index:06d}.parquet"
        pq.write_table(table, parquet_path)
        num_frames = int(episode["states"].shape[0])
        if export_videos:
            image_paths = discover_image_paths(episode_dir)
            if len(image_paths) != num_frames:
                raise ValueError(
                    f"{episode_dir.name}: expected {num_frames} PNG frames, found {len(image_paths)}"
                )
            video_path = video_chunk_dir / f"episode_{episode_index:06d}.mp4"
            encode_png_sequence_to_mp4(image_paths, video_path, fps=fps)
        episode_records.append(
            {
                "episode_index": episode_index,
                "episode_id": episode_dir.name,
                "tasks": [episode["metadata"].get("language_instruction", "")],
                "length": num_frames,
            }
        )
        global_index += num_frames

    tasks = sorted(
        {
            str(episode["metadata"].get("language_instruction", ""))
            for episode in episodes
            if episode["metadata"].get("language_instruction")
        }
    )
    if not tasks:
        tasks = [episodes[0]["metadata"].get("task_name", "robot_task")]
    task_records = [{"task_index": index, "task": task} for index, task in enumerate(tasks)]

    stats = {
        "observation.state": compute_feature_stats(episodes, "observation.state", "states"),
        "action": compute_feature_stats(episodes, "action", "actions"),
        "observation.ee_pose": compute_feature_stats(
            episodes, "observation.ee_pose", "ee_poses"
        ),
        "observation.object_pose": compute_feature_stats(
            episodes, "observation.object_pose", "object_poses"
        ),
    }

    info = {
        "codebase_version": CODEBASE_VERSION,
        "robot_type": episodes[0]["metadata"].get("robot", "kuka_iiwa"),
        "total_episodes": len(episodes),
        "total_frames": global_index,
        "total_tasks": len(task_records),
        "total_videos": len(episodes) if export_videos else 0,
        "total_chunks": 1,
        "chunks_size": 1000,
        "fps": fps,
        "splits": {"train": f"0:{len(episodes)}"},
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": (
            "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4"
            if export_videos
            else None
        ),
        "features": features,
    }

    (meta_dir / "info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    (meta_dir / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    (meta_dir / "tasks.jsonl").write_text(
        "\n".join(json.dumps(record) for record in task_records) + "\n",
        encoding="utf-8",
    )
    (meta_dir / "episodes.jsonl").write_text(
        "\n".join(json.dumps(record) for record in episode_records) + "\n",
        encoding="utf-8",
    )

    return {
        "output_dir": str(output_dir),
        "total_episodes": len(episodes),
        "total_frames": global_index,
        "total_videos": len(episodes) if export_videos else 0,
        "tasks": task_records,
    }


def main() -> int:
    args = parse_args()
    output_dir = args.output or (args.dataset_dir / "lerobot_export")
    summary = export_dataset(
        args.dataset_dir,
        output_dir,
        fps=args.fps,
        export_videos=args.export_videos,
        camera_key=args.camera_key,
    )
    print(
        "Wrote LeRobot-compatible export to "
        f"{summary['output_dir']} "
        f"({summary['total_episodes']} episodes, {summary['total_frames']} frames, "
        f"{summary['total_videos']} videos)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
