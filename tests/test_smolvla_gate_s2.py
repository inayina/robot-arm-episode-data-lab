"""Unit tests for SmolVLA Gate S2 open-loop packaging (no GPU / no Hub)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from evaluation.vla_contract.smolvla_panda_s2 import (
    MAPPING_HYPOTHESIS,
    aggregate_open_loop_metrics,
    build_open_loop_report,
    frame_errors,
    h3_semantic_status,
    map_libero6_to_abs_channels,
    panda_state6_from_row,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "evaluation" / "schemas" / "vla_open_loop_report.schema.json"


def test_map_libero6_hypothesis() -> None:
    mapped = map_libero6_to_abs_channels([0.1, 0.2, 0.3, 9.0, -1.0, 1.5])
    assert mapped["mapping_hypothesis"] == MAPPING_HYPOTHESIS
    assert mapped["ee_target_xyz"] == [0.1, 0.2, 0.3]
    assert mapped["ee_target_xyzw"] is None
    assert mapped["gripper_cmd"] == 1.0  # clipped


def test_frame_errors_and_h3_nogo() -> None:
    mapped = map_libero6_to_abs_channels([1.0, 1.0, 1.0, 0, 0, 0.0])
    expert = [0.4, 0.1, 0.05, 1, 0, 0, 0, 0.0]
    errs = frame_errors(mapped, expert)
    assert errs["ee_position_l2_m"] > 0.5
    assert errs["quaternion_angular_error_rad"] is None
    metrics = aggregate_open_loop_metrics(
        [{**errs, "pred_xyz": mapped["ee_target_xyz"]}],
        [100.0, 110.0],
    )
    assert h3_semantic_status(metrics) == "no_go"
    report = build_open_loop_report(metrics, notes="unit")
    assert report["claims_task_success"] is False
    assert report["forbids_act_delta_mixed_table"] is True


def test_open_loop_report_validates_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    mapped = map_libero6_to_abs_channels([0.42, 0.11, 0.04, 0, 0, 0.0])
    expert = [0.42, 0.11, 0.04, 1, 0, 0, 0, 0.0]
    errs = frame_errors(mapped, expert)
    metrics = aggregate_open_loop_metrics([{**errs, "pred_xyz": mapped["ee_target_xyz"]}], [50.0])
    report = build_open_loop_report(metrics, notes="schema unit")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(instance=report, schema=schema)


def test_panda_state6_mapping() -> None:
    row = {
        "observation.ee_pose": [0.4, 0.1, 0.05, 1, 0, 0, 0],
        "observation.state": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
    }
    s = panda_state6_from_row(row)
    assert s.shape == (6,)
    np.testing.assert_allclose(s[:3], [0.4, 0.1, 0.05])
    np.testing.assert_allclose(s[3:], [0.1, 0.2, 0.3])


def test_rejects_delta7_expert() -> None:
    from evaluation.vla_contract.smolvla_panda_s2 import expert_absolute_action8

    with pytest.raises(ValueError, match="ee_delta"):
        expert_absolute_action8({"action": [0.0] * 7})
