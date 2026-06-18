#!/usr/bin/env python3
"""Update generated project-progress documentation blocks.

This script intentionally uses only the Python standard library so it can run
before project dependencies are installed.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTO_START = "<!-- AUTO_STATUS_START -->"
AUTO_END = "<!-- AUTO_STATUS_END -->"


@dataclass(frozen=True)
class StatusItem:
    label: str
    done: bool
    evidence: str


@dataclass(frozen=True)
class StatusSection:
    title: str
    items: list[StatusItem]


def exists(relative_path: str) -> bool:
    return (ROOT / relative_path).exists()


def file_contains(relative_path: str, pattern: str) -> bool:
    path = ROOT / relative_path
    if not path.exists():
        return False
    return re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE) is not None


def json_metadata_has_true_success(relative_dir: str) -> bool:
    path = ROOT / relative_dir / "metadata.json"
    if not path.exists():
        return False
    try:
        import json

        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return metadata.get("success") is True


def count_episode_frames(relative_dir: str) -> int:
    images_dir = ROOT / relative_dir / "images"
    if not images_dir.is_dir():
        return 0
    return len(sorted(images_dir.glob("*.png")))


def count_dataset_episodes(relative_dir: str) -> int:
    root = ROOT / relative_dir
    if not root.is_dir():
        return 0
    count = 0
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "metadata.json").exists():
            count += 1
    return count


def checkbox(done: bool) -> str:
    return "x" if done else " "


def episode_matches_default_sample(relative_dir: str) -> bool:
    path = ROOT / relative_dir / "metadata.json"
    if not path.exists():
        return False
    try:
        import json

        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        metadata.get("num_steps") == 100
        and metadata.get("image_width") == 640
        and metadata.get("image_height") == 480
        and count_episode_frames(relative_dir) == 100
    )


def build_status_sections() -> list[StatusSection]:
    baseline = StatusSection(
        "作品集基线",
        [
            StatusItem(
                "V0 最小样例",
                exists("dataset_sample/v0/image.png")
                and exists("dataset_sample/v0/joint_state.npy")
                and exists("dataset_sample/v0/metadata.json"),
                "`dataset_sample/v0/`",
            ),
            StatusItem(
                "V1 episode 数据闭环",
                exists("dataset_sample/episode_000001/states.npy")
                and exists("dataset_sample/episode_000001/actions.npy")
                and exists("dataset_sample/episode_000001/ee_poses.npy")
                and exists("dataset_sample/episode_000001/object_poses.npy")
                and exists("dataset_sample/episode_000001/metadata.json")
                and count_episode_frames("dataset_sample/episode_000001") > 0,
                "`dataset_sample/episode_000001/`",
            ),
            StatusItem(
                "数据校验脚本",
                exists("scripts/validate_dataset.py"),
                "`scripts/validate_dataset.py`",
            ),
            StatusItem(
                "回放 GIF 脚本",
                exists("scripts/visualize_episode.py"),
                "`scripts/visualize_episode.py`",
            ),
            StatusItem(
                "数据结构与采集流程文档",
                exists("docs/data_schema.md") and exists("docs/collection_pipeline.md"),
                "`docs/data_schema.md`, `docs/collection_pipeline.md`",
            ),
        ],
    )

    phase05 = StatusSection(
        "Phase 0.5 工程与展示（广撒网）",
        [
            StatusItem(
                "config 接入采集脚本",
                file_contains("scripts/collect_episode.py", r"--config")
                and file_contains("scripts/collect_episode.py", r"default\.yaml"),
                "`collect_episode.py --config configs/default.yaml`",
            ),
            StatusItem(
                "统一样例 episode",
                episode_matches_default_sample("dataset_sample/episode_000001"),
                "`dataset_sample/episode_000001/`（100 步、640×480）",
            ),
            StatusItem(
                "展示 GIF",
                exists("assets/gifs/demo_replay.gif"),
                "`assets/gifs/demo_replay.gif`",
            ),
            StatusItem(
                "pytest 测试",
                exists("tests/test_validate_dataset.py")
                and exists("tests/test_trajectory.py"),
                "`pytest -q`",
            ),
            StatusItem(
                "GitHub Actions CI",
                exists(".github/workflows/ci.yml"),
                "`.github/workflows/ci.yml`",
            ),
            StatusItem(
                "LICENSE",
                exists("LICENSE"),
                "`LICENSE`",
            ),
        ],
    )

    phase1 = StatusSection(
        "Phase 1 HAL + IK + 笛卡尔",
        [
            StatusItem(
                "任务 1：PyBullet 控制逻辑审计",
                exists("docs/phase1_task1_pybullet_audit.md"),
                "`docs/phase1_task1_pybullet_audit.md`",
            ),
            StatusItem(
                "任务 2：RobotControl 抽象基类",
                exists("core/hal.py"),
                "`core/hal.py`",
            ),
            StatusItem(
                "任务 3：PyBulletRobot 控制封装",
                exists("core/pybullet_robot.py"),
                "`core/pybullet_robot.py`",
            ),
            StatusItem(
                "任务 4：HAL smoke demo",
                exists("scripts/run_cartesian_demo.py"),
                "`scripts/run_cartesian_demo.py`",
            ),
            StatusItem(
                "任务 5：IK 求解封装",
                exists("core/ik.py"),
                "`core/ik.py`",
            ),
            StatusItem(
                "任务 6：笛卡尔直线插补",
                exists("core/trajectory.py"),
                "`core/trajectory.py`",
            ),
            StatusItem(
                "任务 8：采集脚本接入 cartesian_ik 模式",
                file_contains("scripts/collect_episode.py", r"--control-mode")
                and file_contains("scripts/collect_episode.py", r"cartesian_ik"),
                "`collect_episode.py --control-mode cartesian_ik`",
            ),
        ],
    )

    phase15 = StatusSection(
        "Phase 1.5 任务可信度（广撒网）",
        [
            StatusItem(
                "Task FSM",
                exists("agents/task_fsm.py"),
                "`agents/task_fsm.py`",
            ),
            StatusItem(
                "Evaluator Agent",
                exists("agents/evaluator.py"),
                "`agents/evaluator.py`",
            ),
            StatusItem(
                "Motion planner 模块",
                exists("agents/motion_planner.py"),
                "`agents/motion_planner.py`",
            ),
            StatusItem(
                "成功 pick/lift GIF",
                exists("assets/gifs/demo_pick_success.gif")
                or json_metadata_has_true_success("dataset_sample/episode_pick_001"),
                "`assets/gifs/demo_pick_success.gif`",
            ),
        ],
    )

    phase2 = StatusSection(
        "Phase 2 批量数据 + LeRobot（广撒网）",
        [
            StatusItem(
                "批量采集脚本",
                exists("scripts/batch_collect.py"),
                "`scripts/batch_collect.py`",
            ),
            StatusItem(
                "数据集目录 ≥ 20 episode",
                count_dataset_episodes("dataset/v1") >= 20,
                "`dataset/v1/`",
            ),
            StatusItem(
                "LeRobot 真导出",
                file_contains("scripts/export_lerobot_style.py", r"lerobot")
                or exists("dataset/v1/lerobot_export"),
                "`export_lerobot_style.py`",
            ),
            StatusItem(
                "数据集 README",
                exists("dataset/v1/README.md"),
                "`dataset/v1/README.md`",
            ),
        ],
    )

    phase3 = StatusSection(
        "Phase 3 展示与迁移叙事（广撒网）",
        [
            StatusItem(
                "面试讲稿",
                exists("docs/interview_walkthrough.md"),
                "`docs/interview_walkthrough.md`",
            ),
            StatusItem(
                "ROS/MoveIt 迁移设计",
                exists("docs/migration_ros2_moveit.md"),
                "`docs/migration_ros2_moveit.md`",
            ),
            StatusItem(
                "广撒网路线图文档",
                exists("docs/portfolio_roadmap_broad.md"),
                "`docs/portfolio_roadmap_broad.md`",
            ),
        ],
    )

    return [baseline, phase05, phase1, phase15, phase2, phase3]


def render_status_block() -> str:
    sections = build_status_sections()
    lines = [
        AUTO_START,
        "## 自动进度快照",
        "",
        "> 这个区块由 `python scripts/update_project_docs.py` 根据仓库文件自动生成；",
        "> 手动修改会在下次运行时被覆盖。",
        "",
    ]
    for section in sections:
        lines.extend([f"### {section.title}", ""])
        lines.extend(
            f"- [{checkbox(item.done)}] {item.label}：{item.evidence}"
            for item in section.items
        )
        lines.append("")
    lines.append(AUTO_END)
    return "\n".join(lines)


def write_project_status() -> str:
    sections = build_status_sections()
    lines = [
        "# Project Status",
        "",
        "本文档由 `scripts/update_project_docs.py` 自动生成，用于减少手动同步进度文档的成本。",
        "",
        "广撒网 4 周详细任务见 [portfolio_roadmap_broad.md](portfolio_roadmap_broad.md)。",
        "",
    ]
    for section in sections:
        lines.extend([f"## {section.title}", ""])
        lines.extend(
            f"- [{checkbox(item.done)}] {item.label}：{item.evidence}"
            for item in section.items
        )
        lines.append("")
    lines.extend(
        [
            "## 更新方式",
            "",
            "```bash",
            "python scripts/update_project_docs.py",
            "```",
            "",
            "如已启用 `.githooks/pre-commit`，提交前会自动刷新本文件以及",
            "`README.md`、`PLAN.md`、`roadmap.md` 中的自动进度快照。",
        ]
    )
    content = "\n".join(lines) + "\n"
    path = ROOT / "docs/project_status.md"
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != content:
        path.write_text(content, encoding="utf-8")
        return str(path.relative_to(ROOT))
    return ""


def replace_or_insert_block(path: Path, block: str) -> bool:
    content = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"{re.escape(AUTO_START)}.*?{re.escape(AUTO_END)}",
        re.DOTALL,
    )
    if pattern.search(content):
        updated = pattern.sub(block, content)
    else:
        lines = content.splitlines()
        if lines and lines[0].startswith("# "):
            updated = "\n".join([lines[0], "", block, "", *lines[1:]]) + "\n"
        else:
            updated = block + "\n\n" + content
    if updated != content:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def update_docs() -> list[str]:
    changed: list[str] = []
    status_path = write_project_status()
    if status_path:
        changed.append(status_path)

    block = render_status_block()
    for relative_path in ("README.md", "PLAN.md", "roadmap.md"):
        path = ROOT / relative_path
        if replace_or_insert_block(path, block):
            changed.append(relative_path)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Update generated project status sections in docs."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Return a non-zero exit code if docs were stale before updating.",
    )
    args = parser.parse_args()

    changed = update_docs()
    if changed:
        print("Updated generated docs:")
        for path in changed:
            print(f"  - {path}")
        return 1 if args.check else 0

    print("Generated docs are already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
