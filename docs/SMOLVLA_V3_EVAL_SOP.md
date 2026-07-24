# SmolVLA Recovery v3 全链评测 SOP（prospective → gate_v3 → 有界 S4 → 下游复用 → 统一信封 → 出图）

**版本**：v1.0（2026-07-24，依据当日已跑通的 v3 链路固化）
**定位**：`docs/EMBODIED_POLICY_EVALUATION_SOP.md`（通用协议 v1.6）之上的 **SmolVLA v3 主线专用执行清单**。通用判定标签、指标权威来源、五类指标分栏规则以通用 SOP 为准，本文只固化 v3 这条线的具体命令、产物与止损点。
**硬口径**：open-loop Pass、interface Pass、`ran_isaac=true`、PolicyRunner smoke 完成，都**不是**任务成功、不是 Sim2Real、不是真机。所有产物 `claims_task_success=false`。

---

## 0. 开始前必读（硬约束）

1. **人工批准点**（缺一不可，不得由 Agent 自动推进）：
   - 新采集 / data-fix / 重训：需显式人工批准（`max_data_fix_retries: 1` 已用尽）；
   - 进入 Isaac S4：需 open-loop canonical **Pass** + 人工批准（有界 ≤5 seeds）；
   - S4 Hold（如 lift 0/5）后扩种子 / 重训 / 真机：默认禁止，需另批。
2. **Gate 冻结**：判定以 `configs/smolvla_s3/eval_gate_v3.yaml` + `eval_gate_v3.lock.json`（SHA256 锁）为准；不得为了过线回改阈值再追溯改判。
3. **物理收尾（Nuke On Done）**：任何拉起 ROS / MuJoCo / Isaac 的步骤，结束前必须强杀：

```bash
pkill -9 -f "teleop_bringup" || true
pkill -9 -f "mujoco_sim" || true
pkill -9 -f "lerobot_recorder" || true
pkill -9 -f "servo_node" || true
pkill -9 -f "ros2_control" || true
```

---

## 1. 链路总览

| 步骤 | 仓库 | 入口 | 关键产物 | 判定 |
|---|---|---|---|---|
| A. prospective eval-only 采集 | 中游（编排上游） | `scripts/collect_smolvla_s3_prospective_eval10.sh` | `runs/smolvla_s3/prospective_eval10_v3_*/` + manifest | 每位 accepted 数达标 |
| B. open-loop gate_v3 | 中游（GPU） | `training/scripts/run_smolvla_s3_open_loop.py` | `s3_open_loop_report.json` / `s3_open_loop_summary.json` | `gate_decision: pass/hold` |
| C. 有界 Isaac S4（≤5 seeds） | 上游（中游薄封装） | `scripts/run_smolvla_s4_bounded_isaac.sh` | `evidence/smolvla_s4_bounded5_*/s4_gate.json` | `gate_pass`（lift ≥ threshold） |
| D1. 下游 PolicyRunner smoke | 中游导出 + 下游执行 | `training/scripts/export_smolvla_openloop_to_pybullet_handoff.py` + 下游 `benchmark_system.py` | `benchmark_summary.json` + `benchmark_timeseries.csv` | interface 完成度（非任务） |
| D2. offline risk readiness | 下游 | `scripts/run_offline_risk_readiness.py` | `smolvla_v3_ep0_risk_offline_*.json` | 仅对照，不作 go/no-go |
| E. 统一评测信封 | 中游 | `training/scripts/normalize_unified_eval_report.py` | `evidence/smolvla_v3_eval_framework_*/` + bundle | schema 校验 + `claims_*=false` |
| F. 出图 + portfolio | 中游 | `scripts/generate_smolvla_v3_portfolio_figures.py` | `docs/portfolio/smolvla_*.png`（7 张） | 图与证据一致、带诚实脚注 |

2026-07-24 参考产物：B **Pass**（EE 0.0253 m）、C **Hold**（lift 0/5）、D/E/F 已完成。

---

## 2. Step A — prospective eval-only 采集（需人工批准）

- **配置**：`configs/smolvla_s3/prospective_eval10_v3.yaml`（P0–P4 各 2 条 accepted；v3 用 seeds 70–74）；随机化定义 `configs/smolvla_s3/prospective_eval_randomization/P{0..4}.yaml`。
- **原则**：eval-only、绝不混入训练集；原始 episode 留上游，中游只记录 manifest 与 accepted 清单。

```bash
cd /home/ina/robot-sim-lab/robot-arm-episode-data-lab
PROSPECTIVE_CFG=configs/smolvla_s3/prospective_eval10_v3.yaml \
PROSPECTIVE_RUN_TAG=prospective_eval10_v3 PROSPECTIVE_STAMP=<YYYYMMDD> \
./scripts/collect_smolvla_s3_prospective_eval10.sh
```

- **通过条件**：每个位置 accepted 达到 `accepted_episodes_per_position`；QA（schema + success split）Pass。
- **止损**：某位置 attempts 用尽仍不足 → 停止并上报，不得自动换 seed 续采。
- 采集脚本自带 trap cleanup；仍需确认无残留进程。

## 3. Step B — canonical open-loop（eval_gate_v3）

- **前置**：checkpoint config audit Pass（policy/preprocessor state[15]、scene camera、action8、K 与 PEFT 核验）。
- **协议**：canonical = 全帧 `stride=1` + `canonical_first_action`；`queued_diagnostic` 只作诊断，禁止用它判 Pass。

```bash
python3 training/scripts/run_smolvla_s3_open_loop.py \
  --base-dir <smolvla_base> --vlm-dir <vlm> \
  --lora-dir runs/smolvla_s3/recovery_v3_lora_20260723T125632Z/lerobot_run/checkpoints/005705/pretrained_model \
  --eval-gate configs/smolvla_s3/eval_gate_v3.yaml \
  --data-root <prospective_eval10_v3_data> \
  --slices validation,benchmark \
  --output-dir runs/smolvla_s3/openloop_recovery_v3_prospective_<tag>
```

- **判定**：以 report 内 `gate_decision` / `gate_decision_detail.pass_failures` 为准。v3 冻结执行语义：`clip(raw,0,1)`；close-edge beyond-ε、分类/时序不变式为硬门禁，开爪边过冲仅 diagnostic。
- **报告必含**：EE RMSE、gripper BA、close timing offset、clip MAE、latency p50/p95、`per_episode_raw_results`（base + lora 成对）。
- **止损**：Hold → 默认停止；任何重训/data-fix 回到 §0 人工批准。

## 4. Step C — 有界 Isaac S4（需人工批准；≤5 seeds）

- **前置**：Step B canonical **Pass** + 人工批准记录（见 `docs/SMOLVLA_S3_ISAAC_S4_RUN_CHECKLIST.md` §3 勾选）。
- **runtime 合同单源**：`configs/smolvla_s3/s4_runtime_contract.{yaml,json}`（chunk10 / K5 / 10 Hz / gripper clip / async double-buffer）；上游包内 SHA 相同副本，启动时 assert。

```bash
export ISAAC_FRANKA_USD=$HOME/isaac_assets/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd
export ISAAC_REQUIRE_LOCAL_FRANKA=1
export RECORD_SCENE_VIDEO=false
export SEEDS="1 2 3 4 5"
./scripts/run_smolvla_s4_bounded_isaac.sh
```

- **产物**：`evidence/smolvla_s4_bounded5_<stamp>/`：`s4_gate.json`、`episode_results.jsonl`（continuous GT subgoals）、`trials/seed_*/report.json`（latency、excursion、safety）。
- **判定**：`s4_gate.json.gate_pass`（lift ≥ `pass_threshold`）。interface 5/5 但 lift 0/5 = **Hold**。
- **止损**：任一种子 E-stop 过多或 lift 0/N → Hold，**不得自动扩种子**；收尾必须 Nuke On Done。

## 5. Step D — 下游复用 smoke + offline risk readiness

D1（中游导出 → 下游 PolicyRunner，interface smoke，`is_closed_loop=false`）：

```bash
# 中游：把 1 条 open-loop 预测导出为 ee_delta handoff（diagnostic）
python3 training/scripts/export_smolvla_openloop_to_pybullet_handoff.py \
  --open-loop-report runs/smolvla_s3/openloop_recovery_v3_prospective_<tag>/s3_open_loop_report.json \
  --output-dir runs/smolvla_s3/pybullet_smoke_v3_ep0 \
  --episode-index 0

# 下游：PolicyRunner 回放（~/ros2_ws，source install/setup.bash）
python3 src/ros2-moveit-pybullet-bridge/scripts/benchmark_system.py \
  --strategy panda_jsonl_replay \
  --panda-handoff-path <midstream>/runs/smolvla_s3/pybullet_smoke_v3_ep0 \
  --episodes 1 --duration-sec 10.0 --launch-stack
```

D2（offline RiskAggregator 对照；**不得**作任务 go/no-go、不得覆盖 `failure_lane`）：

```bash
cd /home/ina/ros2_ws/src/ros2-moveit-pybullet-bridge
python3 scripts/run_offline_risk_readiness.py \
  --timeseries evidence/downstream/smolvla_v3_ep0_policyrunner_<stamp>/benchmark_timeseries.csv \
  --summary evidence/downstream/smolvla_v3_ep0_policyrunner_<stamp>/benchmark_summary.json \
  --s4-trials <midstream>/evidence/smolvla_s4_bounded5_<stamp>/trials \
  --out evidence/downstream/smolvla_v3_ep0_risk_offline_<stamp>.json
```

## 6. Step E — 统一评测信封（unified_eval_report_v0）

```bash
cd /home/ina/robot-sim-lab/robot-arm-episode-data-lab
python3 training/scripts/normalize_unified_eval_report.py \
  --open-loop runs/smolvla_s3/openloop_recovery_v3_prospective_<tag>/s3_open_loop_summary.json \
  --policy-runner evidence/downstream/smolvla_v3_ep0_benchmark_summary.json \
  --isaac-s4 evidence/smolvla_s4_bounded5_<stamp>/s4_gate.json \
  --risk-readiness evidence/downstream/smolvla_v3_ep0_risk_offline_<stamp>.json \
  --out-dir evidence/smolvla_v3_eval_framework_<stamp> \
  --bundle-out evidence/smolvla_v3_eval_framework_<stamp>/smolvla_v3_eval_framework_bundle.json \
  --bundle-id smolvla_v3_eval_framework_<stamp>

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/test_unified_eval_report.py
```

- **不变式**：三份 report + bundle 均 `claims_task_success=false`、`claims_sim2real=false`；risk 只进 `appendix.risk_readiness`。

## 7. Step F — 出图与 portfolio 挂载

```bash
python3 scripts/generate_smolvla_v3_portfolio_figures.py   # 输出 docs/portfolio/smolvla_*.png（7 张）
```

- 每张图必须带证据路径脚注 + `Not task success / not Sim2Real` 声明；
- 新图必须登记进 `docs/portfolio/EVIDENCE_INDEX.md`（生成脚本 + 输入产物可追溯）；
- 挂载位置：`docs/portfolio/SMOLVLA_RECOVERY_V3_PORTFOLIO.md`（图表节）、`docs/portfolio/UNIFIED_EVAL_REPORT.md`。

---

## 8. 止损与升级矩阵

| 情形 | 动作 | 升级到人工的问题 |
|---|---|---|
| Step A 采集不足 | 停止，不换 seed 续采 | 是否放宽 attempts / 换位置定义 |
| Step B Hold | 默认停止；产物归档为 Hold 证据 | 是否批准新一轮 data-fix / 重训（当前额度已用尽） |
| Step C lift 0/N | Hold；不扩种子不重训 | 下一步走行为归因还是冻结该候选 |
| Step D smoke 失败 | 修 interface（handoff/加载），不改评测结论 | — |
| Step E 校验失败 | 修 normalizer/schema，禁止手改产物 JSON | — |
| 图与 JSON 数字不一致 | 以 JSON 为准重出图 | — |

## 9. 完成定义（DoD checklist）

- [ ] A：prospective manifest + 每位 accepted 达标 + QA Pass
- [ ] B：`s3_open_loop_report.json`（含 paired base/lora + per-episode）+ gate 判定 + checkpoint audit
- [ ] C：`s4_gate.json` + `episode_results.jsonl` + 5×`trials/seed_*/report.json`（若获批）
- [ ] D：`benchmark_summary.json` + `benchmark_timeseries.csv` + risk offline JSON
- [ ] E：unified reports + bundle + `pytest tests/test_unified_eval_report.py` 通过
- [ ] F：7 张 PNG 重出 + EVIDENCE_INDEX 登记 + portfolio 文档挂载
- [ ] 收尾：Nuke On Done 清理确认；结论口径不含任务成功 / Sim2Real
