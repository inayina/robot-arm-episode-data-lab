"""Headless PyBullet integration test for RRT planning."""

from __future__ import annotations

import numpy as np
import pytest

pybullet = pytest.importorskip("pybullet")
import pybullet_data

from agents.motion_planner import plan_rrt_segment
from core.collision import CollisionChecker
from core.joint_limits import get_joint_limits
from core.pybullet_robot import PyBulletRobot
from core.rrt import RRTConfig


@pytest.fixture
def rrt_scene():
    client_id = pybullet.connect(pybullet.DIRECT)
    pybullet.setAdditionalSearchPath(pybullet_data.getDataPath())
    pybullet.resetSimulation()
    pybullet.setGravity(0.0, 0.0, -9.81)
    pybullet.loadURDF("plane.urdf")
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

    home = np.array([0.0, 0.45, 0.0, -1.35, 0.0, 1.1, 0.0], dtype=np.float32)
    for joint_index, joint_position in zip(joint_indices, home):
        pybullet.resetJointState(robot_id, joint_index, float(joint_position))

    robot = PyBulletRobot(
        robot_id=robot_id,
        joint_indices=joint_indices,
        ee_link_index=joint_indices[-1],
    )
    limits = get_joint_limits(robot_id, joint_indices)
    checker = CollisionChecker(
        robot_id=robot_id,
        obstacle_ids=[],
        joint_indices=joint_indices,
        ee_link_index=joint_indices[-1],
    )

    yield robot, checker, limits

    pybullet.disconnect(client_id)


def test_rrt_plans_in_open_scene(rrt_scene) -> None:
    robot, checker, limits = rrt_scene
    start_q = robot.get_joint_positions()
    _, start_ori = robot.get_end_effector_pose()
    goal_pos = start_q.copy()
    goal_pos[1] += 0.25
    goal_pos = limits.clamp(goal_pos)

    result = plan_rrt_segment(
        robot,
        start_q,
        goal_pos,
        checker,
        limits,
        num_interp_steps=20,
        rrt_config=RRTConfig(max_iterations=1500, step_size=0.12),
        rng=np.random.default_rng(11),
    )

    assert result.success is True
    assert len(result.actions) == 20
