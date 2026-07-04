#!/usr/bin/env python3
"""Inspect a Panda dataset against a declared robot schema."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_SCHEMA = REPO_ROOT / "configs" / "robot_schemas" / "panda.yaml"


@dataclass
class FieldResult:
    key: str
    status: str
    expected: str
    observed: str
    message: str = ""


@dataclass
class InspectionReport:
    dataset: str
    robot: str
    schema_id: str
    action_type: str
    episodes: int
    frames: int
    required: list[FieldResult] = field(default_factory=list)
    optional: list[FieldResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "robot": self.robot,
            "schema_id": self.schema_id,
            "action_type": self.action_type,
            "episodes": self.episodes,
            "frames": self.frames,
            "required": [vars(result) for result in self.required],
            "optional": [vars(result) for result in self.optional],
            "errors": self.errors,
            "warnings": self.warnings,
            "status": "PASS" if self.passed else "FAIL",
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True, help="Dataset directory.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Robot schema YAML.")
    parser.add_argument("--json-output", type=Path, default=None, help="Optional JSON report path.")
    return parser.parse_args()


def load_schema(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_manifest(dataset: Path) -> dict[str, Any]:
    path = dataset / "manifest.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def load_rows(dataset: Path) -> list[dict[str, Any]]:
    if (dataset / "frames.jsonl").exists():
        return load_jsonl_rows(dataset / "frames.jsonl")
    if (dataset / "frames.npz").exists():
        return load_npz_rows(dataset / "frames.npz")
    return load_huggingface_rows(dataset)


def load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return rows


def load_npz_rows(path: Path) -> list[dict[str, Any]]:
    payload = np.load(path, allow_pickle=True)
    if not payload.files:
        return []
    first = np.asarray(payload[payload.files[0]])
    if first.ndim == 0:
        raise ValueError("frames.npz values must have a leading frame dimension")
    frame_count = int(first.shape[0])
    rows: list[dict[str, Any]] = []
    for index in range(frame_count):
        row: dict[str, Any] = {}
        for key in payload.files:
            value = np.asarray(payload[key])
            if value.shape[0] != frame_count:
                raise ValueError(f"frames.npz key {key!r} has inconsistent frame count")
            item = value[index]
            row[key] = item.tolist() if hasattr(item, "tolist") else item
        rows.append(row)
    return rows


def load_huggingface_rows(dataset: Path) -> list[dict[str, Any]]:
    try:
        from datasets import load_from_disk
    except ImportError as exc:
        raise FileNotFoundError(
            f"No frames.jsonl or frames.npz found under {dataset}, and "
            "HuggingFace datasets is not installed."
        ) from exc

    loaded = load_from_disk(str(dataset))
    return [dict(row) for row in loaded]


def inspect_dataset(dataset: Path, schema: dict[str, Any]) -> InspectionReport:
    manifest = load_manifest(dataset)
    rows = load_rows(dataset)
    action_type = str(manifest.get("action_type", schema["action"]["default_type"]))
    report = InspectionReport(
        dataset=str(dataset),
        robot=str(manifest.get("robot", schema["robot"])),
        schema_id=str(manifest.get("schema_id", schema["schema_id"])),
        action_type=action_type,
        episodes=count_episodes(rows),
        frames=len(rows),
    )

    if not rows:
        report.errors.append("dataset contains no frames")
        return report

    if report.robot != schema["robot"]:
        report.errors.append(f"robot={report.robot!r} does not match schema robot={schema['robot']!r}")
    if action_type not in schema["action"]:
        report.errors.append(f"action_type={action_type!r} is not declared in schema")
        action_dim = None
    else:
        action_dim = int(schema["action"][action_type]["dim"])

    add_required(report, rows, "observation.state", int(schema["observation"]["state"]["dim"]))
    add_required(report, rows, "observation.ee_pose", int(schema["observation"]["ee_pose"]["dim"]))
    if action_dim is not None:
        add_required(report, rows, "action", action_dim)
    add_required_scalar(report, rows, "timestamp")
    add_required_scalar(report, rows, "frame_index")
    add_required_scalar(report, rows, "episode_index")
    add_required_scalar(report, rows, schema["task"]["key"])

    add_optional(report, rows, "observation.object_pose", int(schema["observation"]["object_pose"]["dim"]))
    add_optional(report, rows, "observation.ft", int(schema["observation"]["ft"]["dim"]))
    for image_spec in schema["observation"]["images"].values():
        if isinstance(image_spec, dict) and "key" in image_spec:
            add_optional(report, rows, str(image_spec["key"]), tuple(image_spec["shape"]))

    for result in report.required:
        if result.status == "FAIL":
            report.errors.append(f"{result.key}: {result.message}")
    for result in report.optional:
        if result.status == "WARN":
            report.warnings.append(f"{result.key}: {result.message}")
        elif result.status == "FAIL":
            report.errors.append(f"{result.key}: {result.message}")
    return report


def count_episodes(rows: Iterable[dict[str, Any]]) -> int:
    episode_ids = {row.get("episode_index") for row in rows if "episode_index" in row}
    return len(episode_ids)


def add_required(report: InspectionReport, rows: list[dict[str, Any]], key: str, dim: int) -> None:
    report.required.append(validate_vector_field(rows, key, dim, required=True))


def add_optional(
    report: InspectionReport,
    rows: list[dict[str, Any]],
    key: str,
    expected_shape: int | tuple[int, ...],
) -> None:
    report.optional.append(validate_vector_field(rows, key, expected_shape, required=False))


def add_required_scalar(report: InspectionReport, rows: list[dict[str, Any]], key: str) -> None:
    missing = [index for index, row in enumerate(rows) if key not in row]
    if missing:
        report.required.append(
            FieldResult(key, "FAIL", "scalar", "missing", f"missing in {len(missing)} frames")
        )
        return
    report.required.append(FieldResult(key, "OK", "scalar", "scalar"))


def validate_vector_field(
    rows: list[dict[str, Any]],
    key: str,
    expected_shape: int | tuple[int, ...],
    *,
    required: bool,
) -> FieldResult:
    missing = [index for index, row in enumerate(rows) if key not in row]
    expected = format_shape(expected_shape)
    if missing:
        status = "FAIL" if required else "WARN"
        return FieldResult(key, status, expected, "missing", f"missing in {len(missing)} frames")

    observed_shapes = {shape_of(row[key]) for row in rows}
    if len(observed_shapes) != 1:
        return FieldResult(
            key,
            "FAIL",
            expected,
            ", ".join(sorted(map(str, observed_shapes))),
            "inconsistent shape across frames",
        )

    observed_shape = next(iter(observed_shapes))
    if not shape_matches(observed_shape, expected_shape):
        return FieldResult(
            key,
            "FAIL",
            expected,
            format_shape(observed_shape),
            "shape does not match schema",
        )
    return FieldResult(key, "OK", expected, format_shape(observed_shape))


def shape_of(value: Any) -> tuple[int, ...]:
    array = np.asarray(value)
    return tuple(int(dim) for dim in array.shape)


def shape_matches(observed: tuple[int, ...], expected: int | tuple[int, ...]) -> bool:
    if isinstance(expected, int):
        return observed == (expected,)
    return observed == tuple(expected)


def format_shape(shape: int | tuple[int, ...]) -> str:
    if isinstance(shape, int):
        return f"[{shape}]"
    return "[" + ", ".join(str(dim) for dim in shape) + "]"


def print_report(report: InspectionReport) -> None:
    print(f"Dataset: {report.dataset}")
    print(f"Robot: {report.robot}")
    print(f"Schema: {report.schema_id}")
    print(f"Action type: {report.action_type}")
    print(f"Episodes: {report.episodes}")
    print(f"Frames: {report.frames}")
    print()
    print("Required fields:")
    for result in report.required:
        print(f"  {result.key}: {result.status}, expected={result.expected}, observed={result.observed}")
    print()
    print("Optional fields:")
    for result in report.optional:
        print(f"  {result.key}: {result.status}, expected={result.expected}, observed={result.observed}")
    if report.errors:
        print()
        print("Errors:")
        for error in report.errors:
            print(f"  - {error}")
    if report.warnings:
        print()
        print("Warnings:")
        for warning in report.warnings:
            print(f"  - {warning}")
    print()
    print(f"Status: {'PASS' if report.passed else 'FAIL'}")


def main() -> int:
    args = parse_args()
    schema = load_schema(args.schema)
    try:
        report = inspect_dataset(args.dataset, schema)
    except Exception as exc:  # noqa: BLE001 - CLI should turn loader errors into FAIL reports.
        print(f"Dataset: {args.dataset}")
        print(f"Status: FAIL")
        print(f"Error: {exc}")
        return 1
    print_report(report)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
