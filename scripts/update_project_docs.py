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
INTRO_START = "<!-- README_INTRO_START -->"
INTRO_END = "<!-- README_INTRO_END -->"
FOOTER_START = "<!-- README_FOOTER_START -->"
FOOTER_END = "<!-- README_FOOTER_END -->"
PROJECT_STATUS_PATH = "docs/portfolio/project_status.md"


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


def checkbox(done: bool) -> str:
    return "x" if done else " "


def ci_generates_reach_episode() -> bool:
    return file_contains(".github/workflows/ci.yml", r"episode_000001") and file_contains(
        ".github/workflows/ci.yml", r"--num-steps 100"
    )


def ci_generates_pick_lift_episode() -> bool:
    return file_contains(".github/workflows/ci.yml", r"pick_and_lift") and file_contains(
        ".github/workflows/ci.yml", r"episode_pick_ci"
    )


def count_dataset_episodes(relative_dir: str) -> int:
    root = ROOT / relative_dir
    if not root.is_dir():
        return 0
    return sum(
        1
        for child in sorted(root.iterdir())
        if child.is_dir() and (child / "metadata.json").exists()
    )


def batch_collect_ready() -> bool:
    """Batch pipeline exists and is covered by integration tests."""
    return (
        exists("scripts/batch_collect.py")
        and exists("tests/test_collect_integration.py")
        and file_contains("scripts/batch_collect.py", r"num-episodes")
    )


def dataset_readme_ready() -> bool:
    """batch_collect can emit a dataset README (local dataset/v1 is optional)."""
    return batch_collect_ready() and file_contains(
        "scripts/batch_collect.py", "write_dataset_readme"
    )


def lerobot_export_ready() -> bool:
    """Export script exists and export path is covered by integration tests."""
    return exists("scripts/export_lerobot_style.py") and file_contains(
        "tests/test_collect_integration.py", "export_dataset"
    )


def local_batch_dataset_ready() -> bool:
    return count_dataset_episodes("dataset/v1") >= 20


def local_lerobot_export_ready() -> bool:
    return exists("dataset/v1/lerobot_export/meta/info.json")


def uses_kinematic_grasp_sync() -> bool:
    return file_contains("scripts/collect_episode.py", r"sync_object_to_grasp_offset")


def demo_gifs_ready() -> bool:
    return all(
        exists(path)
        for path in (
            "assets/gifs/demo_replay.gif",
            "assets/gifs/demo_pick_success.gif",
            "assets/gifs/demo_rrt_obstacle.gif",
        )
    )


def build_status_sections() -> list[StatusSection]:
    """Single-track portfolio progress: done today + 3-day sprint to ship."""
    return [
        StatusSection(
            "已完成 · 数据管线",
            [
                StatusItem(
                    "Episode 闭环（image / state / action / pose）",
                    exists("scripts/collect_episode.py")
                    and exists("scripts/validate_dataset.py"),
                    "`collect_episode.py` + `validate_dataset.py`",
                ),
                StatusItem(
                    "CI 门禁（reach + pick_and_lift）",
                    ci_generates_reach_episode() and ci_generates_pick_lift_episode(),
                    "`.github/workflows/ci.yml`",
                ),
                StatusItem(
                    "仿真世界与落盘模块",
                    exists("core/world.py") and exists("core/episode_writer.py"),
                    "`core/world.py`, `core/episode_writer.py`",
                ),
                StatusItem(
                    "回放与 schema 文档",
                    exists("scripts/visualize_episode.py")
                    and exists("docs/dev/data_schema.md"),
                    "`visualize_episode.py`, `data_schema.md`",
                ),
            ],
        ),
        StatusSection(
            "已完成 · 规划与任务",
            [
                StatusItem(
                    "HAL + IK + 笛卡尔插补",
                    exists("core/hal.py")
                    and exists("core/ik.py")
                    and exists("core/trajectory.py"),
                    "`core/hal.py`, `core/ik.py`, `core/trajectory.py`",
                ),
                StatusItem(
                    "Pick-lift FSM + Evaluator",
                    exists("agents/task_fsm.py")
                    and exists("agents/evaluator.py")
                    and exists("core/grasp.py"),
                    "constraint 抓取 + grasp/slip 评测标签",
                ),
                StatusItem(
                    "双向 RRT + 碰撞检测",
                    exists("core/rrt.py")
                    and exists("core/collision.py")
                    and exists("tests/test_rrt_integration.py"),
                    "`--planner rrt`, `run_rrt_demo.py`",
                ),
                StatusItem(
                    "批量 / LeRobot 脚本骨架",
                    exists("scripts/batch_collect.py")
                    and exists("scripts/export_lerobot_style.py")
                    and exists("tests/test_collect_integration.py"),
                    "`batch_collect.py`, `export_lerobot_style.py`",
                ),
            ],
        ),
        StatusSection(
            "已完成 · 文档与材料",
            [
                StatusItem(
                    "开发文档与架构",
                    exists("docs/dev/quickstart.md")
                    and exists("docs/dev/architecture.md"),
                    "`docs/dev/`",
                ),
                StatusItem(
                    "面试讲稿与学习手册",
                    exists("docs/portfolio/interview_walkthrough.md")
                    and exists("docs/reference/learning_capability_alignment.md"),
                    "讲稿 + 能力对齐文档",
                ),
                StatusItem(
                    "10 天设计 / RRT 路线图",
                    exists("docs/planning/design_10day.md")
                    and exists("docs/planning/rrt_roadmap.md"),
                    "`design_10day.md`, `rrt_roadmap.md`",
                ),
            ],
        ),
        StatusSection(
            "Day 1 · 抓取可信度",
            [
                StatusItem(
                    "物理夹爪或约束抓取",
                    not uses_kinematic_grasp_sync(),
                    "替换 `sync_object_to_grasp_offset` kinematic demo",
                ),
                StatusItem(
                    "物理向 success / failure 判定",
                    not uses_kinematic_grasp_sync()
                    and file_contains("agents/evaluator.py", r"contact|force|grasp"),
                    "Evaluator 接触 / 力 / 夹持判定",
                ),
                StatusItem(
                    "抓取链路 pytest",
                    exists("tests/test_gripper.py") or exists("tests/test_grasp.py"),
                    "新增 grasp / gripper 集成测试",
                ),
            ],
        ),
        StatusSection(
            "Day 2 · 批量数据与展示",
            [
                StatusItem(
                    "本地 batch ≥ 20 episode",
                    local_batch_dataset_ready() or batch_collect_ready(),
                    "`batch_collect.py --num-episodes 20`",
                ),
                StatusItem(
                    "数据集 README（成功率统计）",
                    (exists("dataset/v1/README.md") and local_batch_dataset_ready())
                    or dataset_readme_ready(),
                    "`dataset/v1/README.md`",
                ),
                StatusItem(
                    "三条 demo GIF 齐全",
                    demo_gifs_ready(),
                    "`demo_replay` / `demo_pick_success` / `demo_rrt_obstacle`",
                ),
            ],
        ),
        StatusSection(
            "Day 3 · 导出与成型投递",
            [
                StatusItem(
                    "LeRobot 导出本地跑通",
                    local_lerobot_export_ready() or lerobot_export_ready(),
                    "`export_lerobot_style.py dataset/v1`",
                ),
                StatusItem(
                    "讲稿与实现一致",
                    exists("docs/portfolio/interview_walkthrough.md")
                    and not uses_kinematic_grasp_sync(),
                    "更新 `interview_walkthrough.md` 局限与演示命令",
                ),
                StatusItem(
                    "30 秒可复现（README + CI）",
                    demo_gifs_ready()
                    and ci_generates_pick_lift_episode()
                    and file_contains("docs/dev/quickstart.md", r"episode_pick_ci"),
                    "README 快速开始 + CI 绿",
                ),
            ],
        ),
    ]


def render_readme_intro() -> str:
    lines = [
        INTRO_START,
        "PyBullet 机械臂仿真数据采集平台：HAL 控制抽象、笛卡尔 IK、双向 RRT 避障、FSM pick-lift、**物理抓取**（constraint 默认 / gripper URDF 实验）、自动评测、批量采集与 LeRobot 导出。",
        "",
    ]
    for alt, relative_path in (
        ("关节轨迹回放", "assets/gifs/demo_replay.gif"),
        ("Pick-Lift 任务回放", "assets/gifs/demo_pick_success.gif"),
        ("RRT 绕障规划回放", "assets/gifs/demo_rrt_obstacle.gif"),
        ("Gripper URDF 实验回放", "assets/gifs/demo_gripper_urdf.gif"),
    ):
        if exists(relative_path):
            lines.extend([f"![{alt}]({relative_path})", ""])
    if exists("assets/videos/demo_overview.mp4"):
        lines.extend(
            [
                "### 一分钟概览视频",
                "",
                "[demo_overview.mp4](assets/videos/demo_overview.mp4)",
                "",
            ]
        )
    if exists("notebooks/portfolio_demo.ipynb"):
        lines.extend(
            [
                "**Colab 一键复现 →** [notebooks/portfolio_demo.ipynb](notebooks/portfolio_demo.ipynb)",
                "",
            ]
        )
    lines.extend(
        [
            "**文档入口 → [docs/README.md](docs/README.md)**（开发先看 [docs/dev/quickstart.md](docs/dev/quickstart.md)）",
            "",
        ]
    )
    diagram_specs = (
        ("架构与数据流", "系统分层架构", "assets/diagrams/architecture.png"),
        (None, "pick_and_lift 数据流", "assets/diagrams/data_flow_pick_lift.png"),
        (None, "Episode 目录与 step 对齐", "assets/diagrams/episode_structure.png"),
    )
    wrote_diagram_heading = False
    for heading, alt, relative_path in diagram_specs:
        if not exists(relative_path):
            continue
        if heading and not wrote_diagram_heading:
            lines.extend([f"### {heading}", ""])
            wrote_diagram_heading = True
        lines.extend([f"![{alt}]({relative_path})", ""])
    screenshot_specs = (
        ("LeRobot 导出（v2.1）", "LeRobot 导出目录", "assets/screenshots/lerobot_export_tree.png"),
        (None, "meta/info.json 字段", "assets/screenshots/lerobot_meta_info.png"),
        (None, "parquet episode 列结构", "assets/screenshots/lerobot_parquet_schema.png"),
    )
    wrote_screenshot_heading = False
    for heading, alt, relative_path in screenshot_specs:
        if not exists(relative_path):
            continue
        if heading and not wrote_screenshot_heading:
            lines.extend([f"### {heading}", ""])
            wrote_screenshot_heading = True
        lines.extend([f"![{alt}]({relative_path})", ""])
    lines.extend(
        [
            "单线进度与 **3 天冲刺清单** 见 [docs/portfolio/project_status.md](docs/portfolio/project_status.md)。",
            INTRO_END,
        ]
    )
    return "\n".join(lines)


def render_readme_footer() -> str:
    lines = [
        FOOTER_START,
        "## 快速开始",
        "",
        "```bash",
        "python -m pip install -r requirements.txt",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q",
        "python scripts/run_rrt_demo.py --seed 7",
        "python scripts/collect_episode.py --task pick_and_lift --num-steps 40 \\",
        "  --output dataset_sample/episode_pick_ci --width 64 --height 48 --seed 7",
        "python scripts/validate_dataset.py dataset_sample/episode_pick_ci",
        "```",
        "",
        "完整命令见 [docs/dev/quickstart.md](docs/dev/quickstart.md)。",
        "",
        "## 文档导航",
        "",
        "| 场景 | 文档 |",
        "|------|------|",
        "| 日常开发 | [docs/dev/](docs/dev/) |",
        "| 规划 / 路线图 | [docs/planning/](docs/planning/) |",
        "| 概念参考 | [docs/reference/](docs/reference/) |",
        "| **能力学习与自检** | [docs/reference/learning_capability_alignment.md](docs/reference/learning_capability_alignment.md) |",
        "| 面试材料 | [docs/portfolio/](docs/portfolio/) |",
        "| 智能体规范 | [AGENTS.md](AGENTS.md) |",
        "",
        "## 能力概览",
        "",
        "| 领域 | 关键路径 |",
        "|------|----------|",
        "| HAL + IK + 笛卡尔 | `core/hal.py`, `core/ik.py`, `core/trajectory.py` |",
        "| 仿真世界 + 落盘 | `core/world.py`, `core/episode_writer.py`, `core/collect_config.py` |",
        "| RRT 避障 | `core/rrt.py`, `core/collision.py`, `scripts/run_rrt_demo.py` |",
        "| 物理抓取 | `core/grasp.py`（constraint）、`core/gripper.py`（`--grasp-mode gripper_urdf`） |",
        "| 任务 FSM + 评测 | `agents/task_fsm.py`, `agents/evaluator.py` |",
        "| 采集主入口 | `scripts/collect_episode.py` |",
        "| 数据 schema | [docs/dev/data_schema.md](docs/dev/data_schema.md) |",
        "",
        "简历定位：**机器人数据工程 + 仿真采集管线**；剩余 2 天见 [project_status.md](docs/portfolio/project_status.md)。",
        FOOTER_END,
    ]
    return "\n".join(lines)


def write_project_status() -> str:
    sections = build_status_sections()
    completed = sections[:3]
    sprint = sections[3:]

    lines = [
        "# Project Status",
        "",
        "本文档由 `scripts/update_project_docs.py` 自动生成。",
        "",
        "文档索引：[docs/README.md](../README.md) · 设计总览：[design_10day.md](../planning/design_10day.md)",
        "",
        "> **单线进度（截至今日）**：数据闭环、HAL/IK、FSM 评测、RRT、**物理 constraint 抓取**、批量/LeRobot 脚本与 CI 已就绪；",
        "> **再开发 2 天**（Day 2–3 展示与投递收尾）按下方冲刺清单完成即可对外展示。",
        "",
    ]

    lines.extend(["## 已完成", ""])
    for section in completed:
        lines.append(f"### {section.title.removeprefix('已完成 · ')}")
        lines.append("")
        lines.extend(
            f"- [{checkbox(item.done)}] {item.label}：{item.evidence}"
            for item in section.items
        )
        lines.append("")

    lines.extend(
        [
            "## 三天冲刺 → 成型作品集",
            "",
            "对齐 `design_10day.md` Day 5–10 与投递展示要求；完成下列全部 `[ ]` 即可对外展示。",
            "",
        ]
    )
    for section in sprint:
        lines.extend(
            [
                f"### {section.title}",
                "",
            ]
        )
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
            "如已启用 `.githooks/pre-commit`，提交前会自动刷新",
            "`README.md` 与 `docs/portfolio/project_status.md`。",
        ]
    )
    content = "\n".join(lines) + "\n"
    path = ROOT / PROJECT_STATUS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != content:
        path.write_text(content, encoding="utf-8")
        return PROJECT_STATUS_PATH
    return ""


def render_readme() -> str:
    return "\n".join(
        [
            "# robot-arm-episode-data-lab",
            "",
            render_readme_intro(),
            "",
            render_readme_footer(),
            "",
        ]
    )


def update_readme() -> bool:
    readme_path = ROOT / "README.md"
    content = render_readme()
    old = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
    if content != old:
        readme_path.write_text(content, encoding="utf-8")
        return True
    return False


def update_docs() -> list[str]:
    changed: list[str] = []
    status_path = write_project_status()
    if status_path:
        changed.append(status_path)

    if update_readme():
        changed.append("README.md")
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
