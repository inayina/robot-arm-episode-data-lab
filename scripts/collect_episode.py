#!/usr/bin/env python3
"""Collect minimal PyBullet robot-arm episode data."""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import pybullet as p
    import pybullet_data
except ImportError as exc:  # pragma: no cover - exercised only without deps.
    raise SystemExit(
        "Missing dependency: pybullet. Install dependencies with "
        "`python -m pip install -r requirements.txt`."
    ) from exc


@dataclass(frozen=True)
class CameraConfig:
    width: int = 640
    height: int = 480
    eye: tuple[float, float, float] = (1.15, -1.05, 0.85)
    target: tuple[float, float, float] = (0.45, 0.0, 0.25)
    up: tuple[float, float, float] = (0.0, 0.0, 1.0)
    fov: float = 55.0


@dataclass(frozen=True)
class World:
    robot_id: int
    cube_id: int
    joint_indices: list[int]
    ee_link_index: int


FRAME_NAME_RE = re.compile(r"^\d{6}\.png$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect V0 or V1 PyBullet robot-arm episode data."
    )
    parser.add_argument(
        "--mode",
        choices=("v0", "episode"),
        default="episode",
        help="Use v0 for one image and one joint_state.npy; episode for full V1 data.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dataset_sample/episode_000001"),
        help="Output directory.",
    )
    parser.add_argument("--num-steps", type=int, default=100, help="Episode length.")
    parser.add_argument("--width", type=int, default=640, help="Camera image width.")
    parser.add_argument("--height", type=int, default=480, help="Camera image height.")
    parser.add_argument("--gui", action="store_true", help="Run PyBullet with GUI.")
    parser.add_argument("--seed", type=int, default=7, help="Numpy random seed.")
    return parser.parse_args()


def connect(gui: bool) -> int:
    connection_mode = p.GUI if gui else p.DIRECT
    client_id = p.connect(connection_mode)
    if client_id < 0:
        raise RuntimeError("Failed to connect to PyBullet.")
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    return client_id


def setup_world() -> World:
    p.resetSimulation()
    p.setGravity(0.0, 0.0, -9.81)
    p.loadURDF("plane.urdf")

    robot_id = p.loadURDF(
        "kuka_iiwa/model.urdf",
        basePosition=(0.0, 0.0, 0.0),
        useFixedBase=True,
    )
    cube_id = p.loadURDF(
        "cube_small.urdf",
        basePosition=(0.63, 0.0, 0.025),
        baseOrientation=p.getQuaternionFromEuler((0.0, 0.0, 0.0)),
    )

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


def collect_v0(output_dir: Path, camera: CameraConfig, gui: bool) -> None:
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
) -> None:
    if num_steps <= 0:
        raise ValueError("--num-steps must be positive.")

    images_dir = prepare_episode_dir(output_dir)
    world = setup_world()
    action_dim = len(world.joint_indices)

    states: list[np.ndarray] = []
    actions: list[np.ndarray] = []
    ee_poses: list[np.ndarray] = []
    object_poses: list[np.ndarray] = []

    for step in range(num_steps):
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
    )
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(f"Wrote episode with {num_steps} steps to {output_dir}")


def build_metadata(
    output_dir: Path,
    mode: str,
    num_steps: int,
    state_dim: int,
    action_dim: int,
    camera: CameraConfig,
) -> dict[str, object]:
    return {
        "episode_id": output_dir.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "simulator": "pybullet",
        "mode": mode,
        "task_name": "reach_cube",
        "num_steps": num_steps,
        "image_width": camera.width,
        "image_height": camera.height,
        "state_dim": state_dim,
        "action_dim": action_dim,
        "control_mode": "joint_position",
        "robot": "kuka_iiwa",
        "object": "cube",
        "camera": {
            "type": "fixed_rgb",
            "width": camera.width,
            "height": camera.height,
            "eye": list(camera.eye),
            "target": list(camera.target),
            "up": list(camera.up),
            "fov": camera.fov,
        },
        "notes": (
            "Minimal PyBullet image-state-action episode for portfolio "
            "data collection demonstration."
        ),
    }


def main() -> int:
    args = parse_args()
    np.random.seed(args.seed)
    camera = CameraConfig(width=args.width, height=args.height)
    client_id = connect(args.gui)
    try:
        if args.mode == "v0":
            collect_v0(args.output, camera, args.gui)
        else:
            collect_episode(args.output, args.num_steps, camera, args.gui)
    finally:
        p.disconnect(client_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
