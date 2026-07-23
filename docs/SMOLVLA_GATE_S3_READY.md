# SmolVLA Gate S3（本地冻结 / open-loop Hold）

**状态**：`S3 Hold`（open-loop `gate_decision=hold`；**不是** Ready / Pass / No-Go）
**日期**：2026-07-23
**约束**：v1 griptiming + α64 LoRA 已训且 checkpoint 审计通过；open-loop **Hold**；**不得进 Isaac**；默认停止，任何继续修复需显式人工批准。未改写 S2 evidence。

| 冻结指针 | 值 |
|---|---|
| midstream freeze commit（S3 Ready 基线） | `8fc2a2161d1e2fbdd8ad19d39a6c9dbfbf1762a0` |
| canonical train | `runs/smolvla_s3/train_v1_alpha64_20260722T155559Z/` |
| canonical open-loop | `runs/smolvla_s3/openloop_v1_alpha64_20260722T161454Z/` |
| release（v1 data-fix） | `smolvla_s3_abs_eef_rgb_v1_griptiming` |
| release（v0 诊断基线） | `smolvla_s3_abs_eef_rgb_v0` |
| AutoDL Python | **≥3.12**（`lerobot>=0.5`） |

### 2026-07-23 Hold 收口（当前权威）

| 项 | 结果 |
|---|---|
| train | `train_v1_alpha64_20260722T155559Z`；checkpoint `001000` 配置审计 **passed**（α=64，dropout=0.05） |
| open-loop | `openloop_v1_alpha64_20260722T161454Z`；**`gate_decision=hold`** |
| EE | RMSE **0.061 m**（Pass 带）；相对 S2 **+77.7%** |
| 原 evaluator grip | 连续容差 acc **0.569**（不是分类 accuracy，不再作为 v1 gate 指标） |
| 原 evaluator Pass 未过项 | grip / timing / smooth / sat |
| evaluator audit | v0 报告使用 stride=10 + 每集前 20 个采样点；连续容差被命名为 grip accuracy，timing/smoothness 单位不对齐 |
| CPU re-audit v1 | balanced grip≈`0.709`，但 timing/smooth/sat/temporal coverage 仍未过；旧缺失帧不能补造 |
| data-fix 配额 | `max_data_fix_retries: 1` **已用尽**（v0 No-Go → v1 griptiming） |
| Isaac / S4 | **禁止**（未过 open-loop Pass） |
| 下一步 | 已批准 evaluator-only 修复；同 checkpoint/release 做 stride=1、全 episode 重评；不训练 |

本地证据（相对中游仓根）：

- `runs/smolvla_s3/train_v1_alpha64_20260722T155559Z/run_metadata.json`
- `runs/smolvla_s3/train_v1_alpha64_20260722T155559Z/train_log.txt`
- `runs/smolvla_s3/train_v1_alpha64_20260722T155559Z/lerobot_run/checkpoints/001000/`
- `runs/smolvla_s3/openloop_v1_alpha64_20260722T161454Z/s3_open_loop_summary.json`
- `runs/smolvla_s3/openloop_v1_alpha64_20260722T161454Z/s3_open_loop_report.json`
- `runs/smolvla_s3/openloop_v1_alpha64_20260722T161454Z/checkpoint_config_audit.json`
- `runs/smolvla_s3/openloop_v1_alpha64_20260722T161454Z/evaluator_gripper_timing_audit.md`
- `runs/smolvla_s3/openloop_v1_alpha64_20260722T161454Z/evaluator_reaudit_v1.json`

**诚实口径**：Hold ≠ 任务成功；≠ Sim2Real；≠ 可进 Isaac；≠ S3 Pass。

### 2026-07-22 首次 GPU 结果与入口修复（历史诊断）

| 项 | 结果 |
|---|---|
| checkpoint | `runs/smolvla_s3/train_20260722T115223Z/.../001000/pretrained_model`；已保存并可重载 |
| 配置审计 | **Fail**：实际 alpha/dropout/lr/weight decay/grad norm/warmup/log/eval/save 与冻结 YAML 漂移 |
| open-loop | **No-Go**：EE RMSE `0.1847 m`，grip acc `0.3125`，相对 S2 改善 `32.4%` |
| Isaac | 未运行；S4 仍禁止 |
| 修复 | train CLI 全字段透传 + checkpoint 回读审计 + 完成态 metadata；open-loop `0=闭/1=开` + pre-CUDA 审计 |

首次漂移 checkpoint 只保留作配置漂移诊断，不计作 canonical S3 Pass。其后已完成一次人工批准的 v1 griptiming + α64 重跑，结果为 open-loop **Hold**（见上节）。

## 1. 冻结事实（与 canonical 一致）

| 项 | 事实 |
|---|---|
| ACT | **Frozen diagnostic baseline**；不再盲目训练 |
| Scripted oracle | E3.5 lift **5/5**（物理链参考） |
| LingBot V0/V0.5 | 完成；本机 V1 **No-Go**；路线 **Closed / Archived** |
| SmolVLA S2 | 接口 Pass；H-4 Pass；base zero-shot open-loop **No-Go**（EE RMSE≈0.273 m；gripper acc 0） |
| 活动路线 | **唯一**：SmolVLA **S3 Hold**（默认停止；继续需人工批准） |
| S4 Isaac | **禁止**，除非 S3 open-loop **Pass** |

证据：`docs/portfolio/THREE_REPO_CANONICAL_FACTS.md`、`docs/SMOLVLA_GATE_S2_OPEN_LOOP.md`、`evaluation/examples/smolvla_gate_s2_report.json`。

## 2. Canonical S3 release

| 字段 | 值 |
|---|---|
| release_id | `smolvla_s3_abs_eef_rgb_v0` |
| 路径 | `data/releases/smolvla_s3_abs_eef_rgb_v0/` |
| episodes / frames | 10 / 2052 |
| semantics | `absolute_eef_gripper_v0`（**不是** ACT `ee_delta_gripper`） |
| RGB complete | 1.0 |
| quat | xyzw，已归一化 |
| splits | train 6 / validation 2 / benchmark 2（无泄漏） |

校验：

```bash
python3 training/scripts/validate_smolvla_s3_release.py
```

**禁止**用中游 `e2_500hz_random35_closelift_*`（ee_delta）当 VLA S3 标签。

## 3. Canonical LoRA 配置

路径：[`configs/smolvla_s3/lora_train.yaml`](../configs/smolvla_s3/lora_train.yaml)

- base：`lerobot/smolvla_base`（revision 在首次 AutoDL 下载后钉死 SHA）
- PEFT LoRA：`r=64`，`lora_alpha=64`，`dropout=0.05`，`target_modules=[q_proj,v_proj]`
- seed `42`，`max_steps=1000`，lr `1e-3`
- **preflight-bound**：`batch_size∈{1,2,4,8}`；当前固定入口只允许 `grad_accum=1`；`precision∈{bf16,fp16}`
- 无结构改动、无新 loss、无自动搜参

## 4. 入口（相互独立）

### Preflight

```bash
./scripts/run_smolvla_s3_preflight.sh
# 本机默认 mock-preflight
S3_PREFLIGHT_MODE=preflight S3_PREFLIGHT_STEPS=32 ./scripts/run_smolvla_s3_preflight.sh
```

失败必须停止；**不会**启动正式训练。

### 正式训练（人工确认）

```bash
export S3_PREFLIGHT_REPORT=/path/to/REAL/preflight_report.json
export S3_I_UNDERSTAND_BILLING=1
export SMOLVLA_S3_EXECUTE_TRAIN=1
export S3_DATASET_ROOT=/path/to/mounted/upstream/v21/trees
export SMOLVLA_BASE_DIR=/path/to/pinned/smolvla_base
export SMOLVLA_BASE_REVISION=<40-hex-huggingface-commit>
./scripts/run_smolvla_s3_train.sh
```

Mock preflight **不能**授权正式训练。

## 5. Open-loop 门禁

[`configs/smolvla_s3/eval_gate.yaml`](../configs/smolvla_s3/eval_gate.yaml)

| 判定 | 要点 |
|---|---|
| **Pass** | EE RMSE≤0.100 m 且相对 S2 改善≥50%；grip acc≥0.70；quat≤0.35 rad（可测时）；阶段时序可信 |
| **Hold** | EE≤0.205 m（≥25% 改善）或部分改善但夹爪/阶段仍错；最多一次明确数据修复（**当前已落在此带；配额已用尽**） |
| **No-Go** | EE≥0.246 m 或 grip≤0.15 或近静止/异常/严重过拟合 |
| Isaac | 未过 open-loop **Pass** → **不得**进 S4 |

阈值来自 S2 基线与 train-split expert scale（`norm_stats.json`），非拍脑袋。

## 6. AutoDL

完整顺序见 [`SMOLVLA_S3_AUTODL_RUNBOOK.md`](SMOLVLA_S3_AUTODL_RUNBOOK.md)。  
环境：`scripts/autodl_setup_smolvla_s3.sh` + `configs/smolvla_s3/environment.lock.txt`。

## 7. 本地验收 vs 真实 GPU

| 类型 | 含义 |
|---|---|
| **mock-preflight** | 本机控制流 / schema / 门禁解析通过；**不是**真实 GPU preflight |
| **REAL_GPU_PREFLIGHT** | AutoDL 上 20–50 步；通过后才可人工批准正式 LoRA |

## 8. 明确未做 / 当前禁止

- open-loop **Pass**（当前为 Hold）
- Isaac / S4
- 第二次 data-fix / 自动继续重训（`max_data_fix_retries: 1` 已用尽）
- 覆盖 S2 报告或把 Hold 写成任务成功 / Sim2Real
- 在无显式人工批准下启动任何新 train / open-loop / 采集
