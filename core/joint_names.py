"""Canonical joint names shared with ros2-moveit-pybullet-bridge (iiwa7 profile)."""

from __future__ import annotations

# Keep in sync with pybullet_bridge.robot_profiles.IIWA_JOINTS
IIWA_ARM_JOINTS: tuple[str, ...] = (
    "lbr_iiwa_joint_1",
    "lbr_iiwa_joint_2",
    "lbr_iiwa_joint_3",
    "lbr_iiwa_joint_4",
    "lbr_iiwa_joint_5",
    "lbr_iiwa_joint_6",
    "lbr_iiwa_joint_7",
)

GRIPPER_JOINTS: tuple[str, ...] = (
    "left_finger_joint",
    "right_finger_joint",
)


def lerobot_joint_names(*, robot: str, grasp_mode: str, dim: int) -> list[str]:
    """Return LeRobot feature names aligned with bridge URDF / MoveIt."""
    if robot == "kuka_iiwa":
        if grasp_mode == "gripper_urdf" and dim == len(IIWA_ARM_JOINTS) + len(GRIPPER_JOINTS):
            return list(IIWA_ARM_JOINTS) + list(GRIPPER_JOINTS)
        if dim == len(IIWA_ARM_JOINTS):
            return list(IIWA_ARM_JOINTS)
    return [f"joint_{index}" for index in range(dim)]
