# Project Status

本文档由 `scripts/update_project_docs.py` 自动生成。

文档索引：[docs/README.md](../README.md) · 设计总览：[design_10day.md](../planning/design_10day.md)

> **单线进度（截至今日）**：数据闭环、HAL/IK、FSM 评测、RRT、**物理 constraint 抓取**、批量/LeRobot 脚本与 CI 已就绪；
> **再开发 2 天**（Day 2–3 展示与投递收尾）按下方冲刺清单完成即可对外展示。

## 已完成

### 数据管线

- [x] Episode 闭环（image / state / action / pose）：`collect_episode.py` + `validate_dataset.py`
- [x] CI 门禁（reach + pick_and_lift）：`.github/workflows/ci.yml`
- [x] 仿真世界与落盘模块：`core/world.py`, `core/episode_writer.py`
- [x] 回放与 schema 文档：`visualize_episode.py`, `data_schema.md`

### 规划与任务

- [x] HAL + IK + 笛卡尔插补：`core/hal.py`, `core/ik.py`, `core/trajectory.py`
- [x] Pick-lift FSM + Evaluator：constraint 抓取 + grasp/slip 评测标签
- [x] 双向 RRT + 碰撞检测：`--planner rrt`, `run_rrt_demo.py`
- [x] 批量 / LeRobot 脚本骨架：`batch_collect.py`, `export_lerobot_style.py`

### 文档与材料

- [x] 开发文档与架构：`docs/dev/`
- [x] 面试讲稿与学习手册：讲稿 + 能力对齐文档
- [x] 10 天设计 / RRT 路线图：`design_10day.md`, `rrt_roadmap.md`

## 三天冲刺 → 成型作品集

对齐 `design_10day.md` Day 5–10 与投递展示要求；完成下列全部 `[ ]` 即可对外展示。

### Day 1 · 抓取可信度

- [x] 物理夹爪或约束抓取：替换 `sync_object_to_grasp_offset` kinematic demo
- [x] 物理向 success / failure 判定：Evaluator 接触 / 力 / 夹持判定
- [x] 抓取链路 pytest：新增 grasp / gripper 集成测试

### Day 2 · 批量数据与展示

- [x] 本地 batch ≥ 20 episode：`batch_collect.py --num-episodes 20`
- [x] 数据集 README（成功率统计）：`dataset/v1/README.md`
- [x] 三条 demo GIF 齐全：`demo_replay` / `demo_pick_success` / `demo_rrt_obstacle`

### Day 3 · 导出与成型投递

- [x] LeRobot 导出本地跑通：`export_lerobot_style.py dataset/v1`
- [x] 讲稿与实现一致：更新 `interview_walkthrough.md` 局限与演示命令
- [x] 30 秒可复现（README + CI）：README 快速开始 + CI 绿

## 更新方式

```bash
python scripts/update_project_docs.py
```

如已启用 `.githooks/pre-commit`，提交前会自动刷新
`README.md` 与 `docs/portfolio/project_status.md`。
