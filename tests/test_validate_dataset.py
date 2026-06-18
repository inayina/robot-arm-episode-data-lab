from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest
from PIL import Image

from scripts.export_lerobot_style import export_dataset
from scripts.validate_dataset import collect_dataset_summary, collect_errors, discover_episode_dirs


def write_episode(
    episode_dir: Path,
    *,
    num_steps: int = 3,
    image_width: int = 8,
    image_height: int = 6,
    task_name: str = "reach_cube",
    success: bool | None = None,
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
        "task_name": task_name,
        "num_steps": num_steps,
        "image_width": image_width,
        "image_height": image_height,
        "state_dim": 7,
        "action_dim": 7,
        "control_mode": "task_fsm" if task_name == "pick_and_lift" else "joint_position",
        "robot": "kuka_iiwa",
        "object": "cube",
        "camera": {"type": "fixed_rgb"},
    }
    if task_name == "pick_and_lift":
        metadata["language_instruction"] = "pick up the cube"
    if success is not None:
        metadata["success"] = success
        metadata["failure_reason"] = None if success else "insufficient_lift"
        metadata["object_z_lift"] = 0.05 if success else 0.0
        metadata["grasp_established"] = bool(success)
        metadata["grasp_mode"] = "constraint"
        metadata["aborted"] = not success
    (episode_dir / "metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )


def test_collect_dataset_summary_reports_success_rate(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    write_episode(dataset_dir / "episode_000001", task_name="pick_and_lift", success=True)
    write_episode(dataset_dir / "episode_000002", task_name="pick_and_lift", success=False)

    summary = collect_dataset_summary(dataset_dir)

    assert summary["episode_count"] == 2
    assert summary["success_count"] == 1
    assert summary["success_rate"] == pytest.approx(0.5)


def test_discover_episode_dirs_supports_dataset_root(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    write_episode(dataset_dir / "episode_000001")
    write_episode(dataset_dir / "episode_000002")

    discovered = discover_episode_dirs(dataset_dir)

    assert len(discovered) == 2


def test_export_lerobot_style_writes_v21_layout(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    write_episode(
        dataset_dir / "episode_000001",
        num_steps=4,
        task_name="pick_and_lift",
        success=True,
    )
    write_episode(
        dataset_dir / "episode_000002",
        num_steps=5,
        task_name="pick_and_lift",
        success=False,
    )
    output_dir = tmp_path / "lerobot_export"

    summary = export_dataset(dataset_dir, output_dir, fps=10.0)

    assert summary["total_episodes"] == 2
    assert summary["total_frames"] == 9
    assert (output_dir / "meta" / "info.json").exists()
    assert (output_dir / "meta" / "episodes.jsonl").exists()
    assert (output_dir / "meta" / "tasks.jsonl").exists()
    assert (output_dir / "data" / "chunk-000" / "episode_000000.parquet").exists()

    info = json.loads((output_dir / "meta" / "info.json").read_text(encoding="utf-8"))
    assert info["codebase_version"] == "v2.1"
    assert "observation.state" in info["features"]

    table = pq.read_table(output_dir / "data" / "chunk-000" / "episode_000000.parquet")
    assert table.num_rows == 4
    assert "observation.state" in table.column_names
    assert "action" in table.column_names
    assert "language_instruction" in table.column_names


def test_collect_errors_reports_invalid_pick_lift_evaluation(tmp_path: Path) -> None:
    episode_dir = tmp_path / "episode_bad_eval"
    write_episode(episode_dir, task_name="pick_and_lift", success=True)
    metadata_path = episode_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["grasp_established"] = False
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    errors = collect_errors(episode_dir)

    assert any("success=true requires grasp_established=true" in error for error in errors)


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
