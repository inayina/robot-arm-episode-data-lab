"""Physical grasp via PyBullet fixed constraint (Day 1 constraint grasp)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.world import World, object_pose

try:
    import pybullet as p
except ImportError:  # pragma: no cover
    p = None


@dataclass(frozen=True)
class GraspState:
    active: bool
    constraint_id: int | None
    grasp_offset: np.ndarray | None
    established_at_step: int | None


class ConstraintGraspController:
    """Latch a fixed constraint between EE link and cube when contact/distance allows."""

    def __init__(
        self,
        world: World,
        *,
        max_grasp_distance: float = 0.08,
        max_grasp_xy_distance: float = 0.08,
        min_contact_points: int = 1,
        max_slip_distance: float = 0.10,
    ) -> None:
        self._world = world
        self._max_grasp_distance = max_grasp_distance
        self._max_grasp_xy_distance = max_grasp_xy_distance
        self._min_contact_points = min_contact_points
        self._max_slip_distance = max_slip_distance
        self._constraint_id: int | None = None
        self._grasp_offset: np.ndarray | None = None
        self._established_at_step: int | None = None

    @property
    def is_grasped(self) -> bool:
        return self._constraint_id is not None

    @property
    def grasp_established_at_step(self) -> int | None:
        return self._established_at_step

    @property
    def grasp_offset(self) -> np.ndarray | None:
        return None if self._grasp_offset is None else self._grasp_offset.copy()

    def state(self) -> GraspState:
        return GraspState(
            active=self.is_grasped,
            constraint_id=self._constraint_id,
            grasp_offset=self.grasp_offset,
            established_at_step=self._established_at_step,
        )

    def try_grasp(self, *, step: int | None = None) -> bool:
        if self.is_grasped:
            return True
        if not self._can_grasp():
            return False
        self._create_constraint(step=step)
        return self.is_grasped

    def release(self) -> None:
        if self._constraint_id is None:
            return
        p.removeConstraint(self._constraint_id)
        self._constraint_id = None

    def check_slip(self) -> bool:
        if not self.is_grasped or self._grasp_offset is None:
            return False
        ee_pos = self._ee_position()
        cube_pos = object_pose(self._world.cube_id)[:3]
        return float(np.linalg.norm(cube_pos - ee_pos)) > self._max_slip_distance

    def _can_grasp(self) -> bool:
        if self._has_contact():
            return True
        ee_pos = self._ee_position()
        cube_pos = object_pose(self._world.cube_id)[:3]
        xy_distance = float(np.linalg.norm(ee_pos[:2] - cube_pos[:2]))
        if xy_distance <= self._max_grasp_xy_distance:
            return True
        return float(np.linalg.norm(ee_pos - cube_pos)) <= self._max_grasp_distance

    def _has_contact(self) -> bool:
        contacts = p.getContactPoints(
            bodyA=self._world.robot_id,
            bodyB=self._world.cube_id,
        )
        return len(contacts) >= self._min_contact_points

    def _ee_position(self) -> np.ndarray:
        ee_state = p.getLinkState(
            self._world.robot_id,
            self._world.ee_link_index,
            computeForwardKinematics=True,
        )
        return np.asarray(ee_state[4], dtype=np.float32)

    def _create_constraint(self, *, step: int | None) -> None:
        ee_state = p.getLinkState(
            self._world.robot_id,
            self._world.ee_link_index,
            computeForwardKinematics=True,
        )
        ee_pos = ee_state[4]
        ee_orn = ee_state[5]
        cube_pos, cube_orn = p.getBasePositionAndOrientation(self._world.cube_id)

        self._grasp_offset = (np.asarray(cube_pos, dtype=np.float32) - np.asarray(ee_pos, dtype=np.float32))

        inv_pos, inv_orn = p.invertTransform(ee_pos, ee_orn)
        parent_pos, parent_orn = p.multiplyTransforms(
            inv_pos,
            inv_orn,
            cube_pos,
            cube_orn,
        )

        self._constraint_id = p.createConstraint(
            parentBodyUniqueId=self._world.robot_id,
            parentLinkIndex=self._world.ee_link_index,
            childBodyUniqueId=self._world.cube_id,
            childLinkIndex=-1,
            jointType=p.JOINT_FIXED,
            jointAxis=[0.0, 0.0, 0.0],
            parentFramePosition=parent_pos,
            parentFrameOrientation=parent_orn,
            childFramePosition=[0.0, 0.0, 0.0],
            childFrameOrientation=[0.0, 0.0, 0.0, 1.0],
        )
        p.changeConstraint(self._constraint_id, maxForce=500.0)
        if step is not None:
            self._established_at_step = step
