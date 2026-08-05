"""Metrics for diagnostic expert-vs-autonomous state distribution shift.

The sampling unit for uncertainty is an episode. Frames are used to estimate a
per-episode distance but are never treated as independent bootstrap units.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np


STATE_DIM = 15
PROGRESS_BIN_LABELS = tuple(f"progress_{i}_of_6" for i in range(6))


@dataclass(frozen=True)
class NormStats:
    mean: np.ndarray
    std: np.ndarray
    names: tuple[str, ...]

    @classmethod
    def from_sequences(
        cls, mean: Sequence[float], std: Sequence[float], names: Sequence[str]
    ) -> "NormStats":
        mean_array = np.asarray(mean, dtype=np.float64)
        std_array = np.asarray(std, dtype=np.float64)
        if mean_array.shape != (STATE_DIM,) or std_array.shape != (STATE_DIM,):
            raise ValueError("state normalization must contain 15 dimensions")
        if len(names) != STATE_DIM or np.any(std_array <= 0) or not np.all(np.isfinite(std_array)):
            raise ValueError("invalid state normalization statistics")
        return cls(mean_array, std_array, tuple(names))


def validate_episode_states(episodes: Mapping[str, np.ndarray]) -> None:
    if not episodes:
        raise ValueError("at least one episode is required")
    for episode_id, values in episodes.items():
        array = np.asarray(values)
        if array.ndim != 2 or array.shape[1] != STATE_DIM or array.shape[0] < 2:
            raise ValueError(f"{episode_id}: expected [N,15] with N>=2")
        if not np.all(np.isfinite(array)):
            raise ValueError(f"{episode_id}: state contains NaN or Inf")


def standardize(values: np.ndarray, stats: NormStats) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != STATE_DIM:
        raise ValueError("expected state matrix [N,15]")
    return (array - stats.mean) / stats.std


def wasserstein_1d(left: np.ndarray, right: np.ndarray, quantiles: int = 512) -> float:
    """Deterministic empirical W1 via a shared quantile grid."""

    a = np.asarray(left, dtype=np.float64).reshape(-1)
    b = np.asarray(right, dtype=np.float64).reshape(-1)
    if not len(a) or not len(b):
        raise ValueError("W1 inputs must be non-empty")
    grid = (np.arange(quantiles, dtype=np.float64) + 0.5) / quantiles
    return float(np.mean(np.abs(np.quantile(a, grid) - np.quantile(b, grid))))


def _even_sample(values: np.ndarray, maximum: int) -> np.ndarray:
    if len(values) <= maximum:
        return values
    indices = np.linspace(0, len(values) - 1, maximum, dtype=np.int64)
    return values[indices]


def _mean_pairwise_distance(left: np.ndarray, right: np.ndarray, block: int = 256) -> float:
    total = 0.0
    count = 0
    for start in range(0, len(left), block):
        chunk = left[start : start + block]
        distances = np.linalg.norm(chunk[:, None, :] - right[None, :, :], axis=2)
        total += float(distances.sum())
        count += distances.size
    return total / count


def energy_distance(
    left: np.ndarray, right: np.ndarray, maximum_per_side: int = 1024
) -> float:
    """Multivariate energy distance on deterministically capped samples."""

    a = _even_sample(np.asarray(left, dtype=np.float64), maximum_per_side)
    b = _even_sample(np.asarray(right, dtype=np.float64), maximum_per_side)
    if a.ndim != 2 or b.ndim != 2 or not len(a) or not len(b) or a.shape[1] != b.shape[1]:
        raise ValueError("energy-distance inputs must be non-empty [N,D] matrices")
    value = (
        2.0 * _mean_pairwise_distance(a, b)
        - _mean_pairwise_distance(a, a)
        - _mean_pairwise_distance(b, b)
    )
    return float(max(0.0, value))


def progress_bin_indices(length: int, bins: int = 6) -> np.ndarray:
    if length < bins:
        raise ValueError("episode is too short for requested progress bins")
    indices = np.floor(np.arange(length, dtype=np.float64) * bins / length).astype(np.int64)
    return np.minimum(indices, bins - 1)


def distance_summary(reference: np.ndarray, comparison: np.ndarray, names: Sequence[str]) -> dict[str, Any]:
    if reference.shape[1] != STATE_DIM or comparison.shape[1] != STATE_DIM:
        raise ValueError("distance summary requires state15 matrices")
    w1 = [wasserstein_1d(reference[:, dim], comparison[:, dim]) for dim in range(STATE_DIM)]
    mean_delta = comparison.mean(axis=0) - reference.mean(axis=0)
    return {
        "reference_frames": int(len(reference)),
        "comparison_frames": int(len(comparison)),
        "mean_wasserstein1_normalized": float(np.mean(w1)),
        "max_wasserstein1_normalized": float(np.max(w1)),
        "normalized_mean_delta_l2": float(np.linalg.norm(mean_delta)),
        "energy_distance_normalized": energy_distance(reference, comparison),
        "per_dimension": [
            {
                "index": dim,
                "name": str(names[dim]),
                "wasserstein1_normalized": float(w1[dim]),
                "standardized_mean_difference": float(mean_delta[dim]),
            }
            for dim in range(STATE_DIM)
        ],
    }


def bootstrap_median_ci(
    values: Sequence[float], *, iterations: int = 2000, seed: int = 20260730
) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.float64)
    if len(array) < 3 or not np.all(np.isfinite(array)):
        raise ValueError("episode bootstrap requires at least three finite episode values")
    rng = np.random.default_rng(seed)
    samples = rng.choice(array, size=(iterations, len(array)), replace=True)
    medians = np.median(samples, axis=1)
    return {
        "sampling_unit": "episode",
        "episode_count": int(len(array)),
        "iterations": iterations,
        "rng_seed": seed,
        "median": float(np.median(array)),
        "ci95_low": float(np.quantile(medians, 0.025)),
        "ci95_high": float(np.quantile(medians, 0.975)),
        "episode_values": array.tolist(),
    }


def behavior_diagnostics(states: np.ndarray, gripper_commands: Sequence[float] | None = None) -> dict[str, Any]:
    values = np.asarray(states, dtype=np.float64)
    ee_xyz = values[:, 7:10]
    step = np.linalg.norm(np.diff(ee_xyz, axis=0), axis=1)
    gripper = values[:, 14]
    result = {
        "frames": int(len(values)),
        "ee_z_start_m": float(ee_xyz[0, 2]),
        "ee_z_min_m": float(np.min(ee_xyz[:, 2])),
        "ee_z_final_m": float(ee_xyz[-1, 2]),
        "ee_xyz_net_displacement_m": float(np.linalg.norm(ee_xyz[-1] - ee_xyz[0])),
        "ee_step_l2_p50_m": float(np.quantile(step, 0.5)),
        "ee_step_l2_p90_m": float(np.quantile(step, 0.9)),
        "near_static_step_fraction_lte_1e_4": float(np.mean(step <= 1e-4)),
        "measured_gripper_min": float(np.min(gripper)),
        "measured_gripper_fraction_below_0_7": float(np.mean(gripper < 0.7)),
    }
    if gripper_commands is not None:
        commands = np.asarray(gripper_commands, dtype=np.float64)
        result["gripper_command_min"] = float(np.min(commands))
        result["gripper_command_fraction_below_0_7"] = float(np.mean(commands < 0.7))
    return result


def analyze_closed_loop_shift(
    train_episodes: Mapping[str, np.ndarray],
    online_episodes: Mapping[str, np.ndarray],
    stats: NormStats,
    *,
    online_gripper_commands: Mapping[str, Sequence[float]] | None = None,
    bootstrap_iterations: int = 2000,
) -> dict[str, Any]:
    validate_episode_states(train_episodes)
    validate_episode_states(online_episodes)
    if len(online_episodes) < 3:
        raise ValueError("at least three online episodes are required")

    train_normalized = {key: standardize(value, stats) for key, value in train_episodes.items()}
    online_normalized = {key: standardize(value, stats) for key, value in online_episodes.items()}
    pooled_train = np.concatenate(list(train_normalized.values()), axis=0)
    pooled_online = np.concatenate(list(online_normalized.values()), axis=0)
    global_summary = distance_summary(pooled_train, pooled_online, stats.names)

    episode_distances = []
    for values in online_normalized.values():
        summary = distance_summary(pooled_train, values, stats.names)
        episode_distances.append(
            {
                "mean_wasserstein1_normalized": summary["mean_wasserstein1_normalized"],
                "energy_distance_normalized": summary["energy_distance_normalized"],
                "normalized_mean_delta_l2": summary["normalized_mean_delta_l2"],
            }
        )
    uncertainty = {
        metric: bootstrap_median_ci(
            [episode[metric] for episode in episode_distances],
            iterations=bootstrap_iterations,
        )
        for metric in episode_distances[0]
    }

    temporal_bins = []
    per_episode_bin_energy: dict[str, list[float]] = {key: [] for key in online_normalized}
    for bin_index, label in enumerate(PROGRESS_BIN_LABELS):
        train_bin = np.concatenate(
            [values[progress_bin_indices(len(values)) == bin_index] for values in train_normalized.values()],
            axis=0,
        )
        online_bin = np.concatenate(
            [values[progress_bin_indices(len(values)) == bin_index] for values in online_normalized.values()],
            axis=0,
        )
        point = distance_summary(train_bin, online_bin, stats.names)
        episode_energy = []
        for episode_id, values in online_normalized.items():
            values_bin = values[progress_bin_indices(len(values)) == bin_index]
            energy = energy_distance(train_bin, values_bin)
            per_episode_bin_energy[episode_id].append(energy)
            episode_energy.append(energy)
        temporal_bins.append(
            {
                "bin_index": bin_index,
                "label": label,
                "conditioning": "normalized_episode_progress_proxy_not_task_phase",
                "distance": point,
                "energy_distance_episode_bootstrap": bootstrap_median_ci(
                    episode_energy, iterations=bootstrap_iterations
                ),
            }
        )

    late_gt_early = {
        episode_id: bool(values[-1] > values[0])
        for episode_id, values in per_episode_bin_energy.items()
    }
    directional_count = sum(late_gt_early.values())
    temporal_assessment = {
        "late_bin_energy_greater_than_early_by_episode": late_gt_early,
        "episodes_supporting_increase": directional_count,
        "episode_count": len(late_gt_early),
        "directional_temporal_shift": directional_count >= 3,
        "phase_conditioned_analysis_available": False,
        "failure_onset_alignment_available": False,
        "h2_assessment": (
            "directional_support_from_progress_proxy_not_causal_proof"
            if directional_count >= 3
            else "not_supported_or_inconclusive"
        ),
    }

    diagnostics = {
        episode_id: behavior_diagnostics(
            states,
            None if online_gripper_commands is None else online_gripper_commands.get(episode_id),
        )
        for episode_id, states in online_episodes.items()
    }
    return {
        "counts": {
            "train_episodes": len(train_episodes),
            "train_frames": int(sum(len(value) for value in train_episodes.values())),
            "online_episodes": len(online_episodes),
            "online_frames": int(sum(len(value) for value in online_episodes.values())),
        },
        "global_distance": global_summary,
        "episode_level_uncertainty": uncertainty,
        "normalized_progress_bins": temporal_bins,
        "temporal_assessment": temporal_assessment,
        "online_behavior_diagnostics": diagnostics,
    }
