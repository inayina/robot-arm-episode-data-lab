from __future__ import annotations

import numpy as np
import pytest

from core.ik import solve_ik
from core.trajectory import interpolate_cartesian_line
from scripts.collect_episode import smooth_trajectory


class _FakeRobot:
    def compute_ik(
        self,
        target_position: np.ndarray,
        target_orientation: np.ndarray | None = None,
    ) -> np.ndarray:
        return np.asarray(target_position, dtype=np.float32)


def test_interpolate_cartesian_line_returns_requested_waypoint_count() -> None:
    start = np.array([0.0, 0.0, 0.5], dtype=np.float32)
    end = np.array([0.1, 0.0, 0.5], dtype=np.float32)
    waypoints = interpolate_cartesian_line(start, end, num_waypoints=5)

    assert len(waypoints) == 5


def test_interpolate_cartesian_line_starts_and_ends_at_targets() -> None:
    start = np.array([0.0, 0.0, 0.5], dtype=np.float32)
    end = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    orientation = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
    waypoints = interpolate_cartesian_line(
        start,
        end,
        num_waypoints=4,
        start_orientation=orientation,
    )

    np.testing.assert_allclose(waypoints[0][0], start)
    np.testing.assert_allclose(waypoints[-1][0], end)
    assert all(np.array_equal(waypoint[1], orientation) for waypoint in waypoints)


def test_interpolate_cartesian_line_rejects_invalid_waypoint_count() -> None:
    with pytest.raises(ValueError, match="num_waypoints must be >= 2"):
        interpolate_cartesian_line(
            np.zeros(3, dtype=np.float32),
            np.ones(3, dtype=np.float32),
            num_waypoints=1,
        )


def test_interpolate_cartesian_line_has_smooth_position_progress() -> None:
    start = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    end = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    waypoints = interpolate_cartesian_line(start, end, num_waypoints=5)
    positions = np.stack([waypoint[0] for waypoint in waypoints])

    step_distances = np.linalg.norm(np.diff(positions, axis=0), axis=1)
    assert np.all(step_distances > 0.0)
    np.testing.assert_allclose(step_distances, step_distances[0], rtol=1e-5)


def test_solve_ik_validates_position_shape() -> None:
    robot = _FakeRobot()
    with pytest.raises(ValueError, match="target_position must have shape"):
        solve_ik(robot, np.zeros((2,), dtype=np.float32))


def test_solve_ik_validates_orientation_shape() -> None:
    robot = _FakeRobot()
    with pytest.raises(ValueError, match="target_orientation must have shape"):
        solve_ik(robot, np.zeros(3, dtype=np.float32), np.zeros(3, dtype=np.float32))


def test_smooth_trajectory_starts_and_ends_at_expected_joint_targets() -> None:
    start = smooth_trajectory(step=0, num_steps=5, action_dim=7)
    end = smooth_trajectory(step=4, num_steps=5, action_dim=7)

    np.testing.assert_allclose(
        start,
        np.array([0.0, 0.45, 0.0, -1.35, 0.0, 1.1, 0.0], dtype=np.float32),
    )
    np.testing.assert_allclose(
        end,
        np.array([-0.35, 0.65, 0.2, -1.15, -0.1, 1.35, 0.25], dtype=np.float32),
    )


def test_smooth_trajectory_respects_action_dimension_and_single_step() -> None:
    action = smooth_trajectory(step=0, num_steps=1, action_dim=3)

    assert action.shape == (3,)
    np.testing.assert_allclose(
        action,
        np.array([-0.35, 0.65, 0.2], dtype=np.float32),
    )


def test_smooth_trajectory_midpoint_is_between_start_and_end() -> None:
    start = smooth_trajectory(step=0, num_steps=3, action_dim=7)
    middle = smooth_trajectory(step=1, num_steps=3, action_dim=7)
    end = smooth_trajectory(step=2, num_steps=3, action_dim=7)

    lower = np.minimum(start, end)
    upper = np.maximum(start, end)

    assert np.all(middle >= lower)
    assert np.all(middle <= upper)
    np.testing.assert_allclose(middle, (start + end) / 2.0, atol=1e-6)
