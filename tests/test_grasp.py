"""Grasp controller and pick-lift physics integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pybullet = pytest.importorskip("pybullet")

from agents.evaluator import EvaluatorAgent, StepObservation
from agents.task_fsm import TaskPhase
from core.collect_config import CollectSettings, camera_from_mapping
from core.grasp import ConstraintGraspController
from core.world import (
    apply_action,
    connect,
    disconnect,
    make_robot,
    object_pose,
    setup_world,
)
from scripts.collect_episode import collect_pick_and_lift
from scripts.validate_dataset import collect_errors


def _pick_lift_settings(output_dir: Path, *, num_steps: int = 40) -> CollectSettings:
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
    )


def test_grasp_fails_when_too_far() -> None:
    client_id = connect(False)
    try:
        world = setup_world()
        robot = make_robot(world)
        far_target = np.array([0.2, 0.2, 0.5], dtype=np.float32)
        action = robot.compute_ik(far_target, None)
        for _ in range(40):
            apply_action(world, action, gui=False)

        grasp = ConstraintGraspController(
            world,
            max_grasp_distance=0.02,
            max_grasp_xy_distance=0.02,
        )
        assert grasp.try_grasp() is False
        assert grasp.is_grasped is False
    finally:
        disconnect(client_id)


def test_grasp_succeeds_near_cube() -> None:
    client_id = connect(False)
    try:
        world = setup_world()
        robot = make_robot(world)
        cube_pos = object_pose(world.cube_id)[:3]
        target = cube_pos + np.array([0.0, 0.0, 0.03], dtype=np.float32)
        action = robot.compute_ik(target, None)
        for _ in range(80):
            apply_action(world, action, gui=False)

        grasp = ConstraintGraspController(world, max_grasp_distance=0.08)
        assert grasp.try_grasp(step=0) is True
        assert grasp.is_grasped is True

        lift_action = robot.compute_ik(target + np.array([0.0, 0.0, 0.08], dtype=np.float32), None)
        initial_z = object_pose(world.cube_id)[2]
        for _ in range(80):
            apply_action(world, lift_action, gui=False)
        final_z = object_pose(world.cube_id)[2]
        assert final_z - initial_z > 0.015
        grasp.release()
    finally:
        disconnect(client_id)


def test_try_grasp_is_idempotent() -> None:
    client_id = connect(False)
    try:
        world = setup_world()
        grasp = ConstraintGraspController(world, max_grasp_distance=0.5)
        with patch("core.grasp.p.createConstraint", return_value=1) as create_constraint:
            with patch("core.grasp.p.changeConstraint"):
                with patch("core.grasp.p.getContactPoints", return_value=[object()]):
                    assert grasp.try_grasp() is True
                    assert grasp.try_grasp() is True
                    create_constraint.assert_called_once()
    finally:
        disconnect(client_id)


def test_evaluator_grasp_failed_without_grasp() -> None:
    evaluator = EvaluatorAgent(
        initial_object_z=0.025,
        require_grasp_established=True,
    )
    object_positions = np.tile(np.array([0.63, 0.0, 0.06], dtype=np.float32), (5, 1))

    result = evaluator.evaluate_success(object_positions, grasp_established=False)

    assert result.success is False
    assert result.failure_reason == "grasp_failed"


def test_evaluator_aborts_on_lift_without_grasp() -> None:
    evaluator = EvaluatorAgent(
        initial_object_z=0.025,
        require_grasp_established=True,
    )
    observation = StepObservation(
        step=1,
        joint_positions=np.zeros(7, dtype=np.float32),
        ee_position=np.array([0.63, 0.0, 0.08], dtype=np.float32),
        object_position=np.array([0.63, 0.0, 0.03], dtype=np.float32),
        phase=TaskPhase.LIFT.value,
        gripper_open=True,
        grasp_active=False,
    )

    reason = evaluator.inspect_step(observation, None)

    assert reason == "grasp_failed"
    assert evaluator.aborted is True


def test_pick_and_lift_episode_uses_constraint_grasp(tmp_path: Path) -> None:
    episode_dir = tmp_path / "episode_pick_phys"
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
    assert metadata["grasp_mode"] == "constraint"
    assert metadata["grasp_established"] is True
    assert metadata["success"] is evaluation.success
    assert evaluation.success is True
    assert collect_errors(episode_dir) == []

    collect_source = Path(__file__).resolve().parents[1] / "scripts" / "collect_episode.py"
    assert "sync_object_to_grasp_offset" not in collect_source.read_text(encoding="utf-8")
