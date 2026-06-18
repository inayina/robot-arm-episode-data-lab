"""Pick-lift 任务规划有限状态机。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class TaskPhase(str, Enum):
    REACH = "reach"
    APPROACH = "approach"
    CLOSE_GRIPPER = "close_gripper"
    LIFT = "lift"
    DONE = "done"


PHASE_ORDER = (
    TaskPhase.REACH,
    TaskPhase.APPROACH,
    TaskPhase.CLOSE_GRIPPER,
    TaskPhase.LIFT,
    TaskPhase.DONE,
)

PHASE_FRACTIONS = {
    TaskPhase.REACH: 0.30,
    TaskPhase.APPROACH: 0.25,
    TaskPhase.CLOSE_GRIPPER: 0.15,
    TaskPhase.LIFT: 0.30,
}


@dataclass(frozen=True)
class PhaseTarget:
    position: np.ndarray
    gripper_open: bool


@dataclass(frozen=True)
class PhaseSegment:
    phase: TaskPhase
    num_steps: int


class PickLiftTaskFSM:
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
        self._cube_position = np.asarray(cube_position, dtype=np.float32).reshape(3)
        self._reach_offset_z = reach_offset_z
        self._approach_offset_z = approach_offset_z
        self._lift_offset_z = lift_offset_z
        self._grasp_distance_threshold = grasp_distance_threshold
        self._phase_index = 0

    @property
    def current_phase(self) -> TaskPhase:
        return PHASE_ORDER[min(self._phase_index, len(PHASE_ORDER) - 1)]

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

    def allocate_phase_steps(self, num_steps: int) -> list[PhaseSegment]:
        if num_steps < len(PHASE_ORDER) - 1:
            raise ValueError(
                f"num_steps must be at least {len(PHASE_ORDER) - 1}, got {num_steps}."
            )

        active_phases = PHASE_ORDER[:-1]
        raw_counts = {
            phase: num_steps * PHASE_FRACTIONS[phase] for phase in active_phases
        }
        counts = {phase: max(1, int(round(raw_counts[phase]))) for phase in active_phases}

        total = sum(counts.values())
        while total > num_steps:
            phase = max(active_phases, key=lambda item: counts[item])
            counts[phase] -= 1
            total -= 1
        while total < num_steps:
            phase = max(active_phases, key=lambda item: PHASE_FRACTIONS[item])
            counts[phase] += 1
            total += 1

        return [PhaseSegment(phase=phase, num_steps=counts[phase]) for phase in active_phases]

    def advance(self) -> TaskPhase:
        if self._phase_index < len(PHASE_ORDER) - 1:
            self._phase_index += 1
        return self.current_phase

    def reset(self) -> None:
        self._phase_index = 0

    def is_done(self) -> bool:
        return self.current_phase == TaskPhase.DONE

    def should_close_gripper(
        self,
        ee_position: np.ndarray,
        phase: TaskPhase,
    ) -> bool:
        if phase != TaskPhase.CLOSE_GRIPPER:
            return False
        distance = float(np.linalg.norm(ee_position - self._cube_position))
        return distance <= self._grasp_distance_threshold
