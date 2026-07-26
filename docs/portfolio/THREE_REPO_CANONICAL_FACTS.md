# Three-Repo Canonical Facts

本文件是三仓当前统一事实源，只记录可追溯事实，不用行业经验补全项目状态。

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
| `robot-arm-episode-data-lab` | 上游 raw Panda episode 与 runtime outcome | adapter、schema/data quality validation、release、ACT/MLP training、offline eval、runtime summary aggregation、model card/SOP、bridge handoff | `frames.jsonl`、release manifest、checkpoint/metrics、evaluation summary/report、bridge handoff | ROS 2 实时控制、MuJoCo/Isaac 物理执行、PyBullet replay 执行、实机控制、重新推导上游 physical success | `implemented_and_verified` for release/training/evaluation aggregation/handoff | `AGENTS.md`, `configs/robot_schemas/panda.yaml`, `training/scripts/train_act_lerobot.py`, `training/scripts/aggregate_evaluation_summary.py`, `docs/EVALUATION_REPORT.md` |
| `ros2-moveit-pybullet-bridge` | midstream bridge handoff | 静态校验、JSONL replay、Panda action adapter、PyBullet replay、tracking/distribution monitoring、risk/fault benchmark | downstream benchmark summary/report | raw episode 采集、数据清洗、模型训练、真实机械臂驱动、实机 Sim2Real | `implemented_and_verified` for loader/adapter/tests and smoke benchmark; broader monitoring is partially verified | `docs/AGENTS.md:9`, `pybullet_bridge/pybullet_bridge/learning/panda_handoff.py:34`, `pybullet_bridge/pybullet_bridge/learning/jsonl_action_replay_policy.py:20`, `pybullet_bridge/pybullet_bridge/learning/panda_action_adapter.py:43`, `scripts/benchmark_system.py:439`, `pybullet_bridge/test/test_panda_handoff.py:46` |

## Current ACT Evaluation Experiment

| 项 | 当前事实 | 状态 | 证据 |
|---|---|---|---|
| E2 selected checkpoint | 30-episode descend ACT；5 epochs；用于权威 E3 nominal20 | `implemented_and_verified` diagnostic baseline | `docs/E2_E3_MODEL_CARD.md`, `data/e2_500hz_act_random30_descend_conservative_5epoch_20260719/metrics.json` |
| E3 nominal20 | seeds 2000–2019；reach 10/20；grasp/lift/place 0/20；`go_no_go=no_go` | `implemented_and_verified` runtime diagnostic | `evidence/e3_nominal20_home_30ep_gt_v1_20260719/summary.json` |
| Evaluator validation | invalid v0 隔离；v1 command/state 分离、FT 接入、2101/2102 preflight PASS | `implemented_and_verified` | `docs/EMBODIED_POLICY_EVALUATION_SOP.md`, `evidence/e3_gt_preflight_v1_20260719/preflight_summary.json` |
| E3.5 scripted oracle | v1 lift 0/5；修物理/contact/GT 后 v2b lift 5/5 | `implemented_and_verified` physics gate | `evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/oracle_gate.json` |
| Close→lift release | release_id 路径含 `random35`，权威 manifest 为 40 episodes / 9,779 frames | `implemented_and_verified` with provenance alias | `data/releases/e2_500hz_random35_closelift_20260720/manifest.json`, `PROVENANCE.md` |
| E3.6 close→lift model | 5-seed interface 5/5；reach/grasp/lift 0/0/0；5/5 `HOME_NO_CLOSE` | `implemented_and_verified` runtime No-Go | `evidence/e3p6_closelift40_5seed_home_20260720/smoke5_gate.json` |
| E4 | 四类 shift、100+ bounded rollout | `documented_plan_only`; blocked by zero-lift gate | `docs/portfolio/EMBODIED_EVALUATION_ENGINEER_ALIGNMENT.md` |
| Model-agnostic Policy Adapter contract | 方法集 + metadata schema + fixture + 中游薄 ABC/`FixturePolicyAdapter` + 三策略注册表；上游运行时包装未挂 | `implemented_and_verified` for midstream contract/registry；upstream wrapper `documented_plan_only` | `docs/POLICY_ADAPTER_CONTRACT.md`, `docs/POLICY_ADAPTER_QUICKSTART.md`, `evaluation/policies/`, `evaluation/registry/policies/` |
| Single-block controlled Benchmark spec | Baseline/ID/OOD-position schema + fixture；完整矩阵未跑 | `documented_plan_only` for execution；spec frozen | `docs/SINGLE_BLOCK_GENERALIZATION_BENCHMARK.md`, `evaluation/schemas/benchmark_spec.schema.json`, `evaluation/examples/benchmark_spec_baseline_id_ood_fixture.json` |
| VLA Gate V0 | LingBot-VLA 2.0 只读兼容性矩阵；不下权重；HOLD-2 已纠正（禁止「可逆 delta 映射」表述）；**路线 CLOSED / ARCHIVED** | `implemented_and_verified` as audit doc (archived route) | `docs/VLA_GATE_V0_COMPATIBILITY_AUDIT.md` |
| VLA Gate V0.5 | Panda 字段审计；推荐 absolute EEF；active-channel + execution adapter；**absolute_eef 导出 fixture 已实现**；**模型无关契约保留**；LingBot 执行路线不进 V1 | `implemented_and_verified` as audit + offline export fixture | `docs/VLA_GATE_V05_PANDA_ACTION_CONTRACT.md`, `evaluation/vla_contract/absolute_eef.py`, `tests/test_absolute_eef_export.py` |
| LingBot Gate V1 | 本机 RTX PRO 500 / 6113 MiB；**No-Go**；未下 6B 权重；**CLOSED / ARCHIVED** | `implemented_and_verified` preflight (archived route) | `docs/VLA_GATE_V1_PREFLIGHT.md` |
| SmolVLA Gate S0 | 活动候选起点；obs/action/data 矩阵；本机 LoRA No-Go；S1–S4 设计冻结 | `implemented_and_verified` as audit doc | `docs/SMOLVLA_GATE_S0_COMPATIBILITY_AUDIT.md` |
| SmolVLA Gate S1 | 官方 `smolvla_base` 加载+`select_action`：**pass**（peak ≈925 MiB / ~171 ms；合成帧；非 Panda） | `implemented_and_verified` | `docs/SMOLVLA_GATE_S1_OFFICIAL_REPRO.md`, `evaluation/examples/smolvla_gate_s1_report.json` |
| SmolVLA Gate S2 | Panda v2.1 RGB+abs EEF open-loop：**interface pass / H-4 pass / H-3 no_go**（EE RMSE≈0.27 m；gripper acc 0；非任务成功） | `implemented_and_verified` | `docs/SMOLVLA_GATE_S2_OPEN_LOOP.md`, `evaluation/examples/smolvla_gate_s2_report.json` |
| SmolVLA Gate S3（v1/v2，**Historical / Superseded**，被下一行 Recovery v3 取代） | v1 griptiming + α64 LoRA canonical 全帧 `stride=1` / 2,594 帧为 **Hold**：EE `0.0547 m`、gripper balanced accuracy `0.7128`，timing 提前 `65` 帧 / `6.5 s`、smoothness p90 `0.103 m`、raw gripper OOB `20.47%`。人工例外 Round-2 v2 late-close release（20 episodes / 7,765 frames）已完成真实 GPU preflight、1000-step LoRA、checkpoint audit，并完成同口径 8 条 / 3,108 帧 open-loop：仍为 **Hold**。v2 EE `0.0669 m`、gripper balanced accuracy `0.7203`，timing 提前 `68.625` 帧 / `6.862 s`、smoothness p90 `0.1196 m`、raw gripper OOB `21.07%`；8/8 episode 均提前闭合，失败项仍为 timing / smooth / sat。相对 v1，timing、smoothness、sat 与 EE 均退化，仅 grip balanced accuracy 小幅 +0.0076。**事后 split 审计发现**：v2 release 虽声明 12 train / 4 validation / 4 benchmark，但 AutoDL 合并训练根与训练日志均为 20 episodes，训练入口未按 split 过滤；因此该 8 条只能称 release-named slices，不能称真正 held-out/OOD，且当前结果是在训练见过这些 episode 的条件下仍 Hold。当前帧 `action[7]`、`action_delta_indices=range(50)`、reset 后 `select_action()` 首动作按序 `popleft()` 的索引链已排除；未执行 action-chunk queue，未跑 Isaac | `implemented_and_verified` v1/v2 full-frame Hold + v2 training/checkpoint audit + split-leak audit；**不是** Pass / 泛化 / 任务成功 | `runs/smolvla_s3/openloop_full_stride1_20260723T055500Z/s3_open_loop_summary.json`, `runs/smolvla_s3/openloop_v2_lateclose_full_stride1_20260723T161000Z/s3_open_loop_summary.json`, `runs/smolvla_s3/train_v2_lateclose_20260723T160000Z/train_log.txt`, `docs/SMOLVLA_S3_RECOVERY_IMPLEMENTATION_PLAN.md` |
| SmolVLA Recovery v3 | train-only 36 episodes、`state[15]+scene RGB`、chunk10/K5、官方精确 PEFT 正则完成 5,705-step LoRA，checkpoint audit Pass（adapter SHA256 `4cfcc46e3270cd0b4fe267e36c87c823e1bb9a473742ac99f58652791910d2f7`）。历史 14 条 / 3,413 帧 canonical first-action 在冻结 `eval_gate_v1` 下为 Hold。2026-07-24 新采 10 条 / 2,673 帧 eval-only scene episode，QA/release Pass；真实 RTX 4090 D prospective `eval_gate_v2` 为 **Hold**（仅开爪边 raw 严重度三项）。同日冻结执行语义 `eval_gate_v3`（lock `gate_sha256=37325a1f…`）后，fresh seeds 70–74 / 2,593 帧 prospective **Pass**（EE `0.0253 m`、grip BA `0.9943`、close-edge beyond-ε `0.386%`、clip 分类/时序变化 0）。Pass 只代表**专家状态分布上的 first-action 离线判定**；`queued_diagnostic` 永不具备 canonical Pass 资格。CPU queue 合同 + online runner 已落地；异步 queue runtime 未实测 | `implemented_and_verified` for train/checkpoint/v1–v3 gates/prospective v3 Pass；**不是**任务成功 / Sim2Real / 泛化保证 | `runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/s3_open_loop_report.json`, `runs/smolvla_s3/recovery_v3_lora_20260723T125632Z/checkpoint_config_audit.json`, `configs/smolvla_s3/eval_gate_v3.yaml`, `configs/smolvla_s3/eval_gate_v3.lock.json`, `training/smolvla_s3/runtime_s4.py`, `docs/portfolio/SMOLVLA_RECOVERY_V3_PORTFOLIO.md` |
| Bounded Isaac S4（SmolVLA Recovery v3） | 人工批准的有界 rollout（`chunk10 / K5 / 10 Hz / clip(raw,0,1)` / scene-only / `state[15]`，seeds 1–5）已在本机 RTX PRO 500 跑完：`ran_isaac=true`；policy interface **5/5** PASS。**权威产物为修光后复测**（policy 输入 JPEG 均值 ≈154）：GT reach **1/5**、grasp **0/5**、lift **0/5**、`outcome_success 0/5`（`pass_threshold=1`）、`gate_pass=false` → **Hold**；5/5 seeds failure=`gripper never closed below 0.700`。首轮近黑场景运行（JPEG 均值 ≈0.3）为 reach 3/5、grasp 1/5、lift 0/5，其 reach/grasp 是失明走廊几何重叠 + `GRIPPER_CLOSE_MAX=0.70` 口径放大，已标注 **Superseded / historical**，不得作权威。默认不扩种子、不重训 | `implemented_and_verified` bounded Isaac run（Hold）；**不是**任务成功 / 在线自主抓取 / Sim2Real / 真机 | `evidence/smolvla_s4_bounded5_relight_20260724T151711Z/s4_gate.json`（权威）, `evidence/smolvla_s4_bounded5_20260724T203700Z/s4_gate.json`（superseded）, `evidence/smolvla_s4_bounded5_telemetry_20260724T144549Z/`, `evidence/smolvla_s4_mujoco_bounded5_20260724T155513Z/s4_gate.json`（H2 训练域对照，`early_stopped=true`）, `docs/SMOLVLA_S4_LIFT0_OFFLINE_ATTRIBUTION.md`, `docs/SMOLVLA_S3_ISAAC_S4_RUN_CHECKLIST.md` |
| ACT HOME_NO_CLOSE hold | 假设—证据矩阵；禁止盲训/扩采/E4 | `implemented_and_verified` decision | `docs/ACT_HOME_NO_CLOSE_HYPOTHESIS_MATRIX.md` |

### VLA 候选路线状态（2026-07-25 收口）

| 候选 | 已完成 Gate | 当前结果 | 当前状态 | 后续条件 |
| --- | --- | --- | --- | --- |
| LingBot-VLA 2.0 | V0、V0.5 | 动作契约完成；本机 V1 资源 No-Go；未下权重/未训练/未跑 Isaac VLA | **Closed / Archived**（路线关闭） | 未来仅在 ≥24GB 资源与明确多本体需求下人工复审；不得自动恢复 V1 |
| SmolVLA | S0–S2 + S3 v1/v2 α64 + Recovery v3 + frozen eval-gate-v2/v3 + bounded S4 | v1/v2 late-close 两次全帧 open-loop 均 Hold。Recovery 修复 train-only split、`state[15]`、scene-only camera、精确 PEFT、chunk10/K5；独立 prospective `eval_gate_v2` Hold（开爪边过冲）；`eval_gate_v3` prospective **Pass**。有界 S4 seeds 1–5：`ran_isaac=true`，interface 5/5，修光后权威 reach 1/5 · grasp 0/5 · lift **0/5** → **Hold**。归因倾向闭环 BC（H2），物理链 / 接口 / state 编码 / 相机失明均已排除 | **Active / S3 open-loop Pass；S4 Hold (lift 0/5)** | 作品集口径见 `docs/portfolio/SMOLVLA_RECOVERY_V3_PORTFOLIO.md`、`docs/portfolio/FINAL_PROJECT_SUMMARY.md`；不得声称任务成功 / Sim2Real；默认不扩种子、不重训 |
| ACT | E2–E3.6 | nominal 0/20；定向模型 lift 0/5 | **Frozen diagnostic baseline**（失败诊断基线） | 不再盲目训练；不启动完整 E4 |
| Scripted oracle | E3.5 | lift 5/5 | **Active system reference**（系统上界参考） | 用于物理链与 GT 校验 |

状态标签含义：路线关闭 ≠ 删除审计；S3 Hold ≠ S3 Pass；活动候选 ≠ 已适配/已成功；失败诊断基线 ≠ 可部署策略；系统上界参考 ≠ learned-policy 成功。

结论：ACT diagnostic training 与 Isaac bounded evaluation 已有可追溯产物；**learned-policy task
success 未验证**；SmolVLA S3 v1/v2 的 canonical 全帧 open-loop 均为 **Hold**。Recovery v3 独立 prospective
`eval_gate_v2` 因开爪边 raw 严重度为 **Hold**；同日执行语义 `eval_gate_v3` 对新 held-out 为 **Pass**。
有界 Isaac S4（≤5 seeds）已在本机 RTX PRO 500 执行：`ran_isaac=true`，policy interface 5/5，
lift **0/5** → **Hold**（权威证据 `evidence/smolvla_s4_bounded5_relight_20260724T151711Z/`；首轮近黑运行
`evidence/smolvla_s4_bounded5_20260724T203700Z/` 为 **Superseded / historical**）。LingBot **执行路线已归档**；
SmolVLA 为**唯一活动预训练候选**。不是 ACT 重训，也不是 VLA 抓取已验证 / Sim2Real。
不得把“ACT run 已完成”写成“ACT 抓取成功”；不得把“S2 接口 Pass”、 “S3 Ready”、open-loop Pass、
S4 interface Pass、reach/grasp 计数或 `ran_isaac=true` 写成“SmolVLA 已适配 Panda / 任务成功 / Sim2Real”；
不得用 `queued_diagnostic` 判 canonical Pass。

**2026-07-25 收口**：P0 事实冻结与作品集材料已完成，统一入口
`docs/portfolio/FINAL_PROJECT_SUMMARY.md`，分层归因 `docs/portfolio/BADCASE_ATTRIBUTION_SUMMARY.md`，
后续路线 `docs/FUTURE_WORK_ROADMAP.md`（P1/P2 仅登记不执行）。

## Historical MLP / Handoff Baseline

| 项 | 当前事实 | 状态 | 证据 |
| --- | --- | --- | --- |
| Canonical 文档 ID | `panda_30_mlp_20260711` | `implemented_and_verified` as documented experiment source | `docs/portfolio/CANONICAL_EXPERIMENT.md:3` |
| 上游数据源 | 上游仓 `data/episodes_mlp` | `implemented_and_verified` | `evidence/upstream/validate_dataset.json`, `data/exports/panda_30_release/manifest.json` |
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
| Retired downstream claims | 旧版未溯源 latency/fault 数字已从 current canonical summary 移除，不得作为作品集事实 | `not_supported` | `docs/portfolio/CANONICAL_EXPERIMENT.md` |
| Latest archived downstream run | release `panda_closed_loop_20260712_214747`, 1/1 completed, mean/max `9.79/34.218 ms`, no fault injection | `smoke_or_mock_only` | `evidence/meta/run_summary.json`, `evidence/downstream/benchmark_summary.json` |

结论：30 episodes、71,737 frames、release、MLP metrics 和 handoff bundle 证据充分；最新下游产物只证明独立的 1-episode no-fault smoke。两段 run 不得拼接成同一次已验证端到端实验。

## Observation And Action Contract

| 字段 | 语义 | 当前事实 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| Upstream action | `ee_pose_gripper[8]` | 上游兼容 action layout | `implemented_and_verified` | `configs/robot_schemas/panda.yaml:79`, `training/adapters/upstream_m6.py:12` |
| Midstream state | `state[8]` | `joint_position[7] + gripper_opening[1]` | `implemented_and_verified` | `configs/robot_schemas/panda.yaml:23`, `training/adapters/upstream_m6.py:63` |
| Midstream action | `ee_delta_gripper[7]` | `delta_xyz[3] + delta_rpy[3] + gripper_cmd[1]` | `implemented_and_verified` | `configs/robot_schemas/panda.yaml:67`, `training/adapters/upstream_m6.py:77` |
| Optional observation | `ee_pose[7]`, `object_pose[7]`, `ft[6]`, images | object/ft present in release; images missing warning | `implemented_and_verified` | `configs/robot_schemas/panda.yaml:32`, `data/exports/panda_30_release/inspection_report.json` |
| Downstream replay input | `ee_delta_gripper[7]` | consumed by `panda_jsonl_replay` and `PandaActionAdapter` | `implemented_and_verified` | `docs/AGENTS.md:20`, `pybullet_bridge/pybullet_bridge/learning/panda_action_adapter.py:97` |

中游 `filter_scope=training_split_only` 时只检查 schema 与 training split，不从 `observation.object_pose` 重新推导 lift/place 成败。证据：`AGENTS.md:66`, `training/scripts/inspect_dataset.py:303`。

## Training And Evaluation Facts

| 能力 | 事实 | 状态 | 证据 |
| --- | --- | --- | --- |
| MLP BC | 低维 state 到 `ee_delta_gripper`，feature contract 排除图像/触觉 | `implemented_and_verified` | `training/scripts/train_mlp_policy.py:166`, `training/reports/panda_mlp_bc/mlp_metrics.json` |
| ACT smoke | 文件名含 ACT 但实际是 ridge/linear smoke baseline | `smoke_or_mock_only` | `training/scripts/train_act_smoke.py:1` |
| LeRobot ACT training | scene ACT、episode split、stage-balanced sampling、多个 3/5-epoch checkpoint 与 hash 已落地 | `implemented_and_verified` diagnostic training | `training/scripts/train_act_lerobot.py`, `docs/E2_E3_MODEL_CARD.md`, `data/e2_500hz_act_random35_closelift_5epoch_20260720/metrics.json` |
| Offline eval | ACT/MLP loss、action RMSE、gripper accuracy 与 replay checks；不等同任务成功率 | `implemented_and_verified` | `docs/EVALUATION_REPORT.md`, `training/reports/panda_mlp_bc/mlp_metrics.json` |
| Online policy rollout | ACT→Isaac 有界 rollout、continuous GT、20-seed summary 与 5-seed gate 已完成；task success 为 0 | `implemented_and_verified` diagnostic No-Go | `evidence/e3_nominal20_home_30ep_gt_v1_20260719/summary.json`, `evidence/e3p6_closelift40_5seed_home_20260720/smoke5_gate.json` |

## Downstream Runtime Facts

| 能力 | 事实 | 状态 | 证据 |
| --- | --- | --- | --- |
| Handoff loader | 校验 manifest、replay check、schema/action/type/finite/action shape | `implemented_and_verified` | `pybullet_bridge/pybullet_bridge/learning/panda_handoff.py:34`, `pybullet_bridge/test/test_panda_handoff.py:46` |
| JSONL replay | open-loop replay `ee_delta_gripper[7]` | `implemented_and_verified` | `pybullet_bridge/pybullet_bridge/learning/jsonl_action_replay_policy.py:20` |
| PandaActionAdapter | 支持 hold/mock_ik/pybullet_ik，含 delta/gripper/finite 校验 | `implemented_and_verified` | `pybullet_bridge/pybullet_bridge/learning/panda_action_adapter.py:43`, `pybullet_bridge/test/test_panda_action_adapter.py:9` |
| Benchmark | `panda_jsonl_replay` CLI and summary fields implemented | `implemented_and_verified` | `scripts/benchmark_system.py:500`, `scripts/benchmark_system.py:439` |
| Sensor fusion/contact/slip | 节点代码存在；阶段 1 未找到 canonical Panda handoff 运行证据 | `implemented_not_fully_verified` | `pybullet_bridge/pybullet_bridge/sensor_fusion_node.py:20` |
| Risk engine | aggregation code exists; canonical benchmark only proves limited smoke evidence | `implemented_not_fully_verified` | `risk_engine/risk_engine/aggregator.py:8`, `evidence/downstream/benchmark_summary.json` |
| Real Panda driver | 当前项目证据不足，无法确认 | `not_supported` | `docs/CURRENT_STATUS.md:28` |

## What Current Evidence Cannot Prove

| 声明 | 结论 | 证据状态 |
| --- | --- | --- |
| 已完成真实机械臂部署 | 当前项目证据不足，无法确认 | `not_supported` |
| 已完成真实 Sim2Real | 当前项目证据不足，无法确认；只能写 Sim2Sim / Sim2Real-readiness | `not_supported` |
| 稳定在线自主抓取 | 已有 learned-policy rollout，但 E3 为 0/20、E3.6 lift 0/5，不能声称成功 | `not_supported` |
| MLP loss 提升等同抓取成功率提升 | 当前项目证据不足，无法确认 | `not_supported` |
| 下游 PyBullet replay 已验证物理抓取成功 | 当前项目证据不足，无法确认；downstream 主要验证 replay/monitor/risk | `implemented_not_fully_verified` for replay, not for grasp success |
| ACT 已完成 diagnostic training/run | 已确认；但 learned-policy task success 未通过 | `implemented_and_verified` diagnostic No-Go |

## Legacy Boundary

| 范围 | 结论 | 状态 | 证据 |
| --- | --- | --- | --- |
| 中游 `agents/`, `core/` | PyBullet/KUKA 历史 Agent，不与 Panda training release 混用 | `legacy` | `AGENTS.md:11`, `archive/README.md` |
| 中游 KUKA pick/lift assets | 只能放 Legacy/历史实验区 | `legacy` | `assets/gifs/*`, `assets/videos/demo_overview.mp4` |
| 下游 iiwa/dual-repo assets | 不是当前 Panda handoff replay 主线 | `legacy` | `docs/CURRENT_STATUS.md:19`, `docs/assets/README.md:9` |

## Evidence Notes

- 项目事实查询使用 `python3 -m project_knowledge.cli query --no-llm --query "<question>"`；LLM 只可总结已选择证据。
- 三仓 checkout 位置由 `configs/knowledge_registry.yaml` 的环境变量、相对路径和 fallback 解析，不依赖某台机器的固定绝对路径。
- 当前结论以代码、测试、配置和机器可读运行产物为准；作品集摘要不能覆盖它们。
