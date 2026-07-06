from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from training.scripts.make_mock_panda_dataset import make_rows, write_dataset
from training.scripts.prepare_dataset_release import prepare_release
from training.scripts.train_act_smoke import train_smoke_policy


SCHEMA_PATH = Path("configs/robot_schemas/panda.yaml")


def load_schema() -> dict:
    return yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))


def write_release(path: Path, *, action_type: str = "ee_delta_gripper") -> Path:
    schema = load_schema()
    source = path / "source"
    rows = make_rows(
        schema,
        episodes=2,
        frames_per_episode=5,
        seed=7,
        action_type=action_type,
    )
    write_dataset(source, schema, rows, action_type=action_type, seed=7)
    release = path / "release"
    prepare_release(
        source,
        release,
        schema,
        release_id="panda_mock_train_v0",
    )
    return release


def test_train_smoke_policy_writes_expected_artifacts(tmp_path: Path) -> None:
    schema = load_schema()
    release = write_release(tmp_path)
    output = tmp_path / "train_out"

    metrics = train_smoke_policy(
        release,
        schema,
        output,
        seed=7,
        val_ratio=0.2,
        ridge=1e-6,
    )

    assert metrics["policy_type"] == "linear_smoke"
    assert metrics["num_frames"] == 10
    assert metrics["state_dim"] == 8
    assert metrics["action_dim"] == 7
    assert metrics["train_frames"] == 8
    assert metrics["val_frames"] == 2
    assert (output / "checkpoint.npz").exists()
    assert (output / "metrics.json").exists()
    assert (output / "normalization.json").exists()
    assert (output / "config_resolved.yaml").exists()

    persisted = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert persisted["release_id"] == "panda_mock_train_v0"


def test_train_smoke_policy_rejects_pose_gripper_action_type(tmp_path: Path) -> None:
    schema = load_schema()
    release = write_release(tmp_path, action_type="ee_pose_gripper")

    with pytest.raises(ValueError, match="requires action_type"):
        train_smoke_policy(
            release,
            schema,
            tmp_path / "train_out",
            seed=7,
            val_ratio=0.2,
            ridge=1e-6,
        )
