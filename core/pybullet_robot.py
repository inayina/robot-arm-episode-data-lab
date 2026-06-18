"""RobotControl HAL 的 PyBullet 实现。"""

from __future__ import annotations

import numpy as np

try:
    import pybullet as p
except ImportError:  # pragma: no cover - exercised only without deps.
    p = None

from core.hal import RobotControl


class PyBulletRobot(RobotControl):
    """Robot controller backed by a PyBullet articulated body."""

    def __init__(
        self,
        robot_id: int,
        joint_indices: list[int],
        ee_link_index: int,
        max_force: float = 120.0,
    ) -> None:
        if p is None:
            raise RuntimeError(
                "Missing dependency: pybullet. Install dependencies with "
                "`python -m pip install -r requirements.txt`."
            )
        self._robot_id = robot_id
        self._joint_indices = list(joint_indices)
        self._ee_link_index = ee_link_index
        self._max_force = max_force

    @property
    def num_joints(self) -> int:
        return len(self._joint_indices)

    def get_joint_positions(self) -> np.ndarray:
        states = p.getJointStates(self._robot_id, self._joint_indices)
        return np.asarray([state[0] for state in states], dtype=np.float32)

    def get_end_effector_pose(self) -> tuple[np.ndarray, np.ndarray]:
        link_state = p.getLinkState(
            self._robot_id,
            self._ee_link_index,
            computeForwardKinematics=True,
        )
        position = np.asarray(link_state[4], dtype=np.float32)
        orientation = np.asarray(link_state[5], dtype=np.float32)
        return position, orientation

    def set_joint_positions(self, target_positions: np.ndarray) -> None:
        target = np.asarray(target_positions, dtype=np.float32).reshape(-1)
        if target.shape[0] != len(self._joint_indices):
            raise ValueError(
                "target_positions length "
                f"{target.shape[0]} does not match controlled joint count "
                f"{len(self._joint_indices)}."
            )
        p.setJointMotorControlArray(
            bodyUniqueId=self._robot_id,
            jointIndices=self._joint_indices,
            controlMode=p.POSITION_CONTROL,
            targetPositions=target.tolist(),
            forces=[self._max_force] * len(self._joint_indices),
        )

    def reset_joint_positions(self, target_positions: np.ndarray) -> None:
        target = np.asarray(target_positions, dtype=np.float32).reshape(-1)
        if target.shape[0] != len(self._joint_indices):
            raise ValueError(
                "target_positions length "
                f"{target.shape[0]} does not match controlled joint count "
                f"{len(self._joint_indices)}."
            )
        for joint_index, joint_position in zip(self._joint_indices, target):
            p.resetJointState(self._robot_id, joint_index, float(joint_position))

    def compute_ik(
        self,
        target_position: np.ndarray,
        target_orientation: np.ndarray | None = None,
    ) -> np.ndarray:
        position = np.asarray(target_position, dtype=np.float64).reshape(3)
        if target_orientation is None:
            _, target_orientation = self.get_end_effector_pose()
        orientation = np.asarray(target_orientation, dtype=np.float64).reshape(4)

        ik_result = p.calculateInverseKinematics(
            self._robot_id,
            self._ee_link_index,
            targetPosition=position.tolist(),
            targetOrientation=orientation.tolist(),
            maxNumIterations=100,
            residualThreshold=1e-5,
        )
        return np.asarray(
            [ik_result[joint_index] for joint_index in self._joint_indices],
            dtype=np.float32,
        )

    def step(self) -> None:
        p.stepSimulation()
