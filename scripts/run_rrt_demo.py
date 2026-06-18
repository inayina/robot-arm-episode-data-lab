#!/usr/bin/env python3
"""RRT 避障规划可视化 demo。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.motion_planner import plan_rrt_segment
from core.collect_config import CameraConfig
from core.joint_limits import get_joint_limits
from core.rrt import RRTConfig
from core.world import (
    apply_action,
    connect,
    disconnect,
    make_collision_checker,
    make_robot,
    render_rgb,
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
    parser.add_argument(
        "--save-gif",
        type=Path,
        default=None,
        help="Write a headless camera replay GIF to this path.",
    )
    parser.add_argument("--fps", type=float, default=8.0, help="GIF playback FPS.")
    parser.add_argument(
        "--frame-stride",
        type=int,
        default=3,
        help="Capture every N execution steps when writing a GIF.",
    )
    return parser.parse_args()


def capture_frame(camera: CameraConfig, overlay_lines: list[str]) -> Image.Image:
    image = Image.fromarray(render_rgb(camera))
    draw = ImageDraw.Draw(image)
    box_bottom = 14 + len(overlay_lines) * 18 + 8
    draw.rectangle((8, 8, 440, box_bottom), fill=(0, 0, 0))
    for line_index, line in enumerate(overlay_lines):
        draw.text((16, 14 + line_index * 18), line, fill=(255, 255, 255))
    return image


def save_gif(frames: list[Image.Image], output_path: Path, fps: float) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration_ms = max(1, int(1000.0 / fps))
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
    )


def main() -> int:
    args = parse_args()
    if args.fps <= 0:
        print("--fps must be positive")
        return 1
    if args.frame_stride <= 0:
        print("--frame-stride must be positive")
        return 1

    rng = np.random.default_rng(args.seed)
    client_id = connect(args.gui)
    camera = CameraConfig(width=640, height=480)
    frames: list[Image.Image] = []
    try:
        world = setup_world(with_obstacles=True)
        robot = make_robot(world)
        joint_limits = get_joint_limits(world.robot_id, world.joint_indices)
        collision_checker = make_collision_checker(world)

        start_q = robot.get_joint_positions()
        start_pos, start_ori = robot.get_end_effector_pose()
        goal_q = robot.compute_ik(np.asarray(args.goal_position, dtype=np.float32), start_ori)

        if args.save_gif is not None:
            frames.append(
                capture_frame(
                    camera,
                    [
                        "RRT-Connect obstacle avoidance",
                        f"goal: {tuple(round(v, 3) for v in args.goal_position)}",
                        f"start ee: {start_pos.round(3).tolist()}",
                    ],
                )
            )

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
        if args.save_gif is not None:
            frames.append(
                capture_frame(
                    camera,
                    [
                        "planning: success",
                        f"path steps: {len(result.actions)}",
                    ],
                )
            )

        last_step = len(result.actions) - 1
        for step_index, action in enumerate(result.actions):
            apply_action(world, action, args.gui)
            if args.save_gif is not None and (
                step_index % args.frame_stride == 0 or step_index == last_step
            ):
                ee_pos, _ = robot.get_end_effector_pose()
                frames.append(
                    capture_frame(
                        camera,
                        [
                            f"step: {step_index:03d}/{last_step:03d}",
                            f"ee: {ee_pos.round(3).tolist()}",
                        ],
                    )
                )
            if args.gui and step_index % 10 == 0:
                ee_pos, _ = robot.get_end_effector_pose()
                print(f"  step {step_index:03d}: ee={ee_pos.round(3).tolist()}")

        final_pos, _ = robot.get_end_effector_pose()
        error = float(np.linalg.norm(final_pos - np.asarray(args.goal_position, dtype=np.float32)))
        print(f"Final EE position error: {error:.4f} m")
        if args.save_gif is not None:
            save_gif(frames, args.save_gif, args.fps)
            print(f"Wrote GIF replay to {args.save_gif} ({len(frames)} frames)")
        if args.gui:
            time.sleep(2.0)
        return 0 if error < 0.08 else 1
    finally:
        if p is not None:
            disconnect(client_id)


if __name__ == "__main__":
    raise SystemExit(main())
