"""PyBullet 配置空间碰撞检测。"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

try:
    import pybullet as p
except ImportError:  # pragma: no cover
    p = None

from core.pybullet_robot import PyBulletRobot


@dataclass
class CollisionChecker:
    """Check whether a joint configuration is collision-free in PyBullet."""

    robot_id: int
    obstacle_ids: list[int]
    joint_indices: list[int]
    ee_link_index: int
    ignore_pairs: list[tuple[int, int]] = field(default_factory=list)
    check_self_collision: bool = True

    def __post_init__(self) -> None:
        if p is None:
            raise RuntimeError("pybullet is required for collision checking.")
        self._ignore_set = {
            (min(body_a, body_b), max(body_a, body_b))
            for body_a, body_b in self.ignore_pairs
        }
        for body_a, body_b in self.ignore_pairs:
            p.setCollisionFilterPair(body_a, body_b, -1, -1, enableCollision=0)

    def is_configuration_free(self, robot: PyBulletRobot, q: np.ndarray) -> bool:
        """Save state, set ``q``, query collisions, then restore state."""
        saved = robot.get_joint_positions()
        try:
            robot.reset_joint_positions(q)
            p.performCollisionDetection()
            return not self._has_collision()
        finally:
            robot.reset_joint_positions(saved)

    def has_environment_collision(self, robot_id: int | None = None) -> bool:
        """Check collisions without changing joint state (for runtime monitoring)."""
        body_id = robot_id if robot_id is not None else self.robot_id
        p.performCollisionDetection()
        for obstacle_id in self.obstacle_ids:
            if self._bodies_collide(body_id, obstacle_id):
                return True
        return False

    def _has_collision(self) -> bool:
        for obstacle_id in self.obstacle_ids:
            if self._bodies_collide(self.robot_id, obstacle_id):
                return True

        if not self.check_self_collision:
            return False

        num_joints = p.getNumJoints(self.robot_id)
        for link_a in range(num_joints):
            for link_b in range(link_a + 2, num_joints):
                if self._links_collide(self.robot_id, link_a, self.robot_id, link_b):
                    return True
        return False

    def _bodies_collide(self, body_a: int, body_b: int) -> bool:
        pair = (min(body_a, body_b), max(body_a, body_b))
        if pair in self._ignore_set:
            return False
        points = p.getClosestPoints(body_a, body_b, distance=0.0)
        return any(float(point[8]) <= 0.0 for point in points)

    def _links_collide(
        self,
        body_a: int,
        link_a: int,
        body_b: int,
        link_b: int,
    ) -> bool:
        pair = (min(body_a, body_b), max(body_a, body_b))
        if pair in self._ignore_set:
            return False
        points = p.getClosestPoints(
            body_a,
            body_b,
            distance=0.0,
            linkIndexA=link_a,
            linkIndexB=link_b,
        )
        return any(float(point[8]) <= 0.0 for point in points)
