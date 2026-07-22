# SmolVLA S3 AutoDL Runbook

严格按顺序执行。目标：把计费 GPU 时间压缩为「环境验证 → 短 preflight → 一次正式 LoRA → 一次 open-loop」。

**禁止**：在 AutoDL 上临时改数据定义；自动超参搜索；同时推进多个模型；未过 preflight 继续训练；未过 open-loop 跑 Isaac；覆盖 S2 / 历史 evidence；把 HF token 写入仓库。

## 0. 实例规格（最低）

| 项 | 最低 |
|---|---|
| GPU VRAM | **≥16 GB**（推荐 24 GB） |
| 系统盘 / 数据盘空闲 | **≥25 GB**（推荐 40 GB） |
| 磁盘构成粗估 | env~8GB + smolvla_base~2GB + VLM cache~2GB + 数据~2GB + runs/ckpt~5GB + 余量 |
| Python | conda/venv **非**系统 Python |

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
git checkout <CANONICAL_MIDSTREAM_COMMIT>
git rev-parse HEAD   # 记录到 run_metadata
```

同步上游数据树（只读挂载/拷贝），不要改 episode 契约。

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
```

## 6. 数据 / schema 测试

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/test_smolvla_s3_ready.py \
  tests/test_smolvla_gate_s2.py \
  tests/test_absolute_eef_export.py
```

## 7. S3 preflight（20–50 步）

```bash
export S3_PREFLIGHT_MODE=preflight
export S3_PREFLIGHT_STEPS=32
./scripts/run_smolvla_s3_preflight.sh
```

验收：LoRA 初始化、数据可读（若走全模型路径）、forward/backward、无 OOM、loss 有限、LoRA 参数更新、checkpoint 存/载、记录峰值显存与单步耗时。

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
export S3_DATASET_ROOT=/path/to/dataset_root
./scripts/run_smolvla_s3_train.sh
```

## 10. 重新加载 checkpoint

用训练输出目录做一次 load smoke（官方 `from_pretrained` / peft reload），确认可恢复。

## 11. Open-loop 评测（base vs LoRA 成对）

按 `configs/smolvla_s3/eval_gate.yaml` 计算指标与 Pass/Hold/No-Go。  
未 **Pass** → **不得**进入 Isaac。

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
