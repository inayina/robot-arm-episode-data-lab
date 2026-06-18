#!/usr/bin/env python3
"""采集 PyBullet 机械臂 episode 数据。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.evaluator import EvaluatorAgent, EvaluationResult, StepObservation
from agents.motion_planner import (
    PlanningResult,
    plan_cartesian_segment,
    plan_rrt_segment,
)
from agents.task_fsm import PickLiftTaskFSM, TaskPhase
from core.collect_config import (
    DEFAULT_CONFIG_PATH,
    CameraConfig,
    CollectSettings,
    resolve_settings,
    settings_from_config,
)
from core.episode_writer import (
    build_metadata,
    prepare_episode_dir,
    save_episode_arrays,
    save_png,
    write_metadata,
)
from core.collision import CollisionChecker
from core.grasp import ConstraintGraspController
from core.ik import solve_ik
from core.joint_limits import JointLimits, get_joint_limits
from core.pybullet_robot import PyBulletRobot
from core.rrt import RRTConfig
from core.world import (
    World,
    apply_action,
    build_cartesian_actions,
    connect,
    disconnect,
    joint_positions,
    link_pose,
    make_collision_checker,
    make_robot,
    object_pose,
    render_rgb,
    setup_world,
    smooth_trajectory,
)

# Backward-compatible re-exports for scripts/tests that import from collect_episode.
__all__ = [
    "CameraConfig",
    "CollectSettings",
    "DEFAULT_CONFIG_PATH",
    "World",
    "apply_action",
    "build_cartesian_actions",
    "connect",
    "collect_episode",
    "collect_pick_and_lift",
    "make_collision_checker",
    "make_robot",
    "render_rgb",
    "resolve_settings",
    "settings_from_config",
    "setup_world",
    "smooth_trajectory",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect V0 or V1 PyBullet robot-arm episode data."
    )
    parser.add_argument(
        "--config",
        type=Path,
        nargs="?",
        const=DEFAULT_CONFIG_PATH,
        default=argparse.SUPPRESS,
        help=(
            "YAML config file. Defaults to configs/default.yaml when omitted. "
            "CLI flags override config values."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("v0", "episode"),
        default=argparse.SUPPRESS,
        help="Use v0 for one image and one joint_state.npy; episode for full V1 data.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=argparse.SUPPRESS,
        help="Output directory.",
    )
    parser.add_argument(
        "--num-steps",
        type=int,
        default=argparse.SUPPRESS,
        help="Episode length.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=argparse.SUPPRESS,
        help="Camera image width.",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=argparse.SUPPRESS,
        help="Camera image height.",
    )
    parser.add_argument("--gui", action="store_true", help="Run PyBullet with GUI.")
    parser.add_argument("--seed", type=int, default=argparse.SUPPRESS, help="Numpy random seed.")
    parser.add_argument(
        "--control-mode",
        choices=("joint_position", "cartesian_ik", "task_fsm"),
        default=argparse.SUPPRESS,
        help="Action generation strategy for episode collection.",
    )
    parser.add_argument(
        "--task",
        default=argparse.SUPPRESS,
        help="Task name, e.g. reach_cube or pick_and_lift.",
    )
    parser.add_argument(
        "--planner",
        choices=("cartesian", "rrt"),
        default=argparse.SUPPRESS,
        help="Motion planner for pick_and_lift: cartesian (default) or rrt.",
    )
    return parser.parse_args()


def collect_v0(output_dir: Path, camera: CameraConfig, gui: bool, settings: CollectSettings) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    world = setup_world()
    image = render_rgb(camera)
    save_png(output_dir / "image.png", image)
    np.save(output_dir / "joint_state.npy", joint_positions(world))
    metadata = build_metadata(
        output_dir=output_dir,
        mode="v0",
        num_steps=1,
        state_dim=len(world.joint_indices),
        action_dim=len(world.joint_indices),
        camera=camera,
        settings=settings,
    )
    write_metadata(output_dir, metadata)
    if gui:
        time.sleep(1.0)
    print(f"Wrote V0 sample to {output_dir}")


def collect_episode(
    output_dir: Path,
    num_steps: int,
    camera: CameraConfig,
    gui: bool,
    settings: CollectSettings,
    cube_xy_offset: tuple[float, float] = (0.0, 0.0),
) -> None:
    if num_steps <= 0:
        raise ValueError("--num-steps must be positive.")

    images_dir = prepare_episode_dir(output_dir)
    world = setup_world(cube_xy_offset)
    action_dim = len(world.joint_indices)

    states: list[np.ndarray] = []
    actions: list[np.ndarray] = []
    ee_poses: list[np.ndarray] = []
    object_poses: list[np.ndarray] = []

    if settings.control_mode == "cartesian_ik":
        planned_actions = build_cartesian_actions(world, num_steps)
    else:
        planned_actions = None

    for step in range(num_steps):
        if planned_actions is not None:
            action = planned_actions[step]
        else:
            action = smooth_trajectory(step, num_steps, action_dim)
        apply_action(world, action, gui)

        states.append(joint_positions(world))
        actions.append(action.astype(np.float32))
        ee_poses.append(link_pose(world.robot_id, world.ee_link_index))
        object_poses.append(object_pose(world.cube_id))
        save_png(images_dir / f"{step:06d}.png", render_rgb(camera))

    states_array = np.stack(states).astype(np.float32)
    actions_array = np.stack(actions).astype(np.float32)
    ee_poses_array = np.stack(ee_poses).astype(np.float32)
    object_poses_array = np.stack(object_poses).astype(np.float32)

    save_episode_arrays(output_dir, states_array, actions_array, ee_poses_array, object_poses_array)
    metadata = build_metadata(
        output_dir=output_dir,
        mode="episode",
        num_steps=num_steps,
        state_dim=states_array.shape[1],
        action_dim=actions_array.shape[1],
        camera=camera,
        settings=settings,
    )
    write_metadata(output_dir, metadata)
    print(f"Wrote episode with {num_steps} steps to {output_dir}")


def plan_segment_for_phase(
    robot: PyBulletRobot,
    target_position: np.ndarray,
    start_orientation: np.ndarray,
    num_steps: int,
    planner: str,
    collision_checker: CollisionChecker | None,
    joint_limits: JointLimits | None,
    rng: np.random.Generator,
) -> PlanningResult:
    start_pos, _ = robot.get_end_effector_pose()
    if planner == "rrt":
        if collision_checker is None or joint_limits is None:
            raise ValueError("RRT planner requires collision_checker and joint_limits.")
        start_q = robot.get_joint_positions()
        try:
            goal_q = solve_ik(robot, target_position, start_orientation)
        except ValueError:
            return PlanningResult(success=False, actions=[], failure_reason="ik_unreachable")
        return plan_rrt_segment(
            robot,
            start_q,
            goal_q,
            collision_checker,
            joint_limits,
            num_steps,
            rrt_config=RRTConfig(max_iterations=2500, step_size=0.12),
            rng=rng,
        )

    return plan_cartesian_segment(
        robot,
        start_pos,
        target_position,
        start_orientation,
        num_steps,
    )


def collect_pick_and_lift(
    output_dir: Path,
    num_steps: int,
    camera: CameraConfig,
    gui: bool,
    settings: CollectSettings,
    cube_xy_offset: tuple[float, float] = (0.0, 0.0),
) -> EvaluationResult:
    if num_steps < 4:
        raise ValueError("pick_and_lift requires at least 4 steps.")

    images_dir = prepare_episode_dir(output_dir)
    use_obstacles = settings.planner == "rrt"
    world = setup_world(cube_xy_offset, with_obstacles=use_obstacles)
    robot = make_robot(world)
    joint_limits = get_joint_limits(world.robot_id, world.joint_indices)
    collision_checker = make_collision_checker(world) if use_obstacles else None
    rng = np.random.default_rng(settings.seed)
    cube_pose = object_pose(world.cube_id)
    cube_position = cube_pose[:3]

    fsm = PickLiftTaskFSM(cube_position)
    grasp_controller = ConstraintGraspController(world)
    evaluator = EvaluatorAgent(
        initial_object_z=float(cube_position[2]),
        collision_checker=collision_checker,
        require_grasp_established=True,
    )
    segments = fsm.allocate_phase_steps(num_steps)

    states: list[np.ndarray] = []
    actions: list[np.ndarray] = []
    ee_poses: list[np.ndarray] = []
    object_poses: list[np.ndarray] = []
    gripper_states: list[int] = []
    phase_labels: list[str] = []

    previous_joints: np.ndarray | None = None
    last_action = robot.get_joint_positions()
    aborted = False
    planning_success = True
    planning_failure_reason: str | None = None

    for segment in segments:
        if aborted or len(states) >= num_steps:
            break

        target = fsm.target_for_phase(segment.phase)
        _, start_ori = robot.get_end_effector_pose()
        planned = plan_segment_for_phase(
            robot,
            target.position,
            start_ori,
            segment.num_steps,
            settings.planner,
            collision_checker,
            joint_limits,
            rng,
        )
        if not planned.success:
            planning_success = False
            planning_failure_reason = planned.failure_reason or "planning_failed"
            evaluator.abort_with_reason(planning_failure_reason)
            aborted = True
            break

        for action in planned.actions:
            if len(states) >= num_steps:
                break

            if segment.phase == TaskPhase.CLOSE_GRIPPER:
                grasp_controller.try_grasp(step=len(states))

            apply_action(world, action, gui)
            last_action = action.astype(np.float32)
            current_joints = joint_positions(world)
            current_object_pose = object_pose(world.cube_id)
            current_ee_pose = link_pose(world.robot_id, world.ee_link_index)

            gripper_open = not grasp_controller.is_grasped
            observation = StepObservation(
                step=len(states),
                joint_positions=current_joints,
                ee_position=current_ee_pose[:3],
                object_position=current_object_pose[:3],
                phase=segment.phase.value,
                gripper_open=gripper_open,
                grasp_active=grasp_controller.is_grasped,
            )
            if evaluator.inspect_step(observation, previous_joints):
                aborted = True

            states.append(current_joints)
            actions.append(last_action)
            ee_poses.append(current_ee_pose)
            object_poses.append(current_object_pose)
            gripper_states.append(1 if gripper_open else 0)
            phase_labels.append(segment.phase.value)
            save_png(images_dir / f"{len(states) - 1:06d}.png", render_rgb(camera))
            previous_joints = current_joints

            if aborted:
                break

    while len(states) < num_steps:
        apply_action(world, last_action, gui)
        current_joints = joint_positions(world)
        current_object_pose = object_pose(world.cube_id)
        current_ee_pose = link_pose(world.robot_id, world.ee_link_index)
        gripper_open = not grasp_controller.is_grasped

        states.append(current_joints)
        actions.append(last_action)
        ee_poses.append(current_ee_pose)
        object_poses.append(current_object_pose)
        gripper_states.append(1 if gripper_open else 0)
        phase_labels.append(TaskPhase.DONE.value)
        save_png(images_dir / f"{len(states) - 1:06d}.png", render_rgb(camera))

    object_poses_array = np.stack(object_poses).astype(np.float32)
    evaluation = evaluator.evaluate_success(
        object_poses_array,
        grasp_established=grasp_controller.is_grasped,
    )

    states_array = np.stack(states).astype(np.float32)
    actions_array = np.stack(actions).astype(np.float32)
    ee_poses_array = np.stack(ee_poses).astype(np.float32)

    save_episode_arrays(output_dir, states_array, actions_array, ee_poses_array, object_poses_array)

    task_settings = CollectSettings(
        mode=settings.mode,
        output=settings.output,
        num_steps=settings.num_steps,
        width=settings.width,
        height=settings.height,
        gui=settings.gui,
        seed=settings.seed,
        simulator=settings.simulator,
        task_name="pick_and_lift",
        robot=settings.robot,
        object_name=settings.object_name,
        control_mode="task_fsm",
        camera=settings.camera,
        config_path=settings.config_path,
        planner=settings.planner,
    )
    metadata = build_metadata(
        output_dir=output_dir,
        mode="episode",
        num_steps=num_steps,
        state_dim=states_array.shape[1],
        action_dim=actions_array.shape[1],
        camera=camera,
        settings=task_settings,
        evaluation=evaluation,
        gripper_states=gripper_states,
        phase_labels=phase_labels,
        planning_success=planning_success,
        planning_failure_reason=planning_failure_reason,
        grasp_mode="constraint",
        grasp_established=grasp_controller.is_grasped,
        grasp_established_at_step=grasp_controller.grasp_established_at_step,
    )
    write_metadata(output_dir, metadata)
    grasp_controller.release()
    print(
        f"Wrote pick_and_lift episode with {num_steps} steps to {output_dir} "
        f"(success={evaluation.success}, object_z_lift={evaluation.object_z_lift:.4f})"
    )
    return evaluation


def main() -> int:
    args = parse_args()
    settings = resolve_settings(args)
    np.random.seed(settings.seed)
    client_id = connect(settings.gui)
    try:
        if settings.mode == "v0":
            collect_v0(settings.output, settings.camera, settings.gui, settings)
        elif settings.task_name == "pick_and_lift":
            collect_pick_and_lift(
                settings.output,
                settings.num_steps,
                settings.camera,
                settings.gui,
                settings,
            )
        else:
            collect_episode(
                settings.output,
                settings.num_steps,
                settings.camera,
                settings.gui,
                settings,
            )
    finally:
        disconnect(client_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
