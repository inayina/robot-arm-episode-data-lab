"""PyBullet 仿真世界搭建、渲染与低层控制。"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from core.collect_config import CameraConfig
from core.collision import CollisionChecker
from core.ik import solve_ik
from core.pybullet_robot import PyBulletRobot
from core.trajectory import interpolate_cartesian_line

try:
    import pybullet as p
    import pybullet_data
except ImportError:  # pragma: no cover - exercised only without deps.
    p = None
    pybullet_data = None


@dataclass(frozen=True)
class World:
    robot_id: int
    cube_id: int
    joint_indices: list[int]
    ee_link_index: int
    plane_id: int
    obstacle_ids: tuple[int, ...] = ()
    gripper_id: int | None = None
    gripper_joint_indices: tuple[int, ...] = ()
    gripper_mount_constraint_id: int | None = None

    @property
    def arm_dim(self) -> int:
        return len(self.joint_indices)

    @property
    def gripper_dim(self) -> int:
        return len(self.gripper_joint_indices)

    @property
    def control_dim(self) -> int:
        return self.arm_dim + self.gripper_dim


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


def gripper_positions(world: World) -> np.ndarray:
    if world.gripper_id is None or not world.gripper_joint_indices:
        return np.zeros(0, dtype=np.float32)
    states = p.getJointStates(world.gripper_id, list(world.gripper_joint_indices))
    return np.asarray([state[0] for state in states], dtype=np.float32)


def state_vector(world: World) -> np.ndarray:
    arm = joint_positions(world)
    if world.gripper_dim == 0:
        return arm
    return np.concatenate([arm, gripper_positions(world)]).astype(np.float32)


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
    """Kinematic demo grasp: teleport cube to EE + offset each step.

    .. deprecated::
        Day 1 grasp work replaces this with physical constraint grasp
        (``core/grasp.py``). Production ``pick_and_lift`` must not call this
        after Task 3; keep only for tests or kinematic baseline comparison.

    Args:
        world: Active simulation world (robot + cube).
        grasp_offset: Cube position minus EE position at grasp time, shape (3,).
            Reusable as parent-child offset for ``createConstraint``.
    """
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
    apply_episode_action(world, action, gui)


def apply_episode_action(world: World, action: np.ndarray, gui: bool) -> None:
    action = np.asarray(action, dtype=np.float32).reshape(-1)
    arm_action = action[: world.arm_dim]
    p.setJointMotorControlArray(
        bodyUniqueId=world.robot_id,
        jointIndices=world.joint_indices,
        controlMode=p.POSITION_CONTROL,
        targetPositions=arm_action.tolist(),
        forces=[120.0] * world.arm_dim,
    )
    if world.gripper_id is not None and world.gripper_dim > 0:
        if action.shape[0] < world.control_dim:
            finger_targets = gripper_positions(world)
        else:
            finger_targets = action[world.arm_dim : world.control_dim]
        p.setJointMotorControlArray(
            bodyUniqueId=world.gripper_id,
            jointIndices=list(world.gripper_joint_indices),
            controlMode=p.POSITION_CONTROL,
            targetPositions=finger_targets.tolist(),
            forces=[80.0] * world.gripper_dim,
        )
    for _ in range(4):
        p.stepSimulation()
        if gui:
            time.sleep(1.0 / 240.0)


def disconnect(client_id: int) -> None:
    if p is not None:
        p.disconnect(client_id)
