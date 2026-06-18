"""基于 RobotControl 的逆运动学求解封装。"""

from __future__ import annotations

import numpy as np

from core.hal import RobotControl


def solve_ik(
    robot: RobotControl,
    target_position: np.ndarray,
    target_orientation: np.ndarray | None = None,
) -> np.ndarray:
    """Solve IK for a Cartesian target and return joint targets."""
    position = np.asarray(target_position, dtype=np.float32)
    if position.shape != (3,):
        raise ValueError(
            f"target_position must have shape (3,), got {position.shape}."
        )

    orientation = None
    if target_orientation is not None:
        orientation = np.asarray(target_orientation, dtype=np.float32)
        if orientation.shape != (4,):
            raise ValueError(
                f"target_orientation must have shape (4,), got {orientation.shape}."
            )

    joint_targets = robot.compute_ik(position, orientation)
    joint_targets = np.asarray(joint_targets, dtype=np.float32).reshape(-1)
    return joint_targets
