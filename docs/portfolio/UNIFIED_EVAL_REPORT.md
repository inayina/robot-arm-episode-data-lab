# Unified Evaluation Report (P1)

**状态（2026-07-24）**：最小跨后端评测信封已落地（schema + normalizer + 单测）；P3 可选 `appendix.risk_readiness` 挂 offline RiskAggregator对照。  
**不是**：任务成功、Sim2Real、种子扩采、把 Isaac 迁到下游、用 risk 覆盖任务 go/no-go。

## 一句话

同一套 `unified_eval_report_v0` 信封，三个后端证据列成 **interface / behavior / task / offline** 分栏；只 remap 已有 JSON 字段，不发明指标。

## 三个后端（one framework）

| Backend `backend_id` | 源证据 | 主分栏 | 当前口径 |
|---|---|---|---|
| `smolvla_open_loop` | [`s3_open_loop_summary.json`](../../runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/s3_open_loop_summary.json) | offline + behavior；task=`evaluated:false` | gate_v3 **Pass**；非任务成功 |
| `downstream_policy_runner` | [`smolvla_v3_ep0_benchmark_summary.json`](../../evidence/downstream/smolvla_v3_ep0_benchmark_summary.json) | interface；task unevaluated | 1-ep PyBullet smoke；`is_closed_loop=false` |
| `isaac_s4_bounded` | [`s4_gate.json`](../../evidence/smolvla_s4_bounded5_relight_20260724T151711Z/s4_gate.json) | interface + task funnel | interface 5/5；reach 1/5 · grasp 0/5 · lift 0/5 → Hold；`claims_*=false` |

组合产物（**当前权威**）：[`evidence/smolvla_v3_eval_framework_relight_20260725/smolvla_v3_eval_framework_bundle.json`](../../evidence/smolvla_v3_eval_framework_relight_20260725/smolvla_v3_eval_framework_bundle.json)

**历史信封（Superseded，保留）**：[`evidence/smolvla_v3_eval_framework_20260724/`](../../evidence/smolvla_v3_eval_framework_20260724/) 的
`isaac_s4_bounded` 分栏来自**首轮近黑场景**运行（`smolvla_s4_bounded5_20260724T203700Z`，reach 3/5 · grasp 1/5 · lift 0/5）。
修光后同 seeds 复测证明那组 reach/grasp 是失明走廊几何重叠 + `GRIPPER_CLOSE_MAX=0.70` 口径放大，
因此权威信封改用 relight run。两轮的 open-loop 与 PolicyRunner 分栏相同，`gate_decision` 同为 Hold（lift 0/5），
判定结论未变；历史信封不删除，只降级标注。归因见 [`../SMOLVLA_S4_LIFT0_OFFLINE_ATTRIBUTION.md`](../SMOLVLA_S4_LIFT0_OFFLINE_ATTRIBUTION.md) §6。

一图汇总（`scripts/generate_smolvla_v3_portfolio_figures.py` 可复现）：

![unified eval framework summary](smolvla_v3_eval_framework_summary.png)

下游 PolicyRunner smoke 的 timeseries 可视化：

![downstream policyrunner timeseries](smolvla_v3_downstream_policyrunner_timeseries.png)

图中 `1,084 latency-bearing commands` 是 CSV 中 latency 非空的样本数；统一信封记录的
`1,105 timeseries rows` 是全部 telemetry 行数，两者统计口径不同，不是产物冲突。

## 契约字段（最小）

| 字段 | 含义 |
|---|---|
| `evaluation_run_id` | 运行/目录/handoff 标识 |
| `claims_task_success` / `claims_sim2real` / `claims_online_autonomous_grasp` | **恒为 false** |
| `failure_lane` | 对齐 Policy Adapter：`none` / `interface_fail` / `behavior_tag` / `task_gt` / `system_fail` / `data_fail` |
| `columns.{interface,behavior,task,offline}` | 各含 `evaluated` + `metrics`（仅映射已有字段） |

机器可读：

- YAML stub：[`configs/evaluation/unified_eval_report_v0.yaml`](../../configs/evaluation/unified_eval_report_v0.yaml)
- JSON Schema：[`evaluation/schemas/unified_eval_report.schema.json`](../../evaluation/schemas/unified_eval_report.schema.json)
- Normalizer：[`evaluation/unified_report.py`](../../evaluation/unified_report.py)
- CLI：[`training/scripts/normalize_unified_eval_report.py`](../../training/scripts/normalize_unified_eval_report.py)

关联：[`EVALUATION_CONTRACT.md`](../EVALUATION_CONTRACT.md) §7 六层分栏、[`POLICY_ADAPTER_CONTRACT.md`](../POLICY_ADAPTER_CONTRACT.md) `failure_lane`。

**P2（S4 runtime 权威合同 + SHA 锁定镜像）**：chunk/K/gripper/workspace 以中游 `configs/smolvla_s3/s4_runtime_contract.json` 为权威；上游 Isaac 路径加载包内同 SHA 镜像并在启动时 assert，禁止静默漂移。这不改变任何评测 Pass/Hold 结论，也不声称任务成功。

**P3（offline RiskAggregator readiness对照）**：用下游 `RiskAggregator` 对 PolicyRunner timeseries（+ 可选 S4 trial reports 作 companion）做离线六维风险对照；产物见 [`evidence/downstream/smolvla_v3_ep0_risk_offline_20260724T215900Z.json`](../../evidence/downstream/smolvla_v3_ep0_risk_offline_20260724T215900Z.json)。可经 `--risk-readiness` 挂到 bundle `appendix.risk_readiness`。**硬约束**：`claims_task_success=false`、`overrides_failure_lane=false`、`use_as_task_go_no_go=false`；不得覆盖 ContinuousTaskEvaluator / S4 GT funnel。

对接说明（在线 `--launch-stack` vs 离线 appendix）见下游仓库 README「Risk 对接」一节，以及中游根 README「下游 risk 如何接到本仓」。

## 重新生成

```bash
cd /home/ina/robot-sim-lab/robot-arm-episode-data-lab
python3 training/scripts/normalize_unified_eval_report.py \
  --open-loop runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/s3_open_loop_summary.json \
  --policy-runner evidence/downstream/smolvla_v3_ep0_benchmark_summary.json \
  --isaac-s4 evidence/smolvla_s4_bounded5_relight_20260724T151711Z/s4_gate.json \
  --risk-readiness evidence/downstream/smolvla_v3_ep0_risk_offline_20260724T215900Z.json \
  --out-dir evidence/smolvla_v3_eval_framework_relight_20260725 \
  --bundle-out evidence/smolvla_v3_eval_framework_relight_20260725/smolvla_v3_eval_framework_bundle.json \
  --bundle-id smolvla_v3_eval_framework_relight_20260725
```

校验：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/test_unified_eval_report.py
```

## 禁止话术

- open-loop Pass / PolicyRunner smoke / Isaac interface Pass ≠ 任务成功
- `ran_isaac=true` ≠ Sim2Real / 真机
- 不得因 lift 0/5 自动扩种子或重训
- offline risk R-level / composite ≠ 任务 go/no-go；不得改写 `failure_lane`
