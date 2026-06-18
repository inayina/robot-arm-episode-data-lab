"""从 PyBullet URDF 模型读取关节限位。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    import pybullet as p
except ImportError:  # pragma: no cover
    p = None


@dataclass(frozen=True)
class JointLimits:
    lower: np.ndarray
    upper: np.ndarray

    def clamp(self, q: np.ndarray) -> np.ndarray:
        return np.clip(np.asarray(q, dtype=np.float32), self.lower, self.upper)

    def sample_uniform(self, rng: np.random.Generator) -> np.ndarray:
        return rng.uniform(self.lower, self.upper).astype(np.float32)


def get_joint_limits(robot_id: int, joint_indices: list[int]) -> JointLimits:
    """Read lower/upper joint limits from ``getJointInfo``."""
    if p is None:
        raise RuntimeError("pybullet is required for joint limit extraction.")

    lowers: list[float] = []
    uppers: list[float] = []
    for joint_index in joint_indices:
        joint_info = p.getJointInfo(robot_id, joint_index)
        lowers.append(float(joint_info[8]))
        uppers.append(float(joint_info[9]))

    return JointLimits(
        lower=np.asarray(lowers, dtype=np.float32),
        upper=np.asarray(uppers, dtype=np.float32),
    )
