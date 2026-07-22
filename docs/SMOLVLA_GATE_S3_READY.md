# SmolVLA Gate S3 Ready（本地冻结 / AutoDL 执行准备）

**状态**：`S3 Ready`（本地准备与验证完成）  
**日期**：2026-07-22  
**约束**：本轮**未**下载完整新权重、**未**正式训练 SmolVLA、**未**跑 Isaac、**未**改写 S2/历史 evidence。

## 1. 冻结事实（与 canonical 一致）

| 项 | 事实 |
|---|---|
| ACT | **Frozen diagnostic baseline**；不再盲目训练 |
| Scripted oracle | E3.5 lift **5/5**（物理链参考） |
| LingBot V0/V0.5 | 完成；本机 V1 **No-Go**；路线 **Closed / Archived** |
| SmolVLA S2 | 接口 Pass；H-4 Pass；base zero-shot open-loop **No-Go**（EE RMSE≈0.273 m；gripper acc 0） |
| 活动路线 | **唯一**：SmolVLA **S3**（外部 GPU + 人工批准） |
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
- **preflight-bound**：`batch_size∈{1,2,4,8}`，`grad_accum∈{1,2,4}`，`precision∈{bf16,fp16}`
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
./scripts/run_smolvla_s3_train.sh
```

Mock preflight **不能**授权正式训练。

## 5. Open-loop 门禁

[`configs/smolvla_s3/eval_gate.yaml`](../configs/smolvla_s3/eval_gate.yaml)

| 判定 | 要点 |
|---|---|
| **Pass** | EE RMSE≤0.100 m 且相对 S2 改善≥50%；grip acc≥0.70；quat≤0.35 rad（可测时）；阶段时序可信 |
| **Hold** | EE≤0.205 m（≥25% 改善）或部分改善但夹爪/阶段仍错；最多一次明确数据修复 |
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

## 8. 明确未做

- 正式 S3 LoRA 训练
- Isaac / S4
- 覆盖 S2 报告或历史 checkpoint
- 声称任务成功
