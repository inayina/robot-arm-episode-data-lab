# VLA Gate V1 预检报告（官方环境 / 6B / 官方任务）

> **状态：CLOSED / ARCHIVED**  
> **决策日期：2026-07-21**  
> **当前结论：不进入本机 Gate V1，不作为第一 Panda 后训练策略；不得自动恢复本预检路径。**  
> **主要原因：本机 ~6GB（RTX PRO 500 / 6113 MiB）不满足 LingBot 6B 官方复现；相对 SmolVLA ROI 更低。**  
> **保留原因：** 资源门禁与「批准下载 ≠ 可验收」止损证据。  
> **当前活动路线：** SmolVLA Gate S0–S2（Hold at S2）。

**日期**：2026-07-22  
**触发**：用户明确批准「装官方环境、下 6B、官方任务复现」（不接 Panda）。  
**结论**：**Gate V1 本机执行 No-Go（预检失败）** — 未 clone 安装、未下载权重、未跑官方推理。

---

## 0. 宿主机 `nvidia-smi` 用户实测（权威）

用户于宿主机终端回报（2026-07-22）：

```text
name, memory.total [MiB]
NVIDIA RTX PRO 500 Blackwell Generation Laptop GPU, 6113 MiB
```

| 项 | 值 | 对 Gate V1 的含义 |
|---|---|---|
| GPU | **RTX PRO 500 Blackwell Laptop** | 本机有可用 NVIDIA GPU（宿主机侧） |
| VRAM | **6113 MiB ≈ 6 GB** | 相对官方示例 **4090D** 级严重不足 |
| Agent 侧 | 仍无 `/dev/nvidia*` | Agent 会话不能直接跑 CUDA；须宿主机终端或可透传 GPU 的环境 |

**判定**：即使用户已批准下载，**本机 6GB 不足以作为官方 6B + Qwen3-VL 推理复现平台**（HOLD-1 → **No-Go**）。下载 ~28G 权重只会占盘，不能完成「官方任务复现」验收。

---

## 1. 批准项核对

| Gate V0.5 §6.3 要求 | 状态 |
|---|---|
| 人工批准下载依赖/权重 | **已批准**（本轮用户指令） |
| 足够 GPU（公开示例偏 4090D） | **未满足**（见下） |
| LICENSE/权重条款 | 代码 + HF 卡片声明 Apache-2.0；包内逐文件待下载后复核 |
| 本轮不接 Panda | **遵守** |

---

## 2. 硬件 / 驱动事实

| 项 | 观测 |
|---|---|
| PCI | `01:00.0 NVIDIA Device 10de:2db9`（Lenovo `17aa:512c`） |
| Kernel driver | `nvidia` in use；modules `nvidia` / `nvidia_uvm` / `nvidia_modeset` / `nvidia_drm` 已加载 |
| Driver pkg | `nvidia-driver-580-open` 580.159.03 |
| `/dev/nvidia*` | **不存在**（本 Agent 沙箱 `/dev` 仅有 null/tty/pts/shm，**无** dri/nvidia 节点） |
| `nvidia-smi` | **失败**：无法与 driver 通信 |
| Prefetchable BAR | Region1 **8G**（强烈暗示约 8GB 级显存，非 4090 24GB） |
| GPU 识别（推断） | `10de:2db9` ≈ **RTX 5060 Laptop**（8GB 级）；非官方示例 4090D |
| 磁盘可用 | `/` ≈ **164G free**（6B 包公开 usedStorage ≈ 28G，空间原则上够） |
| 本 Agent 环境 | **查过**：即使用户说「你查吧」，Agent 仍无法访问宿主机 GPU 字符设备；`nvidia-modprobe` 未装且无法在沙箱内创建 `/dev/nvidia*` |

**2026-07-22 复检（用户要求 Agent 自查）**：结论不变 — `nvidia-smi` 失败、`/dev/nvidia*` 缺失。宿主机内核侧 modules 仍在，但是 **Cursor Agent 进程的 `/dev` 命名空间未挂载 GPU**，因此 Gate V1 不能由 Agent 在本会话直接完成。

官方 `tools/create_train_env.sh` 硬断言：

```text
assert torch.cuda.is_available()
torch==2.8.0
```

在当前机器/会话下该断言 **必然失败**。

---

## 3. Gate V1 官方路径（参考，未执行）

来源：https://github.com/Robbyant/lingbot-vla-v2

```bash
git clone https://github.com/Robbyant/lingbot-vla-v2.git
cd lingbot-vla-v2
bash tools/create_train_env.sh --env-name lingbotvla

python3 scripts/download_hf_model.py \
  --repo_id robbyant/lingbot-vla-v2-6b \
  --local_dir lingbot-vla

# Open-loop（需 post-train ckpt + robotwin 验证集；纯预训练权重不一定可直接当 robotwin open-loop）
export QWEN3_PATH=Qwen/Qwen3-VL-4B-Instruct
python scripts/open_loop_eval.py \
  --model_path path_to_posttraining_ckpt \
  --robo_name robotwin \
  --data_path path_to_validation_data \
  --use_length 50
```

**重要语义**：README 的 open-loop / RoboTwin deploy 示例指向 **post-training checkpoint** + `robotwin` config，不是「下载 6B 预训练后立刻出 Panda 成功率」。Gate V1 的合格证据应是：

1. 环境可 `torch.cuda.is_available()==True`
2. 权重落盘 + sha256 / LICENSE 复核
3. 官方脚本至少完成一次 **可记录的** 推理或 open-loop（官方任务/配置），并写 latency/显存
4. **明确** `claims_task_success=false` 且 **未接本仓 Panda**

---

## 4. 阻塞分级

| ID | 阻塞 | 影响 |
|---|---|---|
| B1 | 无 `/dev/nvidia*` / `nvidia-smi` 失败 | **硬阻塞**安装脚本与任何 CUDA 推理 |
| B2 | 预估 ~8GB 显存 vs 公开 4090D 级 6B+VLM | **高概率**推理 OOM（HOLD-1 升级） |
| B3 | 官方复现常需 RoboTwin 数据 + 可选 post-train ckpt | 仅下 6B 预训练 **不等于** 官方任务数字复现 |

---

## 5. 用户侧解法（本机终端，非 Agent）

在**宿主机普通终端**（有真实 `/dev`、可 sudo）执行：

```bash
# 1) 恢复 GPU 设备节点
sudo apt install -y nvidia-modprobe
sudo nvidia-modprobe -u -c=0
# 或重启后确认：
nvidia-smi

# 2) 确认显存（需 ≥ 公开 4090 级才谈 6B 官方复现；8GB 级建议改用远程 GPU）
nvidia-smi --query-gpu=name,memory.total --format=csv

# 3) 通过后再让 Agent / 本机跑 Gate V1 安装与下载
```

若只有 8GB 笔记本 GPU：建议 **换 24GB+ 机器** 做 Gate V1，本机只保留契约/fixture。

---

## 6. 本轮明确未做

- 未 `git clone` lingbot-vla-v2 到大目录（避免半装污染；可按你确认后立即 clone）
- 未创建 `lingbotvla` conda env
- 未下载 `robbyant/lingbot-vla-v2-6b`（~28G）
- 未接 Panda / 未改 E3 evidence

---

## 7. 验收状态

- [x] 记录用户批准
- [x] 硬件/驱动预检
- [ ] 官方环境安装
- [ ] 6B 下载 + LICENSE 包内复核
- [ ] 官方任务/open-loop 复现日志

**Gate V1 go_no_go：`no_go_preflight_gpu`**
