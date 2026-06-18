"""评测智能体：episode 安全检查与 success 标签。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.collision import CollisionChecker

# pick_and_lift 评测可能写入 metadata.failure_reason 的取值
FAILURE_REASONS = frozenset(
    {
        "grasp_failed",
        "object_slipped",
        "insufficient_lift",
        "object_fell_below_table",
        "joint_delta_spike",
        "unexpected_collision",
        "planning_failed",
        "start_in_collision",
        "goal_in_collision",
        "timeout",
        "ik_unreachable",
    }
)


@dataclass(frozen=True)
class StepObservation:
    step: int
    joint_positions: np.ndarray
    ee_position: np.ndarray
    object_position: np.ndarray
    phase: str
    gripper_open: bool
    grasp_active: bool = False


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
        max_grasp_slip_distance: float = 0.10,
        collision_checker: CollisionChecker | None = None,
        require_grasp_established: bool = False,
    ) -> None:
        self._initial_object_z = float(initial_object_z)
        self._lift_threshold = lift_threshold
        self._max_joint_delta = max_joint_delta
        self._min_object_z = min_object_z
        self._max_grasp_slip_distance = max_grasp_slip_distance
        self._collision_checker = collision_checker
        self._require_grasp_established = require_grasp_established
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

        if observation.phase == "lift" and self._require_grasp_established:
            if not observation.grasp_active:
                self._abort("grasp_failed")
                return self._failure_reason
            slip_distance = float(
                np.linalg.norm(observation.ee_position - observation.object_position)
            )
            if slip_distance > self._max_grasp_slip_distance:
                self._abort("object_slipped")
                return self._failure_reason

        return None

    def evaluate_success(
        self,
        object_positions: np.ndarray,
        *,
        grasp_established: bool = False,
    ) -> EvaluationResult:
        if object_positions.ndim != 2 or object_positions.shape[1] < 3:
            raise ValueError("object_positions must have shape [T, >=3].")

        final_z = float(object_positions[-1, 2])
        object_z_lift = final_z - self._initial_object_z
        success = (not self._aborted) and object_z_lift >= self._lift_threshold
        if self._require_grasp_established:
            success = success and grasp_established
        failure_reason = self._failure_reason
        if not success and failure_reason is None:
            if self._require_grasp_established and not grasp_established:
                failure_reason = "grasp_failed"
            else:
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
