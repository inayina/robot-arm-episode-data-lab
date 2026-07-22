from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from evaluation.vla_contract import (
    CANONICAL_DIM,
    AbsoluteEefExportError,
    action_active_mask,
    apply_norm,
    compute_active_norm_stats,
    export_frame,
    export_frames,
    normalize_xyzw,
    pack_action55,
    pack_state55,
    quat_angular_error_rad,
    state_active_mask,
    write_frames_jsonl,
)
from training.adapters.upstream_m6 import adapt_rows
import yaml


SCHEMA_DIR = Path("evaluation/schemas")
EXAMPLE_DIR = Path("evaluation/examples")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validator(name: str) -> Draft202012Validator:
    schema = load_json(SCHEMA_DIR / name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def upstream_rows() -> list[dict]:
    path = EXAMPLE_DIR / "absolute_eef_upstream_rows_fixture.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_normalize_xyzw_and_angular_error() -> None:
    q = normalize_xyzw([0.0, 0.0, 0.0, 2.0])
    assert q == pytest.approx([0.0, 0.0, 0.0, 1.0])
    # 180 deg about z: [0,0,1,0] vs identity
    err = quat_angular_error_rad([0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0])
    assert err == pytest.approx(math.pi, rel=1e-6)
    with pytest.raises(AbsoluteEefExportError):
        normalize_xyzw([0.0, 0.0, 0.0, 0.0])


def test_export_rejects_delta_action() -> None:
    row = upstream_rows()[0]
    # Derived delta shape must be refused.
    row = dict(row)
    row["action"] = [0.01, 0.0, 0.02, 0.0, 0.0, 0.0, 0.5]
    with pytest.raises(AbsoluteEefExportError, match="ee_delta_gripper"):
        export_frame(row)


def test_export_absolute_eef_frames_pad_and_masks() -> None:
    frames = export_frames(upstream_rows())
    assert len(frames) == 3
    frame = frames[0]
    assert frame["claims_task_success"] is False
    assert frame["policy_action_semantics"] == "absolute_eef_gripper_v0"
    assert len(frame["state55"]) == CANONICAL_DIM
    assert len(frame["action55"]) == CANONICAL_DIM

    state = np.asarray(frame["state55"])
    action = np.asarray(frame["action55"])
    s_mask = state_active_mask()
    a_mask = action_active_mask()
    assert np.allclose(state[~s_mask], 0.0)
    assert np.allclose(action[~a_mask], 0.0)
    # Measured vs command must differ on first fixture row (0.9 vs 0.85).
    assert frame["state_active"]["gripper_measured"] == pytest.approx(0.9)
    assert frame["action_active"]["gripper_cmd"] == pytest.approx(0.85)
    assert frame["padding_anomaly"]["action_pad_l2"] == pytest.approx(0.0)


def test_export_from_adapted_pose_gripper_rows() -> None:
    schema = yaml.safe_load(Path("configs/robot_schemas/panda.yaml").read_text())
    adapted, action_type = adapt_rows(upstream_rows(), schema, derive_ee_delta_action=False)
    assert action_type == "ee_pose_gripper"
    frames = export_frames(adapted)
    assert frames[0]["action_active"]["ee_target_xyz"][0] == pytest.approx(0.41)


def test_norm_ignores_padding_dims() -> None:
    frames = export_frames(upstream_rows())
    actions = [f["action55"] for f in frames]
    mask = action_active_mask()
    stats = compute_active_norm_stats(actions, mask)
    mean = np.asarray(stats["mean"])
    std = np.asarray(stats["std"])
    # Pad dims stay sentinel mean=0 std=1
    assert np.allclose(mean[~mask], 0.0)
    assert np.allclose(std[~mask], 1.0)
    # Active dims: std is positive finite
    assert np.all(std[mask] >= 1e-6)
    normalized = apply_norm(actions[0], stats["mean"], stats["std"], mask)
    assert np.allclose(np.asarray(normalized)[~mask], 0.0)


def test_write_and_roundtrip_jsonl(tmp_path: Path) -> None:
    out = tmp_path / "absolute_eef.jsonl"
    frames = export_frames(upstream_rows())
    write_frames_jsonl(out, frames)
    loaded = [
        json.loads(line)
        for line in out.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(loaded) == 3
    assert loaded[1]["frame_index"] == 1


def test_open_loop_report_schema_forbids_task_and_delta_mix() -> None:
    payload = load_json(EXAMPLE_DIR / "vla_open_loop_report_fixture.json")
    validator("vla_open_loop_report.schema.json").validate(payload)
    assert payload["claims_task_success"] is False
    assert payload["forbids_act_delta_mixed_table"] is True
    assert "act_ee_delta_l1" in payload["prohibited_fields"]

    payload["claims_task_success"] = True
    with pytest.raises(ValidationError):
        validator("vla_open_loop_report.schema.json").validate(payload)

    bad = load_json(EXAMPLE_DIR / "vla_open_loop_report_fixture.json")
    bad["forbids_act_delta_mixed_table"] = False
    with pytest.raises(ValidationError):
        validator("vla_open_loop_report.schema.json").validate(bad)


def test_open_loop_report_rejects_extra_act_delta_field() -> None:
    payload = load_json(EXAMPLE_DIR / "vla_open_loop_report_fixture.json")
    # additionalProperties false on root — injecting ACT delta field must fail.
    payload["act_ee_delta_rmse"] = 0.01
    with pytest.raises(ValidationError):
        validator("vla_open_loop_report.schema.json").validate(payload)


def test_pack_helpers_match_export() -> None:
    row = upstream_rows()[0]
    assert pack_state55(row) == export_frame(row)["state55"]
    assert pack_action55(row) == export_frame(row)["action55"]
