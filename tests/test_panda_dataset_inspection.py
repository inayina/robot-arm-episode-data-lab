from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from training.scripts.inspect_dataset import inspect_dataset
from training.scripts.make_mock_panda_dataset import make_rows, write_dataset


SCHEMA_PATH = Path("configs/robot_schemas/panda.yaml")


def load_schema() -> dict:
    return yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))


def write_mock_dataset(path: Path) -> Path:
    schema = load_schema()
    rows = make_rows(
        schema,
        episodes=2,
        frames_per_episode=3,
        seed=7,
        action_type=schema["action"]["default_type"],
    )
    write_dataset(
        path,
        schema,
        rows,
        action_type=schema["action"]["default_type"],
        seed=7,
    )
    return path


def test_inspect_mock_panda_dataset_passes_with_optional_warnings(tmp_path: Path) -> None:
    dataset = write_mock_dataset(tmp_path / "panda_mock")
    report = inspect_dataset(dataset, load_schema())

    assert report.passed
    assert report.episodes == 2
    assert report.frames == 6
    assert any("observation.images.scene" in warning for warning in report.warnings)
    assert field_status(report.required, "observation.state") == "OK"
    assert field_status(report.required, "action") == "OK"


def test_inspect_dataset_fails_when_required_field_is_missing(tmp_path: Path) -> None:
    dataset = write_mock_dataset(tmp_path / "panda_bad")
    frames_path = dataset / "frames.jsonl"
    rows = [json.loads(line) for line in frames_path.read_text(encoding="utf-8").splitlines()]
    rows[0].pop("observation.state")
    frames_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    report = inspect_dataset(dataset, load_schema())

    assert not report.passed
    assert any("observation.state" in error for error in report.errors)


def test_inspect_dataset_fails_when_action_dimension_is_wrong(tmp_path: Path) -> None:
    dataset = write_mock_dataset(tmp_path / "panda_bad_action")
    frames_path = dataset / "frames.jsonl"
    rows = [json.loads(line) for line in frames_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["action"] = rows[0]["action"][:-1]
    frames_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    report = inspect_dataset(dataset, load_schema())

    assert not report.passed
    assert any("action" in error and "inconsistent shape" in error for error in report.errors)


def test_inspect_dataset_fails_when_robot_manifest_mismatches_schema(tmp_path: Path) -> None:
    dataset = write_mock_dataset(tmp_path / "wrong_robot")
    manifest_path = dataset / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["robot"] = "kuka_iiwa"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = inspect_dataset(dataset, load_schema())

    assert not report.passed
    assert any("does not match schema robot" in error for error in report.errors)


def field_status(results, key: str) -> str:
    for result in results:
        if result.key == key:
            return result.status
    raise AssertionError(f"missing field result for {key}")
