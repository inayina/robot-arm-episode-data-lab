from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from training.scripts.make_mock_panda_dataset import make_rows, write_dataset
from training.scripts.prepare_bridge_handoff import prepare_bridge_handoff
from training.scripts.prepare_dataset_release import prepare_release
from training.scripts.replay_policy import export_replay
from training.scripts.train_act_smoke import train_smoke_policy


SCHEMA_PATH = Path("configs/robot_schemas/panda.yaml")


def load_schema() -> dict:
    return yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))


def replay_fixture(tmp_path: Path) -> tuple[Path, Path, dict]:
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
    prepare_release(source, release, schema, release_id="panda_bridge_handoff_v0")
    train_smoke_policy(
        release,
        schema,
        tmp_path / "train_out",
        seed=7,
        val_ratio=0.2,
        ridge=1e-6,
    )
    replay = tmp_path / "train_out" / "predicted_actions.jsonl"
    export_replay(release, tmp_path / "train_out" / "checkpoint.npz", schema, replay)
    return release, replay, schema


def test_prepare_bridge_handoff_writes_bundle(tmp_path: Path) -> None:
    release, replay, schema = replay_fixture(tmp_path)
    output = tmp_path / "handoff"

    manifest = prepare_bridge_handoff(
        release,
        replay,
        schema,
        output,
        handoff_id="panda_bridge_smoke",
    )

    assert manifest["handoff_format"] == "panda_bridge_handoff_v0"
    assert manifest["handoff_id"] == "panda_bridge_smoke"
    assert manifest["consumer_repo"] == "ros2-moveit-pybullet-bridge"
    assert manifest["schema_id"] == schema["schema_id"]
    assert manifest["action_type"] == "ee_delta_gripper"
    assert manifest["action_dim"] == 7
    assert manifest["frames"] == 10
    assert (output / "predicted_actions.jsonl").exists()
    assert (output / "dataset_manifest.json").exists()
    assert (output / "dataset_inspection_report.json").exists()
    assert (output / "replay_check.json").exists()
    assert (output / "handoff_manifest.json").exists()

    check = json.loads((output / "replay_check.json").read_text(encoding="utf-8"))
    assert check["status"] == "PASS"
    assert len(check["action_min"]) == 7
    assert len(check["action_max"]) == 7


def test_prepare_bridge_handoff_rejects_bad_action_dim(tmp_path: Path) -> None:
    release, replay, schema = replay_fixture(tmp_path)
    rows = [json.loads(line) for line in replay.read_text(encoding="utf-8").splitlines()]
    rows[0]["action"] = rows[0]["action"][:-1]
    replay.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="handoff check failed"):
        prepare_bridge_handoff(release, replay, schema, tmp_path / "handoff")
