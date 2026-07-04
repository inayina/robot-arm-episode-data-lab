from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from training.scripts.make_mock_panda_dataset import make_rows, write_dataset
from training.scripts.prepare_dataset_release import prepare_release
from training.scripts.replay_policy import export_replay
from training.scripts.train_act_smoke import train_smoke_policy


SCHEMA_PATH = Path("configs/robot_schemas/panda.yaml")


def load_schema() -> dict:
    return yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))


def train_fixture(tmp_path: Path) -> tuple[Path, Path, dict]:
    schema = load_schema()
    source = tmp_path / "source"
    rows = make_rows(
        schema,
        episodes=2,
        frames_per_episode=5,
        seed=7,
        action_type=schema["action"]["default_type"],
    )
    write_dataset(
        source,
        schema,
        rows,
        action_type=schema["action"]["default_type"],
        seed=7,
    )
    release = tmp_path / "release"
    prepare_release(source, release, schema, release_id="panda_replay_v0")
    train_smoke_policy(
        release,
        schema,
        tmp_path / "train_out",
        seed=7,
        val_ratio=0.2,
        ridge=1e-6,
    )
    return release, tmp_path / "train_out" / "checkpoint.npz", schema


def test_export_replay_writes_neutral_jsonl(tmp_path: Path) -> None:
    release, checkpoint, schema = train_fixture(tmp_path)
    output = tmp_path / "predicted_actions.jsonl"

    summary = export_replay(release, checkpoint, schema, output)

    assert summary["num_frames"] == 10
    assert summary["action_dim"] == 7
    assert summary["action_type"] == schema["action"]["default_type"]
    lines = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 10
    first = lines[0]
    assert first["robot"] == "panda"
    assert first["schema_id"] == schema["schema_id"]
    assert first["release_id"] == "panda_replay_v0"
    assert first["action_type"] == "ee_delta_gripper"
    assert first["episode_index"] == 0
    assert first["frame_index"] == 0
    assert isinstance(first["timestamp"], float)
    assert len(first["action"]) == 7


def test_export_replay_rejects_action_type_mismatch(tmp_path: Path) -> None:
    release, checkpoint, schema = train_fixture(tmp_path)
    manifest_path = release / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["action_type"] = "ee_pose_gripper"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="action_type"):
        export_replay(release, checkpoint, schema, tmp_path / "predicted_actions.jsonl")
