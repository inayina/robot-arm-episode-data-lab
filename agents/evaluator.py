"""评测智能体：episode 安全检查与 success 标签。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.collision import CollisionChecker


@dataclass(frozen=True)
class StepObservation:
    step: int
    joint_positions: np.ndarray
    ee_position: np.ndarray
    object_position: np.ndarray
    phase: str
    gripper_open: bool


@dataclass(frozen=True)
class EvaluationResult:
    success: bool
    failure_reason: str | None
    aborted: bool
    object_z_lift: float


class EvaluatorAgent:
    """Monitor step safety and label pick-lift success from object lift."""

    def __init__(
        self,
        initial_object_z: float,
        *,
        lift_threshold: float = 0.03,
        max_joint_delta: float = 0.75,
        min_object_z: float = -0.02,
        collision_checker: CollisionChecker | None = None,
    ) -> None:
        self._initial_object_z = float(initial_object_z)
        self._lift_threshold = lift_threshold
        self._max_joint_delta = max_joint_delta
        self._min_object_z = min_object_z
        self._collision_checker = collision_checker
        self._aborted = False
        self._failure_reason: str | None = None

    @property
    def aborted(self) -> bool:
        return self._aborted

    @property
    def failure_reason(self) -> str | None:
        return self._failure_reason

    def abort_with_reason(self, reason: str) -> None:
        self._abort(reason)

    def inspect_step(
        self,
        observation: StepObservation,
        previous_joint_positions: np.ndarray | None,
    ) -> str | None:
        if self._aborted:
            return self._failure_reason

        object_z = float(observation.object_position[2])
        if object_z < self._min_object_z:
            self._abort("object_fell_below_table")
            return self._failure_reason

        if previous_joint_positions is not None:
            delta = np.abs(observation.joint_positions - previous_joint_positions)
            if float(np.max(delta)) > self._max_joint_delta:
                self._abort("joint_delta_spike")
                return self._failure_reason

        if (
            self._collision_checker is not None
            and self._collision_checker.has_environment_collision()
        ):
            self._abort("unexpected_collision")
            return self._failure_reason

        return None

    def evaluate_success(self, object_positions: np.ndarray) -> EvaluationResult:
        if object_positions.ndim != 2 or object_positions.shape[1] < 3:
            raise ValueError("object_positions must have shape [T, >=3].")

        final_z = float(object_positions[-1, 2])
        object_z_lift = final_z - self._initial_object_z
        success = (not self._aborted) and object_z_lift >= self._lift_threshold
        failure_reason = self._failure_reason
        if not success and failure_reason is None:
            failure_reason = "insufficient_lift"

        return EvaluationResult(
            success=success,
            failure_reason=None if success else failure_reason,
            aborted=self._aborted,
            object_z_lift=object_z_lift,
        )

    def _abort(self, reason: str) -> None:
        self._aborted = True
        self._failure_reason = reason
