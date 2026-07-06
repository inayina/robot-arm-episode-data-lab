from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from training.scripts.make_mock_panda_dataset import make_rows, write_dataset
from training.scripts.prepare_dataset_release import prepare_release


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


def test_train_mlp_policy_executes_successfully(tmp_path: Path) -> None:
    pytest.importorskip("torch")
    from training.scripts.train_mlp_policy import main as mlp_train_main

    release = write_release(tmp_path)
    output = tmp_path / "train_out"

    # Use sys.argv simulation to run main
    import sys
    orig_argv = sys.argv
    sys.argv = [
        "train_mlp_policy.py",
        "--dataset", str(release),
        "--output", str(output),
        "--epochs", "2",
        "--batch-size", "4",
        "--lr", "0.01"
    ]
    try:
        exit_code = mlp_train_main()
        assert exit_code == 0
        assert (output / "mlp_policy.pth").exists()
        assert (output / "mlp_metrics.json").exists()
        metrics = json.loads((output / "mlp_metrics.json").read_text(encoding="utf-8"))
        assert metrics["policy_type"] == "mlp_bc"
        assert metrics["state_dim"] == 8
        assert metrics["action_dim"] == 7
    finally:
        sys.argv = orig_argv
