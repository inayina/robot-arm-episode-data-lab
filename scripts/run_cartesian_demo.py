#!/usr/bin/env python3
"""Phase 1 HAL + IK + 笛卡尔插补冒烟测试与演示。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.ik import solve_ik
from core.pybullet_robot import PyBulletRobot
from core.trajectory import interpolate_cartesian_line
from core.collect_config import CameraConfig
from core.world import connect, disconnect, setup_world

try:
    import pybullet as p
except ImportError:  # pragma: no cover - exercised only without deps.
    p = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate HAL, IK, and Cartesian interpolation in PyBullet."
    )
    parser.add_argument(
        "--num-steps",
        type=int,
        default=60,
        help="Joint-position smoke-test simulation steps.",
    )
    parser.add_argument(
        "--num-waypoints",
        type=int,
        default=None,
        help="If set, run Cartesian line + IK demo with this many waypoints.",
    )
    parser.add_argument(
        "--steps-per-waypoint",
        type=int,
        default=8,
        help="Simulation steps to execute per Cartesian waypoint.",
    )
    parser.add_argument("--gui", action="store_true", help="Run PyBullet with GUI.")
    return parser.parse_args()


def make_robot(world) -> PyBulletRobot:
    return PyBulletRobot(
        robot_id=world.robot_id,
        joint_indices=world.joint_indices,
        ee_link_index=world.ee_link_index,
    )


def run_joint_smoke_test(robot: PyBulletRobot, num_steps: int) -> None:
    start_joints = robot.get_joint_positions()
    start_pos, _ = robot.get_end_effector_pose()

    target = start_joints.copy()
    if target.shape[0] >= 2:
        target[1] += 0.05

    for _ in range(num_steps):
        robot.set_joint_positions(target)
        robot.step()

    end_joints = robot.get_joint_positions()
    end_pos, _ = robot.get_end_effector_pose()

    print("HAL joint smoke test")
    print(f"  joint_dim: {start_joints.shape[0]}")
    print(f"  start_joints: {np.round(start_joints, 4).tolist()}")
    print(f"  end_joints: {np.round(end_joints, 4).tolist()}")
    print(f"  start_ee_position: {np.round(start_pos, 4).tolist()}")
    print(f"  end_ee_position: {np.round(end_pos, 4).tolist()}")


def run_cartesian_demo(
    robot: PyBulletRobot,
    world,
    num_waypoints: int,
    steps_per_waypoint: int,
) -> None:
    start_pos, start_ori = robot.get_end_effector_pose()
    cube_pos, _ = p.getBasePositionAndOrientation(world.cube_id)
    cube_pos = np.asarray(cube_pos, dtype=np.float32)

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
        num_waypoints,
        start_orientation=start_ori,
        end_orientation=start_ori,
    )

    print("Cartesian + IK demo")
    print(f"  num_waypoints: {num_waypoints}")
    print(f"  start_ee_position: {np.round(start_pos, 4).tolist()}")
    print(f"  target_ee_position: {np.round(target_pos, 4).tolist()}")

    for waypoint_pos, waypoint_ori in waypoints:
        action = solve_ik(robot, waypoint_pos, waypoint_ori)
        if action.shape[0] != robot.num_joints:
            raise RuntimeError(
                f"IK action shape {action.shape} does not match joint count "
                f"{robot.num_joints}."
            )
        robot.set_joint_positions(action)
        for _ in range(steps_per_waypoint):
            robot.step()

    end_pos, _ = robot.get_end_effector_pose()
    error = float(np.linalg.norm(end_pos - target_pos))
    print(f"  end_ee_position: {np.round(end_pos, 4).tolist()}")
    print(f"  target_error_m: {error:.4f}")


def main() -> int:
    args = parse_args()
    client_id = connect(args.gui)
    try:
        world = setup_world()
        robot = make_robot(world)

        if args.num_waypoints is None:
            run_joint_smoke_test(robot, args.num_steps)
        else:
            run_cartesian_demo(
                robot,
                world,
                num_waypoints=args.num_waypoints,
                steps_per_waypoint=args.steps_per_waypoint,
            )
    finally:
        disconnect(client_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
