# 具身操作模型评测 SOP（Panda / ACT → Isaac 有界评测）

**版本**：v1.5（2026-07-20）<br>
**适用岗位能力映射**：具身操作模型评测工程师（仿真评测主路径；真机为 readiness，不虚构已部署）<br>
**仓库边界**：三仓闭环；本 SOP 以中游编排 + 上游 Isaac runtime 证据为主
**关联**：

- 契约层：[`EVALUATION_CONTRACT.md`](EVALUATION_CONTRACT.md)（E0 run/episode/summary schema）
- 实验证据：[`E2_ACT_BASELINE_PREFLIGHT.md`](E2_ACT_BASELINE_PREFLIGHT.md)
- 岗位对齐：[`portfolio/EMBODIED_EVALUATION_ENGINEER_ALIGNMENT.md`](portfolio/EMBODIED_EVALUATION_ENGINEER_ALIGNMENT.md)
- 上游入口：`ros2-arm-teleoperation-suite/scripts/run_isaac_act_smoke.sh`
- 中游有界汇总：`training/scripts/summarize_isaac_act_evaluation.py`
- 中游契约聚合：`training/scripts/aggregate_evaluation_summary.py`

---

## 0. 一句话原则

> 评测的目标不是“把 loss 跑低”或“把 episode 堆到 50”，而是在**固定身份（model / release / simulator / 协议）**下，产出**可重复、可对比、可归因、可驱动下一动作**的证据。

离线指标、接口通过、任务成功必须分栏报告；禁止互相替代。

---

## 1. 评测对象与非目标

### 1.1 当前 SOP 覆盖（已实现）

| 层级 | 内容 | 证据形态 |
|---|---|---|
| 离线契约 | release inspect、ACT val L1 / gripper acc | `metrics.json`、inspection JSON |
| 接口/执行 | checkpoint 加载、在线推理、有界动作、safety/E-stop | `report.json.status` / `execution_status` |
| 行为诊断 | home 起步 vs pregrasp warmstart；降 Z / 对准 / 闭合 | 判定标签 + EE/grip 曲线 |
| 系统健康 | latency、GPU/VRAM、残留进程清理 | `gpu_during_policy.csv`、cleanup log |

### 1.2 明确非目标（不得在报告中声称）

- 真实机械臂部署或真实 Sim2Real 完成；
- 离线 loss 提升 ≡ 任务成功率提升；
- 单次有界 smoke ≡ 统计显著的泛化结论；
- warmstart 成功 ≡ home 自主抓取成功；
- E0 schema fixture 中的 `null` runtime 字段 ≡ 已跑评测。

完整 multi-seed suite + runtime ground-truth evaluator 见 `EVALUATION_CONTRACT.md`；本 SOP 是其上的**日常可执行诊断层**。

### 1.3 五类指标权威来源对照（与当前代码对齐）

没有统一的根级 `evaluate.py` 同时打出这五项。报告时必须分栏；下表只记录**当前代码实际写出什么**，不补行业惯例。

| 口语指标 | 当前权威字段 / 产物 | 生产者（仓库 · 符号） | 何时有值 | 禁止当作 |
|---|---|---|---|---|
| **Success Rate** | 批采门禁：`meta.json` / `_validate_episode` 的 `success`；契约行：`outcome.success`；聚合：`summary.overall_success.rate` | 上游 `batch_generator._validate_episode`（物理主 gate）；上游 `ContinuousTaskEvaluator.finalize`（`evaluator_id=panda_continuous_gt_v0`）；中游 `aggregate_evaluation_summary.aggregate` | batch：`episode_results_path` 非空时写 JSONL，且 completed 时把 `outcome.success` **对齐** `_validate_episode`；Isaac：仅当 `EPISODE_RESULTS_PATH` 非空时启动 `isaac_continuous_gt_recorder.py`（`run_isaac_act_smoke.sh` 默认空；`run_isaac_nominal_suite.sh` 会设置） | 离线 loss / action RMSE；`summarize_isaac_act_evaluation.py` 的 endpoint 诊断（其 `task.runtime_ground_truth_evaluator=false`，且 `task_pass` 固定为 false） |
| **RMSE** | 离线：`rmse_action_error` / ACT `action_rmse`；运行时 EE：`motion.ee_tracking_rmse_m`；Sim2Sim：`normalized_trajectory_l2_rmse` | 中游 `evaluate_policy.evaluate_policy`；中游 `train_act_lerobot` evaluate 路径；上游 `ContinuousTaskEvaluator._motion_stats`（需 `ee_cmd_xyz`）；中游 `compare_sim_backends.compare_datasets` | 离线：有 checkpoint+release 即可；EE RMSE：batch 在 `_cmd_pos` 有值时传入 `ee_cmd_xyz`；**Isaac GT recorder 当前不传 `ee_cmd_xyz`，该字段为 `null`**；Sim2Sim：两套 adapted episode | 任务成功率 |
| **Episode Time** | `motion.completion_time_s` | 上游 `ContinuousTaskEvaluator._completion_time_s`（monotonic end−start） | 任意写入 `episode_results.jsonl` 且 evaluator 已 `reset`+`finalize` 的路径（batch continuous / Isaac GT recorder） | 接口 latency（`summarize_isaac_act_evaluation` 的 inference P50/P95） |
| **Collision** | `contact_safety.collision_count` | 上游 `ContinuousTaskEvaluator.observe`：仅当 `contact_force_n > 80.0` 时 `+= 1` | batch：`_observe_continuous_sample` 当前多半未传 FT；Isaac GT **v1** `isaac_continuous_gt_recorder` 订阅 `/ft_sensor` 并写入 `peak_force_n` | 下游 MoveIt collision plan-rejection（`check_moveit_closure.py`，非 policy 评测） |
| **Distribution Shift** | 下游风险维 `distribution_shift`；Sim2Sim `wasserstein_1` / mean shift | 下游 `dist_monitor.metrics_core.compute_distribution_metrics`（KL/W1/MMD）→ `risk_engine.risk_node` 归一化为 `scores['distribution_shift']`；中游 `compare_sim_backends` | PyBullet dual-source / monitor 运行时；或两套 episode 离线对比。**不在** E0 `summary.schema.json` / `aggregate_evaluation_summary` 输出里 | 上游 `outcome.success` |

补充（同仓已实现、但不是上表五项的替代）：

| 用途 | 脚本 | 实际输出 |
|---|---|---|
| 有界 Isaac ACT 诊断汇总 | `training/scripts/summarize_isaac_act_evaluation.py` | interface PASS/FAIL、latency、endpoint object 位移；**不**宣称 runtime GT 任务成功 |
| 契约 suite 聚合 | `training/scripts/aggregate_evaluation_summary.py` | 只聚合 `overall_success` / subgoal funnel / failure Pareto / `go_no_go`；**不**聚合 RMSE、completion_time、collision、distribution_shift |
| 数据集标签成功率 | `evaluate_policy.summarize_success` / `scripts/validate_dataset.py` | 来自 episode `success` **元数据**，不是在线 rollout GT |

---

## 2. 角色与三仓职责

| 角色 | 仓库 | 做什么 | 禁止 |
|---|---|---|---|
| Runtime Executor | 上游 `ros2-arm-teleoperation-suite` | Isaac backend、policy_inference、safety、pose/object dump | 不改中游 schema；不用 loss 判任务成功 |
| Eval Orchestrator | 中游 `robot-arm-episode-data-lab` | release 身份、汇总 `summary.json`、止损与增采建议 | 不从 `object_pose` 重推 lift/place 物理门禁 |
| Risk / Replay Reviewer | 下游 `ros2-moveit-pybullet-bridge` | handoff replay、risk（可选对照） | risk 不覆盖上游 runtime success |

物理任务成功的权威来源只能是：**已完成执行 + runtime ground-truth evaluator**（契约层）。
本 SOP 的有界 Isaac smoke 默认 `runtime_ground_truth_evaluator=false`，task 栏最多给**端点检查 / 行为诊断标签**，不得写成“抓取成功率”。

---

## 3. 评测身份卡（每次必填）

运行前冻结并写入证据目录：

```text
model_id / checkpoint_path / sha256
release_id / episodes / frames / upstream_gate
protocol_id: home_start | pregrasp_warmstart
control_envelope:
  max_actions, n_action_steps, inference_rate_hz
  max_translation_m, max_joint_excursion_rad, max_ee_excursion_m
  workspace_min/max, backend_duration_sec
git: 上游/中游 commit（至少记录）
date, host GPU, ROS_DOMAIN_ID
```

任一字段变化，即视为**新 run**，禁止与旧 run 直接横向“提升/下降”而不声明差异。

---

## 4. 标准评测协议

### 4.1 P0 — 离线门禁（每次训后）

1. `inspect_dataset` PASS；
2. release manifest 完整；
3. 记录 val L1、gripper open/close accuracy、stage weights（若启用）。

**通过条件**：inspection PASS。
**不通过**：禁止进入 Isaac；先修数据/schema。

### 4.2 P0.5 — Isaac scripted oracle 物理链门禁（E3 后、再训/E4 前）

在 E3 learned-policy nominal 失败（无有效 lift）之后，**先**跑固定专家轨迹，确认 Isaac
抓取物理链可抬起红方块。这不是 policy 成功。

**当前状态（2026-07-20）**：已通过。权威套件
`evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/`（lift 5/5，`gate_pass=true`）。
完整实验过程（v1 失败 → 归因 → 修复 → v2b）见
[`E3P5_ISAAC_SCRIPTED_ORACLE_EXPERIMENT.md`](E3P5_ISAAC_SCRIPTED_ORACLE_EXPERIMENT.md)。

```bash
# 上游（默认名义位姿、validation_mode=lift、5 trials）
cd /home/ina/dev/ros2-arm-teleoperation-suite
bash scripts/run_isaac_scripted_oracle.sh \
  /home/ina/robot-sim-lab/robot-arm-episode-data-lab/evidence/e3p5_isaac_scripted_oracle_5x_lift_YYYYMMDD
```

产物：`trials/trial_*/oracle_report.json`、`episode_results.jsonl`、`oracle_gate.json`、
（可选）`summary.json`。

**通过条件**：`oracle_gate.json` 中 `lift >= 4`（5 次中至少 4 次 lift）。
**不通过**：优先修 TCP / 夹爪碰撞体 / 摩擦 / 接触 / 物体初态；**禁止**继续采同类下降数据、
禁止开完整 E4、禁止把失败归因成“再堆 ACT epoch”。
**通过后**：只补「对准完成→接触闭合→抬升」阶段数据；新模型先 5-seed smoke，再进 E4 本机
每 suite 2–5 次 smoke。暂不优先加 `observation.ft`。

### 4.3 P1 — 接口/执行 smoke（learned-policy）

```bash
# 上游
export CHECKPOINT=.../checkpoint.pt
export MAX_ACTIONS=160
export N_ACTION_STEPS=8
export INFERENCE_RATE_HZ=5.0
export MAX_JOINT_EXCURSION_RAD=3.0
export MAX_TRANSLATION_M=0.015
export MAX_EE_EXCURSION_M=0.55
export WORKSPACE_MIN=0.20,-0.40,0.02
export BACKEND_DURATION_SEC=280
export PREGRASP_WARMSTART=false   # P1 默认 home
bash scripts/run_isaac_act_smoke.sh "$EVID"

# 中游汇总（--output 为目录）
python training/scripts/summarize_isaac_act_evaluation.py \
  --evidence "$EVID" --checkpoint "$CHECKPOINT" --release "$REL" \
  --output "$EVID/summary"
```

**通过条件**：

- `report.json` 存在；
- `interface_execution.status=PASS`（完成请求步数，或明确记录护栏原因）；
- `safety_ok=true` 且无非预期 E-stop（护栏触发需归类，见 §6）。

### 4.4 P2 — 行为分层诊断（本 SOP 核心）

同一 checkpoint 至少跑两类协议，**分栏对比**：

| 协议 ID | 初态 | 目的 | 典型开关 |
|---|---|---|---|
| `home_start` | Isaac 默认 home | 测自主接近/降 Z/闭合 | `PREGRASP_WARMSTART=false` |
| `pregrasp_warmstart` | 插值到物上 ~4 cm | 测“进入接近态后是否闭合/接触” | `PREGRASP_WARMSTART=true` |

**禁止**：用 warmstart 成功直接宣称 home 任务成功。

### 4.5 P3 — 对照 A/B（模型或数据变更后）

固定协议与 control envelope，只改一个因素：

- A：旧 checkpoint / 旧 release；
- B：新 checkpoint / 新 release。

报告必须含：identity diff 一行表 + 判定标签对比 + 是否触发止损规则（§7）。

### 4.6 收尾（强制）

每次 Isaac/ROS 评测结束执行物理清理（防残留污染下一 run）：

```bash
pkill -9 -f "isaac_panda_backend.py" || true
pkill -9 -f "isaac_scripted_oracle.py" || true
pkill -9 -f "policy_inference_node" || true
pkill -9 -f "teleop_bringup" || true
pkill -9 -f "mujoco_sim" || true
pkill -9 -f "lerobot_recorder" || true
pkill -9 -f "servo_node" || true
pkill -9 -f "ros2_control" || true
./scripts/stop_stack.sh || true
```

---

## 5. 指标与判定标签

### 5.1 分栏指标（必须分开展示）

| 栏 | 指标 | 含义 |
|---|---|---|
| Offline | val L1、gripper acc | 拟合质量，**非**任务成功 |
| Interface | completed/requested、latency p50/p95、clipped_actions | 系统能否跑完 |
| Safety | safety_ok、estop、joint/ee excursion | 是否可继续 rollout |
| Behavior | grip min、first close idx、z span、ee↔object XY start/best/end、object endpoint Δ | 操作行为诊断 |
| Task (bounded) | summary.task.status | 端点检查；默认 FAIL≠“模型全废” |

### 5.2 行为判定标签（Home 协议）

| 标签 | 定义（操作定义） | 下一动作倾向 |
|---|---|---|
| `HOME_STILL_OPEN` | grip≈1，EE 近静止 | 查 chunk 执行 / 动作尺度 / 数据时序 |
| `HOME_APPROACH_NO_CLOSE` | XY 靠近，几乎不降 Z，不闭合 | 补 descend 或加长有效接近 |
| `HOME_DESCEND_NO_CLOSE` | 明显降 Z，不闭合 | 查对齐与闭合条件；勿只加 epoch |
| `HOME_CLOSE_MISALIGNED` | 闭合但 best XY 差 / 闭合时已漂远 | **数据侧：先 XY 对齐再降**（且验证专家到达门） |
| `HOME_DESCEND_CLOSE` | 降 Z + 对准 + 闭合（诊断通过） | 才考虑扩数据 / 开 multi-seed suite |
| `WARM_CLOSE_CONTACT` | warmstart 下闭合且物体端点有位移 | 证明闭合头可用；不代替 home |
| `GUARD_FAIL` / `NO_REPORT` | 护栏/后端寿命/报告丢失 | **先修评测平台**，禁止据此增采 |

标签写入评测报告正文与 `evidence/*/notes`（可用 Markdown 一段），与 `summary.json` 并存。

### 5.3 推荐衍生量（脚本内可算）

```text
xy_start, xy_best, xy_end, best_i
z_min, z_max, z_span
grip_min, first_i(grip<0.5), first_i(grip<0.1)
steps(bnd_dz < -5mm)
workspace_clipped_count
max_observed_joint_excursion_rad
```

---

## 6. 失败归因树（问题 → 可执行建议）

```text
Interface FAIL / NO_REPORT?
  ├─ backend duration < policy horizon → 提高 BACKEND_DURATION_SEC；报告立即 flush
  ├─ joint excursion trip → 区分“护栏过紧”vs“策略乱拧”；先放宽诊断再定论
  └─ E-stop / safety not ok → 先修执行链，禁止扩大 rollout / 禁止扩数据

Interface PASS 但 Behavior 差?
  ├─ home 不闭合，warmstart 闭合 → 能力在接近态；瓶颈=home→pregrasp
  ├─ 降 Z 但 XY 漂后闭合 → CLOSE_MISALIGNED；查专家 approach_xy 到达门
  ├─ 扩数据后行为回退 → 停止合并；做 A/B；检查新数据是否真改变了阶段分布
  └─ 仅 offline 变好、Isaac 不变 → 禁止宣称模型提升

专家示教质量门（数据侧评测）?
  └─ approach_xy 日志 err_xy ≈ ee_xy_tolerance 就 “reached”
     → 对齐门过松；先修采集门限，再采“先对齐再降”
```

**岗位闭环口径**：每条失败必须落到三类建议之一（可多选）：

1. **平台/评测修复**（护栏、寿命、报告落盘、QoS）；
2. **数据生产策略**（阶段、到达门、IC 分布）；
3. **模型/训练策略**（horizon、replan、权重——且需有对照）。

---

## 7. 止损与扩数据门禁（强制）

来自实际迭代，写入日常决策：

| 观察 | 结论 | 动作 |
|---|---|---|
| gripper≈1 且 EE 近静止 | 未进入有效 approach/close | 查 chunk/时序；**不扫权重堆 epoch** |
| warmstart 闭合、home 不闭合 | 闭合可学，home 进入失败 | **不**为凑 50 条而扩；先修接近链 |
| 扩数据后 home 从 CLOSE_* 回退到 NO_CLOSE | 新数据无效或冲淡 | **回退最佳 checkpoint**；修专家门后再采 |
| 两组协议均稳定接近并合理闭合 | 数据扩充可能有效 | 再扩到 30→50，并启动契约层 multi-seed |
| Interface/E-stop 失败 | 系统失败 | 先修执行链，禁止扩大 rollout |

**E2 路线“约 50 条”是里程碑完整度目标，不是无条件扩数据许可证。**

当前最佳 home 行为参考（截至 2026-07-19）：

- Checkpoint：`data/e2_500hz_act_random30_descend_conservative_5epoch_20260719`
- sha256：`948e2949ae8af099f8347837969f596018bbf68a18cc703b6bc09abd01a92501`
- 判定：`HOME_CLOSE_MISALIGNED`
- 40-ep loose xyalign → `HOME_NO_CLOSE`；tight approach_xy 重采 → home `HOME_DESCEND_NO_CLOSE` / warm `WARM_CLOSE_CONTACT` → **仍不选用为 E3 主模型**（见 `E2_E3_MODEL_CARD.md`）

2026-07-20 E3.5 / E3.6 接力结论：

- scripted oracle v2b：lift **5/5**，证明 Isaac 名义物理链可抓起红方块；
- 定向 close→lift release：路径名含 `random35`，但 `manifest.num_episodes=40`（30+10）；
- 新 5-epoch checkpoint：offline inspection/training PASS；
- 5-seed home smoke（2200–2204）：interface 5/5 PASS，但 reach/grasp/lift=`0/0/0`，
  5/5 `HOME_NO_CLOSE`，`grip_min=1.0`，`z_span≈0.014 m`；
- 机器可读 gate：
  `evidence/e3p6_closelift40_5seed_home_20260720/smoke5_gate.json`，
  `gate_pass_ge1=false`。

**当前止损**：不继续扩大该 checkpoint，不开完整 E4。下一归因仍是
home→对准→闭合的观测/阶段建模，不是继续增加同类轨迹或只扫采样权重。

---

## 8. 证据目录规范

```text
evidence/<run_id>/
  report.json              # policy 原始动作序列（权威）
  summary/summary.json     # 中游汇总（或扁平 summary.json）
  summary/report.md
  runner.log / policy.log / backend.log
  initial_ee_pose.txt / initial_object_pose.txt
  final_*（若 stack 仍存活）
  pregrasp_warmstart.log   # 仅 warmstart 协议
  gpu_during_policy.csv
  cleanup.log
  VERDICT.md               # 可选：人工/脚本写入判定标签与建议
```

`run_id` 命名建议包含：`{ckpt_tag}_{protocol}_{envelope}_{date}`。

---

## 9. 报告模板（每次交付）

```markdown
# Eval Report — <run_id>

## Identity
- checkpoint / sha256 / release_id
- protocol / envelope
- git commits

## Results (split columns)
| Offline | Interface | Safety | Behavior | Task(bounded) |
| ... | ... | ... | ... | ... |

## Verdict label
`HOME_CLOSE_MISALIGNED`（示例）

## What this does / does not prove
- Does prove: ...
- Does not prove: pick/place success / Sim2Real / ...

## Actionable recommendations
1. Platform: ...
2. Data: ...
3. Model: ...

## Evidence paths
- ...
```

---

## 10. 与 JD 能力映射（面试可述）

| JD 要求 | 本 SOP 中的落点 |
|---|---|
| 仿真评测 | Isaac ACT 有界 rollout + MuJoCo 采集门禁 |
| 真机评测意识 | safety/E-stop/excursion；真机仅 readiness，不虚构 |
| 设计/迭代评测流程与指标 | 协议分层、判定标签、止损门、A/B 身份卡 |
| 结构化报告与追踪 | evidence 目录 + summary + VERDICT + preflight 文档 |
| 问题 → 可执行改进 | §6 归因树（平台/数据/模型） |
| 驱动数据生产 | 扩数据门禁；专家到达门质量评测 |
| 可重复可量化 | 固定 envelope、seed/release 身份、分栏指标 |

---

## 11. 已知缺口（诚实清单）

| 缺口 | 状态 |
|---|---|
| 契约层 multi-seed suite + CI 置信区间 | schema + `aggregate_evaluation_summary.py` 有；日常 `run_isaac_act_smoke.sh` 默认不写 `EPISODE_RESULTS_PATH` |
| runtime continuous lift/contact evaluator | **已实现（有界）**：`ContinuousTaskEvaluator` + JSONL；Isaac GT **v1**（分离 gripper cmd/state + FT）。`invalid_evaluator_v0` 不计 E3 |
| EE tracking RMSE / collision 在 Isaac 路径 | EE tracking 仍缺 `ee_cmd_xyz`；collision/`peak_force_n` 在 GT **v1** 已接 `/ft_sensor` |
| 真机评测 | 未做；仅 Sim2Real-readiness |
| 统一 `evaluate.py` 打出五项 | **不存在**；按 §1.3 分栏，勿合并口径 |
| 专家 approach_xy 到达门过松 | **已修**：`approach_xy_tolerance=0.025`；seed50/51 日志 `err_xy≈0.003–0.004`。合并训练仍未超过 30-ep home 闭合 |

---

## 12. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-07-19 | v1.0：固化 home/warmstart 分层、判定标签、止损门、控制信封与证据规范；纳入 CLOSE_MISALIGNED 与 xyalign 回退教训 |
| 2026-07-19 | v1.1：`approach_xy_tolerance` 阶段门已落地并重采；tight 40-ep → `HOME_DESCEND_NO_CLOSE`，最佳仍为 30-ep descend |
| 2026-07-19 | v1.2：30 vs 40-tight warm A/B 完成；E3 最终 ckpt=30-ep（model card + sha256）；止损不扩 50 |
| 2026-07-19 | v1.3：上游 continuous GT → `episode_results.jsonl`（`panda_continuous_gt_v0`）；SOP 缺口更新 |
| 2026-07-19 | v1.4：Isaac GT invalid_v0 止损；recorder v1 + preflight；nominal20 `*_gt_v1_*` 关闭（0/20 place，`no_go`） |
| 2026-07-19 | v1.4b：§1.3 五类指标权威来源对照 |
| 2026-07-20 | v1.5：E3.5 oracle lift 5/5；close→lift 40-episode 定向模型 5-seed 仍 lift 0/5，明确不开完整 E4 |
