# SmolVLA S4 lift 0/5 离线归因报告

**日期**：2026-07-24（含同日遥测复跑修订）
**证据根**：
- 首轮：`evidence/smolvla_s4_bounded5_20260724T203700Z/`（无相机帧）
- 遥测复跑：`evidence/smolvla_s4_bounded5_telemetry_20260724T144549Z/`（同 seeds 1–5；`RECORD_SCENE_VIDEO=true` + policy-input JPEG + `observations.jsonl`）
**方法**：首轮只读 trial 产物 + open-loop `frame_logs`；复跑补齐视觉/state 遥测后修订 H1/H3。
**口径**：失败归因；S4 仍为 **Hold**（lift 0/5）；不授权扩种子 / 重训 / 真机。

---

## 1. 一句话结论

**策略在线是「视觉失明 + 习惯走廊」：Isaac 喂给策略的 scene 相机帧几乎全黑（像素均值 ≈ 0.3/255），而同 harness 家族的 E3.5 oracle 视频均值 ≈ 114、MuJoCo 训练帧均值 ≈ 50。** 在无有效视觉条件下，策略走完 150 步相位化走廊（z 最低 0.20 m、半闭爪、方块位移数值零）。`observation.state[15]` 与训练约定一致（H3 排除）。主因曾升级为 **H1′：Isaac 离线场景缺光 / 相机无效**；修光后 Isaac 仍 Hold，且 MuJoCo 训练域对照（§6.1）同样几乎不闭爪 → **当前归因倾向 H2（闭环 BC）**，而非主要 Isaac 外观域差。

## 2. 遥测复跑事实（2026-07-24 批准，不扩种子）

| 项 | 结果 |
|---|---|
| Evidence | `evidence/smolvla_s4_bounded5_telemetry_20260724T144549Z/` |
| Gate | interface 5/5；reach 3/5；grasp 1/5；lift **0/5**；`gate_pass=false`（与首轮同型） |
| 相机帧 | 每 seed **150/150** JPEG（`trials/seed_*/telemetry/camera/action_XXXX.jpg`） |
| state15 | 每 action 写入 `report.json` + `telemetry/observations.jsonl`（750 行合计） |
| 场景视频 | `videos/seed_*.mp4` 有文件但 recorder flush 失败（`scene.note.txt`）；**以 JPEG 为准** |

视觉对照（policy-input / 同分辨率 240×320）：

| 源 | 像素均值 | 说明 |
|---|---|---|
| MuJoCo 训练（adapted episode frame） | **≈ 50** | 可见红块/臂/桌面 |
| Isaac E3.5 oracle `trial_0.mp4` | **≈ 114** | 同家族 harness，有光照 |
| Isaac S4 遥测 policy 输入（5 seed × 多帧） | **≈ 0.3** | 近黑；仅见底座微弱蓝光 |

作品集对照图：
- `docs/portfolio/smolvla_s4_mujoco_train_scene_ref.jpg`
- `docs/portfolio/smolvla_s4_isaac_oracle_scene_ref.jpg`
- `docs/portfolio/smolvla_s4_isaac_online_scene_seed1_a075.jpg`（近黑）

## 3. 首轮行为证据（仍成立）

### 3.1 关键量对照（首轮；复跑 funnel 同型）

| seed | 方块 (x, y) | EE z min | grip min | peak force (N) | reach | grasp | lift delta (m) |
|---|---|---|---|---|---|---|---|
| 1 | (0.371, +0.104) | 0.226 | 0.235 | 0.81 | ✓ | – | ~0 |
| 2 | (0.436, +0.134) | 0.208 | 0.229 | 0.80 | – | – | ~0 |
| 3 | (0.379, +0.013) | 0.203 | 0.207 | 0.55 | ✓ | ✓ | ~0 |
| 4 | (0.379, −0.119) | 0.229 | 0.224 | 0.76 | – | – | ~0 |
| 5 | (0.410, +0.073) | 0.235 | 0.277 | 0.80 | ✓ | – | ~0 |

方块从未被移动（lift delta 数值零）。`clipped=False` 150/150；限幅/E-stop/碰撞均非原因。

### 3.2 open-loop vs online

| 量 | 专家 | open-loop 预测 | online 自主 |
|---|---|---|---|
| EE z 最低 | 0.040 | ≤0.022（多数 ep） | **0.20–0.24** |
| 夹爪最低 | 0.000 | 0.000 | **0.21–0.28** |

同 checkpoint 在教师强迫观测下能下降/全闭；在线（黑图）不能。

### 3.3 reach/grasp 去魅

仍为走廊几何重叠 + `GRIPPER_CLOSE_MAX=0.70` 口径放大，**不是**视觉伺服部分成功。详见首轮分析；遥测未改变该解释。

## 4. H3 检验结果（已排除）

对比 prospective release parquet `observation.state[15]`（N=2593）与遥测 online state15（N=750）：

| 检查 | 结果 |
|---|---|
| 布局 | joint7 + ee7 + grip1，两端一致 |
| home 关节 L2（train0 vs online0） | **0.006** |
| home 四元数 L2 | **6.8e-6** |
| 夹爪量纲 | 训练 [0.034, 1.0]；在线 [0.16, 1.0]（同 [0,1]） |
| 在线 z 最低 | 0.194（仍远高于训练 0.040）——行为差，非 state 编码差 |

**结论：H3 不成立。** 失败不是 joint 顺序 / ee 系 / 夹爪归一搞错。

## 5. 假设矩阵（遥测后修订）

| # | 假设 | 状态 | 证据 |
|---|---|---|---|
| **H1′** | Isaac 离线场景 **缺有效光照 / 相机对策略近黑**，视觉输入无效 → 习惯走廊 | **首轮主因（已证实）**；**灯光修复冒烟已 Pass** | 修光前 JPEG mean≈0.3；修光后 smoke1 mean≈233 且红块可见（`smolvla_s4_lightfix_smoke1_20260724T150519Z`） |
| H1 | 泛泛 MuJoCo→Isaac 外观域差 | 降级为次级 | 在相机近黑时无法讨论「纹理域差」；需先修光 |
| H2 | 闭环 compounding / 训练域闭环 BC | **主因倾向（早期证据）** | MuJoCo 训练域 JPEG≈50 仍几乎不闭爪（§6.1）；非主要 Isaac 外观域差 |
| H3 | state[15] 约定差 | **已排除** | §4 |
| H4 | GT 阈值 artifact | 已解释 funnel，非 lift 根因 | close_max=0.70 / reach 几何 |
| H5 | 物理/执行链故障 | 已排除 | oracle 5/5；interface 5/5 |

## 6. 修光后有界 5-seed 复测（2026-07-24 批准）

**证据**：`evidence/smolvla_s4_bounded5_relight_20260724T151711Z/`（dome=450 / distant=900；遥测开）

| 项 | 黑光基线（`…telemetry_20260724T144549Z`） | 修光复测 |
|---|---|---|
| JPEG 均值 | ≈0.3 | ≈**154**（5 seed 稳定） |
| interface | 5/5 | **5/5** |
| reach / grasp / lift | 3/5 · 1/5 · **0/5** | **1/5 · 0/5 · 0/5** |
| `gate_pass` | false | **false（Hold）** |
| 典型 failure_reason | `lift_failed delta≈0`（半闭被 0.70 口径算 closed） | **`gripper never closed below 0.700`**（5/5 均未真正闭合） |
| 动作形态 | z 最低 ≈0.20–0.24；grip 最低 ≈0.21–0.28 | z 多停在 ≈0.42–0.53（seed4 最低 0.232）；**grip 最低 ≈0.85–0.93** |

**解读（诚实）**：

1. 修光成功——视觉输入已可用；黑光下的「习惯走廊半闭」不再出现。
2. 有视觉后策略**几乎不开爪闭合、多数 seed 不下降到抓取高度** → funnel 数字比黑光基线更差，但这是**更真实**的失败（不再被 close_max=0.70 放大 grasp）。
3. 黑光基线的 reach 3/5、grasp 1/5 **不能**当作「修光前部分成功」；修光后证明那些是失明+阈值假象。
4. **仍不得**声称任务成功 / 扩种子 / 重训。

## 6.1 MuJoCo 训练域闭环对照（H2，2026-07-24/25；人工提前停止）

**目的**：修光后 Isaac Hold 的 failure 是「Isaac 域差」还是「闭环 BC 本身」？在训练域 MuJoCo 上复用同一 Recovery-v3 LoRA、seeds 计划 1–5、同一 ContinuousTaskEvaluator（`gripper_close_max=0.70`）。

**证据**：`evidence/smolvla_s4_mujoco_bounded5_20260724T155513Z/`（`s4_gate.json`：`early_stopped=true`，`seeds_completed=1`）

| 项 | Isaac relight（权威 S4，5/5） | MuJoCo H2（提前停止） |
|---|---|---|
| JPEG 均值（policy 输入） | ≈154 | ≈**50**（对齐训练域） |
| GT 完整种子 | 5 | **1**（seed1）；seed2 仅有部分 report/遥测，无 GT 行 |
| reach / grasp / lift | 1/5 · 0/5 · **0/5** | seed1：**0 / 0 / 0** |
| 典型 failure_reason | `gripper never closed below 0.700` | 同左（seed1） |
| grip_min（cmd） | ≈0.85–0.93 | seed1 **≈0.976**；seed2 部分 **≈0.973** |
| EE z_min（cmd） | ≈0.23–0.53 | ≈**0.47–0.50**（近 home，几乎不下探） |
| interface PASS | 5/5 | 0（墙钟内未跑满 150 actions；chunk 重规划 7–13 s） |

**解读（诚实）**：

1. 训练域视觉已可用（JPEG≈50），策略仍几乎全开爪、不下探 → **不能**把修光后 Isaac Hold 主要归因于 MuJoCo→Isaac 外观域差。
2. 归因倾向 **H2：闭环 BC / covariate shift（开环教师强迫观测 Pass ≠ 在线闭环会闭爪）**。
3. Suite **人工提前停止**（未跑完 seeds 3–5）；seed2 无完整 GT。结论是有方向的诊断，**不是**完整 5-seed gate，**不等于**任务成功或可扩种子。
4. MuJoCo EGL 与 SmolVLA 共抢本机 GPU，每 chunk 推理常 **7–13 s**，故有界跑法墙钟极长——这是提前停止的工程原因，不是策略变好的证据。

入口：上游 `scripts/run_mujoco_smolvla_s4.sh`；中游 `scripts/run_smolvla_s4_mujoco_bounded.sh`。

## 7. 下一步（均需另批）

1. 接受修光后 Isaac Hold 为当前 **Isaac S4** 权威；MuJoCo H2 早期对照支持「失败在闭环策略侧」。
2. 冻结候选，不再投入；**禁止**为凑满 5 seeds 自动重跑 / 扩种子 / 重训。
3. 作品集写清：黑光假 funnel → 修光后真实 Hold → 训练域 MuJoCo 同样不闭爪（H2）。

**禁止项不变**：不自动扩种子、不第三次 data-fix、不重训、不真机、不把 reach/grasp 写成部分成功。

## 8. 证据清单

**首轮行为（黑光）**
- `evidence/smolvla_s4_bounded5_20260724T203700Z/`

**遥测（黑光，H1′/H3）**
- `evidence/smolvla_s4_bounded5_telemetry_20260724T144549Z/`

**修光冒烟**
- `evidence/smolvla_s4_lightfix_smoke1_natural_20260724T150939Z/`（自然光单 seed）

**修光后有界 5-seed（当前权威 Isaac S4）**
- `evidence/smolvla_s4_bounded5_relight_20260724T151711Z/s4_gate.json`
- `.../trials/seed_*/telemetry/camera/` + `observations.jsonl`

**MuJoCo H2 训练域对照（提前停止）**
- `evidence/smolvla_s4_mujoco_bounded5_20260724T155513Z/s4_gate.json`（`early_stopped=true`，`seeds_completed=1`）
- seed1 GT + telemetry；seed2 部分 telemetry（无 GT）

**对照图**
- `docs/portfolio/smolvla_s4_isaac_online_scene_seed1_a075.jpg`（黑）
- `docs/portfolio/smolvla_s4_isaac_online_scene_seed1_a075_natural_light.jpg` / `smolvla_s4_relight5_seed1_a075.jpg`（修光后）
- MuJoCo / oracle 参考帧见同目录

**代码**
- 上游 `offline_assets.add_offline_scene_lights`（Dome 450 + Distant 900）
- 上游 `smolvla_policy_inference_node`（`telemetry_dir`）
- 上游 `isaac_panda_backend`（FixedCuboid + 显式灯光）
- 上游 `scripts/run_mujoco_smolvla_s4.sh`；中游 `scripts/run_smolvla_s4_mujoco_bounded.sh`
