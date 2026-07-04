from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from training.adapters.upstream_m6 import adapt_rows
from training.scripts.inspect_dataset import inspect_dataset
from training.adapters.upstream_m6 import write_adapted_dataset


SCHEMA_PATH = Path("configs/robot_schemas/panda.yaml")


def load_schema() -> dict:
    return yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))


def upstream_rows() -> list[dict]:
    rows = []
    for frame_index in range(3):
        z = 0.35 + 0.01 * frame_index
        rows.append(
            {
                "observation.state": [0.1 * i for i in range(7)],
                "observation.gripper": [0.8 - 0.1 * frame_index],
                "observation.ee_pose": [0.4, 0.0, z, 0.0, 0.0, 0.0, 1.0],
                "observation.ft": [0.0] * 6,
                "action": [0.41, 0.0, z + 0.02, 0.0, 0.0, 0.0, 1.0, 0.5],
                "timestamp": frame_index / 30.0,
                "frame_index": frame_index,
                "episode_index": 0,
                "task": "upstream_mock",
            }
        )
    return rows


def test_adapt_upstream_rows_preserves_pose_gripper_action_by_default(tmp_path: Path) -> None:
    schema = load_schema()
    adapted, action_type = adapt_rows(upstream_rows(), schema)

    assert action_type == "ee_pose_gripper"
    assert len(adapted[0]["observation.state"]) == 8
    assert adapted[0]["observation.state"][-1] == pytest.approx(0.8)
    assert len(adapted[0]["action"]) == 8

    output = tmp_path / "adapted"
    write_adapted_dataset(
        output,
        adapted,
        schema,
        action_type=action_type,
        source=tmp_path / "upstream",
        derive_ee_delta_action=False,
    )
    report = inspect_dataset(output, schema)
    assert report.passed
    assert report.action_type == "ee_pose_gripper"


def test_adapt_upstream_rows_can_derive_ee_delta_action(tmp_path: Path) -> None:
    schema = load_schema()
    adapted, action_type = adapt_rows(
        upstream_rows(),
        schema,
        derive_ee_delta_action=True,
    )

    assert action_type == "ee_delta_gripper"
    assert len(adapted[0]["action"]) == 7
    assert adapted[0]["action"][:3] == pytest.approx([0.01, 0.0, 0.02], abs=1e-6)
    assert adapted[0]["action"][3:6] == pytest.approx([0.0, 0.0, 0.0], abs=1e-6)
    assert adapted[0]["action"][-1] == pytest.approx(0.5)

    output = tmp_path / "adapted_delta"
    write_adapted_dataset(
        output,
        adapted,
        schema,
        action_type=action_type,
        source=tmp_path / "upstream",
        derive_ee_delta_action=True,
    )
    report = inspect_dataset(output, schema)
    assert report.passed
    assert report.action_type == "ee_delta_gripper"


def test_adapt_upstream_rows_rejects_missing_gripper_for_state7() -> None:
    schema = load_schema()
    rows = upstream_rows()
    rows[0].pop("observation.gripper")

    with pytest.raises(ValueError, match="observation.gripper"):
        adapt_rows(rows, schema)


def test_adapted_manifest_records_source_and_action_type(tmp_path: Path) -> None:
    schema = load_schema()
    adapted, action_type = adapt_rows(upstream_rows(), schema)
    output = tmp_path / "manifest_check"
    write_adapted_dataset(
        output,
        adapted,
        schema,
        action_type=action_type,
        source=tmp_path / "upstream",
        derive_ee_delta_action=False,
    )

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"] == "ros2-arm-teleoperation-suite"
    assert manifest["action_type"] == "ee_pose_gripper"
    assert manifest["source_action_type"] == "ee_pose_gripper"
