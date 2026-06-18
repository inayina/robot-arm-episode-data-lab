"""Parallel-jaw gripper control and contact-based grasp detection (Plan B)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from core.world import World, get_controlled_joints

try:
    import pybullet as p
except ImportError:  # pragma: no cover
    p = None

REPO_ROOT = Path(__file__).resolve().parents[1]
GRIPPER_URDF = REPO_ROOT / "assets" / "urdf" / "simple_gripper.urdf"

FINGER_OPEN_POSITION = 0.025
FINGER_CLOSE_POSITION = 0.0
GRIPPER_MOUNT_OFFSET_Z = -0.055


@dataclass(frozen=True)
class GripperGraspState:
    active: bool
    established_at_step: int | None
    finger_positions: np.ndarray
    finger_targets: np.ndarray


def attach_gripper(world: World) -> World:
    """Load a two-finger URDF and fix it to the robot EE link."""
    if p is None:
        raise RuntimeError("pybullet is required for gripper attachment.")

    ee_state = p.getLinkState(
        world.robot_id,
        world.ee_link_index,
        computeForwardKinematics=True,
    )
    ee_pos, ee_orn = ee_state[4], ee_state[5]
    mount_pos, mount_orn = p.multiplyTransforms(
        ee_pos,
        ee_orn,
        [0.0, 0.0, GRIPPER_MOUNT_OFFSET_Z],
        [0.0, 0.0, 0.0, 1.0],
    )

    p.setAdditionalSearchPath(str(GRIPPER_URDF.parent))
    gripper_id = p.loadURDF(
        str(GRIPPER_URDF.name),
        basePosition=mount_pos,
        baseOrientation=mount_orn,
        useFixedBase=False,
    )
    gripper_joint_indices = get_controlled_joints(gripper_id)

    mount_constraint_id = p.createConstraint(
        parentBodyUniqueId=world.robot_id,
        parentLinkIndex=world.ee_link_index,
        childBodyUniqueId=gripper_id,
        childLinkIndex=-1,
        jointType=p.JOINT_FIXED,
        jointAxis=[0.0, 0.0, 0.0],
        parentFramePosition=[0.0, 0.0, GRIPPER_MOUNT_OFFSET_Z],
        parentFrameOrientation=[0.0, 0.0, 0.0, 1.0],
        childFramePosition=[0.0, 0.0, 0.0],
        childFrameOrientation=[0.0, 0.0, 0.0, 1.0],
    )
    p.changeConstraint(mount_constraint_id, maxForce=500.0)

    for body_id in (gripper_id, world.cube_id):
        p.changeDynamics(body_id, -1, lateralFriction=1.2, rollingFriction=0.01)

    for joint_index in gripper_joint_indices:
        p.resetJointState(gripper_id, joint_index, FINGER_OPEN_POSITION)
        p.setJointMotorControl2(
            gripper_id,
            joint_index,
            controlMode=p.POSITION_CONTROL,
            targetPosition=FINGER_OPEN_POSITION,
            force=80.0,
        )

    for _ in range(10):
        p.stepSimulation()

    return World(
        robot_id=world.robot_id,
        cube_id=world.cube_id,
        joint_indices=world.joint_indices,
        ee_link_index=world.ee_link_index,
        plane_id=world.plane_id,
        obstacle_ids=world.obstacle_ids,
        gripper_id=gripper_id,
        gripper_joint_indices=tuple(gripper_joint_indices),
        gripper_mount_constraint_id=mount_constraint_id,
    )


class GripperGraspController:
    """Drive finger joints and latch grasp when cube contact force is sufficient."""

    def __init__(
        self,
        world: World,
        *,
        grasp_force_threshold: float = 1.0,
        min_contact_points: int = 1,
    ) -> None:
        if world.gripper_id is None or not world.gripper_joint_indices:
            raise ValueError("GripperGraspController requires a world with an attached gripper.")
        self._world = world
        self._grasp_force_threshold = grasp_force_threshold
        self._min_contact_points = min_contact_points
        self._finger_target = FINGER_OPEN_POSITION
        self._grasped = False
        self._established_at_step: int | None = None

    @property
    def is_grasped(self) -> bool:
        return self._grasped

    @property
    def grasp_established_at_step(self) -> int | None:
        return self._established_at_step

    def finger_positions(self) -> np.ndarray:
        states = p.getJointStates(
            self._world.gripper_id,
            list(self._world.gripper_joint_indices),
        )
        return np.asarray([state[0] for state in states], dtype=np.float32)

    def finger_targets(self) -> np.ndarray:
        target = float(self._finger_target)
        return np.full(len(self._world.gripper_joint_indices), target, dtype=np.float32)

    def open(self) -> None:
        self._finger_target = FINGER_OPEN_POSITION
        self._apply_finger_targets()

    def close(self) -> None:
        self._finger_target = FINGER_CLOSE_POSITION
        self._apply_finger_targets()

    def try_grasp(self, *, step: int | None = None) -> bool:
        self.close()
        if self._detect_grasp_contact():
            self._grasped = True
            if step is not None and self._established_at_step is None:
                self._established_at_step = step
            return True
        return self._grasped

    def state(self) -> GripperGraspState:
        return GripperGraspState(
            active=self._grasped,
            established_at_step=self._established_at_step,
            finger_positions=self.finger_positions(),
            finger_targets=self.finger_targets(),
        )

    def _apply_finger_targets(self) -> None:
        targets = [float(self._finger_target)] * len(self._world.gripper_joint_indices)
        p.setJointMotorControlArray(
            bodyUniqueId=self._world.gripper_id,
            jointIndices=list(self._world.gripper_joint_indices),
            controlMode=p.POSITION_CONTROL,
            targetPositions=targets,
            forces=[80.0] * len(self._world.gripper_joint_indices),
        )

    def _detect_grasp_contact(self) -> bool:
        contacts = p.getContactPoints(
            bodyA=self._world.gripper_id,
            bodyB=self._world.cube_id,
        )
        if len(contacts) < self._min_contact_points:
            return False

        for contact in contacts:
            normal_force = abs(float(contact[9]))
            if normal_force >= self._grasp_force_threshold:
                return True
        return len(contacts) >= self._min_contact_points
