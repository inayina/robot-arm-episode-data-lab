"""Synthetic metric and schema tests for RA-WP2."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
import numpy as np
import pytest

from evaluation.closed_loop_shift import (
    NormStats,
    analyze_closed_loop_shift,
    bootstrap_median_ci,
    energy_distance,
    progress_bin_indices,
    wasserstein_1d,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "evaluation/schemas/closed_loop_shift_report.schema.json"
FROZEN_REPORT = ROOT / "evidence/closed_loop_shift_v1/report.json"


def _stats() -> NormStats:
    return NormStats.from_sequences([0.0] * 15, [1.0] * 15, [f"s{i}" for i in range(15)])


def test_wasserstein_and_energy_detect_known_shift() -> None:
    base = np.linspace(-1.0, 1.0, 100)
    shifted = base + 2.0
    assert wasserstein_1d(base, base) == pytest.approx(0.0, abs=1e-12)
    assert wasserstein_1d(base, shifted) == pytest.approx(2.0, rel=1e-3)
    matrix = np.column_stack([base, base])
    assert energy_distance(matrix, matrix) == pytest.approx(0.0, abs=1e-12)
    assert energy_distance(matrix, matrix + 2.0) > 1.0


def test_progress_bins_cover_episode_once_in_order() -> None:
    bins = progress_bin_indices(60)
    assert bins.tolist() == [index for index in range(6) for _ in range(10)]
    assert progress_bin_indices(61)[-1] == 5


def test_episode_bootstrap_is_deterministic_and_episode_scoped() -> None:
    first = bootstrap_median_ci([1.0, 2.0, 3.0, 4.0, 5.0], iterations=100)
    second = bootstrap_median_ci([1.0, 2.0, 3.0, 4.0, 5.0], iterations=100)
    assert first == second
    assert first["sampling_unit"] == "episode"
    assert first["episode_count"] == 5


def test_analysis_reports_progress_proxy_and_noncausal_direction() -> None:
    train = {
        f"train_{episode}": np.zeros((60, 15), dtype=np.float64)
        for episode in range(4)
    }
    online = {}
    for episode in range(5):
        values = np.zeros((60, 15), dtype=np.float64)
        values[:, 7] = np.linspace(0.0, 2.0 + episode * 0.1, 60)
        online[f"seed_{episode + 1}"] = values
    report = analyze_closed_loop_shift(train, online, _stats(), bootstrap_iterations=100)
    assert report["counts"] == {
        "train_episodes": 4,
        "train_frames": 240,
        "online_episodes": 5,
        "online_frames": 300,
    }
    assert len(report["normalized_progress_bins"]) == 6
    assert report["temporal_assessment"]["directional_temporal_shift"] is True
    assert report["temporal_assessment"]["phase_conditioned_analysis_available"] is False
    assert report["global_distance"]["mean_wasserstein1_normalized"] > 0


def test_schema_requires_diagnostic_nonclaims() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    payload = {
        "contract_version": "closed_loop_shift_report_v1",
        "artifact_type": "closed_loop_shift_report",
        "created_at": "2026-07-30T00:00:00Z",
        "status": "pass",
        "provenance": {},
        "method": {},
        "analysis": {},
        "conclusion": {},
        "diagnostic_only": True,
        "gate_eligible": False,
        "claims_causal_proof": False,
        "claims_task_success": False,
        "claims_sim2real": False,
        "claims_real_robot": False,
    }
    Draft202012Validator(schema).validate(payload)
    payload["claims_causal_proof"] = True
    assert not Draft202012Validator(schema).is_valid(payload)


def test_norm_stats_reject_wrong_dimension_or_zero_scale() -> None:
    with pytest.raises(ValueError):
        NormStats.from_sequences([0.0] * 14, [1.0] * 14, ["x"] * 14)
    with pytest.raises(ValueError):
        NormStats.from_sequences([0.0] * 15, [0.0] * 15, ["x"] * 15)


def test_frozen_ra_wp2_report_matches_authoritative_inputs_and_nonclaims() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    report = json.loads(FROZEN_REPORT.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(report)
    analysis = report["analysis"]
    assert analysis["counts"] == {
        "train_episodes": 36,
        "train_frames": 9122,
        "online_episodes": 5,
        "online_frames": 750,
    }
    assert analysis["global_distance"]["mean_wasserstein1_normalized"] == pytest.approx(0.7228415384)
    assert analysis["global_distance"]["energy_distance_normalized"] == pytest.approx(2.0554271677)
    temporal = analysis["temporal_assessment"]
    assert temporal["episodes_supporting_increase"] == 5
    assert temporal["phase_conditioned_analysis_available"] is False
    assert temporal["failure_onset_alignment_available"] is False
    assert report["conclusion"]["h2_assessment"] == (
        "directional_support_from_progress_proxy_not_causal_proof"
    )
    assert report["diagnostic_only"] is True
    assert report["gate_eligible"] is False
    assert report["claims_causal_proof"] is False
    assert report["claims_task_success"] is False
    assert report["claims_sim2real"] is False
