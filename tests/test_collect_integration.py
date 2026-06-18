"""Headless integration tests for collection, batch export, and validation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pybullet = pytest.importorskip("pybullet")

from core.collect_config import CollectSettings, camera_from_mapping
from core.world import connect, disconnect
from scripts.collect_episode import collect_pick_and_lift
from scripts.export_lerobot_style import export_dataset
from scripts.validate_dataset import collect_errors, discover_episode_dirs


def _pick_lift_settings(output_dir: Path, *, num_steps: int = 40) -> CollectSettings:
    camera = camera_from_mapping(64, 48, None)
    return CollectSettings(
        mode="episode",
        output=output_dir,
        num_steps=num_steps,
        width=64,
        height=48,
        gui=False,
        seed=7,
        simulator="pybullet",
        task_name="pick_and_lift",
        robot="kuka_iiwa",
        object_name="cube",
        control_mode="task_fsm",
        camera=camera,
        config_path=None,
        planner="cartesian",
    )


def test_collect_pick_and_lift_writes_valid_episode(tmp_path: Path) -> None:
    episode_dir = tmp_path / "episode_pick_ci"
    settings = _pick_lift_settings(episode_dir)

    client_id = connect(False)
    try:
        evaluation = collect_pick_and_lift(
            episode_dir,
            settings.num_steps,
            settings.camera,
            settings.gui,
            settings,
        )
    finally:
        disconnect(client_id)

    metadata = json.loads((episode_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["task_name"] == "pick_and_lift"
    assert metadata["control_mode"] == "task_fsm"
    assert metadata["grasp_mode"] == "constraint"
    assert metadata["grasp_established"] is True
    assert metadata["success"] is evaluation.success
    assert metadata["aborted"] is evaluation.aborted
    assert metadata["language_instruction"] == "pick up the cube"
    assert collect_errors(episode_dir) == []
    assert evaluation.success is True


def test_batch_collect_smoke(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "batch_smoke"
    command = [
        sys.executable,
        "scripts/batch_collect.py",
        "--output",
        str(dataset_dir),
        "--num-episodes",
        "2",
        "--num-steps",
        "40",
        "--seed",
        "99",
    ]
    result = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    assert (dataset_dir / "README.md").exists()
    assert (dataset_dir / "episode_000001" / "metadata.json").exists()
    assert (dataset_dir / "episode_000002" / "metadata.json").exists()
    for episode_dir in discover_episode_dirs(dataset_dir):
        assert collect_errors(episode_dir) == []


def test_batch_collect_and_export_lerobot_smoke(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "batch_export"
    command = [
        sys.executable,
        "scripts/batch_collect.py",
        "--output",
        str(dataset_dir),
        "--num-episodes",
        "2",
        "--num-steps",
        "40",
        "--seed",
        "101",
    ]
    result = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    export_dir = tmp_path / "lerobot_export"
    summary = export_dataset(dataset_dir, export_dir, fps=10.0)

    assert summary["total_episodes"] == 2
    assert (export_dir / "meta" / "info.json").exists()
    assert (export_dir / "data" / "chunk-000" / "episode_000000.parquet").exists()
