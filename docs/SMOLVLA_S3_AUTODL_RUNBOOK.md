# SmolVLA S3 AutoDL Runbook

严格按顺序执行。目标：把计费 GPU 时间压缩为「环境验证 → 短 preflight → 一次正式 LoRA → 一次 open-loop」。

**禁止**：在 AutoDL 上临时改数据定义；自动超参搜索；同时推进多个模型；未过 preflight 继续训练；未过 open-loop 跑 Isaac；覆盖 S2 / 历史 evidence；把 HF token 写入仓库。

## 0. 实例规格（最低）

| 项 | 最低 |
|---|---|
| GPU VRAM | **≥16 GB**（推荐 24 GB） |
| 系统盘 / 数据盘空闲 | **≥25 GB**（推荐 40 GB） |
| 磁盘构成粗估 | env~8GB + smolvla_base~2GB + VLM cache~2GB + 数据~2GB + runs/ckpt~5GB + 余量 |
| Python | conda/venv **Python ≥3.12**（**非**系统 Python；lerobot≥0.5 要求） |

## 1. 检查 GPU / CUDA / 内存 / 磁盘

```bash
nvidia-smi
free -h
df -h ~
```

VRAM <15GB → **S3 No-Go**，关机换实例。

## 2. Checkout 固定 commit

```bash
cd /path/to/robot-arm-episode-data-lab
git fetch --all
# Canonical S3 Ready freeze (2026-07-22):
git checkout 8fc2a2161d1e2fbdd8ad19d39a6c9dbfbf1762a0
git rev-parse HEAD   # 必须等于上述 SHA；记录到 run_metadata
```

同步上游数据树（只读挂载/拷贝），不要改 episode 契约。
`manifest.source_dataset_roots` 是本机绝对路径；AutoDL 上按目录名挂载/拷贝同名树，并用运行时路径映射，**不得**改 release hash / splits。

## 3. 安装锁定环境

```bash
chmod +x scripts/autodl_setup_smolvla_s3.sh
./scripts/autodl_setup_smolvla_s3.sh
# 激活脚本创建的 conda/venv
```

## 4. 下载或挂载固定数据 release

1. 确认中游 `data/releases/smolvla_s3_abs_eef_rgb_v0/manifest.json` 存在。
2. 将上游两个 LeRobot v2.1 目录放到与 manifest `source_dataset_roots` 对应的位置（或更新仅运行时路径映射，**不改** hash/split）。
3. 运行：

```bash
python3 training/scripts/validate_smolvla_s3_release.py
```

失败 → **No-Go**，停止。

## 5. 下载指定 revision 的 base checkpoint

```bash
export HF_HOME=~/autodl-tmp/hf_cache
export SMOLVLA_S3_DOWNLOAD_BASE=1
./scripts/autodl_setup_smolvla_s3.sh   # or huggingface-cli download
# 将实际 commit SHA 写回 configs/smolvla_s3/lora_train.yaml base_checkpoint.revision
export SMOLVLA_BASE_DIR=~/autodl-tmp/smolvla_s3/smolvla_base
export SMOLVLA_BASE_REVISION=<40-hex-huggingface-commit>
```

训练入口会拒绝 `main`、空值或非 40 位 SHA；base 身份未钉死时不得计费重跑。

## 6. 数据 / schema 测试

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/test_smolvla_s3_ready.py \
  tests/test_smolvla_gate_s2.py \
  tests/test_absolute_eef_export.py
```

## 7. S3 preflight（20–50 步）

Recovery 技术入口目前只支持本节的**无正式训练** probe；但
`recovery_decisions.yaml` 仍明确 `AutoDL billing` 未授权，实际开机前还需人工批准 GPU 计费：

```bash
export S3_CONFIG="$PWD/configs/smolvla_s3/lora_train_recovery_draft.yaml"
export S3_RELEASE_DIR="$PWD/data/releases/smolvla_s3_abs_eef_rgb_v2_griptiming_lateclose"
export SMOLVLA_BASE_DIR=/root/autodl-tmp/smolvla_s3/smolvla_base
export S3_PREFLIGHT_MODE=preflight
export S3_PREFLIGHT_STEPS=32
./scripts/run_smolvla_s3_preflight.sh
```

验收：`used_full_smolvla_weights=true`、
`live_peft_resolve_probe_passed=true`、官方 PEFT 正则解析到非零参数、CUDA
backward/optimizer 更新、adapter 保存、无 OOM、loss 有限，并记录峰值显存与单步耗时。
该 probe 明确写入 `policy_forward_executed=false` 和
`inference_latency_measured=false`；它不冒充策略推理或 empty-camera profiler。
Recovery 配置还要求 `dependency_version_audit.passed=true`；当前
preflight-qualified 栈含 `peft==0.19.1`。任何版本漂移都会在 CUDA probe 前
fail closed。由于该门禁是在 2026-07-23 首次 probe 后加入，旧 report 只保留为
PEFT resolve 证据，不可直接授权修订后配置训练。

失败 → **停止**，不得启动正式训练。

## 8. 报告资源结果，等待人工批准

打包 `preflight_report.json` + `env_versions.json`，人工确认：

- VRAM 峰值与 batch 是否落在 preflight-bound 允许集
- 是否只跑**一次**正式 LoRA

## 9. 人工批准后执行一次正式 LoRA

```bash
export S3_PREFLIGHT_REPORT=/path/to/preflight_report.json
export S3_I_UNDERSTAND_BILLING=1
export SMOLVLA_S3_EXECUTE_TRAIN=1
# Train-only root (required; refuses unfiltered 20-ep merge)
export S3_STATE_CONTRACT=recovery15
./scripts/materialize_smolvla_s3_train_root.sh
export S3_DATASET_ROOT=/path/to/train_only_root   # must contain train_root_provenance.json
./scripts/run_smolvla_s3_train.sh
```

当前 `lora_train_recovery_draft.yaml` 仍有
`authorized_to_train=false` 且 `train.max_steps=0`，入口会 fail closed。只有在
train-only frame 数、稳定 batch、5-epoch budget 和人工批准均写入新的 resolved
配置后，才能执行本节；不得直接修改 draft 绕过。

入口限定在已核对的 LeRobot `0.5.x` CLI/schema，并显式透传 mixed precision、
LoRA alpha/dropout/bias/targets、optimizer、warmup、log/eval/save 频率和 chunk；
完成后自动回读 `adapter_config.json`、`config.json`、
`train_config.json`。任一冻结字段漂移都会使 `run_metadata.json` 为 `no_go`，脚本非零退出。

## 10. 重新加载 checkpoint

`run_metadata.json` 必须同时满足 `executed=true`、`completed=true`、
`gate=checkpoint_config_verified`；随后用训练输出目录做一次 load smoke（官方
`from_pretrained` / peft reload），确认可恢复。

## 11. Open-loop 评测（base vs LoRA 成对）

按 `configs/smolvla_s3/eval_gate.yaml` 计算指标与 Pass/Hold/No-Go。  
未 **Pass** → **不得**进入 Isaac。

Open-loop 在申请 CUDA 前复用 checkpoint 配置审计；漂移 checkpoint 会直接生成
`checkpoint_config_audit.json` + `s3_open_loop_summary.json(no_go)`。夹爪时序严格采用
Panda 契约 `0=closed, 1=open`。
评测只有 `gate_decision=pass` 才以 0 退出；`hold` / `no_go` 均非零退出，不能被流水线误当作 Isaac-ready。

Evaluator v2 的 canonical Pass 评测必须使用完整轨迹：

```bash
export S3_OPENLOOP_STRIDE=1
export S3_OPENLOOP_MAX_FRAMES=0   # 0 = 每条 episode 全帧
export S3_OPENLOOP_INFERENCE_MODE=canonical_first_action
./scripts/run_smolvla_s3_open_loop.sh
```

它只重新推理与评测，不训练。`stride>1` 或截断帧数仍可用于快速诊断，但
`temporal_metrics_gate_eligible=false`，最多只能 Hold / No-Go。队列语义诊断使用
`S3_OPENLOOP_INFERENCE_MODE=queued_diagnostic`；该模式仅在 episode 边界 reset，
会消费 checkpoint 的 action queue，但同样强制不可 Pass。v2 分开报告：

- 夹爪连续容差与 threshold-classification balanced accuracy / F1；
- debounce 后的 signed close offset（源帧与秒，负数表示提前闭合）；
- teacher-forced 首动作 smoothness 与同 stride expert smoothness；
- `raw_gripper_oob_ratio`；
- full-episode coverage。
- latency mean / p50 / p95 / max。

旧报告可在 CPU 上只读重算已有预测（不能补回未推理帧）：

```bash
python3 training/scripts/recompute_smolvla_s3_saved_open_loop.py \
  --report <old-run>/s3_open_loop_report.json \
  --output <old-run>/evaluator_reaudit_v1.json
```

## 12. 打包证据

至少包含：

- `lora_train.yaml` + config sha256
- release `manifest.json` + hashes
- `preflight_report.json`
- `run_metadata.json` / train log
- checkpoint metadata（非必要勿回传整模）
- open-loop 报告与 per-episode raw JSON

## 13. 下载后关闭实例

确认本地已落盘证据 → 释放 GPU。

---

## 数据与权重获取说明（无密钥）

| 资产 | 来源 | 说明 |
|---|---|---|
| S3 release 元数据 | 本仓 `data/releases/smolvla_s3_abs_eef_rgb_v0/` | 已进 git（gitignore 例外） |
| RGB+parquet | 上游 `e2_red_500hz_seed52_*` 与 `seed53_*` | 按 manifest hash 校验 |
| `lerobot/smolvla_base` | Hugging Face Hub | 实例上 login；**勿提交 token** |
| ACT ee_delta release | **禁止**用作 S3 VLA 标签 | NG-C |

## HF cache

```bash
export HF_HOME=~/autodl-tmp/hf_cache
export HUGGINGFACE_HUB_CACHE=$HF_HOME/hub
export TRANSFORMERS_CACHE=$HF_HOME/transformers
```
