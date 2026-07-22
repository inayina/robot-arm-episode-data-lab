# SmolVLA Gate S1：官方环境与资源复现

**日期**：2026-07-21T17:13:52Z  
**状态**：`pass`  
**约束**：未用 Panda 数据；未训练；未跑 Isaac；`claims_task_success=false`。

## 结论

在本机 **RTX PRO 500（约 5672 MiB）** 上，`lerobot/smolvla_base` **可加载并完成一次 `select_action` 前向**。

| 项 | 值 |
|---|---|
| Load peak VRAM | **884 MiB** |
| Infer peak VRAM | **925 MiB** |
| Full forward latency (mean, after `policy.reset()`) | **~171 ms** |
| Action shape | `[1, 6]` |
| Hub revision | `c83c3163b8ca9b7e67c509fffd9121e66cb96205` |
| LICENSE | LeRobot **Apache-2.0**（本地 `lerobot/LICENSE`） |

**S1 Go**：本地推理资源门禁通过（远低于 6GB 卡上限）。  
**非声明**：未证明 Panda 任务成功；未跑官方 `lerobot/libero` 帧（缺 `av` / 数据集依赖）；未训练 LoRA。

## 硬件

| 项 | 值 |
|---|---|
| GPU | NVIDIA RTX PRO 500 Blackwell Generation Laptop GPU |
| VRAM total | 5672 MiB |
| Load peak | 884 MiB |
| Infer peak | 925 MiB |

## 模型与样本

| 项 | 值 |
|---|---|
| model_id | `lerobot/smolvla_base` |
| VLM backbone（本地） | `HuggingFaceTB/SmolVLM2-500M-Video-Instruct` → `checkpoints/SmolVLM2-500M-Video-Instruct` |
| frame_source | `synthetic_smolvla_base_schema`（schema 对齐合成帧；非 Liber） |
| infer_mode | `synthetic_frame_select_action` |

机器可读：[`evaluation/examples/smolvla_gate_s1_report.json`](../evaluation/examples/smolvla_gate_s1_report.json)

## 复现命令

```bash
# 权重已在 checkpoints/ 时（跳过 pip / Hub）：
SKIP_PIP=1 bash scripts/run_smolvla_gate_s1_host.sh

# 或直接：
python training/scripts/run_smolvla_gate_s1_smoke.py \
  --local-dir checkpoints/smolvla_base_gate_s1 \
  --vlm-local-dir checkpoints/SmolVLM2-500M-Video-Instruct \
  --local-files-only \
  --report-json evaluation/examples/smolvla_gate_s1_report.json \
  --report-md docs/SMOLVLA_GATE_S1_OFFICIAL_REPRO.md
```

## 已知缺口（不阻塞 S1）

- `lerobot/libero` 未拉取：`av` 未装；可用合成帧完成资源门禁。
- Hub `license` 字段为空；以 LeRobot Apache-2.0 LICENSE 文件为准。
- HF Hub 直连易卡在 Xet；本机用 CDN `curl -C -` 下完 `model.safetensors`（policy ~865MB + VLM ~1.9GB）。

## 下一闸（未批准不执行）

- **S2**：已完成 — [`SMOLVLA_GATE_S2_OPEN_LOOP.md`](SMOLVLA_GATE_S2_OPEN_LOOP.md)（接口 pass / H-3 no_go）
- **S3**：LoRA（本机 6GB → 仍建议 **No-Go**；需 ≥16GB）
- **S4**：Isaac 在线
