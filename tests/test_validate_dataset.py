from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.validate_dataset import collect_errors


def write_episode(
    episode_dir: Path,
    *,
    num_steps: int = 3,
    image_width: int = 8,
    image_height: int = 6,
) -> None:
    images_dir = episode_dir / "images"
    images_dir.mkdir(parents=True)

    for step in range(num_steps):
        image = Image.new("RGB", (image_width, image_height), color=(step, 20, 40))
        image.save(images_dir / f"{step:06d}.png")

    np.save(episode_dir / "states.npy", np.zeros((num_steps, 7), dtype=np.float32))
    np.save(episode_dir / "actions.npy", np.ones((num_steps, 7), dtype=np.float32))
    np.save(episode_dir / "ee_poses.npy", np.zeros((num_steps, 7), dtype=np.float32))
    np.save(episode_dir / "object_poses.npy", np.zeros((num_steps, 7), dtype=np.float32))

    metadata = {
        "episode_id": episode_dir.name,
        "simulator": "pybullet",
        "task_name": "reach_cube",
        "num_steps": num_steps,
        "image_width": image_width,
        "image_height": image_height,
        "state_dim": 7,
        "action_dim": 7,
        "control_mode": "joint_position",
        "robot": "kuka_iiwa",
        "object": "cube",
        "camera": {"type": "fixed_rgb"},
    }
    (episode_dir / "metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )


def test_collect_errors_accepts_valid_episode(tmp_path: Path) -> None:
    episode_dir = tmp_path / "episode_000001"
    write_episode(episode_dir)

    assert collect_errors(episode_dir) == []


def test_collect_errors_reports_frame_and_metadata_mismatches(tmp_path: Path) -> None:
    episode_dir = tmp_path / "episode_000002"
    write_episode(episode_dir, num_steps=3)

    (episode_dir / "images" / "000001.png").unlink()
    metadata_path = episode_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["image_width"] = 99
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    errors = collect_errors(episode_dir)

    assert any("image frames must be continuous" in error for error in errors)
    assert any("metadata image_width=99" in error for error in errors)
    assert any("states.npy has 3 rows but images/ has 2 frames" in error for error in errors)
