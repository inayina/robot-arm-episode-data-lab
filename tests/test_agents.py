from __future__ import annotations

import numpy as np
import pytest

from agents.evaluator import EvaluatorAgent, StepObservation
from agents.task_fsm import PickLiftTaskFSM, PickPlaceTaskFSM, TaskPhase


def test_pick_lift_fsm_allocates_exact_step_budget() -> None:
    """PickLiftTaskFSM keeps the legacy four active phases."""
    fsm = PickLiftTaskFSM(np.array([0.63, 0.0, 0.025], dtype=np.float32))
    segments = fsm.allocate_phase_steps(80)

    assert sum(segment.num_steps for segment in segments) == 80
    assert [segment.phase for segment in segments] == [
        TaskPhase.REACH,
        TaskPhase.APPROACH,
        TaskPhase.CLOSE_GRIPPER,
        TaskPhase.LIFT,
    ]


def test_pick_lift_fsm_requires_minimum_steps() -> None:
    fsm = PickLiftTaskFSM(np.zeros(3, dtype=np.float32))
    with pytest.raises(ValueError, match="num_steps must be at least"):
        fsm.allocate_phase_steps(3)


# ─── PickPlaceTaskFSM 新功能测试 ────────────────────────────────────────────────

def test_pick_place_fsm_full_phase_sequence() -> None:
    """PickPlaceTaskFSM includes the full seven active phases."""
    obj_pos = np.array([0.45, 0.0, 0.025], dtype=np.float32)
    bin_pos = np.array([0.40, -0.2, 0.02], dtype=np.float32)
    fsm = PickPlaceTaskFSM(
        obj_pos,
        bin_position=bin_pos,
        language_instruction="pick up the red box and place it in the left bin",
    )

    segments = fsm.allocate_phase_steps(100)
    assert sum(s.num_steps for s in segments) == 100
    assert [s.phase for s in segments] == [
        TaskPhase.REACH,
        TaskPhase.APPROACH,
        TaskPhase.CLOSE_GRIPPER,
        TaskPhase.LIFT,
        TaskPhase.TRANSPORT,
        TaskPhase.PLACE,
        TaskPhase.RELEASE,
    ]


def test_pick_place_fsm_requires_minimum_steps() -> None:
    fsm = PickPlaceTaskFSM(np.zeros(3, dtype=np.float32))
    with pytest.raises(ValueError, match="num_steps must be at least"):
        fsm.allocate_phase_steps(6)


def test_pick_place_fsm_transport_target_uses_bin_xy() -> None:
    """TRANSPORT 阶段目标的 XY 坐标应与 bin_position 对齐。"""
    obj_pos = np.array([0.45, 0.0, 0.025], dtype=np.float32)
    bin_pos = np.array([0.40, -0.2, 0.02], dtype=np.float32)
    fsm = PickPlaceTaskFSM(obj_pos, bin_position=bin_pos)

    transport_target = fsm.target_for_phase(TaskPhase.TRANSPORT)
    assert transport_target.gripper_open is False
    np.testing.assert_allclose(transport_target.position[:2], bin_pos[:2], atol=1e-5)


def test_pick_place_fsm_release_opens_gripper() -> None:
    """RELEASE 阶段夹爪应当张开。"""
    fsm = PickPlaceTaskFSM(np.array([0.45, 0.0, 0.025], dtype=np.float32))
    release_target = fsm.target_for_phase(TaskPhase.RELEASE)
    assert release_target.gripper_open is True


def test_pick_place_fsm_language_instruction_stored() -> None:
    """language_instruction 参数应正确存储在 FSM 属性上。"""
    instr = "pick up the blue cylinder and place it in the right bin"
    fsm = PickPlaceTaskFSM(
        np.zeros(3, dtype=np.float32),
        language_instruction=instr,
    )
    assert fsm.language_instruction == instr


def test_pick_place_fsm_default_bin_position_derived_from_object() -> None:
    """未指定 bin_position 时，应自动生成默认放置点。"""
    obj_pos = np.array([0.45, 0.0, 0.025], dtype=np.float32)
    fsm = PickPlaceTaskFSM(obj_pos)
    transport_target = fsm.target_for_phase(TaskPhase.TRANSPORT)
    # 默认 bin 在物体 Y+0.2 处
    assert transport_target.position[1] == pytest.approx(0.2, abs=1e-4)


def test_pick_lift_fsm_targets_move_from_hover_to_lift() -> None:
    cube = np.array([0.63, 0.0, 0.025], dtype=np.float32)
    fsm = PickLiftTaskFSM(cube)

    reach = fsm.target_for_phase(TaskPhase.REACH)
    approach = fsm.target_for_phase(TaskPhase.APPROACH)
    lift = fsm.target_for_phase(TaskPhase.LIFT)

    assert reach.gripper_open is True
    assert approach.gripper_open is True
    assert lift.gripper_open is False
    assert reach.position[2] > approach.position[2]
    assert lift.position[2] > approach.position[2]
    np.testing.assert_allclose(reach.position[:2], cube[:2])





def test_evaluator_marks_success_when_object_is_lifted() -> None:
    evaluator = EvaluatorAgent(initial_object_z=0.025, lift_threshold=0.03)
    object_positions = np.tile(np.array([0.63, 0.0, 0.06], dtype=np.float32), (5, 1))

    result = evaluator.evaluate_success(object_positions)

    assert result.success is True
    assert result.failure_reason is None
    assert result.object_z_lift == pytest.approx(0.035)


def test_evaluator_marks_failure_when_lift_is_insufficient() -> None:
    evaluator = EvaluatorAgent(initial_object_z=0.025, lift_threshold=0.03)
    object_positions = np.tile(np.array([0.63, 0.0, 0.04], dtype=np.float32), (5, 1))

    result = evaluator.evaluate_success(object_positions)

    assert result.success is False
    assert result.failure_reason == "insufficient_lift"


def test_evaluator_aborts_on_joint_delta_spike() -> None:
    evaluator = EvaluatorAgent(initial_object_z=0.025)
    previous = np.zeros(7, dtype=np.float32)
    current = np.full(7, 1.0, dtype=np.float32)
    observation = StepObservation(
        step=1,
        joint_positions=current,
        ee_position=np.zeros(3, dtype=np.float32),
        object_position=np.array([0.63, 0.0, 0.03], dtype=np.float32),
        phase=TaskPhase.APPROACH.value,
        gripper_open=True,
    )

    reason = evaluator.inspect_step(observation, previous)

    assert reason == "joint_delta_spike"
    assert evaluator.aborted is True


def test_evaluator_aborts_when_object_falls_below_table() -> None:
    evaluator = EvaluatorAgent(initial_object_z=0.025, min_object_z=-0.02)
    observation = StepObservation(
        step=1,
        joint_positions=np.zeros(7, dtype=np.float32),
        ee_position=np.zeros(3, dtype=np.float32),
        object_position=np.array([0.63, 0.0, -0.05], dtype=np.float32),
        phase=TaskPhase.APPROACH.value,
        gripper_open=True,
    )

    reason = evaluator.inspect_step(observation, None)

    assert reason == "object_fell_below_table"
    assert evaluator.aborted is True


def test_evaluator_aborts_on_object_slipped_during_lift() -> None:
    evaluator = EvaluatorAgent(
        initial_object_z=0.025,
        require_grasp_established=True,
        max_grasp_slip_distance=0.05,
    )
    observation = StepObservation(
        step=10,
        joint_positions=np.zeros(7, dtype=np.float32),
        ee_position=np.array([0.63, 0.0, 0.20], dtype=np.float32),
        object_position=np.array([0.63, 0.0, 0.03], dtype=np.float32),
        phase=TaskPhase.LIFT.value,
        gripper_open=False,
        grasp_active=True,
    )

    reason = evaluator.inspect_step(observation, None)

    assert reason == "object_slipped"
    assert evaluator.aborted is True


def test_evaluator_success_requires_grasp_when_enabled() -> None:
    evaluator = EvaluatorAgent(
        initial_object_z=0.025,
        lift_threshold=0.03,
        require_grasp_established=True,
    )
    object_positions = np.tile(np.array([0.63, 0.0, 0.06], dtype=np.float32), (5, 1))

    without_grasp = evaluator.evaluate_success(object_positions, grasp_established=False)
    with_grasp = evaluator.evaluate_success(object_positions, grasp_established=True)

    assert without_grasp.success is False
    assert without_grasp.failure_reason == "grasp_failed"
    assert with_grasp.success is True
    assert with_grasp.failure_reason is None
