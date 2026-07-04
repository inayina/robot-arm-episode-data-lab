from __future__ import annotations

from pathlib import Path

import yaml


SCHEMA_PATH = Path("configs/robot_schemas/panda.yaml")


def load_schema() -> dict:
    return yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_panda_schema_declares_robot_and_joints() -> None:
    schema = load_schema()

    assert schema["robot"] == "panda"
    assert schema["schema_id"] == "panda_ee_delta_gripper_v0"
    assert schema["joint_names"] == [
        "panda_joint1",
        "panda_joint2",
        "panda_joint3",
        "panda_joint4",
        "panda_joint5",
        "panda_joint6",
        "panda_joint7",
    ]


def test_panda_schema_state_and_default_action_dims_are_consistent() -> None:
    schema = load_schema()
    state = schema["observation"]["state"]
    default_action_type = schema["action"]["default_type"]
    default_action = schema["action"][default_action_type]

    assert state["dim"] == len(schema["joint_names"]) + 1
    assert state["fields"] == ["joint_position[7]", "gripper_opening[1]"]
    assert default_action_type == "ee_delta_gripper"
    assert default_action["required"] is True
    assert default_action["dim"] == 7


def test_panda_schema_records_upstream_compatibility_layout() -> None:
    schema = load_schema()
    upstream = schema["compatibility"]["upstream_ros2_arm_teleoperation_suite"]
    pose_action = schema["action"]["ee_pose_gripper"]

    assert upstream["current_state_layout"] == "observation.state[7] plus observation.gripper[1]"
    assert upstream["current_action_layout"] == "ee_pose_gripper[8]"
    assert pose_action["compatibility"] == "upstream_m6_recorder_import"
    assert pose_action["dim"] == 8
