"""机器人控制硬件抽象层（HAL）。"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class RobotControl(ABC):
    """机器人控制器抽象接口。

    上层模块依赖此契约，而不是仿真器专有 API。
    位姿约定与 ``ee_poses.npy`` 一致：位置 ``[x, y, z]``，
    四元数 ``[qx, qy, qz, qw]``。
    """

    @abstractmethod
    def get_joint_positions(self) -> np.ndarray:
        """Return current controlled joint positions, shape ``[state_dim]``."""

    @abstractmethod
    def get_end_effector_pose(self) -> tuple[np.ndarray, np.ndarray]:
        """Return end-effector position and orientation quaternion."""

    @abstractmethod
    def set_joint_positions(self, target_positions: np.ndarray) -> None:
        """Command target joint positions without advancing simulation."""

    @abstractmethod
    def compute_ik(
        self,
        target_position: np.ndarray,
        target_orientation: np.ndarray | None = None,
    ) -> np.ndarray:
        """Solve inverse kinematics for a Cartesian target pose."""

    @abstractmethod
    def step(self) -> None:
        """Advance the simulation by one timestep."""
