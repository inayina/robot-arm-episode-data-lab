#!/usr/bin/env python3
"""将本地 episode 数据转换为 HuggingFace datasets（hf_dataset）格式。

与 export_lerobot_style.py 的区别：
  - export_lerobot_style.py  → LeRobot v2.1 原生布局（Parquet + MP4 + meta JSON），
                               适合上传 HuggingFace Hub 或使用 lerobot 库直接加载。
  - export_to_lerobot.py     → HuggingFace datasets.save_to_disk() 格式（Arrow），
                               可直接被 ros2-arm-teleoperation-suite 的
                               lerobot_recorder 节点以 datasets.load_from_disk() 读取，
                               也可送入 ACT / Diffusion Policy 训练管线。

输出目录结构：
  <output>/
    export_info.json          ← 溯源信息（源路径、robot、fps 等）
    train/
      dataset_info.json
      data-00000-of-00001.arrow
      ...
    val/                      ← 仅当指定 --split 时存在

用法示例：
  python scripts/export_to_lerobot.py dataset/v1
  python scripts/export_to_lerobot.py dataset/v1 --output data/hf_export
  python scripts/export_to_lerobot.py dataset/v1 --split train:0.8 val:0.2
  python scripts/export_to_lerobot.py dataset/v1 --dry-run --verbose

在 ros2-arm-teleoperation-suite 中加载：
  from datasets import load_from_disk
  ds = load_from_disk("path/to/hf_export/train")
  print(ds[0].keys())
  # dict_keys(['observation.state', 'action', 'observation.ee_pose',
  #            'observation.object_pose', 'timestamp', 'episode_index',
  #            'frame_index', 'done', 'language_instruction', 'success'])
"""

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

try:
    from datasets import Dataset, Features, Sequence, Value
except ImportError as exc:  # pragma: no cover
    sys.exit(
        f"Missing dependency: {exc}\n"
        "Install with: pip install 'datasets>=2.14.0'"
    )

DEFAULT_FPS = 10.0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export episode dataset to HuggingFace datasets (hf_dataset) format "
            "for use with ros2-arm-teleoperation-suite lerobot_recorder."
        ),
    )
    parser.add_argument(
        "dataset_dir",
        type=Path,
        help="Dataset root or single episode directory (must contain episode_* subdirs).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Output directory for the hf_dataset. "
            "Defaults to <dataset_dir>/hf_export."
        ),
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=DEFAULT_FPS,
        help=f"Episode frame rate used to compute timestamps. Default: {DEFAULT_FPS}",
    )
    parser.add_argument(
        "--split",
        nargs="*",
        default=None,
        metavar="NAME:RATIO",
        help=(
            "Optional train/val split specification, e.g. --split train:0.8 val:0.2. "
            "If omitted, all episodes go into a single 'train' split."
        ),
    )
    parser.add_argument(
        "--include-images",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Embed raw PNG bytes in the dataset under 'observation.image' (bytes column). "
            "Disabled by default to keep dataset size small."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate episodes without writing any output.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-episode statistics.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Episode discovery & loading
# ---------------------------------------------------------------------------

def is_episode_dir(path: Path) -> bool:
    """A valid episode directory must have metadata.json + states.npy."""
    return (path / "metadata.json").exists() and (path / "states.npy").exists()


def discover_episode_dirs(dataset_dir: Path) -> list[Path]:
    if is_episode_dir(dataset_dir):
        return [dataset_dir]
    episodes = sorted(
        child for child in dataset_dir.iterdir()
        if child.is_dir() and is_episode_dir(child)
    )
    if not episodes:
        raise FileNotFoundError(
            f"No valid episode directories found under {dataset_dir}.\n"
            "Each episode dir must contain metadata.json and states.npy."
        )
    return episodes


def load_episode(episode_dir: Path) -> dict[str, Any]:
    """Load all arrays and metadata from one episode directory."""
    metadata = json.loads((episode_dir / "metadata.json").read_text(encoding="utf-8"))

    def _load(name: str) -> np.ndarray:
        path = episode_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Missing required file: {path}")
        return np.load(path)

    states = _load("states.npy")               # (T, state_dim)
    actions = _load("actions.npy")             # (T, action_dim)
    ee_poses = _load("ee_poses.npy")           # (T, 7)
    object_poses = _load("object_poses.npy")   # (T, 7)

    T = states.shape[0]
    for arr_name, arr in [("actions", actions), ("ee_poses", ee_poses),
                           ("object_poses", object_poses)]:
        if arr.shape[0] != T:
            raise ValueError(
                f"{episode_dir.name}: {arr_name}.npy has {arr.shape[0]} rows "
                f"but states.npy has {T} rows."
            )

    image_paths: list[Path] = []
    images_dir = episode_dir / "images"
    if images_dir.is_dir():
        image_paths = sorted(images_dir.glob("*.png"))

    return {
        "dir": episode_dir,
        "metadata": metadata,
        "states": states.astype(np.float32),
        "actions": actions.astype(np.float32),
        "ee_poses": ee_poses.astype(np.float32),
        "object_poses": object_poses.astype(np.float32),
        "image_paths": image_paths,
        "num_frames": T,
    }


# ---------------------------------------------------------------------------
# Dataset construction
# ---------------------------------------------------------------------------

def episodes_to_rows(
    episodes: list[dict[str, Any]],
    *,
    fps: float,
    include_images: bool,
) -> dict[str, list[Any]]:
    """Flatten all episodes into column-oriented lists (one entry per frame)."""
    rows: dict[str, list[Any]] = {
        "observation.state": [],
        "action": [],
        "observation.ee_pose": [],
        "observation.object_pose": [],
        "timestamp": [],
        "episode_index": [],
        "frame_index": [],
        "done": [],
        "language_instruction": [],
        "success": [],
    }
    if include_images:
        rows["observation.image"] = []

    for episode_index, ep in enumerate(episodes):
        T = ep["num_frames"]
        meta = ep["metadata"]
        lang = str(meta.get("language_instruction", meta.get("task_name", "")))
        success = bool(meta.get("success", False))

        for t in range(T):
            rows["observation.state"].append(ep["states"][t].tolist())
            rows["action"].append(ep["actions"][t].tolist())
            rows["observation.ee_pose"].append(ep["ee_poses"][t].tolist())
            rows["observation.object_pose"].append(ep["object_poses"][t].tolist())
            rows["timestamp"].append(float(t) / fps)
            rows["episode_index"].append(episode_index)
            rows["frame_index"].append(t)
            rows["done"].append(t == T - 1)
            rows["language_instruction"].append(lang)
            rows["success"].append(success)

            if include_images:
                if t < len(ep["image_paths"]):
                    rows["observation.image"].append(
                        ep["image_paths"][t].read_bytes()
                    )
                else:
                    rows["observation.image"].append(b"")

    return rows


def build_features(
    state_dim: int,
    action_dim: int,
    *,
    include_images: bool,
) -> Features:
    """Construct the HuggingFace Features schema."""
    feats: dict[str, Any] = {
        "observation.state": Sequence(Value("float32"), length=state_dim),
        "action": Sequence(Value("float32"), length=action_dim),
        "observation.ee_pose": Sequence(Value("float32"), length=7),
        "observation.object_pose": Sequence(Value("float32"), length=7),
        "timestamp": Value("float64"),
        "episode_index": Value("int64"),
        "frame_index": Value("int64"),
        "done": Value("bool"),
        "language_instruction": Value("string"),
        "success": Value("bool"),
    }
    if include_images:
        feats["observation.image"] = Value("binary")
    return Features(feats)


def parse_splits(split_specs: list[str] | None, n_episodes: int) -> dict[str, range]:
    """Parse --split args like 'train:0.8 val:0.2' into episode index ranges."""
    if not split_specs:
        return {"train": range(n_episodes)}

    ratios: dict[str, float] = {}
    for spec in split_specs:
        if ":" not in spec:
            raise ValueError(f"Invalid split spec '{spec}', expected NAME:RATIO")
        name, ratio_str = spec.split(":", 1)
        ratios[name] = float(ratio_str)

    total = sum(ratios.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Split ratios must sum to 1.0, got {total:.4f}")

    result: dict[str, range] = {}
    cursor = 0
    items = list(ratios.items())
    for i, (name, ratio) in enumerate(items):
        end = n_episodes if i == len(items) - 1 else cursor + round(ratio * n_episodes)
        result[name] = range(cursor, end)
        cursor = end
    return result


# ---------------------------------------------------------------------------
# Metadata sidecar
# ---------------------------------------------------------------------------

def write_sidecar(
    output_dir: Path,
    episodes: list[dict[str, Any]],
    *,
    fps: float,
    source_dataset_dir: Path,
) -> None:
    """Write export_info.json alongside the hf_dataset for traceability."""
    first_meta = episodes[0]["metadata"]
    info = {
        "format": "hf_dataset (datasets.save_to_disk / load_from_disk)",
        "compatible_with": "ros2-arm-teleoperation-suite lerobot_recorder",
        "source_dataset": str(source_dataset_dir.resolve()),
        "source_simulator": first_meta.get("simulator", "unknown"),
        "source_robot": first_meta.get("robot", "unknown"),
        "fps": fps,
        "total_episodes": len(episodes),
        "total_frames": sum(ep["num_frames"] for ep in episodes),
        "state_dim": int(episodes[0]["states"].shape[1]),
        "action_dim": int(episodes[0]["actions"].shape[1]),
        "feature_keys": [
            "observation.state", "action", "observation.ee_pose",
            "observation.object_pose", "timestamp", "episode_index",
            "frame_index", "done", "language_instruction", "success",
        ],
        "episode_ids": [ep["metadata"]["episode_id"] for ep in episodes],
        "load_example": (
            "from datasets import load_from_disk; "
            f"ds = load_from_disk('{output_dir}/train')"
        ),
    }
    (output_dir / "export_info.json").write_text(
        json.dumps(info, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------

def export(
    dataset_dir: Path,
    output_dir: Path,
    fps: float,
    *,
    split_specs: list[str] | None = None,
    include_images: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    episode_dirs = discover_episode_dirs(dataset_dir)
    print(f"Found {len(episode_dirs)} episode(s) in {dataset_dir}")

    episodes = []
    for ep_dir in episode_dirs:
        ep = load_episode(ep_dir)
        episodes.append(ep)
        if verbose:
            meta = ep["metadata"]
            print(
                f"  {ep_dir.name}: {ep['num_frames']} frames, "
                f"state_dim={ep['states'].shape[1]}, "
                f"action_dim={ep['actions'].shape[1]}, "
                f"success={meta.get('success', 'N/A')}"
            )

    # Consistency check across episodes
    state_dim = int(episodes[0]["states"].shape[1])
    action_dim = int(episodes[0]["actions"].shape[1])
    for ep in episodes[1:]:
        if ep["states"].shape[1] != state_dim:
            raise ValueError(
                f"{ep['dir'].name}: state_dim={ep['states'].shape[1]} "
                f"differs from first episode ({state_dim})"
            )
        if ep["actions"].shape[1] != action_dim:
            raise ValueError(
                f"{ep['dir'].name}: action_dim={ep['actions'].shape[1]} "
                f"differs from first episode ({action_dim})"
            )

    features = build_features(state_dim, action_dim, include_images=include_images)
    splits = parse_splits(split_specs, len(episodes))
    print(f"Splits: { {k: f'{len(v)} episodes' for k, v in splits.items()} }")

    if dry_run:
        total = sum(ep["num_frames"] for ep in episodes)
        print(f"[dry-run] Validation passed — {len(episodes)} episodes, {total} frames total.")
        return {
            "dry_run": True,
            "total_episodes": len(episodes),
            "total_frames": total,
            "state_dim": state_dim,
            "action_dim": action_dim,
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    split_frame_counts: dict[str, int] = {}

    for split_name, ep_range in splits.items():
        split_episodes = [episodes[i] for i in ep_range]
        rows = episodes_to_rows(split_episodes, fps=fps, include_images=include_images)
        ds = Dataset.from_dict(rows, features=features)
        split_dir = output_dir / split_name
        ds.save_to_disk(str(split_dir))
        split_frame_counts[split_name] = len(ds)
        print(f"  [{split_name}] {len(ep_range)} episodes, {len(ds)} frames → {split_dir}")

    write_sidecar(output_dir, episodes, fps=fps, source_dataset_dir=dataset_dir)

    total_frames = sum(split_frame_counts.values())
    return {
        "output_dir": str(output_dir),
        "total_episodes": len(episodes),
        "total_frames": total_frames,
        "splits": split_frame_counts,
        "state_dim": state_dim,
        "action_dim": action_dim,
    }


def main() -> int:
    args = parse_args()
    output_dir = args.output or (args.dataset_dir / "hf_export")

    result = export(
        args.dataset_dir,
        output_dir,
        fps=args.fps,
        split_specs=args.split,
        include_images=args.include_images,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    if result.get("dry_run"):
        return 0

    print(
        f"\n✓ Export complete → {result['output_dir']}\n"
        f"  Episodes  : {result['total_episodes']}\n"
        f"  Frames    : {result['total_frames']}\n"
        f"  state_dim : {result['state_dim']}\n"
        f"  action_dim: {result['action_dim']}\n"
        f"\nLoad in ros2-arm-teleoperation-suite:\n"
        f"  from datasets import load_from_disk\n"
        f"  ds = load_from_disk('{output_dir}/train')\n"
        f"  print(ds[0].keys())"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
