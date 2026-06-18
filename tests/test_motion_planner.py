"""Tests for motion planner integration helpers."""

from __future__ import annotations

import numpy as np

from agents.motion_planner import PlanningResult, plan_cartesian_segment
from core.trajectory import interpolate_cartesian_line


class _FakeRobot:
    def __init__(self) -> None:
        self._joints = np.zeros(3, dtype=np.float32)

    def get_joint_positions(self) -> np.ndarray:
        return self._joints.copy()

    def get_end_effector_pose(self) -> tuple[np.ndarray, np.ndarray]:
        return self._joints.copy(), np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)

    def compute_ik(
        self,
        target_position: np.ndarray,
        target_orientation: np.ndarray | None = None,
    ) -> np.ndarray:
        return np.asarray(target_position[:3], dtype=np.float32)


def test_plan_cartesian_segment_returns_planning_result() -> None:
    robot = _FakeRobot()
    start = np.array([0.4, 0.0, 0.3], dtype=np.float32)
    end = np.array([0.5, 0.0, 0.3], dtype=np.float32)
    orientation = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)

    result = plan_cartesian_segment(robot, start, end, orientation, num_steps=5)

    assert isinstance(result, PlanningResult)
    assert result.success is True
    assert len(result.actions) == 5


def test_interpolate_cartesian_line_endpoints() -> None:
    start = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    end = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    waypoints = interpolate_cartesian_line(start, end, 4)

    np.testing.assert_allclose(waypoints[0][0], start)
    np.testing.assert_allclose(waypoints[-1][0], end)
