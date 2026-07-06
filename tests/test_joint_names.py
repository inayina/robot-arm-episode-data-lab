"""Tests for canonical joint names used in LeRobot export."""

from core.joint_names import GRIPPER_JOINTS, IIWA_ARM_JOINTS, lerobot_joint_names


def test_lerobot_joint_names_iiwa7():
    names = lerobot_joint_names(robot="kuka_iiwa", grasp_mode="constraint", dim=7)
    assert names == list(IIWA_ARM_JOINTS)


def test_lerobot_joint_names_gripper_mode():
    names = lerobot_joint_names(robot="kuka_iiwa", grasp_mode="gripper_urdf", dim=9)
    assert names == list(IIWA_ARM_JOINTS) + list(GRIPPER_JOINTS)
