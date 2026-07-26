# Open-loop 扰动诊断结果（P1-0A / P1-0B）

**状态**：已执行（diagnostic only）  
**跑次**：`runs/smolvla_s3/openloop_perturbation_20260725T045044Z/`  
**GPU**：NVIDIA RTX PRO 500 · peak VRAM **927 MiB** · wall **161.7 s** · **1080** 次独立 first-action 推理  
**诚实边界**：**Not task success / Not Sim2Real / Not real robot** · `gate_eligible=false` · **不得**改写 `eval_gate_v3` Pass

协议见 [../SMOLVLA_OPENLOOP_PERTURBATION_DESIGN.md](../SMOLVLA_OPENLOOP_PERTURBATION_DESIGN.md)；配置锁 `configs/smolvla_s3/openloop_perturbation.yaml`。

---

## 1. 跑什么 / 不跑什么

| 层 | 内容 | 次数 |
|---|---|---|
| P1-0A 阶段锚点 | 6 stages × 10 ep × {clean,light,medium,heavy} | **240** |
| P1-0B close 窗口 | 21 帧/ep × 10 × 4 条件 | **840** |
| Clean canonical Gate | 全帧 2593 | **未重跑**（保持既有 Pass） |
| H=5 / H=10 open-loop | — | **未做** |
| State noise 主表 | — | **排除**（需 oracle 重标） |

---

## 2. Layer-1 阶段敏感性（EE RMSE, m）

| Stage | clean | light | medium | heavy | Δ heavy−clean |
|---|---:|---:|---:|---:|---:|
| hover_approach | 0.0101 | — | — | 0.0275 | +0.0175 |
| descend_mid | 0.0252 | — | — | 0.0491 | +0.0239 |
| **pre_close** | **0.0457** | — | — | **0.0744** | **+0.0287** |
| close_transition | 0.0257 | — | — | 0.0482 | +0.0225 |
| early_lift | 0.0238 | — | — | 0.0474 | +0.0236 |
| late_lift | 0.0184 | — | — | 0.0225 | +0.0041 |

聚合（60 锚点/条件）：

| 条件 | EE RMSE | grip BA | wrong-close rate |
|---|---:|---:|---:|
| clean | 0.0271 | 1.000 | 0.000 |
| light | 0.0364 | 1.000 | 0.000 |
| medium | 0.0480 | 0.983 | 0.017 |
| heavy | 0.0479 | 1.000 | 0.000 |

**读法**：图像 nuisance 下 EE 误差随强度上升；**pre_close 最敏感**；夹爪分类在锚点集上整体稳健（medium 仅 1 次错误闭爪）。这不等于闭环鲁棒。

---

## 3. Layer-2 闭爪窗口（210 帧/条件）

| 条件 | EE RMSE | grip BA | wrong-close | close offset mean (帧) | early-close eps |
|---|---:|---:|---:|---:|---:|
| clean | 0.0352 | 0.916 | 0.067 | **−1.1** | 7/10 |
| light | 0.0457 | 0.880 | 0.114 | −2.3 | 10/10 |
| medium | 0.0548 | 0.855 | 0.138 | −2.8 | 10/10 |
| heavy | 0.0595 | 0.860 | 0.133 | −2.7 | 10/10 |

- 3-frame debounce 下 **无漏 close**（`missed_close_episodes=0` 全条件）。  
- 扰动使 **提前闭爪更严重**（median offset clean −1.5 → medium/heavy −3.0）。  
- wrong-close rate 约翻倍（0.067 → ~0.13）。

---

## 4. 可以声称 / 不可以声称

**可以**：
- 在专家态 first-action 协议下，图像 brightness/blur/noise 会抬高 EE 误差；pre_close 阶段最脆；
- close 窗口上 nuisance 加重提前闭爪与错误闭爪倾向；
- 本诊断与 clean Gate / S4 Hold **隔离**，可复现（`anchor_table.json` + 条件种子）。

**不可以**：
- 扰动退化 ≠ 任务失败根因已证明；
- ≠ 可进 Isaac 扩种子 / 重训授权；
- ≠ 替代全帧 clean Pass；
- ≠ Sim2Real / 真机结论。

---

## 5. 复现

```bash
cd /home/ina/robot-sim-lab/robot-arm-episode-data-lab
export S3_PERTURBATION_OUT=runs/smolvla_s3/openloop_perturbation_rerun_$(date -u +%Y%m%dT%H%M%SZ)
./scripts/run_smolvla_s3_open_loop_perturbation.sh
```

CPU 单测：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/test_smolvla_openloop_perturbation.py`
