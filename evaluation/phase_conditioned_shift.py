"""Phase-conditioned state-shift analysis using upstream Task GT timelines.

This module deliberately rejects inferred phases, stale nearest-neighbor joins,
and terminal non-achievement timestamps presented as exact failure onset.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

import numpy as np

from evaluation.closed_loop_shift import (
    NormStats,
    bootstrap_median_ci,
    distance_summary,
    standardize,
)


TIMELINE_CONTRACT = "panda_task_timeline_v1"
OBSERVATION_CONTRACT = "smolvla_observation_telemetry_v2"
PHASE_SEMANTICS = "continuous_gt_achieved_subgoal_frontier"
ANALYZABLE_PHASES = ("HOVER", "DESCEND", "CLOSE", "LIFT", "TRANSPORT", "PLACE", "RELEASE")


def align_observations_to_timeline(
    observations: Sequence[Mapping[str, Any]],
    timeline: Sequence[Mapping[str, Any]],
    *,
    max_age_ms: float = 100.0,
) -> list[dict[str, Any]]:
    """Nearest-monotonic-time join with identity and freshness enforcement."""
    if not observations or not timeline:
        raise ValueError("observation and Task GT timeline rows are required")
    if max_age_ms <= 0:
        raise ValueError("max_age_ms must be positive")
    for row in observations:
        if row.get("contract_version") != OBSERVATION_CONTRACT:
            raise ValueError("online observation telemetry v2 is required")
    for row in timeline:
        if row.get("contract_version") != TIMELINE_CONTRACT:
            raise ValueError("upstream Task GT timeline v1 is required")
        if row.get("phase_semantics") != PHASE_SEMANTICS:
            raise ValueError("Task GT phase semantics mismatch")

    episode_ids = {str(row.get("episode_id")) for row in observations + timeline}
    if len(episode_ids) != 1 or "None" in episode_ids:
        raise ValueError("observation/timeline episode identity mismatch")
    times = np.asarray([int(row["monotonic_ns"]) for row in timeline], dtype=np.int64)
    if np.any(np.diff(times) < 0):
        raise ValueError("Task GT timeline must be monotonic")
    limit_ns = int(max_age_ms * 1e6)
    aligned: list[dict[str, Any]] = []
    for observation in observations:
        stamp = int(observation["observation_monotonic_ns"])
        insertion = int(np.searchsorted(times, stamp))
        candidates = [idx for idx in (insertion - 1, insertion) if 0 <= idx < len(times)]
        nearest = min(candidates, key=lambda idx: abs(int(times[idx]) - stamp))
        gt = timeline[nearest]
        age_ns = abs(int(times[nearest]) - stamp)
        if age_ns > limit_ns:
            continue
        if gt.get("validity") != "VALID" or gt.get("phase") not in ANALYZABLE_PHASES:
            continue
        state = np.asarray(observation.get("state15"), dtype=np.float64)
        if state.shape != (15,) or not np.all(np.isfinite(state)):
            raise ValueError("aligned observation must contain finite state15")
        aligned.append(
            {
                "episode_id": observation["episode_id"],
                "index": int(observation["index"]),
                "observation_monotonic_ns": stamp,
                "task_gt_monotonic_ns": int(times[nearest]),
                "alignment_age_ms": age_ns / 1e6,
                "phase": gt["phase"],
                "state15": state,
                "failure_onset": dict(gt["failure_onset"]),
            }
        )
    if not aligned:
        raise ValueError("no fresh VALID Task GT phase alignments")
    return aligned


def analyze_phase_conditioned_shift(
    train_states: Mapping[str, np.ndarray],
    train_phases: Mapping[str, Sequence[str]],
    online_aligned: Mapping[str, Sequence[Mapping[str, Any]]],
    stats: NormStats,
    *,
    minimum_frames_per_domain: int = 20,
    bootstrap_iterations: int = 2000,
) -> dict[str, Any]:
    """Compare P(state | upstream GT phase) with episode-level uncertainty."""
    if set(train_states) != set(train_phases):
        raise ValueError("train state/phase episode identities must match")
    train_by_phase: dict[str, list[np.ndarray]] = defaultdict(list)
    for episode_id, values in train_states.items():
        array = np.asarray(values, dtype=np.float64)
        phases = list(train_phases[episode_id])
        if array.ndim != 2 or array.shape[1] != 15 or len(array) != len(phases):
            raise ValueError(f"{episode_id}: train state/phase length mismatch")
        normalized = standardize(array, stats)
        for phase in ANALYZABLE_PHASES:
            selected = normalized[np.asarray(phases) == phase]
            if len(selected):
                train_by_phase[phase].append(selected)

    online_by_phase_episode: dict[str, dict[str, np.ndarray]] = defaultdict(dict)
    failure_kinds: dict[str, str] = {}
    exact_onsets: dict[str, int] = {}
    for episode_id, rows in online_aligned.items():
        grouped: dict[str, list[np.ndarray]] = defaultdict(list)
        for row in rows:
            grouped[str(row["phase"])].append(np.asarray(row["state15"], dtype=np.float64))
            onset = row["failure_onset"]
            failure_kinds[episode_id] = str(onset.get("kind", "unavailable"))
            if onset.get("onset_is_exact") is True and onset.get("onset_monotonic_ns") is not None:
                exact_onsets[episode_id] = int(onset["onset_monotonic_ns"])
        for phase, values in grouped.items():
            online_by_phase_episode[phase][episode_id] = standardize(np.vstack(values), stats)

    phase_results = []
    unavailable = []
    for phase in ANALYZABLE_PHASES:
        train_parts = train_by_phase.get(phase, [])
        online_parts = online_by_phase_episode.get(phase, {})
        train_count = sum(len(part) for part in train_parts)
        online_count = sum(len(part) for part in online_parts.values())
        if (
            train_count < minimum_frames_per_domain
            or online_count < minimum_frames_per_domain
            or len(online_parts) < 3
        ):
            unavailable.append(
                {
                    "phase": phase,
                    "train_frames": train_count,
                    "online_frames": online_count,
                    "online_episodes": len(online_parts),
                    "reason": "requires_min_frames_and_three_online_episodes",
                }
            )
            continue
        reference = np.concatenate(train_parts, axis=0)
        comparison = np.concatenate(list(online_parts.values()), axis=0)
        episode_energy = [
            distance_summary(reference, values, stats.names)["energy_distance_normalized"]
            for values in online_parts.values()
        ]
        phase_results.append(
            {
                "phase": phase,
                "distance": distance_summary(reference, comparison, stats.names),
                "energy_distance_episode_bootstrap": bootstrap_median_ci(
                    episode_energy,
                    iterations=bootstrap_iterations,
                ),
                "online_episode_ids": sorted(online_parts),
            }
        )

    return {
        "contract_version": "phase_conditioned_closed_loop_shift_v1",
        "conditioning": {
            "source": "upstream_continuous_task_evaluator",
            "semantics": PHASE_SEMANTICS,
            "proxy": False,
        },
        "phase_results": phase_results,
        "unavailable_phases": unavailable,
        "failure_precedence": {
            "exact_onset_episode_count": len(exact_onsets),
            "exact_onset_monotonic_ns": exact_onsets,
            "failure_kind_by_episode": failure_kinds,
            "eligible": len(exact_onsets) >= 3,
            "causal_claim_allowed": False,
            "reason": (
                "at_least_three_exact_observable_failure_onsets"
                if len(exact_onsets) >= 3
                else "terminal_nonachievement_is_not_an_exact_behavioral_onset"
            ),
        },
        "claims": {
            "uses_true_upstream_phase": True,
            "causal_proof": False,
            "task_success": False,
            "sim2real": False,
            "real_robot": False,
        },
    }
