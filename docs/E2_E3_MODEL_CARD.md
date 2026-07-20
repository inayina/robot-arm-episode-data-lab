# E2 / E3 Model Card — Panda ACT (500 Hz scene)

**Selected E3 checkpoint（最终选型）**: `e2_500hz_act_random30_descend_conservative_5epoch_20260719`

选型依据：SOP P2/P3 以 **home_start 行为**为主门；30-ep descend 在 home 上闭合，40-tight 在 home 上回退。
warmstart 仅作接近态诊断，**不得**用 warm 成功替代 home 成功声明。

---

## 1. Identity

| 字段 | 30-ep descend（**选用**） | 40-ep xyalign-tight（对照） |
|---|---|---|
| model_id | `e2_500hz_act_random30_descend_conservative_5epoch_20260719` | `e2_500hz_act_random40_xyalign_tight_conservative_5epoch_20260719` |
| checkpoint | `data/.../checkpoint.pt` | `data/.../checkpoint.pt` |
| **sha256** | `948e2949ae8af099f8347837969f596018bbf68a18cc703b6bc09abd01a92501` | `4cc25de6088754c70f4184b38c17b7aaa6a91bc018216bd13ad9f3aea559b109` |
| release_id | `e2_500hz_random30_descend_20260719` | `e2_500hz_random40_xyalign_tight_20260719` |
| episodes / frames | 30 / 7727 | 40 / 9696 |
| frames.jsonl sha256 | `5e054ea18bc47b54de02aad6170a6466ed0ca623705a37ad0b107f9b2ba3e045` | `c11fd13a67c4509600010b5fa45d86189e79f74a41169e5fd9f1da46792f344e` |
| policy | LeRobot ACT `scene_act_lerobot`, chunk_size=50 | 同左 |
| train | 5 epoch, stage-balanced, grasp-context | 同左 |
| midstream git（train） | `414cb8c7b8a060063aef144b42c1ff17eba9cc4f` | 同左 |
| upstream git（采集栈） | `d0834081138f29ab29e43bc4f370e7098aa2f45b` | 同左 |

Control envelope（home / warm 共用，除非另注）：

```text
N_ACTION_STEPS=8  INFERENCE_RATE_HZ=5  MAX_ACTIONS=160 (warm 诊断另用 60)
MAX_JOINT_EXCURSION_RAD=3.0  MAX_TRANSLATION_M=0.015
WORKSPACE_MIN=0.20,-0.40,0.02  BACKEND_DURATION_SEC≥280
```

---

## 2. Offline metrics（≠ 任务成功）

| | 30-ep | 40-tight |
|---|---:|---:|
| gripper open/close acc | 0.953 | 0.964 |
| validation L1 | 0.01136 | 0.01060 |
| validation L1 (norm) | 0.336 | 0.275 |

Offline 上 40 略优；**不作为选型主依据**。

---

## 3. P3 A/B — home vs warmstart

| 协议 | 30-ep descend | 40-ep xyalign-tight |
|---|---|---|
| **home_start** | **`HOME_CLOSE_MISALIGNED`**（grip→0，z_span≈0.27，XY 漂） | `HOME_DESCEND_NO_CLOSE`（grip_min≈0.73，能降 Z，未充分闭合） |
| **pregrasp_warmstart** | `WARM_NO_CLOSE`（60@5Hz PASS；grip≈0.98） | **`WARM_CLOSE_CONTACT`**（grip→0 @step20，object Δ≈1.3 cm；后 velocity E-stop） |

证据目录：

- home 30: `evidence/e3_act_random30_descend_home_n8_ws02_160action_j3_tx015_reportfix_20260719/`
- home 40: `evidence/e3_act_random40_xyalign_tight_home_n8_ws02_160action_j3_tx015_20260719/`
- warm 30: `evidence/e3_act_random30_descend_warm_n8_ws02_160action_j3_tx015_20260719/`
- warm 40: `evidence/e3_act_random40_xyalign_tight_warm_n8_ws02_160action_j3_tx015_20260719/`

---

## 4. 止损结论（强制）

| 规则 | 触发？ | 动作 |
|---|---|---|
| 扩数据后 home 从 CLOSE_* 回退到 NO_CLOSE / DESCEND_NO_CLOSE | **是**（30→40-tight） | **回退最佳 checkpoint = 30-ep**；不推广 40 |
| warm 闭合、home 弱 | 40 满足 | **不为凑 50 条扩数据**；先修 home→pregrasp 接近链 |
| 未达 `HOME_DESCEND_CLOSE` | **是**（两边都未达） | **不扩到 50**；50 是里程碑完整度，不是许可证 |
| 专家 approach_xy 假到达 | 已修（`approach_xy_tolerance=0.025`，seed50/51 `err_xy≈0.003`） | 门质量 OK；合并训练仍未超过 30 home |

**最终止损声明**：

1. **E3 对外 / 下游 handoff 默认 checkpoint = 30-ep descend**（上表 sha256）。
2. **暂停均匀扩采到 50**。
3. 下一 ROI：home 对准（减少 CLOSE_MISALIGNED 漂移）或闭合条件，而非再堆同类 XY-align 量。
4. 不声称：真机部署、Sim2Real、稳定在线自主抓取、offline loss ≡ 任务成功。

---

## 5. What this does / does not prove

**Does prove**

- 500 Hz MuJoCo 渲染采集 → adapt/release → ACT 训练 → Isaac 有界执行链路可复现
- home 下 30-ep 可出现降 Z + 夹爪闭合（对准不足）
- warm 下 40-tight 可出现闭合 + 物体微位移（接近态闭合头可用）
- 阶段专用 `approach_xy_tolerance` 修好了专家假到达

**Does not prove**

- pick/place 任务成功或统计显著成功率
- Sim2Sim 物理公平对比 / 真机 Sim2Real
- 40-ep 因帧数更多而更优（home A/B 否定）

---

## 6. E3 nominal20 diagnostic（gt_v1，已关闭套件）

| 项 | 事实 |
|---|---|
| **权威 suite** | `evidence/e3_nominal20_home_30ep_gt_v1_20260719/` |
| Seeds | `2000..2019`（训练分布 XY）；home envelope；ckpt=30-ep descend |
| 产物 | 20×`report.json`、20×`videos/seed_*.mp4`、`episode_results.jsonl`、`summary.json` |
| GT 一致性 | 预飞 2101/2102 + suite 全量：`min_gripper_state == report state[7] min`；`ft_count>0` |
| Task | **0/20 place success**（`go_no_go=no_go`）；主因 `lift_failed`（夹爪已闭合，物体未抬起） |
| **invalid_v0** | `evidence/e3_nominal20_home_30ep_20260719/` 9 条 raw 保留，`episode_results_invalid_evaluator_v0.jsonl` **不计成功率** |

E3 **套件执行已关闭**（契约产物齐全）。**不**等于任务成功或下游 handoff 推广。

**下一 ROI（2026-07-20）**：E3.5 oracle **已通过**（`e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/`，
lift 5/5）；对准→闭合→抬升阶段数据已补，但下方 §6.1 新 checkpoint 的 **5-seed Isaac smoke
仍 lift 0/5**。禁止同类下降扩采与完整 E4；下一归因继续聚焦 home→对准→闭合的观测/阶段建模。

### 6.1 Closelift 增补模型（诊断用，非 E3 权威替换）

| 字段 | 事实 |
|---|---|
| **Episode 计数（权威）** | **40**（30 descend + 10 closelift seeds 52/53） |
| Directory / release_id 命名 | `..._random35_closelift_...`（**命名偏旧**；勿按 35 解读） |
| release | `data/releases/e2_500hz_random35_closelift_20260720/`（`manifest.num_episodes=40`，`num_frames=9779`） |
| model_id / checkpoint | `data/e2_500hz_act_random35_closelift_5epoch_20260720/checkpoint.pt` |
| sha256 | `bc4a8fc49d24e9c22e8337ae9376fe189344235405d91e1034bcb7fe332785c3` |
| 采集口径 | `validation_mode=lift`；短 descend；加长 close/lift；`approach_xy_tol=0.025`；`use_ready_pose=false` |
| 训练 | 5 epoch；stage-balanced（closing 权重 4.0）；offline L1≠任务成功 |
| 5-seed smoke | `evidence/e3p6_closelift40_5seed_home_20260720/` → **lift 0/5**，`gate_pass_ge1=false` |
| 行为标签 | 5/5 `HOME_NO_CLOSE`（grip_min=1.0，z_span≈0.014 m，object≈不动） |
| GT failure | `failure_stage=reach` / `gripper never closed below 0.120` |

**Provenance 规则**：对外与模型卡一律写 **40 episodes**；目录名 `random35` 仅作历史路径别名，不改 checkpoint 路径以免破坏引用。

**止损**：5-seed 未出现真实 lift → **不开完整 E4**；下一 ROI 仍在 home→对准→闭合策略/数据，而非扩 suite。

---

## 7. 推荐引用路径

```text
checkpoint:
  /home/ina/robot-sim-lab/robot-arm-episode-data-lab/data/e2_500hz_act_random30_descend_conservative_5epoch_20260719/checkpoint.pt
release:
  /home/ina/robot-sim-lab/robot-arm-episode-data-lab/data/releases/e2_500hz_random30_descend_20260719
sha256:
  948e2949ae8af099f8347837969f596018bbf68a18cc703b6bc09abd01a92501
```
