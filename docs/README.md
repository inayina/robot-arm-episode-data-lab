# 文档索引

新人建议按以下顺序阅读：本索引 → [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) →
[DATA_FLOW.md](DATA_FLOW.md) → [CLOSED_LOOP_RUNBOOK.md](CLOSED_LOOP_RUNBOOK.md)。
作品集实验摘要见 [portfolio/CANONICAL_EXPERIMENT.md](portfolio/CANONICAL_EXPERIMENT.md)，
**对外作品集（五份）**见 [portfolio/README.md](portfolio/README.md)，
边界冻结见 [portfolio/BOUNDARY_FREEZE.md](portfolio/BOUNDARY_FREEZE.md)，
机器可读证据入口见 [../evidence/README.md](../evidence/README.md)。

面试和作品集展示优先看 **portfolio/README.md** 所列五份；Legacy PyBullet/KUKA 材料仅用于理解历史实现，不代表 Panda 当前主线。

**收口入口（2026-07-27）**：作品集母版见 [portfolio/PORTFOLIO_REFERENCE.md](portfolio/PORTFOLIO_REFERENCE.md)；
对外定位与模块所有权见 [portfolio/BOUNDARY_FREEZE.md](portfolio/BOUNDARY_FREEZE.md)；详细事实底稿见 [portfolio/FINAL_PROJECT_SUMMARY.md](portfolio/FINAL_PROJECT_SUMMARY.md)；
失败归因 [portfolio/BADCASE_ATTRIBUTION_SUMMARY.md](portfolio/BADCASE_ATTRIBUTION_SUMMARY.md)；
后续路线（P1/P2 仅登记）见 [FUTURE_WORK_ROADMAP.md](FUTURE_WORK_ROADMAP.md)。
诚实边界：open-loop Pass、interface Pass、`ran_isaac=true` 都**不是**任务成功、不是 Sim2Real、不是真机。

## 日常开发（优先看这里）

| 文档 | 用途 |
|------|------|
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | **P0** 中游仓库职责、输入输出、边界 |
| [DATA_FLOW.md](DATA_FLOW.md) | **P0** raw episode → schema → release → training → handoff 数据流 |
| [DATA_CLEANING_AND_LEROBOT.md](DATA_CLEANING_AND_LEROBOT.md) | **P0/P1** 数据清洗整理、release、LeRobot/HF export 边界 |
| [TRAINING_PIPELINE.md](TRAINING_PIPELINE.md) | **P0** 最小 baseline training / eval / replay pipeline |
| [TRAINING_METHODS.md](TRAINING_METHODS.md) | **P0/P1** inspection-only、linear smoke、MLP BC、未来训练方式分层 |
| [INTER_REPO_CONTRACTS.md](INTER_REPO_CONTRACTS.md) | **P0** 三仓交接 gate、handoff、feedback loop 和模板入口 |
| [EVALUATION_CONTRACT.md](EVALUATION_CONTRACT.md) | **P0** E0 run/episode/summary + Policy Adapter metadata 契约、六层指标、ownership |
| [POLICY_ADAPTER_CONTRACT.md](POLICY_ADAPTER_CONTRACT.md) | **P0** 模型无关 Policy Adapter 方法集与接入映射（契约冻结；运行时 ABC 待迭代） |
| [POLICY_ADAPTER_QUICKSTART.md](POLICY_ADAPTER_QUICKSTART.md) | **P0** Policy Adapter / 注册表 / Benchmark 三切片一页速查 |
| [POLICY_RUNTIME_INTEGRATION_SPEC.md](POLICY_RUNTIME_INTEGRATION_SPEC.md) | **M0–M6 implementation complete** M6 mock-policy ROS wiring Pass；SmolVLA authoritative 仍未切流 |
| [POLICY_RUNTIME_HOC_IMPLEMENTATION_ROADMAP.md](POLICY_RUNTIME_HOC_IMPLEMENTATION_ROADMAP.md) | **M0–M6 implementation complete** QoS、R2/R3、HOC 四泳道与 trace bundle 已做有界接线实测 |
| [portfolio/POLICY_RUNTIME_M6_WIRING_RESULTS.md](portfolio/POLICY_RUNTIME_M6_WIRING_RESULTS.md) | M6 运行拓扑、验收数字、竞态修复和不可升级结论 |
| [SINGLE_BLOCK_GENERALIZATION_BENCHMARK.md](SINGLE_BLOCK_GENERALIZATION_BENCHMARK.md) | **P0** 单方块受控泛化 Benchmark 规范（不跑完整 E4） |
| [VLA_GATE_V0_COMPATIBILITY_AUDIT.md](VLA_GATE_V0_COMPATIBILITY_AUDIT.md) | **Archived** LingBot-VLA 2.0 Gate V0 兼容性审计（路线 Closed；文档保留） |
| [VLA_GATE_V05_PANDA_ACTION_CONTRACT.md](VLA_GATE_V05_PANDA_ACTION_CONTRACT.md) | **P0** 模型无关 absolute EEF / channel / execution adapter 契约（LingBot 审计触发） |
| [VLA_GATE_V1_PREFLIGHT.md](VLA_GATE_V1_PREFLIGHT.md) | **Archived** LingBot Gate V1 本机预检（~6GB No-Go） |
| [SMOLVLA_GATE_S0_COMPATIBILITY_AUDIT.md](SMOLVLA_GATE_S0_COMPATIBILITY_AUDIT.md) | **P0** SmolVLA Gate S0 只读审计与门禁设计 |
| [SMOLVLA_GATE_S1_OFFICIAL_REPRO.md](SMOLVLA_GATE_S1_OFFICIAL_REPRO.md) | SmolVLA Gate S1 官方推理复现 |
| [SMOLVLA_GATE_S2_OPEN_LOOP.md](SMOLVLA_GATE_S2_OPEN_LOOP.md) | SmolVLA Gate S2 Panda open-loop |
| [SMOLVLA_GATE_S3_READY.md](SMOLVLA_GATE_S3_READY.md) | **Historical / Superseded** SmolVLA S3 v1 本地冻结与 Hold（已被 Recovery v3 取代；文档保留） |
| [SMOLVLA_S3_RECOVERY_IMPLEMENTATION_PLAN.md](SMOLVLA_S3_RECOVERY_IMPLEMENTATION_PLAN.md) | **P0** Recovery 实施计划（train-only split / `state[15]` / PEFT 修复） |
| [SMOLVLA_V3_EVAL_SOP.md](SMOLVLA_V3_EVAL_SOP.md) | **P0** Recovery v3 全链评测 SOP（prospective → gate_v3 → 有界 S4 → 下游 → 信封 → 出图） |
| [SMOLVLA_OPENLOOP_PERTURBATION_DESIGN.md](SMOLVLA_OPENLOOP_PERTURBATION_DESIGN.md) | **P1-0** clean 全帧 / K5 / 扰动锚点+close 窗口；禁 H=5·H=10 |
| [portfolio/OPENLOOP_PERTURBATION_RESULTS.md](portfolio/OPENLOOP_PERTURBATION_RESULTS.md) | **已执行** 2026-07-25 1080× nuisance 诊断结果（非 Gate） |
| [portfolio/QUEUE_RUNTIME_BENCH_RESULTS.md](portfolio/QUEUE_RUNTIME_BENCH_RESULTS.md) | **已执行** P1-1 sync vs async queue 时序（非 Isaac / 非 Gate） |
| [SMOLVLA_S3_ISAAC_S4_RUN_CHECKLIST.md](SMOLVLA_S3_ISAAC_S4_RUN_CHECKLIST.md) | **P0** 有界 Isaac S4 运行清单与批准勾选（已执行；lift 0/5 → Hold） |
| [SMOLVLA_S4_LIFT0_OFFLINE_ATTRIBUTION.md](SMOLVLA_S4_LIFT0_OFFLINE_ATTRIBUTION.md) | **P0** S4 lift 0/5 假设矩阵、遥测修订与修光后复测 |
| [FUTURE_WORK_ROADMAP.md](FUTURE_WORK_ROADMAP.md) | **P0** P0/P1/P2 登记表与执行闸门（P1/P2 不执行） |
| [SMOLVLA_S3_AUTODL_RUNBOOK.md](SMOLVLA_S3_AUTODL_RUNBOOK.md) | **P0** AutoDL S3 执行顺序 |
| [SMOLVLA_GATE_S1_OFFICIAL_REPRO.md](SMOLVLA_GATE_S1_OFFICIAL_REPRO.md) | **P0** Gate S1 官方推理复现 |
| [SMOLVLA_GATE_S2_OPEN_LOOP.md](SMOLVLA_GATE_S2_OPEN_LOOP.md) | **P0** Gate S2 Hold：接口 Pass / base zero-shot absolute-EEF No-Go |
| [ACT_HOME_NO_CLOSE_HYPOTHESIS_MATRIX.md](ACT_HOME_NO_CLOSE_HYPOTHESIS_MATRIX.md) | **P0** ACT diagnostic 止损与 HOME_NO_CLOSE 假设—证据矩阵 |
| [EVALUATION_REPORT.md](EVALUATION_REPORT.md) | **P0** 当前三仓审计结论、E3 0/20、E3.5 oracle 5/5 与 close→lift 5-seed No-Go 总报告 |
| [EMBODIED_POLICY_EVALUATION_SOP.md](EMBODIED_POLICY_EVALUATION_SOP.md) | **P0** 具身操作模型日常评测 SOP；含模型无关入口与指标权威来源对照 |
| [E2_ACT_BASELINE_PREFLIGHT.md](E2_ACT_BASELINE_PREFLIGHT.md) | E2 真实渲染 5-episode preflight、release 与 ACT 1-epoch GPU 证据；不等同于完整约 50 条 E2 |
| [E2_E3_MODEL_CARD.md](E2_E3_MODEL_CARD.md) | **P0** E2/E3 最终 checkpoint 选型、sha256、home/warm A/B 与止损结论 |
| [E2_SINGLE_RED_DATA_EXPANSION_RUNBOOK.md](E2_SINGLE_RED_DATA_EXPANSION_RUNBOOK.md) | **P0** E2 单红块续跑接力；E3 止损后下一 ROI |
| [E3P5_ISAAC_SCRIPTED_ORACLE_EXPERIMENT.md](E3P5_ISAAC_SCRIPTED_ORACLE_EXPERIMENT.md) | **P0** E3.5 Isaac scripted oracle 完整实验日志（动机→v1 失败→修复→v2b 通过→面试口述） |
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

**对外主导航（五份）**：见 [portfolio/README.md](portfolio/README.md)。

| 文档 | 用途 |
|------|------|
| [portfolio/README.md](portfolio/README.md) | 压缩导航（五份对外 + 边界冻结指针） |
| [portfolio/PORTFOLIO_REFERENCE.md](portfolio/PORTFOLIO_REFERENCE.md) | 对外作品集母版：5 分钟价值总览 + 30 分钟技术展开 |
| [portfolio/BOUNDARY_FREEZE.md](portfolio/BOUNDARY_FREEZE.md) | 定位、模块所有权、release 术语、证据包、提交冻结 |
| [portfolio/BADCASE_ATTRIBUTION_SUMMARY.md](portfolio/BADCASE_ATTRIBUTION_SUMMARY.md) | 失败归因案例 |
| [portfolio/EVIDENCE_INDEX.md](portfolio/EVIDENCE_INDEX.md) | 证据索引 + 最小公开证据包 |
| [portfolio/resume_description.md](portfolio/resume_description.md) | 简历话术 |

### 内部审计（不进主导航）

| 文档 | 用途 |
|------|------|
| [portfolio/tracks/README.md](portfolio/tracks/README.md) | 求职材料三轨总导航：技术面试、产品解决方案架构、RA 科研助理独立文档包 |
| [portfolio/tracks/technical_interview/README.md](portfolio/tracks/technical_interview/README.md) | 技术面试：系统链路、专题矩阵、current FAQ 使用规则、STAR 与 readiness |
| [portfolio/tracks/solution_architect/README.md](portfolio/tracks/solution_architect/README.md) | 解决方案架构：客户叙事、文档包、PoC、验收与交付清单 |
| [portfolio/tracks/research_assistant/README.md](portfolio/tracks/research_assistant/README.md) | RA 科研助理：RQ、研究材料、实验与论文交付清单 |
| [portfolio/FINAL_PROJECT_SUMMARY.md](portfolio/FINAL_PROJECT_SUMMARY.md) | 详细事实底稿与完整 Pass/Hold 表 |
| [portfolio/THREE_REPO_CANONICAL_FACTS.md](portfolio/THREE_REPO_CANONICAL_FACTS.md) | 三仓事实源与证据状态标签 |
| [portfolio/UNIFIED_EVAL_REPORT.md](portfolio/UNIFIED_EVAL_REPORT.md) | `unified_eval_report_v0` 跨后端信封 |
| [portfolio/SMOLVLA_RECOVERY_V3_PORTFOLIO.md](portfolio/SMOLVLA_RECOVERY_V3_PORTFOLIO.md) | Recovery v3 一页纸 |
| [portfolio/interview_walkthrough.md](portfolio/interview_walkthrough.md) | 3–5 分钟面试讲稿 |
| [portfolio/project_status.md](portfolio/project_status.md) | 自动生成的进度快照 |
| [portfolio/DEEP_DESIGN_ANALYSIS.md](portfolio/DEEP_DESIGN_ANALYSIS.md) | 三仓库深度设计分析 |
| [portfolio/EMBODIED_EVALUATION_ENGINEER_ALIGNMENT.md](portfolio/EMBODIED_EVALUATION_ENGINEER_ALIGNMENT.md) | 岗位对齐长文 |
| [portfolio/RA_RESEARCH_ASSISTANT_STRENGTHENING_SPEC.md](portfolio/RA_RESEARCH_ASSISTANT_STRENGTHENING_SPEC.md) | RA 科研助理方向补强：研究问题、假设、实验协议、统计与论文式交付 |
| [portfolio/PRODUCT_SOLUTION_ARCHITECT_STRENGTHENING_SPEC.md](portfolio/PRODUCT_SOLUTION_ARCHITECT_STRENGTHENING_SPEC.md) | 产品解决方案架构方向补强：客户场景、reference architecture、PoC、验收与移交 |
| [EVALUATION_REPORT.md](EVALUATION_REPORT.md) | 评测漏斗与 Go/No-Go 审计 |
| [E3P5_ISAAC_SCRIPTED_ORACLE_EXPERIMENT.md](E3P5_ISAAC_SCRIPTED_ORACLE_EXPERIMENT.md) | E3.5 oracle 实验日志 |

## Phase 命名对照（避免混淆）

| 说法 | 文档 | 含义 |
|------|------|------|
| **Panda P0 主线** | `PROJECT_OVERVIEW.md`, `DATA_FLOW.md`, `TRAINING_PIPELINE.md` | 中游 schema / validation / training / handoff |
| **legacy PyBullet/KUKA** | `legacy_pybullet/README.md` | HAL / IK / RRT / grasp / LeRobot 早期样例 |

维护 README 与本文档后运行：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
```
