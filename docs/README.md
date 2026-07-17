# 文档索引

新人建议按以下顺序阅读：本索引 → [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) →
[DATA_FLOW.md](DATA_FLOW.md) → [CLOSED_LOOP_RUNBOOK.md](CLOSED_LOOP_RUNBOOK.md)。
作品集实验摘要见 [portfolio/CANONICAL_EXPERIMENT.md](portfolio/CANONICAL_EXPERIMENT.md)，
机器可读证据入口见 [../evidence/README.md](../evidence/README.md)。

面试和作品集展示优先看 **P0 文档**；Legacy PyBullet/KUKA 材料仅用于理解历史实现，不代表 Panda 当前主线。

## 日常开发（优先看这里）

| 文档 | 用途 |
|------|------|
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | **P0** 中游仓库职责、输入输出、边界 |
| [DATA_FLOW.md](DATA_FLOW.md) | **P0** raw episode → schema → release → training → handoff 数据流 |
| [DATA_CLEANING_AND_LEROBOT.md](DATA_CLEANING_AND_LEROBOT.md) | **P0/P1** 数据清洗整理、release、LeRobot/HF export 边界 |
| [TRAINING_PIPELINE.md](TRAINING_PIPELINE.md) | **P0** 最小 baseline training / eval / replay pipeline |
| [TRAINING_METHODS.md](TRAINING_METHODS.md) | **P0/P1** inspection-only、linear smoke、MLP BC、未来训练方式分层 |
| [INTER_REPO_CONTRACTS.md](INTER_REPO_CONTRACTS.md) | **P0** 三仓交接 gate、handoff、feedback loop 和模板入口 |
| [DEMO_GUIDE.md](DEMO_GUIDE.md) | **P0** 10 分钟可复现 mock Panda 闭环 |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | **P0** schema / action / checkpoint / handoff 排障 |
| [CLOSED_LOOP_RUNBOOK.md](CLOSED_LOOP_RUNBOOK.md) | **P0** 三仓 G0–G3 闭环跑手册 |
| [../AGENTS.md](../AGENTS.md) | **P0** 三仓 Agent 规范 V2.1 |
| [specs/PROJECT_EVIDENCE_AGENT_V1.md](specs/PROJECT_EVIDENCE_AGENT_V1.md) | Project Evidence Agent V1 设计、边界与验收标准；项目事实仍以 registry 选择出的代码、测试和产物为准 |

Project Evidence Agent 命令：

```bash
python3 -m project_knowledge.cli query --mode auto --no-llm --query "三仓当前职责是什么？"
python3 -m project_knowledge.cli audit --json-out /tmp/project-audit.json --markdown-out /tmp/project-audit.md
python3 -m project_knowledge.cli impact --base HEAD~1 --head HEAD
```

## Legacy 与历史规划（仅在明确查询历史实现时阅读）

| 文档 | 用途 |
|------|------|
| [archive/README.md](archive/README.md) | 已完成 SPEC、路线图与媒体计划的统一归档索引 |
| [legacy_pybullet/README.md](legacy_pybullet/README.md) | legacy PyBullet/KUKA 文档归档 |
| [dev/quickstart.md](dev/quickstart.md) | Legacy PyBullet/KUKA 安装、命令与 Demo 入口 |
| [dev/architecture.md](dev/architecture.md) | Legacy PyBullet/KUKA 模块职责与 Phase 命名 |
| [dev/data_schema.md](dev/data_schema.md) | Legacy PyBullet/KUKA episode 字段 |
| [dev/collection_pipeline.md](dev/collection_pipeline.md) | Legacy 采集、控制模式与规划器 |
| [dev/upstream_downstream_contracts.md](dev/upstream_downstream_contracts.md) | 历史过渡版 Panda contract；当前契约以 [INTER_REPO_CONTRACTS.md](INTER_REPO_CONTRACTS.md) 为准 |

## 参考

| 文档 | 用途 |
|------|------|
| [reference/knowledge_base.md](reference/knowledge_base.md) | 具身机械臂概念知识库 |
| [reference/learning_capability_alignment.md](reference/learning_capability_alignment.md) | **能力对齐学习手册**（AI 辅助开发后自检、阶段学习、岗位路径） |
| [THREE_REPO_ARCHITECTURE.md](THREE_REPO_ARCHITECTURE.md) | 三仓库总体架构图：上游 MuJoCo、中游数据闭环、下游 PyBullet 评估 |
| [templates/upstream_feedback_report.yaml](templates/upstream_feedback_report.yaml) | 中游向上游回流质量报告 / 采集调参建议模板 |
| [templates/downstream_replay_summary.yaml](templates/downstream_replay_summary.yaml) | 下游回传 replay / deployment 验证摘要模板 |
| [SIM_BACKENDS_AND_TRANSFER.md](SIM_BACKENDS_AND_TRANSFER.md) | 跨仿真后端边界：上游 MuJoCo、中游统一 schema、下游 PyBullet 与 Sim2Real-readiness |
| [TRAINING_TO_SIM2REAL.md](TRAINING_TO_SIM2REAL.md) | Panda 训练模块与 Sim2Real bridge 的仓库边界 |
| [reference/migration_ros2_moveit.md](reference/migration_ros2_moveit.md) | HAL → ROS2 / MoveIt 迁移 |
| [reference/integration_with_bridge.md](reference/integration_with_bridge.md) | 与 **ros2-moveit-pybullet-bridge** 的 Panda replay / PolicyRunner 边界 |

## 作品集 / 面试

| 文档 | 用途 |
|------|------|
| [portfolio/interview_walkthrough.md](portfolio/interview_walkthrough.md) | 3–5 分钟面试讲稿 |
| [portfolio/resume_description.md](portfolio/resume_description.md) | 在线简历描述与面试核心 Q&A |
| [portfolio/project_status.md](portfolio/project_status.md) | 自动生成的进度快照 |
| [portfolio/DATA_AND_ANALYSIS_PATHS.md](portfolio/DATA_AND_ANALYSIS_PATHS.md) | 中游 KUKA legacy 与 Panda 主线两条数据/分析路径说明 |
| [portfolio/DEEP_DESIGN_ANALYSIS.md](portfolio/DEEP_DESIGN_ANALYSIS.md) | 三仓库深度设计、训练策略分层、下游评估架构与冗余说明 |

## Phase 命名对照（避免混淆）

| 说法 | 文档 | 含义 |
|------|------|------|
| **Panda P0 主线** | `PROJECT_OVERVIEW.md`, `DATA_FLOW.md`, `TRAINING_PIPELINE.md` | 中游 schema / validation / training / handoff |
| **legacy PyBullet/KUKA** | `legacy_pybullet/README.md` | HAL / IK / RRT / grasp / LeRobot 早期样例 |

维护 README 与本文档后运行：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
```
