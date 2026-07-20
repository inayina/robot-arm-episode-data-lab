from __future__ import annotations

import json
from pathlib import Path

import pytest

from training.scripts.compare_sim_backends import compare_datasets, render_markdown


def _write_dataset(root: Path, backend: str, offset: float, dim: int = 2) -> Path:
    root.mkdir(parents=True)
    rows = []
    for index in range(4):
        state = [float(index) + offset, float(index * 2) + offset][:dim]
        rows.append({
            "episode_index": 0,
            "frame_index": index,
            "timestamp": 10.0 + index * 0.1,
            "task": "same_task",
            "observation.state": state,
            "observation.ee_pose": [offset] * 7,
            "observation.object_pose": [offset] * 7,
            "observation.ft": [offset] * 6,
            "observation.gripper": [0.5],
            "action": [offset] * 3,
        })
    (root / "frames.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    episode = root / "episode_000000"
    episode.mkdir()
    (episode / "meta.json").write_text(json.dumps({
        "simulator_backend": backend,
        "simulator_version": "test",
        "scene_id": "same_scene",
        "action_semantics": "same_action_v1",
    }), encoding="utf-8")
    return root


def test_compare_sim_backends_reports_shift_without_calling_it_a_gate(tmp_path: Path):
    reference = _write_dataset(tmp_path / "mujoco", "mujoco", 0.0)
    candidate = _write_dataset(tmp_path / "isaac", "isaac", 1.0)

    report = compare_datasets(reference, candidate)

    assert report["status"] == "EVIDENCE_ONLY"
    assert report["reference"]["provenance"]["simulator_backend"] == ["mujoco"]
    assert report["candidate"]["provenance"]["simulator_backend"] == ["isaac"]
    state = report["field_comparisons"]["observation.state"]
    assert state["mean_shift"] == pytest.approx([1.0, 1.0])
    assert state["wasserstein_1"] == pytest.approx([1.0, 1.0])
    assert state["normalized_trajectory_rmse"] == pytest.approx([1.0, 1.0])
    assert report["comparability"]["raw_action_distribution_equal"] is False
    assert report["comparability"]["declared_scene_ids_equal"] is True
    assert "fewer than 5 episodes" in report["warnings"][0]
    assert "not evidence of real-robot" in render_markdown(report)


def test_compare_sim_backends_rejects_field_dimension_mismatch(tmp_path: Path):
    reference = _write_dataset(tmp_path / "mujoco", "mujoco", 0.0, dim=2)
    candidate = _write_dataset(tmp_path / "isaac", "isaac", 0.0, dim=1)

    with pytest.raises(ValueError, match="field dimension mismatch"):
        compare_datasets(reference, candidate)
