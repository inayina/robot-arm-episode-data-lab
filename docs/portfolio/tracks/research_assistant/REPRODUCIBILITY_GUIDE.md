# Reproducibility Guide

**版本**：v1.0  
**默认复现级别**：CPU-only contract + frozen-evidence verification  
**不会执行**：training、GPU inference、ROS live、Isaac、MuJoCo rollout、real robot。

返回：[RA 科研助理文档包](README.md)

---

## 1. 复现等级

| Level | 内容 | 默认授权 |
|---|---|---|
| R0 | 文档、身份、路径和 claims 一致性 | 是 |
| R1 | schema、contract、fixture、报告和数字回归 | 是，CPU-only |
| R2 | 从冻结 JSON 重生成统计/图 | 是，若不调用模型/仿真 |
| R3 | checkpoint inference / GPU analysis | 否，需单独批准和环境 |
| R4 | bounded simulator rollout | 否，需显式批准、限时和清理 |
| R5 | real robot | 未开始，不在当前范围 |

## 2. 冻结身份

首先读取 [research_identity.yaml](research_identity.yaml)，确认：

- checkpoint artifact SHA；
- train release 与 prospective evaluation ID；
- `eval_gate_v3` SHA；
- authoritative relight S4 路径；
- dark first run 为 Superseded；
- claims 与 planned analysis 状态。

若仓库状态与 identity 冲突，以当前代码/测试和权威 JSON 为准，并记录 identity 需要修订，不能静默替换。

## 3. CPU 回归

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/test_portfolio_docs_consistency.py \
  tests/test_smolvla_s3_eval_gate_v3.py \
  tests/test_smolvla_s3_eval_gate_v3_execution.py \
  tests/test_unified_eval_report.py
```

全仓回归：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
```

知识源审计：

```bash
python3 -m project_knowledge.cli audit \
  --json-out /tmp/ra-project-audit.json \
  --markdown-out /tmp/ra-project-audit.md
```

审计可能因既有 warning 返回非零；必须分别报告 `error` 和 `warning`，不能把 warning 隐藏成全绿。

## 4. 关键数字核验

| Claim | Source |
|---|---|
| open-loop EE `0.0253 m`、grip BA `0.9943` | `runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/s3_open_loop_report.json` |
| prospective 10 ep / 2,593 frames / zero overlap | 同一 report 的 `prospective_evaluation` 与 episodes |
| S4 interface 5/5、reach 1/5、grasp/lift 0/5 | `evidence/smolvla_s4_bounded5_relight_20260724T151711Z/s4_gate.json` |
| oracle lift 5/5 | `evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/oracle_gate.json` |
| Gate SHA | `configs/smolvla_s3/eval_gate_v3.lock.json` |
| RA-WP2 mean W1 `0.7228`、energy `2.0554`、5/5 末段偏移更高 | `evidence/closed_loop_shift_v1/report.json` |
| Phase/failure-onset readiness blocked on old evidence | `evidence/closed_loop_phase_shift_v2/readiness_report.json` |

数字只能从 JSON 读取；Markdown 是解释层，不是数字权威源。

## 5. 结果状态规则

- `Current`：当前权威协议结果；
- `Historical`：历史有效但不代表当前候选；
- `Superseded`：被更严格/修正协议替代，保留但不能做 headline；
- `Invalid`：evaluator、identity 或 provenance 无效；
- `Not Run`：禁止按规划或行业惯例补全。

## 6. RA-WP2 复现

冻结报告已经交付输入 provenance、schema、分析代码、合成测试、RNG seed、episode bootstrap 配置和 claims 字段。CPU-only 重算命令：

```bash
python3 training/scripts/analyze_closed_loop_shift.py \
  --output /tmp/closed_loop_shift_reproduction.json
```

图表只从 JSON 生成：

```bash
python3 scripts/generate_closed_loop_shift_figures.py \
  --report evidence/closed_loop_shift_v1/report.json \
  --output-dir /tmp/closed_loop_shift_figures
```

由于冻结输出已存在，分析器拒绝覆盖；复算应写到新路径，并比较 `analysis`、`method`、`conclusion` 与 provenance hashes。图表不得拥有 JSON 中不存在的数字。

## 7. 复现声明模板

True phase-conditioned analysis 的合同检查：

```bash
python3 training/scripts/audit_phase_telemetry_readiness.py \
  --output /tmp/phase_readiness.json

python3 training/scripts/materialize_train_phase_annotations.py \
  --output /tmp/train_phase_annotations.jsonl
```

在冻结历史证据上，上述命令应分别报告缺少 source telemetry 与缺少训练逐帧 phase。只有新采集同时具备 `panda_train_frame_phase_v1`、`smolvla_observation_telemetry_v2` 和 `panda_task_timeline_v1` 后，才允许运行 `training/scripts/analyze_phase_conditioned_shift.py`。

> We reproduce the CPU-side contracts and verify frozen evidence identities and headline metrics. We do not rerun model inference or simulation. The authoritative closed-loop result remains Hold with lift 0/5; this reproduction does not establish task success, Sim2Real, or real-robot performance.
