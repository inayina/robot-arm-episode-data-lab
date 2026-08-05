"""Synthetic contract tests for true upstream phase-conditioned analysis."""

import numpy as np
import pytest

from evaluation.closed_loop_shift import NormStats
from evaluation.phase_conditioned_shift import (
    align_observations_to_timeline,
    analyze_phase_conditioned_shift,
)


NAMES = tuple(f"state_{index}" for index in range(15))


def _timeline(episode="episode"):
    rows = []
    for index, phase in enumerate(("HOVER", "DESCEND", "CLOSE")):
        rows.append(
            {
                "contract_version": "panda_task_timeline_v1",
                "episode_id": episode,
                "monotonic_ns": (index + 1) * 100_000_000,
                "validity": "VALID",
                "phase": phase,
                "phase_semantics": "continuous_gt_achieved_subgoal_frontier",
                "failure_onset": {
                    "kind": "none_observed",
                    "onset_is_exact": False,
                    "onset_monotonic_ns": None,
                },
            }
        )
    return rows


def test_alignment_uses_shared_monotonic_time_and_rejects_stale_rows():
    observations = [
        {
            "contract_version": "smolvla_observation_telemetry_v2",
            "episode_id": "episode",
            "index": 0,
            "observation_monotonic_ns": 105_000_000,
            "state15": [0.0] * 15,
        },
        {
            "contract_version": "smolvla_observation_telemetry_v2",
            "episode_id": "episode",
            "index": 1,
            "observation_monotonic_ns": 500_000_000,
            "state15": [0.0] * 15,
        },
    ]
    aligned = align_observations_to_timeline(observations, _timeline(), max_age_ms=50)
    assert len(aligned) == 1
    assert aligned[0]["phase"] == "HOVER"
    assert aligned[0]["alignment_age_ms"] == pytest.approx(5.0)


def test_alignment_rejects_old_proxy_telemetry():
    observations = [{"index": 0, "state15": [0.0] * 15}]
    with pytest.raises(ValueError, match="v2"):
        align_observations_to_timeline(observations, _timeline())


def test_phase_analysis_detects_known_close_shift_and_keeps_nonclaims():
    rng = np.random.default_rng(7)
    train_states = {}
    train_phases = {}
    online = {}
    phases = ["HOVER"] * 30 + ["CLOSE"] * 30
    for index in range(4):
        episode = f"train_{index}"
        train_states[episode] = rng.normal(0.0, 0.1, size=(60, 15))
        train_phases[episode] = phases
    for index in range(3):
        episode = f"online_{index}"
        hover = rng.normal(0.0, 0.1, size=(30, 15))
        close = rng.normal(0.0, 0.1, size=(30, 15)) + 2.0
        values = np.vstack((hover, close))
        online[episode] = [
            {
                "phase": phases[row],
                "state15": values[row],
                "failure_onset": {
                    "kind": "terminal_nonachievement",
                    "onset_is_exact": False,
                    "onset_monotonic_ns": 999,
                },
            }
            for row in range(60)
        ]
    result = analyze_phase_conditioned_shift(
        train_states,
        train_phases,
        online,
        NormStats.from_sequences([0.0] * 15, [1.0] * 15, NAMES),
        bootstrap_iterations=100,
    )
    by_phase = {row["phase"]: row for row in result["phase_results"]}
    assert by_phase["CLOSE"]["distance"]["energy_distance_normalized"] > 5.0
    assert by_phase["HOVER"]["distance"]["energy_distance_normalized"] < 0.2
    assert result["conditioning"]["proxy"] is False
    assert result["failure_precedence"]["eligible"] is False
    assert all(value is False for key, value in result["claims"].items() if key != "uses_true_upstream_phase")
