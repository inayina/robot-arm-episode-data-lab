#!/usr/bin/env python3
"""采集 PyBullet 机械臂 episode 数据。"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from PIL import Image

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
from core.collision import CollisionChecker
from core.ik import solve_ik
from core.joint_limits import JointLimits, get_joint_limits
from core.pybullet_robot import PyBulletRobot
from core.rrt import RRTConfig
from core.trajectory import interpolate_cartesian_line

try:
    import pybullet as p
    import pybullet_data
except ImportError:  # pragma: no cover - exercised only without deps.
    p = None
    pybullet_data = None


DEFAULT_CONFIG_PATH = REPO_ROOT / "configs" / "default.yaml"


@dataclass(frozen=True)
class CameraConfig:
    width: int = 640
    height: int = 480
    eye: tuple[float, float, float] = (1.15, -1.05, 0.85)
    target: tuple[float, float, float] = (0.45, 0.0, 0.25)
    up: tuple[float, float, float] = (0.0, 0.0, 1.0)
    fov: float = 55.0
    type: str = "fixed_rgb"


@dataclass(frozen=True)
class CollectSettings:
    mode: str
    output: Path
    num_steps: int
    width: int
    height: int
    gui: bool
    seed: int
    simulator: str
    task_name: str
    robot: str
    object_name: str
    control_mode: str
    camera: CameraConfig
    config_path: Path | None
    planner: str = "cartesian"


@dataclass(frozen=True)
class World:
    robot_id: int
    cube_id: int
    joint_indices: list[int]
    ee_link_index: int
    plane_id: int
    obstacle_ids: tuple[int, ...] = ()


FRAME_NAME_RE = re.compile(r"^\d{6}\.png$")


def resolve_config_path(config_path: Path) -> Path:
    if config_path.is_absolute():
        return config_path
    cwd_candidate = Path.cwd() / config_path
    if cwd_candidate.exists():
        return cwd_candidate
    repo_candidate = REPO_ROOT / config_path
    if repo_candidate.exists():
        return repo_candidate
    return cwd_candidate


def _as_float_triplet(value: Any, field_name: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{field_name} must be a list of three numbers.")
    return (float(value[0]), float(value[1]), float(value[2]))


def load_yaml_config(config_path: Path) -> dict[str, Any]:
    resolved = resolve_config_path(config_path)
    if not resolved.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with resolved.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config root must be a mapping: {resolved}")
    return raw


def camera_from_mapping(
    image_width: int,
    image_height: int,
    camera_mapping: dict[str, Any] | None,
) -> CameraConfig:
    camera_mapping = camera_mapping or {}
    return CameraConfig(
        width=image_width,
        height=image_height,
        eye=_as_float_triplet(
            camera_mapping.get("eye", [1.15, -1.05, 0.85]),
            "camera.eye",
        ),
        target=_as_float_triplet(
            camera_mapping.get("target", [0.45, 0.0, 0.25]),
            "camera.target",
        ),
        up=_as_float_triplet(
            camera_mapping.get("up", [0.0, 0.0, 1.0]),
            "camera.up",
        ),
        fov=float(camera_mapping.get("fov", 55.0)),
        type=str(camera_mapping.get("type", "fixed_rgb")),
    )


def settings_from_config(config_path: Path) -> CollectSettings:
    config = load_yaml_config(config_path)
    camera_mapping = config.get("camera")
    if camera_mapping is not None and not isinstance(camera_mapping, dict):
        raise ValueError("camera must be a mapping in the config file.")

    width = int(config.get("image_width", 640))
    height = int(config.get("image_height", 480))
    output_raw = config.get("output_dir", "dataset_sample/episode_000001")

    return CollectSettings(
        mode="episode",
        output=Path(str(output_raw)),
        num_steps=int(config.get("num_steps", 100)),
        width=width,
        height=height,
        gui=False,
        seed=int(config.get("seed", 7)),
        simulator=str(config.get("simulator", "pybullet")),
        task_name=str(config.get("task_name", "reach_cube")),
        robot=str(config.get("robot", "kuka_iiwa")),
        object_name=str(config.get("object", "cube")),
        control_mode=str(config.get("control_mode", "joint_position")),
        camera=camera_from_mapping(width, height, camera_mapping),
        config_path=resolve_config_path(config_path),
    )


def resolve_settings(args: argparse.Namespace) -> CollectSettings:
    config_arg = getattr(args, "config", None)
    if config_arg is None:
        base = settings_from_config(DEFAULT_CONFIG_PATH)
        config_path: Path | None = None
    else:
        config_path = resolve_config_path(Path(config_arg))
        base = settings_from_config(config_path)

    output = Path(getattr(args, "output", None) or base.output)
    mode = getattr(args, "mode", None) or base.mode
    num_steps = getattr(args, "num_steps", None) or base.num_steps
    width = getattr(args, "width", None) or base.width
    height = getattr(args, "height", None) or base.height
    seed = getattr(args, "seed", None) or base.seed
    gui = bool(getattr(args, "gui", False))

    camera = camera_from_mapping(
        width,
        height,
        {
            "type": base.camera.type,
            "eye": list(base.camera.eye),
            "target": list(base.camera.target),
            "up": list(base.camera.up),
            "fov": base.camera.fov,
        },
    )

    control_mode = getattr(args, "control_mode", None) or base.control_mode
    task_name = getattr(args, "task", None) or base.task_name
    planner = getattr(args, "planner", None) or base.planner

    return CollectSettings(
        mode=mode,
        output=output,
        num_steps=num_steps,
        width=width,
        height=height,
        gui=gui,
        seed=seed,
        simulator=base.simulator,
        task_name=task_name,
        robot=base.robot,
        object_name=base.object_name,
        control_mode=control_mode,
        camera=camera,
        config_path=config_path if config_arg is not None else None,
        planner=planner,
    )


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


def connect(gui: bool) -> int:
    if p is None or pybullet_data is None:
        raise SystemExit(
            "Missing dependency: pybullet. Install dependencies with "
            "`python -m pip install -r requirements.txt`."
        )
    connection_mode = p.GUI if gui else p.DIRECT
    client_id = p.connect(connection_mode)
    if client_id < 0:
        raise RuntimeError("Failed to connect to PyBullet.")
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    return client_id


def setup_world(
    cube_xy_offset: tuple[float, float] = (0.0, 0.0),
    *,
    with_obstacles: bool = False,
) -> World:
    p.resetSimulation()
    p.setGravity(0.0, 0.0, -9.81)
    plane_id = p.loadURDF("plane.urdf")

    robot_id = p.loadURDF(
        "kuka_iiwa/model.urdf",
        basePosition=(0.0, 0.0, 0.0),
        useFixedBase=True,
    )
    cube_id = p.loadURDF(
        "cube_small.urdf",
        basePosition=(
            0.63 + float(cube_xy_offset[0]),
            0.0 + float(cube_xy_offset[1]),
            0.025,
        ),
        baseOrientation=p.getQuaternionFromEuler((0.0, 0.0, 0.0)),
    )

    obstacle_ids: list[int] = []
    if with_obstacles:
        obstacle_shape = p.createCollisionShape(
            p.GEOM_BOX,
            halfExtents=[0.05, 0.05, 0.15],
        )
        obstacle_visual = p.createVisualShape(
            p.GEOM_BOX,
            halfExtents=[0.05, 0.05, 0.15],
            rgbaColor=[0.8, 0.2, 0.2, 1.0],
        )
        obstacle_id = p.createMultiBody(
            baseMass=0.0,
            baseCollisionShapeIndex=obstacle_shape,
            baseVisualShapeIndex=obstacle_visual,
            basePosition=(0.52, 0.12, 0.10),
        )
        obstacle_ids.append(obstacle_id)

    joint_indices = get_controlled_joints(robot_id)
    initial_positions = np.array([0.0, 0.45, 0.0, -1.35, 0.0, 1.1, 0.0])
    initial_positions = initial_positions[: len(joint_indices)]
    for joint_index, joint_position in zip(joint_indices, initial_positions):
        p.resetJointState(robot_id, joint_index, float(joint_position))

    for _ in range(20):
        p.stepSimulation()

    return World(
        robot_id=robot_id,
        cube_id=cube_id,
        joint_indices=joint_indices,
        ee_link_index=joint_indices[-1],
        plane_id=plane_id,
        obstacle_ids=tuple(obstacle_ids),
    )


def make_collision_checker(world: World) -> CollisionChecker:
    return CollisionChecker(
        robot_id=world.robot_id,
        obstacle_ids=list(world.obstacle_ids),
        joint_indices=world.joint_indices,
        ee_link_index=world.ee_link_index,
        ignore_pairs=[(world.robot_id, world.cube_id)],
    )


def get_controlled_joints(robot_id: int) -> list[int]:
    controlled_types = {p.JOINT_REVOLUTE, p.JOINT_PRISMATIC}
    joints: list[int] = []
    for joint_index in range(p.getNumJoints(robot_id)):
        joint_info = p.getJointInfo(robot_id, joint_index)
        if joint_info[2] in controlled_types:
            joints.append(joint_index)
    if not joints:
        raise RuntimeError("No controllable joints found on robot.")
    return joints


def render_rgb(camera: CameraConfig) -> np.ndarray:
    view = p.computeViewMatrix(
        cameraEyePosition=camera.eye,
        cameraTargetPosition=camera.target,
        cameraUpVector=camera.up,
    )
    projection = p.computeProjectionMatrixFOV(
        fov=camera.fov,
        aspect=float(camera.width) / float(camera.height),
        nearVal=0.02,
        farVal=3.5,
    )
    _, _, rgba, _, _ = p.getCameraImage(
        width=camera.width,
        height=camera.height,
        viewMatrix=view,
        projectionMatrix=projection,
        renderer=p.ER_TINY_RENDERER,
    )
    rgba_array = np.asarray(rgba, dtype=np.uint8).reshape(
        camera.height, camera.width, 4
    )
    return rgba_array[:, :, :3]


def joint_positions(world: World) -> np.ndarray:
    states = p.getJointStates(world.robot_id, world.joint_indices)
    return np.asarray([state[0] for state in states], dtype=np.float32)


def link_pose(robot_id: int, link_index: int) -> np.ndarray:
    link_state = p.getLinkState(robot_id, link_index, computeForwardKinematics=True)
    position = link_state[4]
    orientation = link_state[5]
    return np.asarray((*position, *orientation), dtype=np.float32)


def object_pose(object_id: int) -> np.ndarray:
    position, orientation = p.getBasePositionAndOrientation(object_id)
    return np.asarray((*position, *orientation), dtype=np.float32)


def smooth_trajectory(step: int, num_steps: int, action_dim: int) -> np.ndarray:
    if num_steps <= 1:
        alpha = 1.0
    else:
        alpha = step / float(num_steps - 1)
    alpha = 0.5 - 0.5 * math.cos(math.pi * alpha)

    start = np.array([0.0, 0.45, 0.0, -1.35, 0.0, 1.1, 0.0], dtype=np.float32)
    end = np.array([-0.35, 0.65, 0.2, -1.15, -0.1, 1.35, 0.25], dtype=np.float32)
    start = start[:action_dim]
    end = end[:action_dim]
    return (1.0 - alpha) * start + alpha * end


def make_robot(world: World) -> PyBulletRobot:
    return PyBulletRobot(
        robot_id=world.robot_id,
        joint_indices=world.joint_indices,
        ee_link_index=world.ee_link_index,
    )


def build_cartesian_actions(world: World, num_steps: int) -> list[np.ndarray]:
    robot = make_robot(world)
    start_pos, start_ori = robot.get_end_effector_pose()
    cube_pos = object_pose(world.cube_id)[:3]

    direction = cube_pos - start_pos
    distance = float(np.linalg.norm(direction))
    if distance < 1e-6:
        unit = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        move_distance = 0.08
    else:
        unit = direction / distance
        move_distance = min(0.10, distance * 0.8)

    target_pos = start_pos + unit * move_distance
    waypoints = interpolate_cartesian_line(
        start_pos,
        target_pos,
        num_steps,
        start_orientation=start_ori,
        end_orientation=start_ori,
    )
    return [solve_ik(robot, pos, ori) for pos, ori in waypoints]


def sync_object_to_grasp_offset(
    world: World,
    grasp_offset: np.ndarray,
) -> None:
    ee_state = p.getLinkState(
        world.robot_id,
        world.ee_link_index,
        computeForwardKinematics=True,
    )
    ee_position = np.asarray(ee_state[4], dtype=np.float32)
    _, cube_orientation = p.getBasePositionAndOrientation(world.cube_id)
    target_position = (ee_position + grasp_offset).tolist()
    p.resetBasePositionAndOrientation(
        world.cube_id,
        target_position,
        cube_orientation,
    )


def apply_action(world: World, action: np.ndarray, gui: bool) -> None:
    p.setJointMotorControlArray(
        bodyUniqueId=world.robot_id,
        jointIndices=world.joint_indices,
        controlMode=p.POSITION_CONTROL,
        targetPositions=action.tolist(),
        forces=[120.0] * len(world.joint_indices),
    )
    for _ in range(4):
        p.stepSimulation()
        if gui:
            time.sleep(1.0 / 240.0)


def prepare_episode_dir(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    for frame_path in images_dir.glob("*.png"):
        if FRAME_NAME_RE.match(frame_path.name):
            frame_path.unlink()
    return images_dir


def save_png(path: Path, rgb: np.ndarray) -> None:
    Image.fromarray(rgb, mode="RGB").save(path)


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
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
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

    np.save(output_dir / "states.npy", states_array)
    np.save(output_dir / "actions.npy", actions_array)
    np.save(output_dir / "ee_poses.npy", ee_poses_array)
    np.save(output_dir / "object_poses.npy", object_poses_array)

    metadata = build_metadata(
        output_dir=output_dir,
        mode="episode",
        num_steps=num_steps,
        state_dim=states_array.shape[1],
        action_dim=actions_array.shape[1],
        camera=camera,
        settings=settings,
    )
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
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
    evaluator = EvaluatorAgent(
        initial_object_z=float(cube_position[2]),
        collision_checker=collision_checker,
    )
    segments = fsm.allocate_phase_steps(num_steps)

    states: list[np.ndarray] = []
    actions: list[np.ndarray] = []
    ee_poses: list[np.ndarray] = []
    object_poses: list[np.ndarray] = []
    gripper_states: list[int] = []
    phase_labels: list[str] = []

    grasp_offset: np.ndarray | None = None
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

            if grasp_offset is None and segment.phase == TaskPhase.CLOSE_GRIPPER:
                ee_pos, _ = robot.get_end_effector_pose()
                cube_pos = object_pose(world.cube_id)[:3]
                xy_distance = float(np.linalg.norm(ee_pos[:2] - cube_pos[:2]))
                if xy_distance <= 0.08:
                    grasp_offset = (cube_pos - ee_pos).astype(np.float32)

            apply_action(world, action, gui)
            if grasp_offset is not None and segment.phase in (
                TaskPhase.CLOSE_GRIPPER,
                TaskPhase.LIFT,
            ):
                sync_object_to_grasp_offset(world, grasp_offset)
            last_action = action.astype(np.float32)
            current_joints = joint_positions(world)
            current_object_pose = object_pose(world.cube_id)
            current_ee_pose = link_pose(world.robot_id, world.ee_link_index)

            gripper_open = grasp_offset is None
            observation = StepObservation(
                step=len(states),
                joint_positions=current_joints,
                ee_position=current_ee_pose[:3],
                object_position=current_object_pose[:3],
                phase=segment.phase.value,
                gripper_open=gripper_open,
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
        if grasp_offset is not None:
            sync_object_to_grasp_offset(world, grasp_offset)
        current_joints = joint_positions(world)
        current_object_pose = object_pose(world.cube_id)
        current_ee_pose = link_pose(world.robot_id, world.ee_link_index)
        gripper_open = grasp_offset is None

        states.append(current_joints)
        actions.append(last_action)
        ee_poses.append(current_ee_pose)
        object_poses.append(current_object_pose)
        gripper_states.append(1 if gripper_open else 0)
        phase_labels.append(TaskPhase.DONE.value)
        save_png(images_dir / f"{len(states) - 1:06d}.png", render_rgb(camera))

    object_poses_array = np.stack(object_poses).astype(np.float32)
    evaluation = evaluator.evaluate_success(object_poses_array)

    states_array = np.stack(states).astype(np.float32)
    actions_array = np.stack(actions).astype(np.float32)
    ee_poses_array = np.stack(ee_poses).astype(np.float32)

    np.save(output_dir / "states.npy", states_array)
    np.save(output_dir / "actions.npy", actions_array)
    np.save(output_dir / "ee_poses.npy", ee_poses_array)
    np.save(output_dir / "object_poses.npy", object_poses_array)

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
    )
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(
        f"Wrote pick_and_lift episode with {num_steps} steps to {output_dir} "
        f"(success={evaluation.success}, object_z_lift={evaluation.object_z_lift:.4f})"
    )
    return evaluation


def build_metadata(
    output_dir: Path,
    mode: str,
    num_steps: int,
    state_dim: int,
    action_dim: int,
    camera: CameraConfig,
    settings: CollectSettings,
    evaluation: EvaluationResult | None = None,
    gripper_states: list[int] | None = None,
    phase_labels: list[str] | None = None,
    planning_success: bool | None = None,
    planning_failure_reason: str | None = None,
) -> dict[str, object]:
    notes = (
        "Minimal PyBullet image-state-action episode for portfolio "
        "data collection demonstration."
    )
    config_path = settings.config_path or DEFAULT_CONFIG_PATH
    try:
        config_label = config_path.relative_to(REPO_ROOT)
    except ValueError:
        config_label = config_path
    notes += f" Loaded config: {config_label}."

    metadata: dict[str, object] = {
        "episode_id": output_dir.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "simulator": settings.simulator,
        "mode": mode,
        "task_name": settings.task_name,
        "num_steps": num_steps,
        "image_width": camera.width,
        "image_height": camera.height,
        "state_dim": state_dim,
        "action_dim": action_dim,
        "control_mode": settings.control_mode,
        "robot": settings.robot,
        "object": settings.object_name,
        "camera": {
            "type": camera.type,
            "width": camera.width,
            "height": camera.height,
            "eye": list(camera.eye),
            "target": list(camera.target),
            "up": list(camera.up),
            "fov": camera.fov,
        },
        "seed": settings.seed,
        "notes": notes,
        "planning_mode": settings.planner,
    }
    if planning_success is not None:
        metadata["planning_success"] = planning_success
    if planning_failure_reason is not None:
        metadata["planning_failure_reason"] = planning_failure_reason
    if settings.task_name == "pick_and_lift":
        metadata["language_instruction"] = PickLiftTaskFSM.LANGUAGE_INSTRUCTION
    if evaluation is not None:
        metadata["success"] = evaluation.success
        metadata["failure_reason"] = evaluation.failure_reason
        metadata["object_z_lift"] = round(evaluation.object_z_lift, 6)
    if gripper_states is not None:
        metadata["gripper_states"] = gripper_states
    if phase_labels is not None:
        metadata["task_phases"] = phase_labels
    return metadata


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
        p.disconnect(client_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
