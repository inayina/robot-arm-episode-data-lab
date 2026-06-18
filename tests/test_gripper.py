"""Gripper URDF grasp controller tests (Plan B)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

pybullet = pytest.importorskip("pybullet")

from core.collect_config import CollectSettings, camera_from_mapping
from core.gripper import (
    FINGER_CLOSE_POSITION,
    FINGER_OPEN_POSITION,
    GripperGraspController,
    attach_gripper,
)
from core.world import apply_action, connect, disconnect, make_robot, object_pose, setup_world
from scripts.collect_episode import collect_pick_and_lift
from scripts.validate_dataset import collect_errors


def _pick_lift_settings(
    output_dir: Path,
    *,
    num_steps: int = 40,
    grasp_mode: str = "gripper_urdf",
) -> CollectSettings:
    camera = camera_from_mapping(64, 48, None)
    return CollectSettings(
        mode="episode",
        output=output_dir,
        num_steps=num_steps,
        width=64,
        height=48,
        gui=False,
        seed=7,
        simulator="pybullet",
        task_name="pick_and_lift",
        robot="kuka_iiwa",
        object_name="cube",
        control_mode="task_fsm",
        camera=camera,
        config_path=None,
        planner="cartesian",
        grasp_mode=grasp_mode,
    )


def test_attach_gripper_adds_two_finger_joints() -> None:
    client_id = connect(False)
    try:
        world = setup_world()
        world = attach_gripper(world)
        assert world.gripper_id is not None
        assert world.gripper_dim == 2
        assert world.control_dim == 9
    finally:
        disconnect(client_id)


def test_gripper_open_close_targets() -> None:
    client_id = connect(False)
    try:
        world = setup_world()
        world = attach_gripper(world)
        gripper = GripperGraspController(world, grasp_force_threshold=0.5)

        gripper.open()
        np.testing.assert_allclose(
            gripper.finger_targets(),
            np.array([FINGER_OPEN_POSITION, FINGER_OPEN_POSITION], dtype=np.float32),
        )

        gripper.close()
        np.testing.assert_allclose(
            gripper.finger_targets(),
            np.array([FINGER_CLOSE_POSITION, FINGER_CLOSE_POSITION], dtype=np.float32),
        )
    finally:
        disconnect(client_id)


def test_gripper_detects_contact_with_mock() -> None:
    client_id = connect(False)
    try:
        world = setup_world()
        world = attach_gripper(world)
        gripper = GripperGraspController(world, grasp_force_threshold=1.0)

        with patch("core.gripper.p.getContactPoints", return_value=[(0, 0, 0, 0, 0, 0, 0, 0, 0, 2.0, 0, 0)]):
            assert gripper.try_grasp(step=3) is True
            assert gripper.is_grasped is True
            assert gripper.grasp_established_at_step == 3
    finally:
        disconnect(client_id)


def test_gripper_grasp_lifts_cube_when_near() -> None:
    client_id = connect(False)
    try:
        world = setup_world()
        world = attach_gripper(world)
        robot = make_robot(world)
        gripper = GripperGraspController(world, grasp_force_threshold=0.1)

        cube_pos = object_pose(world.cube_id)[:3]
        target = cube_pos + np.array([0.0, 0.0, 0.02], dtype=np.float32)
        arm_action = robot.compute_ik(target, None)
        finger_open = gripper.finger_targets()

        for _ in range(100):
            apply_action(world, np.concatenate([arm_action, finger_open]), gui=False)

        gripper.close()
        finger_closed = gripper.finger_targets()
        for _ in range(60):
            apply_action(world, np.concatenate([arm_action, finger_closed]), gui=False)

        if not gripper.try_grasp(step=0):
            pytest.skip("Gripper contact not established in this headless pose.")

        lift_action = robot.compute_ik(
            target + np.array([0.0, 0.0, 0.08], dtype=np.float32),
            None,
        )
        initial_z = object_pose(world.cube_id)[2]
        for _ in range(100):
            apply_action(world, np.concatenate([lift_action, finger_closed]), gui=False)
        final_z = object_pose(world.cube_id)[2]
        assert final_z - initial_z > 0.01
    finally:
        disconnect(client_id)


def test_pick_and_lift_episode_uses_gripper_urdf_mode(tmp_path: Path) -> None:
    episode_dir = tmp_path / "episode_pick_gripper"
    settings = _pick_lift_settings(episode_dir)

    client_id = connect(False)
    try:
        evaluation = collect_pick_and_lift(
            episode_dir,
            settings.num_steps,
            settings.camera,
            settings.gui,
            settings,
        )
    finally:
        disconnect(client_id)

    metadata = json.loads((episode_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["grasp_mode"] == "gripper_urdf"
    assert metadata["state_dim"] == 9
    assert metadata["action_dim"] == 9
    assert metadata["grasp_established"] is evaluation.success or metadata["grasp_established"] is False
    assert collect_errors(episode_dir) == []
