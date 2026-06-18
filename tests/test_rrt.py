"""Tests for bidirectional RRT-Connect."""

from __future__ import annotations

import numpy as np

from core.joint_limits import JointLimits
from core.rrt import RRTConfig, bidirectional_rrt_connect, resample_joint_path


def _box_is_free(lower: np.ndarray, upper: np.ndarray):
    def is_free(q: np.ndarray) -> bool:
        return bool(np.all(q >= lower) and np.all(q <= upper))

    return is_free


def test_rrt_connect_finds_path_in_open_box() -> None:
    limits = JointLimits(
        lower=np.array([-1.0, -1.0], dtype=np.float32),
        upper=np.array([1.0, 1.0], dtype=np.float32),
    )
    is_free = _box_is_free(limits.lower, limits.upper)
    start = np.array([-0.8, -0.8], dtype=np.float32)
    goal = np.array([0.8, 0.8], dtype=np.float32)

    result = bidirectional_rrt_connect(
        start,
        goal,
        is_free,
        limits,
        config=RRTConfig(step_size=0.2, max_iterations=500, goal_bias=0.2),
        rng=np.random.default_rng(7),
    )

    assert result.success is True
    assert len(result.path) >= 2
    assert result.path[0].shape == (2,)
    assert result.path[-1].shape == (2,)


def test_rrt_connect_reports_start_in_collision() -> None:
    limits = JointLimits(
        lower=np.zeros(2, dtype=np.float32),
        upper=np.ones(2, dtype=np.float32),
    )

    def is_free(q: np.ndarray) -> bool:
        return bool(np.all(q > 0.2))

    result = bidirectional_rrt_connect(
        np.array([0.1, 0.1], dtype=np.float32),
        np.array([0.8, 0.8], dtype=np.float32),
        is_free,
        limits,
        config=RRTConfig(max_iterations=50),
        rng=np.random.default_rng(1),
    )

    assert result.success is False
    assert result.failure_reason == "start_in_collision"


def test_rrt_connect_reports_timeout_in_narrow_gap() -> None:
    limits = JointLimits(
        lower=np.array([-1.0, -1.0], dtype=np.float32),
        upper=np.array([1.0, 1.0], dtype=np.float32),
    )

    def is_free(q: np.ndarray) -> bool:
        blocked = np.abs(q[0]) < 0.05 and np.abs(q[1]) < 0.95
        in_bounds = np.all(q >= limits.lower) and np.all(q <= limits.upper)
        return bool(in_bounds and not blocked)

    result = bidirectional_rrt_connect(
        np.array([-0.9, 0.0], dtype=np.float32),
        np.array([0.9, 0.0], dtype=np.float32),
        is_free,
        limits,
        config=RRTConfig(step_size=0.05, max_iterations=30, goal_bias=0.05),
        rng=np.random.default_rng(3),
    )

    assert result.success is False
    assert result.failure_reason == "timeout"


def test_resample_joint_path_returns_requested_length() -> None:
    path = [
        np.array([0.0, 0.0], dtype=np.float32),
        np.array([0.5, 0.0], dtype=np.float32),
        np.array([1.0, 0.5], dtype=np.float32),
    ]

    resampled = resample_joint_path(path, num_steps=10)

    assert len(resampled) == 10
    np.testing.assert_allclose(resampled[0], path[0], rtol=0.0, atol=1e-5)
    np.testing.assert_allclose(resampled[-1], path[-1], rtol=0.0, atol=1e-5)
