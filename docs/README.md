# 文档索引

日常开发从 **[开发指南](dev/quickstart.md)** 进入；不确定看哪份文档时，先看 **[架构与模块地图](dev/architecture.md)**。

## 日常开发（优先看这里）

| 文档 | 用途 |
|------|------|
| [dev/quickstart.md](dev/quickstart.md) | 安装、常用命令、Demo 入口 |
| [dev/architecture.md](dev/architecture.md) | 目录结构、模块职责、Phase 命名对照 |
| [dev/data_schema.md](dev/data_schema.md) | Episode 目录结构与字段 |
| [dev/collection_pipeline.md](dev/collection_pipeline.md) | 采集链路、控制模式、规划器 |
| [../AGENTS.md](../AGENTS.md) | Task / Motion / Evaluator 智能体职责 |

## 规划与路线图

| 文档 | 用途 |
|------|------|
| [planning/baseline_plan.md](planning/baseline_plan.md) | V0/V1/V2 数据闭环基线 |
| [planning/hal_ik_roadmap.md](planning/hal_ik_roadmap.md) | Phase 1：HAL + IK + 笛卡尔 |
| [planning/rrt_roadmap.md](planning/rrt_roadmap.md) | Phase 2：双向 RRT + 碰撞检测 |
| [planning/design_10day.md](planning/design_10day.md) | 10 天增强栈总览 |
| [planning/portfolio_roadmap.md](planning/portfolio_roadmap.md) | 广撒网 4 周投递路线 |

## 参考

| 文档 | 用途 |
|------|------|
| [reference/knowledge_base.md](reference/knowledge_base.md) | 具身机械臂概念知识库 |
| [reference/pybullet_audit.md](reference/pybullet_audit.md) | Phase 1 PyBullet 控制审计 |
| [reference/migration_ros2_moveit.md](reference/migration_ros2_moveit.md) | HAL → ROS2 / MoveIt 迁移 |

## 作品集 / 面试

| 文档 | 用途 |
|------|------|
| [portfolio/interview_walkthrough.md](portfolio/interview_walkthrough.md) | 3–5 分钟面试讲稿 |
| [portfolio/project_status.md](portfolio/project_status.md) | 自动生成的进度快照 |

## Phase 命名对照（避免混淆）

| 说法 | 文档 | 含义 |
|------|------|------|
| **design 10-day Phase 2** | `planning/rrt_roadmap.md` | 双向 RRT + PyBullet 碰撞 |
| **portfolio Phase 2** | `planning/portfolio_roadmap.md` | 批量采集 + LeRobot 导出 |
| **roadmap Phase 1** | `planning/hal_ik_roadmap.md` | HAL + IK + 笛卡尔插补 |

更新进度快照：

```bash
python scripts/update_project_docs.py
```
