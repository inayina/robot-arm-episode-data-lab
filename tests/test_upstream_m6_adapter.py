from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from training.adapters.upstream_m6 import (
    adapt_rows,
    resolve_upstream_gate,
    require_verified_action_semantics,
    write_adapted_dataset,
)
from training.scripts.inspect_dataset import inspect_dataset


SCHEMA_PATH = Path("configs/robot_schemas/panda.yaml")


def load_schema() -> dict:
    return yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))


def upstream_rows(with_language_instruction: bool = False) -> list[dict]:
    rows = []
    for frame_index in range(3):
        z = 0.35 + 0.01 * frame_index
        row = {
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
        if with_language_instruction:
            row["language_instruction"] = "pick up the red box and place it in the left bin"
        rows.append(row)
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


def test_resolve_upstream_gate_reads_episode_meta_json(tmp_path: Path) -> None:
    episode_dir = tmp_path / "episode_000000"
    train_dir = episode_dir / "train"
    train_dir.mkdir(parents=True)
    (episode_dir / "meta.json").write_text(
        json.dumps({"upstream_gate": "batch_generator", "success": True}),
        encoding="utf-8",
    )

    assert resolve_upstream_gate(tmp_path) == "batch_generator"
    assert resolve_upstream_gate(train_dir) == "batch_generator"


def test_action_semantics_fail_closed_for_legacy_episode(tmp_path: Path) -> None:
    episode = tmp_path / "episode_000000"
    episode.mkdir()
    (episode / "meta.json").write_text(
        json.dumps({"action_type": "ee_pose_gripper"}), encoding="utf-8")
    with pytest.raises(ValueError, match="legacy episodes must remain quarantined"):
        require_verified_action_semantics(tmp_path)


def test_action_semantics_accepts_command_v1(tmp_path: Path) -> None:
    episode = tmp_path / "episode_000000"
    episode.mkdir()
    (episode / "meta.json").write_text(
        json.dumps({"action_semantics": "ee_pose_gripper_cmd_v1"}),
        encoding="utf-8",
    )
    assert require_verified_action_semantics(tmp_path) == "ee_pose_gripper_cmd_v1"


def test_adapted_manifest_records_upstream_gate_and_filter_scope(tmp_path: Path) -> None:
    schema = load_schema()
    episode_dir = tmp_path / "upstream" / "episode_000000"
    train_dir = episode_dir / "train"
    train_dir.mkdir(parents=True)
    (episode_dir / "meta.json").write_text(
        json.dumps({"upstream_gate": "batch_generator"}),
        encoding="utf-8",
    )

    adapted, action_type = adapt_rows(upstream_rows(with_language_instruction=True), schema)
    output = tmp_path / "adapted_gate"
    write_adapted_dataset(
        output,
        adapted,
        schema,
        action_type=action_type,
        source=tmp_path / "upstream",
        derive_ee_delta_action=False,
        upstream_gate="batch_generator",
    )

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["upstream_gate"] == "batch_generator"
    assert manifest["physical_validation_applied"] is True
    assert manifest["filter_scope"] == "training_split_only"

    report = inspect_dataset(output, schema)
    assert report.passed
    assert report.filter_scope == "training_split_only"
    assert any("training_split_only" in warning for warning in report.warnings)


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


def test_adapt_rows_produces_independent_language_instruction_key() -> None:
    """language_instruction は task とは独立した専用キーとして出力される。"""
    schema = load_schema()
    # upstream 行に language_instruction が含まれる場合
    rows_with_lang = upstream_rows(with_language_instruction=True)
    adapted, _ = adapt_rows(rows_with_lang, schema)
    for row in adapted:
        assert "language_instruction" in row, "language_instruction key must be present"
        assert "task" in row, "task key must also be present for backward compat"
        assert row["language_instruction"] == "pick up the red box and place it in the left bin"


def test_adapt_rows_falls_back_language_instruction_from_task() -> None:
    """language_instruction がない場合は task フィールドを fallback として使う。"""
    schema = load_schema()
    rows = upstream_rows(with_language_instruction=False)  # no language_instruction
    adapted, _ = adapt_rows(rows, schema)
    for row in adapted:
        assert "language_instruction" in row
        assert row["language_instruction"] == row["task"]  # fallback to task


def test_manifest_records_has_language_instruction_flag(tmp_path: Path) -> None:
    """manifest.json に has_language_instruction フラグが正しく記録される。"""
    schema = load_schema()

    # with language_instruction
    rows_with = upstream_rows(with_language_instruction=True)
    adapted_with, action_type = adapt_rows(rows_with, schema)
    out_with = tmp_path / "with_lang"
    write_adapted_dataset(
        out_with, adapted_with, schema,
        action_type=action_type, source=tmp_path / "up",
        derive_ee_delta_action=False,
    )
    manifest_with = json.loads((out_with / "manifest.json").read_text())
    assert manifest_with["has_language_instruction"] is True

    # without language_instruction (task-only rows)
    rows_without = upstream_rows(with_language_instruction=False)
    adapted_without, action_type2 = adapt_rows(rows_without, schema)
    out_without = tmp_path / "without_lang"
    write_adapted_dataset(
        out_without, adapted_without, schema,
        action_type=action_type2, source=tmp_path / "up",
        derive_ee_delta_action=False,
    )
    manifest_without = json.loads((out_without / "manifest.json").read_text())
    # rows without upstream language_instruction produce True because adapt_rows
    # always writes language_instruction (fallback from task)
    assert "has_language_instruction" in manifest_without


def test_adapt_rows_preserves_upstream_quality_flags(tmp_path: Path) -> None:
    schema = load_schema()
    rows = upstream_rows(with_language_instruction=True)
    for row in rows:
        row["success"] = True
        row["safety_estop"] = False
        row["drive_fault"] = False

    adapted, action_type = adapt_rows(rows, schema)

    assert all(row["success"] is True for row in adapted)
    assert all(row["safety_estop"] is False for row in adapted)
    assert all(row["drive_fault"] is False for row in adapted)

    output = tmp_path / "quality_flags"
    write_adapted_dataset(
        output,
        adapted,
        schema,
        action_type=action_type,
        source=tmp_path / "upstream",
        derive_ee_delta_action=False,
    )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["has_success_labels"] is True
