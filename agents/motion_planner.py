"""运动规划模块：Phase 1 笛卡尔规划与 Phase 2 RRT 避障规划。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.collision import CollisionChecker
from core.hal import RobotControl
from core.ik import solve_ik
from core.joint_limits import JointLimits
from core.pybullet_robot import PyBulletRobot
from core.rrt import RRTConfig, bidirectional_rrt_connect, resample_joint_path
from core.trajectory import interpolate_cartesian_line


@dataclass(frozen=True)
class PlanningResult:
    success: bool
    actions: list[np.ndarray]
    failure_reason: str | None = None


def plan_cartesian_segment(
    robot: RobotControl,
    start_position: np.ndarray,
    end_position: np.ndarray,
    start_orientation: np.ndarray,
    num_steps: int,
) -> PlanningResult:
    """Plan joint targets for a straight-line Cartesian segment."""
    if num_steps <= 0:
        raise ValueError("num_steps must be positive.")

    waypoints = interpolate_cartesian_line(
        start_position,
        end_position,
        num_steps,
        start_orientation=start_orientation,
        end_orientation=start_orientation,
    )
    actions = [solve_ik(robot, position, orientation) for position, orientation in waypoints]
    return PlanningResult(success=True, actions=actions)


def plan_rrt_segment(
    robot: PyBulletRobot,
    start_q: np.ndarray,
    goal_q: np.ndarray,
    collision_checker: CollisionChecker,
    joint_limits: JointLimits,
    num_interp_steps: int,
    *,
    rrt_config: RRTConfig | None = None,
    rng: np.random.Generator | None = None,
) -> PlanningResult:
    """Plan a collision-free joint-space segment with bidirectional RRT-Connect."""
    if num_interp_steps <= 0:
        raise ValueError("num_interp_steps must be positive.")

    is_free = lambda q: collision_checker.is_configuration_free(robot, q)
    result = bidirectional_rrt_connect(
        start_q,
        goal_q,
        is_free,
        joint_limits,
        config=rrt_config,
        rng=rng,
    )
    if not result.success:
        return PlanningResult(
            success=False,
            actions=[],
            failure_reason=result.failure_reason,
        )

    actions = resample_joint_path(result.path, num_interp_steps)
    return PlanningResult(success=True, actions=actions)


def plan_cartesian_segment_actions(
    robot: RobotControl,
    start_position: np.ndarray,
    end_position: np.ndarray,
    start_orientation: np.ndarray,
    num_steps: int,
) -> list[np.ndarray]:
    """Backward-compatible helper returning only the action list."""
    return plan_cartesian_segment(
        robot,
        start_position,
        end_position,
        start_orientation,
        num_steps,
    ).actions
