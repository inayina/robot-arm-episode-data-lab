"""任务规划有限状态机。

保留 legacy pick-lift 四阶段 FSM，同时提供 pick-place 七阶段 FSM。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class TaskPhase(str, Enum):
    REACH = "reach"
    APPROACH = "approach"
    CLOSE_GRIPPER = "close_gripper"
    LIFT = "lift"
    TRANSPORT = "transport"
    PLACE = "place"
    RELEASE = "release"
    DONE = "done"


PICK_LIFT_PHASE_ORDER = (
    TaskPhase.REACH,
    TaskPhase.APPROACH,
    TaskPhase.CLOSE_GRIPPER,
    TaskPhase.LIFT,
    TaskPhase.DONE,
)

PICK_PLACE_PHASE_ORDER = (
    TaskPhase.REACH,
    TaskPhase.APPROACH,
    TaskPhase.CLOSE_GRIPPER,
    TaskPhase.LIFT,
    TaskPhase.TRANSPORT,
    TaskPhase.PLACE,
    TaskPhase.RELEASE,
    TaskPhase.DONE,
)

PICK_LIFT_PHASE_FRACTIONS = {
    TaskPhase.REACH: 0.30,
    TaskPhase.APPROACH: 0.25,
    TaskPhase.CLOSE_GRIPPER: 0.15,
    TaskPhase.LIFT: 0.30,
}

PICK_PLACE_PHASE_FRACTIONS = {
    TaskPhase.REACH: 0.20,
    TaskPhase.APPROACH: 0.15,
    TaskPhase.CLOSE_GRIPPER: 0.10,
    TaskPhase.LIFT: 0.20,
    TaskPhase.TRANSPORT: 0.20,
    TaskPhase.PLACE: 0.10,
    TaskPhase.RELEASE: 0.05,
}


@dataclass(frozen=True)
class PhaseTarget:
    position: np.ndarray
    gripper_open: bool


@dataclass(frozen=True)
class PhaseSegment:
    phase: TaskPhase
    num_steps: int


class _PhaseBudgetMixin:
    _phase_order: tuple[TaskPhase, ...]
    _phase_fractions: dict[TaskPhase, float]
    _phase_index: int

    @property
    def current_phase(self) -> TaskPhase:
        return self._phase_order[min(self._phase_index, len(self._phase_order) - 1)]

    def allocate_phase_steps(self, num_steps: int) -> list[PhaseSegment]:
        active_phases = self._phase_order[:-1]
        if num_steps < len(active_phases):
            raise ValueError(
                f"num_steps must be at least {len(active_phases)}, got {num_steps}."
            )

        raw_counts = {phase: num_steps * self._phase_fractions[phase] for phase in active_phases}
        counts = {phase: max(1, int(round(raw_counts[phase]))) for phase in active_phases}

        total = sum(counts.values())
        while total > num_steps:
            phase = max(active_phases, key=lambda p: counts[p])
            counts[phase] -= 1
            total -= 1
        while total < num_steps:
            phase = max(active_phases, key=lambda p: self._phase_fractions[p])
            counts[phase] += 1
            total += 1

        return [PhaseSegment(phase=phase, num_steps=counts[phase]) for phase in active_phases]

    def advance(self) -> TaskPhase:
        if self._phase_index < len(self._phase_order) - 1:
            self._phase_index += 1
        return self.current_phase

    def reset(self) -> None:
        self._phase_index = 0

    def is_done(self) -> bool:
        return self.current_phase == TaskPhase.DONE


class PickLiftTaskFSM(_PhaseBudgetMixin):
    """reach → approach → close_gripper → lift 任务状态机。"""

    LANGUAGE_INSTRUCTION = "pick up the cube"

    def __init__(
        self,
        cube_position: np.ndarray,
        *,
        reach_offset_z: float = 0.15,
        approach_offset_z: float = 0.05,
        lift_offset_z: float = 0.20,
        grasp_distance_threshold: float = 0.06,
    ) -> None:
        self._phase_order = PICK_LIFT_PHASE_ORDER
        self._phase_fractions = PICK_LIFT_PHASE_FRACTIONS
        self._cube_position = np.asarray(cube_position, dtype=np.float32).reshape(3)
        self._reach_offset_z = reach_offset_z
        self._approach_offset_z = approach_offset_z
        self._lift_offset_z = lift_offset_z
        self._grasp_distance_threshold = grasp_distance_threshold
        self._phase_index = 0

    @property
    def grasp_distance_threshold(self) -> float:
        return self._grasp_distance_threshold

    def target_for_phase(self, phase: TaskPhase) -> PhaseTarget:
        x, y, z = self._cube_position
        if phase == TaskPhase.REACH:
            return PhaseTarget(
                position=np.array([x, y, z + self._reach_offset_z], dtype=np.float32),
                gripper_open=True,
            )
        if phase == TaskPhase.APPROACH:
            return PhaseTarget(
                position=np.array([x, y, z + self._approach_offset_z], dtype=np.float32),
                gripper_open=True,
            )
        if phase == TaskPhase.CLOSE_GRIPPER:
            return PhaseTarget(
                position=np.array([x, y, z + self._approach_offset_z], dtype=np.float32),
                gripper_open=False,
            )
        if phase == TaskPhase.LIFT:
            return PhaseTarget(
                position=np.array([x, y, z + self._lift_offset_z], dtype=np.float32),
                gripper_open=False,
            )
        approach = self.target_for_phase(TaskPhase.APPROACH)
        return PhaseTarget(position=approach.position.copy(), gripper_open=False)

    def should_close_gripper(
        self,
        ee_position: np.ndarray,
        phase: TaskPhase,
    ) -> bool:
        if phase != TaskPhase.CLOSE_GRIPPER:
            return False
        distance = float(np.linalg.norm(ee_position - self._cube_position))
        return distance <= self._grasp_distance_threshold


class PickPlaceTaskFSM(_PhaseBudgetMixin):
    """reach → approach → close_gripper → lift → transport → place → release 任务状态机。"""

    LANGUAGE_INSTRUCTION = "pick up the object and place it in the bin"

    def __init__(
        self,
        object_position: np.ndarray,
        *,
        bin_position: np.ndarray | None = None,
        language_instruction: str = LANGUAGE_INSTRUCTION,
        reach_offset_z: float = 0.15,
        approach_offset_z: float = 0.05,
        lift_offset_z: float = 0.20,
        place_offset_z: float = 0.08,
        grasp_distance_threshold: float = 0.06,
    ) -> None:
        self._phase_order = PICK_PLACE_PHASE_ORDER
        self._phase_fractions = PICK_PLACE_PHASE_FRACTIONS
        self._object_position = np.asarray(object_position, dtype=np.float32).reshape(3)
        if bin_position is None:
            default_bin = self._object_position.copy()
            default_bin[1] += 0.20
            self._bin_position = default_bin
        else:
            self._bin_position = np.asarray(bin_position, dtype=np.float32).reshape(3)
        self.language_instruction = str(language_instruction)
        self._reach_offset_z = reach_offset_z
        self._approach_offset_z = approach_offset_z
        self._lift_offset_z = lift_offset_z
        self._place_offset_z = place_offset_z
        self._grasp_distance_threshold = grasp_distance_threshold
        self._phase_index = 0

    @property
    def grasp_distance_threshold(self) -> float:
        return self._grasp_distance_threshold

    def target_for_phase(self, phase: TaskPhase) -> PhaseTarget:
        ox, oy, oz = self._object_position
        bx, by, bz = self._bin_position

        if phase == TaskPhase.REACH:
            return PhaseTarget(
                position=np.array([ox, oy, oz + self._reach_offset_z], dtype=np.float32),
                gripper_open=True,
            )
        if phase == TaskPhase.APPROACH:
            return PhaseTarget(
                position=np.array([ox, oy, oz + self._approach_offset_z], dtype=np.float32),
                gripper_open=True,
            )
        if phase == TaskPhase.CLOSE_GRIPPER:
            return PhaseTarget(
                position=np.array([ox, oy, oz + self._approach_offset_z], dtype=np.float32),
                gripper_open=False,
            )
        if phase == TaskPhase.LIFT:
            return PhaseTarget(
                position=np.array([ox, oy, oz + self._lift_offset_z], dtype=np.float32),
                gripper_open=False,
            )
        if phase == TaskPhase.TRANSPORT:
            return PhaseTarget(
                position=np.array([bx, by, oz + self._lift_offset_z], dtype=np.float32),
                gripper_open=False,
            )
        if phase == TaskPhase.PLACE:
            return PhaseTarget(
                position=np.array([bx, by, bz + self._place_offset_z], dtype=np.float32),
                gripper_open=False,
            )
        if phase == TaskPhase.RELEASE:
            return PhaseTarget(
                position=np.array([bx, by, bz + self._place_offset_z], dtype=np.float32),
                gripper_open=True,
            )
        return PhaseTarget(
            position=np.array([bx, by, bz + self._place_offset_z], dtype=np.float32),
            gripper_open=True,
        )

    def should_close_gripper(
        self,
        ee_position: np.ndarray,
        phase: TaskPhase,
    ) -> bool:
        if phase != TaskPhase.CLOSE_GRIPPER:
            return False
        distance = float(np.linalg.norm(ee_position - self._object_position))
        return distance <= self._grasp_distance_threshold
