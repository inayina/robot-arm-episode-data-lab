# Three-Repo Canonical Facts

本文件是三仓 README 重构前的阶段 1 统一事实源。它只记录当前可追溯事实，不改 README，不用行业经验补全项目状态。

统一一句话主线：

> Panda 机械臂的多仓数据、训练、离线评估与 Sim2Sim / Sim2Real-readiness 验证闭环。

当前证据充分确认的是软件仿真与下游 PyBullet replay/readiness 验证；当前项目证据不足，无法确认真实机械臂部署、已完成真实 Sim2Real、稳定在线自主抓取或离线 loss 提升等同于任务成功率提升。

## Evidence Rules

能力状态只使用以下分类：

| 分类 | 含义 |
| --- | --- |
| `implemented_and_verified` | 已实现且有测试或运行产物证据 |
| `implemented_not_fully_verified` | 有当前代码，但缺少完整运行验证或 canonical 产物 |
| `smoke_or_mock_only` | 仅 smoke、mock、fixture 或最小示例 |
| `documented_plan_only` | 文档规划，代码或运行产物未确认 |
| `legacy` | 历史实现，不属于 Panda 当前主线 |
| `not_supported` | 当前未实现或明确不支持 |

项目事实回答时还应区分：已实现、文档声明，代码未确认、基于证据的推断、通用背景知识。

## Repository Roles

| 仓库 | 输入 | 处理 | 输出 | 明确不负责 | 状态 | 主要证据 |
| --- | --- | --- | --- | --- | --- | --- |
| `ros2-arm-teleoperation-suite` | 目标/遥操作或 batch 任务输入 | 安全与运动控制、MoveIt Servo、MuJoCo 交互、episode 录制、上游物理门禁 | raw episode、`episode_*/train/`、`meta.json`、G0 validation | 中游 schema/release/training；下游 PyBullet replay/risk benchmark | `implemented_and_verified` | `docs/AGENTS.md:13`, `docs/AGENTS.md:26`, `docs/AGENTS.md:37`, `docs/AGENTS.md:54`, `src/synth_data_gen/synth_data_gen/batch_generator.py:933`, `evidence/upstream/validate_dataset.json` |
| `robot-arm-episode-data-lab` | 上游 raw Panda episode | adapter、schema/data quality validation、release、EDA、MLP BC、offline eval、predicted action replay、bridge handoff | `frames.jsonl`、release manifest、metrics、`predicted_actions.jsonl`、bridge handoff bundle | ROS 2 实时控制、MuJoCo 物理执行、PyBullet replay 执行、实机控制 | `implemented_and_verified` for release/MLP/handoff; ACT is lower confidence | `AGENTS.md:45`, `configs/robot_schemas/panda.yaml:23`, `training/adapters/upstream_m6.py:12`, `training/scripts/inspect_dataset.py:303`, `training/scripts/train_mlp_policy.py:1`, `training/scripts/prepare_bridge_handoff.py:247` |
| `ros2-moveit-pybullet-bridge` | midstream bridge handoff | 静态校验、JSONL replay、Panda action adapter、PyBullet replay、tracking/distribution monitoring、risk/fault benchmark | downstream benchmark summary/report | raw episode 采集、数据清洗、模型训练、真实机械臂驱动、实机 Sim2Real | `implemented_and_verified` for loader/adapter/tests and smoke benchmark; broader monitoring is partially verified | `docs/AGENTS.md:9`, `pybullet_bridge/learning/panda_handoff.py:34`, `pybullet_bridge/policy/jsonl_action_replay_policy.py:20`, `pybullet_bridge/control/panda_action_adapter.py:43`, `scripts/benchmark_system.py:439`, `pybullet_bridge/test/test_panda_handoff.py:46` |

## Canonical Experiment

| 项 | 当前事实 | 状态 | 证据 |
| --- | --- | --- | --- |
| Canonical 文档 ID | `panda_30_mlp_20260711` | `implemented_and_verified` as documented experiment source | `docs/portfolio/CANONICAL_EXPERIMENT.md:3` |
| 上游数据源 | `/home/ina/dev/ros2-arm-teleoperation-suite/data/episodes_mlp` | `implemented_and_verified` | `evidence/upstream/validate_dataset.json`, `data/exports/panda_30_release/manifest.json` |
| 数据规模 | 30 episodes, 71,737 frames | `implemented_and_verified` | `docs/portfolio/CANONICAL_EXPERIMENT.md:8`, `data/exports/panda_30_release/manifest.json`, `training/reports/panda_mlp_bc/mlp_metrics.json` |
| G0 上游 gate | `upstream_gate=batch_generator`, 30/30 valid | `implemented_and_verified` | `evidence/upstream/validate_dataset.json`, `src/synth_data_gen/synth_data_gen/batch_generator.py:933` |
| 中游 release | `release_id=panda_30_release_v0`, `dataset_format=panda_release_v0` | `implemented_and_verified` | `data/exports/panda_30_release/manifest.json` |
| 训练模型 | MLP BC, 100 epochs, PyTorch/CUDA | `implemented_and_verified` | `training/reports/panda_mlp_bc/mlp_metrics.json`, `training/scripts/train_mlp_policy.py:143` |
| MLP offline loss | train loss `0.049142921178624864`, test loss `0.2350177516977917` | `implemented_and_verified` | `training/reports/panda_mlp_bc/mlp_metrics.json` |
| Linear same-split normalized MSE | train `0.5580591706337537`, test `0.5800455135789114`, same 24/6 episode split as MLP | `implemented_and_verified` | `docs/portfolio/linear_same_split_metrics.json` |
| 线性 smoke baseline | train loss `0.0003472642607876226`, val loss `0.000347889306395142` | `smoke_or_mock_only` | `training/reports/panda_linear_bc/metrics.json`, `training/scripts/train_act_smoke.py:1` |
| MLP vs linear | `assets/diagrams/mlp_bc_loss_comparison.png` 可说明同一 24/6 episode split 下 MLP normalized MSE bar 低于 Linear bar；但 `panda_linear_bc/metrics.json` 是另一个 frame-split smoke MSE artifact，不能混作同一口径结论 | `implemented_and_verified` with scope caveat | `scripts/plot_portfolio_results.py:113`, `training/reports/panda_mlp_bc/mlp_metrics.json`, `docs/portfolio/linear_same_split_metrics.json`, `training/reports/panda_linear_bc/metrics.json` |
| Handoff | `handoff_id=panda_30_mlp_bridge_v0`, 30 episodes, 71,737 actions | `implemented_and_verified` | `training/reports/panda_mlp_bc/bridge_handoff/handoff_manifest.json` |
| Handoff warning | 3,275 gripper commands outside `[0, 1]`; bridge must clamp or reject | `implemented_and_verified` | `training/reports/panda_mlp_bc/bridge_handoff/replay_check.json`, `training/scripts/prepare_bridge_handoff.py:233` |
| Downstream canonical numbers | CANONICAL 文档写 normal mean/max `17.626/49.508 ms` and fault alarm `94.399 ms` | `documented_plan_only` until original summary is located | `docs/portfolio/CANONICAL_EXPERIMENT.md:47` |
| Latest archived downstream run | release `panda_closed_loop_20260712_214747`, 1/1 completed, mean/max `9.79/34.218 ms`, no fault injection | `smoke_or_mock_only` | `evidence/meta/run_summary.json`, `evidence/downstream/benchmark_summary.json` |

结论：30 episodes、71,737 frames、release、MLP metrics 和 handoff bundle 证据充分；下游 latency/fault 数字存在 canonical 文档与最新 archived run 不一致，README 不应挑选单一数字作为统一结论，除非先定位原始 benchmark summary。

## Observation And Action Contract

| 字段 | 语义 | 当前事实 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| Upstream action | `ee_pose_gripper[8]` | 上游兼容 action layout | `implemented_and_verified` | `configs/robot_schemas/panda.yaml:79`, `training/adapters/upstream_m6.py:12` |
| Midstream state | `state[8]` | `joint_position[7] + gripper_opening[1]` | `implemented_and_verified` | `configs/robot_schemas/panda.yaml:23`, `training/adapters/upstream_m6.py:63` |
| Midstream action | `ee_delta_gripper[7]` | `delta_xyz[3] + delta_rpy[3] + gripper_cmd[1]` | `implemented_and_verified` | `configs/robot_schemas/panda.yaml:67`, `training/adapters/upstream_m6.py:77` |
| Optional observation | `ee_pose[7]`, `object_pose[7]`, `ft[6]`, images | object/ft present in release; images missing warning | `implemented_and_verified` | `configs/robot_schemas/panda.yaml:32`, `data/exports/panda_30_release/inspection_report.json` |
| Downstream replay input | `ee_delta_gripper[7]` | consumed by `panda_jsonl_replay` and `PandaActionAdapter` | `implemented_and_verified` | `docs/AGENTS.md:20`, `pybullet_bridge/control/panda_action_adapter.py:97` |

中游 `filter_scope=training_split_only` 时只检查 schema 与 training split，不从 `observation.object_pose` 重新推导 lift/place 成败。证据：`AGENTS.md:66`, `training/scripts/inspect_dataset.py:303`。

## Training And Evaluation Facts

| 能力 | 事实 | 状态 | 证据 |
| --- | --- | --- | --- |
| MLP BC | 低维 state 到 `ee_delta_gripper`，feature contract 排除图像/触觉 | `implemented_and_verified` | `training/scripts/train_mlp_policy.py:166`, `training/reports/panda_mlp_bc/mlp_metrics.json` |
| ACT smoke | 文件名含 ACT 但实际是 ridge/linear smoke baseline | `smoke_or_mock_only` | `training/scripts/train_act_smoke.py:1` |
| LeRobot ACT script | 有 LeRobot ACTPolicy 构建代码，但阶段 1 未发现 canonical 完整训练产物 | `implemented_not_fully_verified` | `training/scripts/train_act_lerobot.py:1`, `training/scripts/train_act_lerobot.py:168` |
| Offline eval | 当前证据是 loss/MAE 和 replay JSONL 检查，不等同任务成功率 | `implemented_and_verified` | `training/reports/panda_mlp_bc/mlp_metrics.json`, `training/reports/panda_mlp_bc/bridge_handoff/replay_check.json` |
| Online policy rollout | 阶段 1 未发现中游在线 rollout 成功证据 | `not_supported` | `docs/CLOSED_LOOP_RUNBOOK.md:172` |

## Downstream Runtime Facts

| 能力 | 事实 | 状态 | 证据 |
| --- | --- | --- | --- |
| Handoff loader | 校验 manifest、replay check、schema/action/type/finite/action shape | `implemented_and_verified` | `pybullet_bridge/learning/panda_handoff.py:34`, `pybullet_bridge/test/test_panda_handoff.py:46` |
| JSONL replay | open-loop replay `ee_delta_gripper[7]` | `implemented_and_verified` | `pybullet_bridge/policy/jsonl_action_replay_policy.py:20` |
| PandaActionAdapter | 支持 hold/mock_ik/pybullet_ik，含 delta/gripper/finite 校验 | `implemented_and_verified` | `pybullet_bridge/control/panda_action_adapter.py:43`, `pybullet_bridge/test/test_panda_action_adapter.py:9` |
| Benchmark | `panda_jsonl_replay` CLI and summary fields implemented | `implemented_and_verified` | `scripts/benchmark_system.py:500`, `scripts/benchmark_system.py:439` |
| Sensor fusion/contact/slip | 节点代码存在；阶段 1 未找到 canonical Panda handoff 运行证据 | `implemented_not_fully_verified` | `pybullet_bridge/sensor_fusion_node.py:20` |
| Risk engine | aggregation code exists; canonical benchmark only proves limited smoke evidence | `implemented_not_fully_verified` | `pybullet_bridge/risk_engine/aggregator.py:8`, `evidence/downstream/benchmark_summary.json` |
| Real Panda driver | 当前项目证据不足，无法确认 | `not_supported` | `docs/CURRENT_STATUS.md:28` |

## What Current Evidence Cannot Prove

| 声明 | 结论 | 证据状态 |
| --- | --- | --- |
| 已完成真实机械臂部署 | 当前项目证据不足，无法确认 | `not_supported` |
| 已完成真实 Sim2Real | 当前项目证据不足，无法确认；只能写 Sim2Sim / Sim2Real-readiness | `not_supported` |
| 稳定在线自主抓取 | 当前项目证据不足，无法确认 | `not_supported` |
| MLP loss 提升等同抓取成功率提升 | 当前项目证据不足，无法确认 | `not_supported` |
| 下游 PyBullet replay 已验证物理抓取成功 | 当前项目证据不足，无法确认；downstream 主要验证 replay/monitor/risk | `implemented_not_fully_verified` for replay, not for grasp success |
| ACT 已完成 canonical training/run | 当前项目证据不足，无法确认 | `implemented_not_fully_verified` for code only |

## Legacy Boundary

| 范围 | 结论 | 状态 | 证据 |
| --- | --- | --- | --- |
| 中游 `agents/`, `core/` | PyBullet/KUKA 历史 Agent，不与 Panda training release 混用 | `legacy` | `AGENTS.md:11`, `archive/README.md` |
| 中游 KUKA pick/lift assets | 只能放 Legacy/历史实验区 | `legacy` | `assets/gifs/*`, `assets/videos/demo_overview.mp4` |
| 下游 iiwa/dual-repo assets | 不是当前 Panda handoff replay 主线 | `legacy` | `docs/CURRENT_STATUS.md:19`, `docs/assets/README.md:9` |

## Evidence Notes

- 已调用项目 RAG：`python3 scripts/rag_assistant.py --query "<three-repo audit query>"`。检索返回相关文档与代码片段；本地 LLM 总结因权限/运行环境失败，阶段 1 结论以直接文件、JSON 产物和代码检索为准。
- 上游与下游仓库不在当前仓库的直接共同父目录下：上游位于 `/home/ina/dev/ros2-arm-teleoperation-suite`，中游位于 `/home/ina/robot-sim-lab/robot-arm-episode-data-lab`，下游位于 `/home/ina/ros2_ws/src/ros2-moveit-pybullet-bridge`。
- 阶段 1 写入前发现三个仓库已有未提交 README/资产改动；本审计不覆盖、不回滚这些改动。
