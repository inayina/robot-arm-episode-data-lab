# Three-Repo README Audit

> **历史审计（阶段 1）**：本文保留 2026-07-14 的 MLP/handoff 基线审计，不再代表当前首页。
> ACT→Isaac E2/E3/E3.5/E3.6 的当前事实与 README 整理结果，以
> [EVALUATION_REPORT.md](../EVALUATION_REPORT.md) 和
> [THREE_REPO_CANONICAL_FACTS.md](THREE_REPO_CANONICAL_FACTS.md) 为准。

阶段 1 审计报告。本文只记录当时的 README 信息架构、措辞、实验数字和资产证据审计结论。

## A. Cross-Repo Conflict Table

| 主题 | 上游表述 | 中游表述 | 下游表述 | 代码/测试事实 | 建议统一表述 |
| --- | --- | --- | --- | --- | --- |
| 三仓路径 | 用户任务假设共同父目录 | 当前仓为中游 | 下游在 ROS workspace | 实际路径分别为 `/home/ina/dev/...`、`/home/ina/robot-sim-lab/...`、`/home/ina/ros2_ws/src/...` | 文档写“三个兄弟/协作仓库”，不要依赖共同父目录假设 |
| Episode 采集 | 上游 recorder/batch generator | 中游读取 raw episode | 下游消费 handoff | 上游 `batch_generator.py` 与 recorder 负责采集；中游 adapter/release；下游 loader/replay | 上游产生 raw episode，中游适配训练并打包，下游 replay/risk |
| LeRobot 导出 | 上游 recorder 写 LeRobot-style episode | 中游 release/handoff 可导出训练视图 | 下游不导出数据集 | `docs/INTER_REPO_CONTRACTS.md` upstream fields；中游 `prepare_dataset_release.py` | “上游录制 episode；中游发布训练 release/handoff” |
| Schema 适配 | 不负责 | 负责 `state[8]` 与 `ee_delta_gripper[7]` | 校验并消费 | `training/adapters/upstream_m6.py:12`, `configs/robot_schemas/panda.yaml:23` | Schema 适配归中游 |
| 训练 | 不负责正式训练 | MLP BC canonical；ACT code 未完整验证 | 不训练 | MLP metrics 存在；ACT script 存在但无 canonical artifact | “当前 canonical 模型为 MLP BC；ACT 为代码路径/规划验证，不作为已完成主线” |
| Replay | 不负责 PyBullet replay | 生成 predicted JSONL/handoff | 执行 JSONL replay | `replay_mlp_policy.py`, `jsonl_action_replay_policy.py`, `benchmark_system.py` | 中游生成 replay 输入，下游执行 replay |
| 物理执行 | MuJoCo 软件仿真交互 | 不做物理执行 | PyBullet replay 执行 | 上游 MuJoCo；下游 PyBullet; 中游无 runtime control | 分别写 MuJoCo 上游与 PyBullet 下游，不写实机执行 |
| 风险监控 | 不负责下游 risk benchmark | 不执行 risk | 下游 risk/monitor | `dist_monitor`, `risk_engine`, `benchmark_system.py` | 风险与故障 benchmark 归下游 |
| ACT 是否完成 | 不应声明 | 代码存在，canonical 未验证 | 不作为 runtime strategy | `train_act_lerobot.py` 有代码；未发现 canonical run | ACT 标为 `implemented_not_fully_verified` 或规划，不写已完成 |
| MLP BC 是否 canonical | 上游不拥有 | 是当前 canonical 训练模型 | 下游消费其 handoff | `CANONICAL_EXPERIMENT.md`, `mlp_metrics.json` | “当前 canonical 训练模型为低维 MLP BC” |
| MLP 优于线性 | 不归上游 | 中游有 `mlp_bc_loss_comparison.png` 和 `docs/portfolio/linear_same_split_metrics.json` 证据 | 不归下游 | Linear same-split normalized MSE: train `0.5580591706337537`, test `0.5800455135789114`; MLP normalized MSE: train `0.049142921178624864`, test `0.2350177516977917`; 另有 `panda_linear_bc/metrics.json` frame-split smoke MSE，不能混用 | 可写“同一 24/6 episode split 的 normalized-MSE 图口径下 MLP 低于 Linear”；不能写成任务成功率结论 |
| Online rollout | 不负责 | 未发现成功证据 | 下游 replay 不是在线学习/在线 ACT | `CLOSED_LOOP_RUNBOOK.md:172`, `JsonlActionReplayPolicy` | 写“offline prediction + open-loop replay smoke”，不写 online rollout 完成 |
| 策略部署 | 不部署策略 | 生成 checkpoint/predicted actions | 下游 replay handoff | 下游 replay 是验证平台，不是实机部署 | 写“handoff replay 验证”，不写生产部署 |
| 自主抓取 | batch generator 有上游 gate | 中游不重新物理判定 | 下游未验证物理抓取成功 | `_validate_episode` upstream; downstream status says physical grasp future | 写“上游仿真物理 gate；下游 replay/risk，不证明物理抓取成功” |
| Sim2Real | scope 文档明确不证明 | docs 有 “Sim2Real-readiness” | README 已提示未完成完整 Sim2Real | `PROJECT_SCOPE_AND_ACCEPTANCE.md:22`, `CURRENT_STATUS.md:28` | 统一为 “Sim2Sim / Sim2Real-readiness” |
| 真实机械臂数据 | 不应默认 | 不应默认 | 不应默认 | 当前 canonical 数据来自 MuJoCo/Panda sim batch | 写“Panda 仿真 episode”，不写真实机械臂数据 |
| Domain Randomization | 上游 M7 可有演示资产 | 中游可分析数据 | 下游有分布图资产 | 未发现能证明泛化的 canonical benchmark | 写“用于压力/分布可视化”，不写确保泛化 |
| 下游抓取成功 | 不负责 | 不负责 | 当前主线是 replay/monitor/risk | `CURRENT_STATUS.md:28` 将 downstream physical object-grasp validation scene 列为 partial/future | 不写“下游验证抓取成功” |
| HOC/Dashboard | 非上游主线 | 非中游主线 | 下游可作为 risk/HOC 辅助 | `CURRENT_STATUS.md` 支持 HOC，但不是 Panda canonical 核心步骤 | README 主体保持 Panda handoff replay；HOC 放扩展/辅助 |
| Handoff/benchmark ID | 上游无 | canonical `panda_30_mlp_bridge_v0` | latest evidence `panda_closed_loop_20260712_214747_bridge` | `handoff_manifest.json` 与 `evidence/meta/run_summary.json` 不同 | README 写清 canonical 2026-07-11 与 latest archived 2026-07-12 的差异 |
| Downstream latency/fault | 不负责 | canonical doc 有 17.626/49.508/94.399 | latest evidence 是 9.79/34.218/no fault | 原始 canonical downstream summary 未定位 | 标为冲突，先不写统一 performance claim |

## B. Wording Audit

| 词/短语 | 证据情况 | 决策 | 建议替代表述 |
| --- | --- | --- | --- |
| 工业级 | 上游目标/设计语境出现；未证明生产/认证/实机可靠性 | 降级 | “面向工业软件栈设计的 ROS 2/Panda 仿真系统” |
| 生产级 | 当前 scope 明确排除 certified/real robot guarantee | 删除或仅作反例 | “研究/作品集级软件验证” |
| 完整闭环 | G0-G3 有最小闭环证据，但非实机/非完整 Sim2Real | 降级 | “最小工程闭环”或“软件仿真闭环” |
| 全链路 | 可指三仓数据流，但容易暗示实机 | 降级 | “三仓数据-训练-replay 验证链路” |
| 真实实验 | 终端/JSON/benchmark 是真实运行产物；不是实机实验 | relabel | “真实运行产物/终端证据” |
| 真实终端 | 可作为截图证据，但需命令、日期、ID 对应 | relabel | “terminal evidence with run ID” |
| 真实抓取 | 上游是 MuJoCo/Panda sim gate；无实机抓取证据 | 删除/降级 | “仿真抓取 episode gate” |
| 确保泛化 | 未发现支撑泛化保证的测试 | 删除 | “用于分布/扰动观察，不保证泛化” |
| 策略部署 | 下游是 replay/risk 验证，不是实机部署 | 降级 | “policy handoff replay” |
| 在线推理 | Downstream replay is open-loop; ACT runtime 未完成 | 降级 | “JSONL replay / offline prediction” |
| Sim2Real | 当前只支持 readiness 叙述 | 降级 | “Sim2Sim / Sim2Real-readiness” |
| 实机 | 当前 canonical 无实机证据 | 删除 | “Panda software simulation” |
| 全自动 | batch generation 可自动采集，但不等于在线自主策略 | 降级 | “batch episode generation” |
| 高可靠 | 有测试/health/fault smoke，不足以证明高可靠 | 降级 | “带 watchdog/risk smoke 验证” |
| 一键复现 | 部分 mock/脚本可跑，完整 ROS 环境依赖强 | 降级 | “quickstart / environment-dependent full path” |
| 向量化 | 如指 numpy/tensor 计算可以保留技术语境；不能作为 RAG 能力 | 限定 | “tensor/numpy batch processing” |
| 向量检索 | `scripts/rag_assistant.py` 是项目检索助手；阶段 1 未确认 embedding/vector DB | 删除或限定 | “项目 RAG/文本检索，具体实现以脚本为准” |
| 智能 Agent | AGENTS 是职责映射，不代表自主智能体系统完整上线 | 降级 | “Agent responsibility map” |

## C. Experiment Number Audit

| 数字/ID | 出现位置 | 原始来源 | 审计结论 |
| --- | --- | --- | --- |
| 30 episodes | canonical doc、release、metrics、G0 evidence | `data/exports/panda_30_release/manifest.json`, `evidence/upstream/validate_dataset.json` | 一致，证据充分 |
| 71,737 frames | canonical doc、release、metrics、handoff | `manifest.json`, `mlp_metrics.json`, `handoff_manifest.json` | 一致，证据充分 |
| 30/30 PASS | canonical doc、G0 validation | `evidence/upstream/validate_dataset.json` | 一致，证据充分 |
| 100 epochs | MLP metrics | `training/reports/panda_mlp_bc/mlp_metrics.json` | 证据充分；代码默认是 50，所以 README 应写该 run 使用 100 epochs |
| MLP train/test loss | MLP metrics | `training/reports/panda_mlp_bc/mlp_metrics.json` | train `0.049142921178624864`, test `0.2350177516977917` |
| Linear same-split normalized loss | rerun metrics | `docs/portfolio/linear_same_split_metrics.json` | train `0.5580591706337537`, test `0.5800455135789114`; matches MLP episode split and normalized action-space metric |
| Linear train/val loss | linear smoke metrics | `training/reports/panda_linear_bc/metrics.json` | train `0.0003472642607876226`, val `0.000347889306395142`; 这是 frame-split smoke MSE artifact，不等同于 loss comparison 图中的 normalized same-split values |
| 24/6 split | MLP metrics | `training/reports/panda_mlp_bc/mlp_metrics.json` | MLP by episode split; linear smoke uses different split/口径 |
| CUDA/GPU | MLP metrics | `training/reports/panda_mlp_bc/mlp_metrics.json` | selected device CUDA; GPU field recorded |
| Handoff ID | canonical handoff | `training/reports/panda_mlp_bc/bridge_handoff/handoff_manifest.json` | `panda_30_mlp_bridge_v0` |
| Latest archived release/handoff ID | latest evidence bundle | `evidence/meta/run_summary.json` | `panda_closed_loop_20260712_214747` / `_bridge`; 与 canonical ID 不同 |
| 3,275 gripper out-of-range | replay check | `training/reports/panda_mlp_bc/bridge_handoff/replay_check.json` | 必须在 README/notes 中作为 warning，不可隐藏 |
| Normal latency 17.626/49.508 ms | canonical doc | `docs/portfolio/CANONICAL_EXPERIMENT.md` | 原始 downstream summary 未定位，标为文档声明 |
| Fault alarm 94.399 ms | canonical doc | `docs/portfolio/CANONICAL_EXPERIMENT.md` | 原始 downstream summary 未定位，标为文档声明 |
| Latest downstream latency 9.79/34.218 ms | latest archived evidence | `evidence/downstream/benchmark_summary.json` | 1-episode smoke，no fault injection |
| KL/W1/MMD | downstream code and assets | `dist_monitor/metrics_core.py`, downstream assets | 计算实现存在；phase 1 未定位 canonical Panda 数值 |
| Downstream sample 10/10 | downstream docs samples | `docs/samples/system-validation/*` | 样例/旧 evidence，不应覆盖 current canonical |
| 实验日期 | canonical 2026-07-11; latest bundle 2026-07-12 | canonical doc, `evidence/meta/run_summary.json` | 日期不同，README 应标注是哪一次 run |

## D. Repository Responsibility Audit

| 仓库 | 主边界 | 当前状态 | 证据充分性 |
| --- | --- | --- | --- |
| 上游 | 目标/遥操作或批采输入 -> 安全与运动控制 -> MuJoCo 仿真交互 -> episode 录制和上游物理门禁 -> raw episode | 符合 | 充分：`docs/AGENTS.md`, `batch_generator.py`, G0 evidence |
| 上游不负责 | 中游 schema 适配、release、MLP/ACT 正式训练、下游 PyBullet replay、下游 risk benchmark | 符合 | 充分：`docs/AGENTS.md:84`, `docs/INTER_REPO_CONTRACTS.md:3` |
| 中游 | raw episode -> adapter -> schema/data quality validation -> release -> EDA -> baseline training -> offline evaluation -> predicted action replay -> bridge handoff | 符合 | 充分：adapter/inspector/release/train/replay/handoff code + artifacts |
| 中游不负责 | ROS 2 实时控制、MuJoCo 物理执行、PyBullet replay 执行、实机控制 | 符合 | 充分：`AGENTS.md:45`, `docs/TRAINING_TO_SIM2REAL.md:1` |
| 下游 | bridge handoff -> 静态校验 -> action adapter -> Panda PyBullet replay -> tracking/distribution monitoring -> risk/fault benchmark -> downstream report | 大体符合；部分 monitoring canonical 证据弱 | loader/adapter/tests/benchmark 充分；sensor fusion/risk full scenario 部分充分 |
| 下游不负责 | raw episode 采集、数据清洗、模型训练、真实机械臂驱动、实机 Sim2Real | 符合 | 充分：`docs/AGENTS.md:69`, `docs/CURRENT_STATUS.md:28` |

## Asset Actions

| 资产范围 | 处理建议 | 原因 |
| --- | --- | --- |
| 三仓 `three_repo_dataflow_diagram.*` | `regenerate` from one canonical source | 不允许三仓手工维护内容不同但标题相同的流程图 |
| 三仓 `three_repo_run_evidence.png` | `regenerate` and link to exact run ID | 上游/下游文件当前 dirty；canonical 与 latest archived 数字冲突 |
| 中游 `assets/diagrams/mlp_bc_loss_comparison.png` | `keep` | 图已由 `docs/portfolio/linear_same_split_metrics.json` 和 `mlp_metrics.json` 重生成；不要与 `panda_linear_bc/metrics.json` frame-split smoke MSE 混用 |
| 中游 KUKA/PyBullet gifs/videos/screenshots | `move_to_legacy` | 不属于 Panda mainline |
| 中游架构/流程图 | `relabel` | 设计图不能作为运行证据 |
| 上游 M1-M7 media | `keep` or `relabel` by evidence level | 需要在 README 只保留 3-5 个核心证据，其余放 evidence index |
| 下游 `docs/assets/dual-repo-*`, `same-task-*`, `m2-iiwa-*` | `move_to_legacy` | 旧 dual-repo/iiwa，不是 Panda handoff replay 主线 |
| 下游 `docs/samples/.capture_tmp/*` | `delete` or `archive` | 临时生成物，不应作为 README evidence |
| 下游 Panda replay plots | `keep` if tied to benchmark JSON; otherwise `relabel/regenerate` | 数据图必须有生成脚本和输入产物 |

## README Directory Drafts

### Upstream README Draft

1. 项目一句话定位：ROS 2 Jazzy + MuJoCo 的 Panda 软件仿真、遥操作/批采、安全控制和 episode 录制上游
2. 本仓在三仓中的位置：raw episode producer
3. 当前已验证能力：teleop/batch, safety, MoveIt Servo, MuJoCo, recorder, upstream gate
4. Canonical experiment 中本仓步骤：30 Panda sim episodes, batch_generator gate, raw episode handoff
5. 系统/data flow 图：引用 canonical 三仓图的 upstream slice
6. 核心证据：最多 3-5 个 M1/M6/M7/G0 evidence
7. 快速验证：software sim, Docker/headless, full ROS path, hardware path as future only
8. 代码与目录导航
9. 当前边界和未完成事项
10. Legacy/扩展阅读
11. 关键文档
12. English brief

### Midstream README Draft

1. 项目一句话定位：Panda episode 数据适配、质量检查、release、MLP BC 离线训练评估与下游 handoff 中游
2. 本仓在三仓中的位置：raw episode consumer and release/handoff producer
3. 当前已验证能力：adapter, inspector, release, EDA, MLP BC, replay JSONL, handoff
4. Canonical experiment：30 episodes, 71,737 frames, MLP metrics, handoff warning
5. 数据/schema/action flow 图
6. 核心证据：manifest, inspection, metrics, replay_check, latest G2 bundle
7. 快速验证：inspect/release/train/replay/handoff; mock vs real data paths separated
8. 代码与目录导航
9. 当前边界和未完成事项：no real Sim2Real, no online rollout, ACT not canonical completed
10. Legacy KUKA/PyBullet folded section
11. 关键文档：canonical facts, runbook, architecture, evidence index
12. English brief

### Downstream README Draft

1. 项目一句话定位：消费 Panda policy handoff，在 PyBullet 中执行 replay，并完成 tracking、分布偏移、故障注入和风险监控的下游验证平台
2. 本仓在三仓中的位置：handoff consumer and replay/risk validator
3. 当前已验证能力：loader, JSONL replay, PandaActionAdapter, benchmark summary, tests
4. Canonical experiment 中本仓步骤：load handoff, run `panda_jsonl_replay`, produce benchmark summary
5. Replay/monitor/risk flow 图
6. 核心证据：handoff loader tests, adapter tests, benchmark JSON, selected plots
7. 快速验证：fixture smoke, Panda handoff replay, fault injection when available
8. 代码与目录导航
9. 当前边界和未完成事项：no raw collection, no training, no real robot, no complete Sim2Real
10. Legacy iiwa/dual-repo/portfolio folded section
11. 关键文档
12. English brief

## Stage-2 Prerequisites

README rewrite should wait until:

- canonical downstream benchmark summary for `panda_30_mlp_bridge_v0` is either located or the canonical doc is updated to the latest archived run;
- common dataflow/evidence images are regenerated from one canonical source;
- MLP-vs-linear figure is regenerated or relabeled;
- each README links to its repo-local `docs/portfolio/EVIDENCE_INDEX.md` and this canonical facts file.
