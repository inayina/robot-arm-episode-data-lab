from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from training.scripts.evaluate_policy import evaluate_policy
from training.scripts.make_mock_panda_dataset import make_rows, write_dataset
from training.scripts.prepare_dataset_release import prepare_release
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
    for row in rows:
        row["success"] = row["episode_index"] == 0
    write_dataset(
        source,
        schema,
        rows,
        action_type=schema["action"]["default_type"],
        seed=7,
    )
    release = tmp_path / "release"
    prepare_release(source, release, schema, release_id="panda_eval_v0")
    train_smoke_policy(
        release,
        schema,
        tmp_path / "train_out",
        seed=7,
        val_ratio=0.2,
        ridge=1e-6,
    )
    return release, tmp_path / "train_out" / "checkpoint.npz", schema


def test_evaluate_policy_writes_eval_json(tmp_path: Path) -> None:
    release, checkpoint, schema = train_fixture(tmp_path)
    output = tmp_path / "eval.json"

    result = evaluate_policy(release, checkpoint, schema, output)

    assert result["policy_type"] == "linear_smoke"
    assert result["num_frames"] == 10
    assert result["state_dim"] == 8
    assert result["action_dim"] == 7
    assert result["release_id"] == "panda_eval_v0"
    assert result["mean_absolute_action_error"] >= 0.0
    assert result["rmse_action_error"] >= 0.0
    assert len(result["per_dim_mean_absolute_action_error"]) == 7
    assert result["smoothness_proxy"]["mean_l2_delta"] >= 0.0
    assert result["success_summary"]["labeled_episodes"] == 2
    assert output.exists()

    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["release_id"] == "panda_eval_v0"


def test_evaluate_policy_rejects_action_type_mismatch(tmp_path: Path) -> None:
    release, checkpoint, schema = train_fixture(tmp_path)
    manifest_path = release / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["action_type"] = "ee_pose_gripper"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="action_type"):
        evaluate_policy(release, checkpoint, schema, tmp_path / "eval.json")
