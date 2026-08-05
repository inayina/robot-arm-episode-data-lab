"""Tests for materializing train frame phases from upstream capture metadata."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from training.scripts.materialize_train_phase_annotations import materialize_rows


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_materialize_rows_from_episode_meta(tmp_path: Path) -> None:
    source = tmp_path / "source"
    release = tmp_path / "release"
    episode_id = "source/episode_000000"
    _write_json(
        source / "episode_000000" / "meta.json",
        {
            "metadata": {
                "task_phase_source": "upstream_continuous_task_evaluator",
                "task_phase_semantics": "continuous_gt_achieved_subgoal_frontier",
                "task_phases": ["HOVER", "DESCEND", "CLOSE"],
            }
        },
    )
    _write_json(release / "splits.json", {"train": [episode_id]})
    (release / "episode_index.jsonl").write_text(
        json.dumps(
            {
                "episode_id": episode_id,
                "source_root": str(source),
                "parquet_path": str(source / "missing.parquet"),
                "num_frames": 3,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    rows = materialize_rows(release)
    assert [row["phase"] for row in rows] == ["HOVER", "DESCEND", "CLOSE"]
    assert all(row["claims_task_success"] is False for row in rows)


def test_materialize_rows_rejects_unavailable_by_default(tmp_path: Path) -> None:
    source = tmp_path / "source"
    release = tmp_path / "release"
    episode_id = "source/episode_000000"
    _write_json(
        source / "episode_000000" / "meta.json",
        {"metadata": {"task_phases": ["HOVER", "UNAVAILABLE"]}},
    )
    _write_json(release / "splits.json", {"train": [episode_id]})
    (release / "episode_index.jsonl").write_text(
        json.dumps(
            {
                "episode_id": episode_id,
                "source_root": str(source),
                "parquet_path": str(source / "missing.parquet"),
                "num_frames": 2,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="UNAVAILABLE"):
        materialize_rows(release)
