#!/usr/bin/env python3
"""批量采集机械臂 episode 到数据集目录。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.collect_episode import (
    CollectSettings,
    connect,
    collect_episode,
    collect_pick_and_lift,
    settings_from_config,
    DEFAULT_CONFIG_PATH,
)
from scripts.validate_dataset import collect_dataset_summary, collect_errors

try:
    import pybullet as p
except ImportError:  # pragma: no cover - exercised only without deps.
    p = None


@dataclass(frozen=True)
class EpisodeResult:
    episode_id: str
    episode_dir: Path
    seed: int
    success: bool | None
    failure_reason: str | None
    object_z_lift: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch collect multiple episodes into a dataset directory."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dataset/v1"),
        help="Dataset root directory.",
    )
    parser.add_argument(
        "--num-episodes",
        type=int,
        default=20,
        help="Number of episodes to collect.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Base random seed.")
    parser.add_argument(
        "--task",
        default="pick_and_lift",
        help="Task name passed to the collector.",
    )
    parser.add_argument(
        "--num-steps",
        type=int,
        default=80,
        help="Steps per episode.",
    )
    parser.add_argument(
        "--cube-jitter",
        type=float,
        default=0.02,
        help="Max XY jitter applied to the cube position per episode.",
    )
    parser.add_argument("--gui", action="store_true", help="Run PyBullet with GUI.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="YAML config used for camera and robot defaults.",
    )
    return parser.parse_args()


def build_episode_settings(
    base: CollectSettings,
    *,
    output_dir: Path,
    task_name: str,
    seed: int,
    num_steps: int,
    gui: bool,
) -> CollectSettings:
    return CollectSettings(
        mode="episode",
        output=output_dir,
        num_steps=num_steps,
        width=base.width,
        height=base.height,
        gui=gui,
        seed=seed,
        simulator=base.simulator,
        task_name=task_name,
        robot=base.robot,
        object_name=base.object_name,
        control_mode="task_fsm" if task_name == "pick_and_lift" else base.control_mode,
        camera=base.camera,
        config_path=base.config_path,
    )


def write_dataset_readme(
    dataset_dir: Path,
    results: list[EpisodeResult],
    *,
    task_name: str,
    num_steps: int,
    base_seed: int,
) -> None:
    total = len(results)
    successes = sum(1 for result in results if result.success is True)
    success_rate = (successes / total) if total else 0.0
    lines = [
        "# 数据集 v1",
        "",
        "面向作品集与 LeRobot 导出的 PyBullet pick-lift episode 批量采集结果。",
        "",
        "## 概览",
        "",
        f"- 任务：`{task_name}`",
        f"- Episode 数量：{total}",
        f"- 每 episode 步数：{num_steps}",
        f"- 成功次数：{successes}",
        f"- 成功率：{success_rate:.1%}",
        f"- 基础随机种子：{base_seed}",
        f"- 生成时间：{datetime.now(timezone.utc).isoformat()}",
        "",
        "## 目录结构",
        "",
        "每个子目录符合 `docs/data_schema.md` 约定：",
        "",
        "```text",
        "episode_000001/",
        "├── images/",
        "├── states.npy",
        "├── actions.npy",
        "├── ee_poses.npy",
        "├── object_poses.npy",
        "└── metadata.json",
        "```",
        "",
        "## metadata 扩展字段",
        "",
        "- `success`、`failure_reason`、`object_z_lift`",
        "- `language_instruction`（pick-lift 任务）",
        "- `gripper_states`、`task_phases`",
        "",
        "## Episode 索引",
        "",
        "| Episode | 种子 | 成功 | 物体 Z 抬升 (m) |",
        "| --- | ---: | --- | ---: |",
    ]
    for result in results:
        lift = "n/a" if result.object_z_lift is None else f"{result.object_z_lift:.4f}"
        success_label = "n/a" if result.success is None else str(result.success)
        lines.append(
            f"| `{result.episode_id}` | {result.seed} | {success_label} | {lift} |"
        )
    lines.extend(
        [
            "",
            "## 常用命令",
            "",
            "```bash",
            "python scripts/validate_dataset.py dataset/v1",
            "python scripts/export_lerobot_style.py dataset/v1 --output dataset/v1/lerobot_export",
            "```",
            "",
        ]
    )
    (dataset_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def collect_one_episode(
    episode_dir: Path,
    settings: CollectSettings,
    cube_xy_offset: tuple[float, float],
) -> EpisodeResult:
    episode_dir.parent.mkdir(parents=True, exist_ok=True)
    client_id = connect(settings.gui)
    try:
        if settings.task_name == "pick_and_lift":
            evaluation = collect_pick_and_lift(
                episode_dir,
                settings.num_steps,
                settings.camera,
                settings.gui,
                settings,
                cube_xy_offset=cube_xy_offset,
            )
            return EpisodeResult(
                episode_id=episode_dir.name,
                episode_dir=episode_dir,
                seed=settings.seed,
                success=evaluation.success,
                failure_reason=evaluation.failure_reason,
                object_z_lift=evaluation.object_z_lift,
            )

        collect_episode(
            episode_dir,
            settings.num_steps,
            settings.camera,
            settings.gui,
            settings,
            cube_xy_offset=cube_xy_offset,
        )
    finally:
        p.disconnect(client_id)

    metadata_path = episode_dir / "metadata.json"
    success = None
    failure_reason = None
    object_z_lift = None
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        success = metadata.get("success")
        failure_reason = metadata.get("failure_reason")
        object_z_lift = metadata.get("object_z_lift")

    return EpisodeResult(
        episode_id=episode_dir.name,
        episode_dir=episode_dir,
        seed=settings.seed,
        success=success,
        failure_reason=failure_reason,
        object_z_lift=object_z_lift,
    )


def main() -> int:
    args = parse_args()
    if args.num_episodes <= 0:
        print("--num-episodes must be positive.")
        return 1

    base_settings = settings_from_config(args.config)
    dataset_dir = args.output
    dataset_dir.mkdir(parents=True, exist_ok=True)

    results: list[EpisodeResult] = []
    for episode_index in range(args.num_episodes):
        episode_seed = args.seed + episode_index
        episode_id = f"episode_{episode_index + 1:06d}"
        episode_dir = dataset_dir / episode_id
        rng = np.random.default_rng(episode_seed)
        jitter = (
            float(rng.uniform(-args.cube_jitter, args.cube_jitter)),
            float(rng.uniform(-args.cube_jitter, args.cube_jitter)),
        )
        settings = build_episode_settings(
            base_settings,
            output_dir=episode_dir,
            task_name=args.task,
            seed=episode_seed,
            num_steps=args.num_steps,
            gui=args.gui,
        )
        print(f"Collecting {episode_id} (seed={episode_seed}, jitter={jitter})...")
        result = collect_one_episode(episode_dir, settings, jitter)
        episode_errors = collect_errors(episode_dir)
        if episode_errors:
            print(f"  validation failed for {episode_id}:")
            for error in episode_errors:
                print(f"    - {error}")
            return 1
        print(
            f"  done: success={result.success}, object_z_lift={result.object_z_lift}"
        )
        results.append(result)

    write_dataset_readme(
        dataset_dir,
        results,
        task_name=args.task,
        num_steps=args.num_steps,
        base_seed=args.seed,
    )
    summary = collect_dataset_summary(dataset_dir)
    print(
        f"Batch collection complete: {summary['episode_count']} episodes, "
        f"success_rate={summary['success_rate']:.1%}"
    )
    print(f"Dataset README: {dataset_dir / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
