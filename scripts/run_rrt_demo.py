#!/usr/bin/env python3
"""RRT 避障规划可视化 demo。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.motion_planner import plan_rrt_segment
from core.collision import CollisionChecker
from core.joint_limits import get_joint_limits
from core.rrt import RRTConfig
from scripts.collect_episode import (
    apply_action,
    connect,
    make_collision_checker,
    make_robot,
    setup_world,
)

try:
    import pybullet as p
except ImportError:  # pragma: no cover
    p = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bidirectional RRT-Connect obstacle avoidance demo.")
    parser.add_argument("--gui", action="store_true", help="Show PyBullet GUI.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for RRT sampling.")
    parser.add_argument(
        "--goal-position",
        type=float,
        nargs=3,
        default=(0.63, 0.0, 0.25),
        metavar=("X", "Y", "Z"),
        help="Target end-effector position.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    client_id = connect(args.gui)
    try:
        world = setup_world(with_obstacles=True)
        robot = make_robot(world)
        joint_limits = get_joint_limits(world.robot_id, world.joint_indices)
        collision_checker = make_collision_checker(world)

        start_q = robot.get_joint_positions()
        _, start_ori = robot.get_end_effector_pose()
        goal_q = robot.compute_ik(np.asarray(args.goal_position, dtype=np.float32), start_ori)

        print(f"Planning RRT path from home to goal position {args.goal_position} ...")
        result = plan_rrt_segment(
            robot,
            start_q,
            goal_q,
            collision_checker,
            joint_limits,
            num_interp_steps=60,
            rrt_config=RRTConfig(max_iterations=3000, step_size=0.12),
            rng=rng,
        )
        if not result.success:
            print(f"RRT planning failed: {result.failure_reason}")
            return 1

        print(f"RRT planning succeeded with {len(result.actions)} control steps.")
        for step_index, action in enumerate(result.actions):
            apply_action(world, action, args.gui)
            if args.gui and step_index % 10 == 0:
                ee_pos, _ = robot.get_end_effector_pose()
                print(f"  step {step_index:03d}: ee={ee_pos.round(3).tolist()}")

        final_pos, _ = robot.get_end_effector_pose()
        error = float(np.linalg.norm(final_pos - np.asarray(args.goal_position, dtype=np.float32)))
        print(f"Final EE position error: {error:.4f} m")
        if args.gui:
            time.sleep(2.0)
        return 0 if error < 0.08 else 1
    finally:
        if p is not None:
            p.disconnect(client_id)


if __name__ == "__main__":
    raise SystemExit(main())
