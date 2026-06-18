"""Tests for PyBullet collision checking."""

from __future__ import annotations

import numpy as np
import pytest

pybullet = pytest.importorskip("pybullet")
import pybullet_data

from core.collision import CollisionChecker
from core.joint_limits import get_joint_limits
from core.pybullet_robot import PyBulletRobot


@pytest.fixture
def pybullet_world():
    client_id = pybullet.connect(pybullet.DIRECT)
    pybullet.setAdditionalSearchPath(pybullet_data.getDataPath())
    pybullet.resetSimulation()
    pybullet.setGravity(0.0, 0.0, -9.81)
    plane_id = pybullet.loadURDF("plane.urdf")
    robot_id = pybullet.loadURDF(
        "kuka_iiwa/model.urdf",
        basePosition=(0.0, 0.0, 0.0),
        useFixedBase=True,
    )

    joint_indices: list[int] = []
    for joint_index in range(pybullet.getNumJoints(robot_id)):
        joint_info = pybullet.getJointInfo(robot_id, joint_index)
        if joint_info[2] in {pybullet.JOINT_REVOLUTE, pybullet.JOINT_PRISMATIC}:
            joint_indices.append(joint_index)

    initial_positions = np.array([0.0, 0.45, 0.0, -1.35, 0.0, 1.1, 0.0], dtype=np.float32)
    for joint_index, joint_position in zip(joint_indices, initial_positions):
        pybullet.resetJointState(robot_id, joint_index, float(joint_position))
    for _ in range(10):
        pybullet.stepSimulation()

    obstacle_shape = pybullet.createCollisionShape(pybullet.GEOM_BOX, halfExtents=[0.05, 0.05, 0.15])
    obstacle_id = pybullet.createMultiBody(
        baseMass=0.0,
        baseCollisionShapeIndex=obstacle_shape,
        basePosition=(0.52, 0.12, 0.10),
    )

    robot = PyBulletRobot(
        robot_id=robot_id,
        joint_indices=joint_indices,
        ee_link_index=joint_indices[-1],
    )
    checker = CollisionChecker(
        robot_id=robot_id,
        obstacle_ids=[obstacle_id],
        joint_indices=joint_indices,
        ee_link_index=joint_indices[-1],
    )
    limits = get_joint_limits(robot_id, joint_indices)

    yield robot, checker, limits, obstacle_id

    pybullet.disconnect(client_id)


def test_home_configuration_is_collision_free(pybullet_world) -> None:
    robot, checker, limits, _ = pybullet_world
    home = limits.clamp(np.array([0.0, 0.45, 0.0, -1.35, 0.0, 1.1, 0.0], dtype=np.float32))

    assert checker.is_configuration_free(robot, home) is True


def test_configuration_into_obstacle_is_in_collision(pybullet_world) -> None:
    robot, checker, limits, _ = pybullet_world
    colliding = np.array(
        [-2.2295477, 0.7147099, 0.8734401, 0.48332405, -0.69027126, 2.0827081, 2.937256],
        dtype=np.float32,
    )
    colliding = limits.clamp(colliding)

    assert checker.is_configuration_free(robot, colliding) is False


def test_collision_check_restores_joint_state(pybullet_world) -> None:
    robot, checker, limits, _ = pybullet_world
    before = robot.get_joint_positions()
    probe = limits.clamp(np.array([0.0, 1.2, 0.0, -0.5, 0.0, 1.4, 0.0], dtype=np.float32))

    checker.is_configuration_free(robot, probe)

    np.testing.assert_allclose(robot.get_joint_positions(), before, rtol=0.0, atol=1e-5)
