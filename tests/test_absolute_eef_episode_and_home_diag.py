from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.diagnostics.home_no_close import (
    build_report,
    histogram,
    label_stage,
    parse_deploy_n_action_steps,
    summarize_actions,
)
from evaluation.vla_contract.absolute_eef import (
    AbsoluteEefExportError,
    export_frames,
    gripper_cmd_vs_measured,
    load_rows_from_parquet,
)


EXAMPLE_DIR = Path("evaluation/examples")
EPISODE_PARQUET = Path(
    "/home/ina/dev/ros2-arm-teleoperation-suite/"
    "data/e2_red_500hz_seed52_closelift5_20260720/"
    "data/chunk-000/episode_000000.parquet"
)
EVIDENCE_DIR = Path("evidence/e3p6_closelift40_5seed_home_20260720")
RELEASE_FRAMES = Path(
    "data/releases/e2_500hz_random35_closelift_20260720/frames.jsonl"
)


def test_gripper_split_cmd_neq_measured_on_fixture() -> None:
    rows = [
        json.loads(line)
        for line in (EXAMPLE_DIR / "absolute_eef_upstream_rows_fixture.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    split = gripper_cmd_vs_measured(rows[0])
    assert split["cmd_neq_measured"] is True
    frames = export_frames(rows)
    assert frames[0]["gripper_split"]["cmd_neq_measured"] is True


@pytest.mark.skipif(not EPISODE_PARQUET.is_file(), reason="upstream parquet absent")
def test_export_from_real_upstream_parquet_sample() -> None:
    rows = load_rows_from_parquet(
        EPISODE_PARQUET,
        max_frames=5,
        prefer_cmd_neq_measured=True,
    )
    assert len(rows) == 5
    for row in rows:
        assert len(row["action"]) == 8
    frames = export_frames(rows)
    assert all(f["claims_task_success"] is False for f in frames)
    assert all(f["quaternion_order"] == "xyzw" for f in frames)
    assert any(f["gripper_split"]["cmd_neq_measured"] for f in frames)
    # Pad dims remain zero.
    assert frames[0]["padding_anomaly"]["action_pad_l2"] == pytest.approx(0.0)


@pytest.mark.skipif(not EPISODE_PARQUET.is_file(), reason="upstream parquet absent")
def test_parquet_rejects_missing_required_via_export_path(tmp_path: Path) -> None:
    # Soft check: loading empty max_frames yields empty list, export stays empty.
    rows = load_rows_from_parquet(EPISODE_PARQUET, max_frames=0)
    assert rows == []
    assert export_frames(rows) == []


def test_home_no_close_stage_and_histogram() -> None:
    assert label_stage(1.0) == "home_like"
    assert label_stage(0.4) == "close_like"
    assert label_stage(0.8) == "transition"
    hist = histogram([0.0, 0.5, 1.0], edges=[0.0, 0.5, 1.01])
    assert hist["counts"] == [1, 2]


def test_home_no_close_summarize_and_parse_log() -> None:
    rows = [
        {"action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]},
        {"action": [0.02, 0.0, 0.01, 0.0, 0.0, 0.0, 0.4]},
    ]
    summary = summarize_actions(rows)
    assert summary["stage_counts"]["home_like"] == 1
    assert summary["stage_counts"]["close_like"] == 1
    parsed = parse_deploy_n_action_steps(
        "[INFO] ACT deploy n_action_steps=8 (chunk_size=50)\n"
    )
    assert parsed == [{"deploy_n_action_steps": 8, "chunk_size": 50}]


@pytest.mark.skipif(
    not (RELEASE_FRAMES.is_file() and EVIDENCE_DIR.is_dir()),
    reason="release/evidence absent",
)
def test_home_no_close_report_from_release_and_evidence(tmp_path: Path) -> None:
    report = build_report(
        frames_path=RELEASE_FRAMES,
        evidence_dir=EVIDENCE_DIR,
        max_frames=2000,
    )
    assert report["claims_task_success"] is False
    assert report["frame_count"] > 0
    pairs = report["deploy_n_action_steps"]["unique_pairs"]
    assert pairs
    assert pairs[0]["deploy_n_action_steps"] == 8
    assert pairs[0]["chunk_size"] == 50
    out = tmp_path / "home_no_close.json"
    out.write_text(json.dumps(report), encoding="utf-8")
    assert out.is_file()


def test_checked_in_episode_sample_fixture_if_present() -> None:
    sample = EXAMPLE_DIR / "absolute_eef_from_episode52_sample.jsonl"
    assert sample.is_file()
    frames = [
        json.loads(line)
        for line in sample.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(frames) >= 3
    assert any(f["gripper_split"]["cmd_neq_measured"] for f in frames)
    assert all(f["claims_task_success"] is False for f in frames)
    assert all(len(f["action55"]) == 55 for f in frames)
    with pytest.raises(AbsoluteEefExportError, match="ee_delta_gripper"):
        from evaluation.vla_contract.absolute_eef import export_frame

        export_frame(
            {
                "observation.state": [0.0] * 8,
                "action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            }
        )