# E3.5 Isaac Scripted Oracle 实验日志（面试取材）

**日期**：2026-07-20<br>
**仓库**：上游实现 / 中游证据与 SOP / 下游面试 FAQ 交叉引用<br>
**协议 ID**：`scripted_oracle_lift`<br>
**权威通过证据**：
[`evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/`](../evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/)<br>
**失败对照证据（保留）**：
[`evidence/e3p5_isaac_scripted_oracle_5x_lift_20260720/`](../evidence/e3p5_isaac_scripted_oracle_5x_lift_20260720/)

> 本文记录 **完整实验过程**（动机 → 设计 → v1 失败 → 归因 → 修复 → v2b 通过 → 下一步），
> 供作品集与面试口述。口径必须区分：**oracle 通过 = Isaac 抓取物理链可用**，
> **≠ learned-policy 成功，≠ Sim2Real，≠ 真机部署**。

---

## 1. 一句话结论（面试开场 15s）

E3 上 ACT 在 Isaac nominal 20 seeds 全失败且无有效 lift 后，我没有继续堆同类数据或直接开 E4，
而是先做 **scripted oracle（专家轨迹）5 次 lift 回归**：先证明仿真物理能不能抓起来。
v1 专家也抬不起；修好 pick 高度、夹爪 PD、物块摩擦和 GT 闭合阈值后，**v2b 达到 lift 5/5**。
因此后续问题应集中在模型的 home→对准→闭合策略，而不是盲目扩采。

---

## 2. 实验前置事实（已关闭套件，勿重跑冒充新结果）

| 项 | 事实 | 证据 |
|---|---|---|
| E2 被测基线 | 30-ep descend ACT checkpoint 可复现 | [`E2_E3_MODEL_CARD.md`](E2_E3_MODEL_CARD.md) |
| E3 nominal20 | **0/20** place；reach 10/20、grasp 0/20、lift 0/20 | [`evidence/e3_nominal20_home_30ep_gt_v1_20260719/summary.json`](../evidence/e3_nominal20_home_30ep_gt_v1_20260719/summary.json) |
| 止损 | 暂停均匀扩采到 50；不把 offline loss 当任务成功 | model card §4 |
| E4 | 四 suite × 20 seeds 文档规划；本机未执行完整 100+ | alignment §E4 |

**决策原则（评测工程）**：在「模型失败」与「仿真抬不起」未分离前，继续采同类下降轨迹或开
泛化矩阵，只会浪费算力并混淆归因。

---

## 3. 实验设计：为什么是 Scripted Oracle

### 3.1 假设二分

```text
H_physics：Isaac 红方块场景下，专家轨迹也无法稳定 lift
           → 先修 TCP / 夹爪 / 摩擦 / 接触 / 初态
H_policy ：专家能稳定 lift，ACT 仍失败
           → 问题在模型 home→对准→闭合；只补对准-闭合-抬升数据
```

### 3.2 协议（固定变量）

| 维度 | 选择 | 理由 |
|---|---|---|
| 控制源 | scripted FSM，**不**跑 ACT | 单变量：只测物理链 |
| 物体 | 名义红方块 `(0.35,-0.07,0.025)`，无 seed 随机 | 重复性，对齐 E1 风格 |
| 动作面 | `/teleop/cmd_pose` + gripper + heartbeat → Servo → Isaac position drive | 与 warmstart / ACT 执行面一致 |
| 成功判定 | Continuous GT `validation_mode=lift`，`lift_success_delta=0.03` | 与 E3 同一 evaluator 家族 |
| 通过线 | ≥4/5 lift | 物理门禁，非统计显著泛化 |
| 重复次数 | 5 | 对齐 E1 5-repeat 习惯；本机可承受 |

### 3.3 FSM 阶段

`approach_xy → hover → descend → close → grasp_pause → lift → hold`

实现：

- 规划纯函数：[`scripted_oracle.py`](https://github.com/inayina/ros2-arm-teleoperation-suite/blob/main/src/isaac_sim_adapter/isaac_sim_adapter/scripted_oracle.py)
- ROS 节点：[`isaac_scripted_oracle.py`](https://github.com/inayina/ros2-arm-teleoperation-suite/blob/main/scripts/isaac_scripted_oracle.py)
- 套件入口：[`run_isaac_scripted_oracle.sh`](https://github.com/inayina/ros2-arm-teleoperation-suite/blob/main/scripts/run_isaac_scripted_oracle.sh)

---

## 4. 实验时间线（可按 STAR 口述）

### 4.1 Situation — E3 全灭

ACT 在 Isaac home nominal 20 seeds：接口可跑通，但 **无有效 lift**。若直接宣称「模型差」或
「再采 50 条」，无法排除「PhysX 夹爪根本抓不起」。

### 4.2 Task — 加 E3.5 物理门禁

在 E3 与 E4 之间插入 **scripted oracle 5× lift**，用同一 GT 契约产出
`episode_results.jsonl` / `summary.json` / `oracle_gate.json`。

### 4.3 Action — 两轮回归

#### Round A（v1，2026-07-20 上午）— 门禁未过

| 指标 | 结果 |
|---|---|
| Oracle 阶段指令完成 | 5/5 PASS |
| GT reach / grasp | 5/5 |
| GT lift | **0/5** |
| `gate_pass` | false → `physics_or_tcp_gripper_contact_triage` |
| 典型现象 | EE 在 z≈0.065 闭合；物块 z 不变（Δ≈0）；peak_force ~0.8–1.2 N |

证据目录：`evidence/e3p5_isaac_scripted_oracle_5x_lift_20260720/`

**归因（有日志支撑）**：

1. **Pick 偏高**：`pick_z_offset=0.04` → 目标 z≈0.065，5 cm 方块顶面约 z=0.05，夹爪在顶面上方空合。
2. **夹爪硬设**：`ParallelGripper.set_joint_positions` 瞬移关节，接触冲量大，后续试低 pick 时会打飞方块。
3. **摩擦默认过滑**：Isaac `DynamicCuboid` 未设接近 MuJoCo 的高摩擦材料。
4. **GT 闭合阈值不匹配侧夹**（在软闭尝试中暴露）：5 cm 方块侧夹时
   `min_gripper_state≈0.62`，默认 `gripper_close_max=0.12` 会报
   `gripper never closed`，把「握着方块」判成未闭合。

对照 MuJoCo 已验证抓取高度：M7 / batch box 稳定在 `pick_height_offset≈0.012–0.015`
（见上游 [`docs/M7_GRASP_DEBUGGING.md`](https://github.com/inayina/ros2-arm-teleoperation-suite/blob/main/docs/M7_GRASP_DEBUGGING.md)）。

#### Round B（v2 → v2b）— 修复后重跑

| 修复项 | 变更 | 代码位置 |
|---|---|---|
| Pick 高度 | `DEFAULT_PICK_Z_OFFSET=0.010` | `scripted_oracle.py` |
| 夹爪驱动 | 硬设 → **PD `apply_action`**；闭合时每步保持 | `isaac_panda_backend.py` |
| 闭合目标 | `gripper_close_target=0.40`（轻挤压，非瞬移到 0） | oracle 默认 / runner |
| 物块摩擦 | static 2.0 / dynamic 1.5 / restitution 0.0 | `isaac_panda_backend.py` |
| 闭合前 Z trim | descend 后若 z 误差大则再 trim | `isaac_scripted_oracle.py` |
| GT 闭合阈值 | oracle 套件 `--gripper-close-max 0.70` | `isaac_continuous_gt_recorder.py` + runner |
| 阶段 | 增加 `grasp_pause` | FSM |

单次 smoke：物块 z `0.025 → ~0.11`，reach/grasp/lift 全 True。
随后 **正式 5×（v2b）**。

### 4.4 Result — 门禁通过

权威套件：`evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/`

| 指标 | v1 | v2b |
|---|---:|---:|
| reach | 5/5 | **5/5** |
| grasp | 5/5 | **5/5** |
| lift | 0/5 | **5/5** |
| outcome.success（lift 模式） | 0/5 | **5/5** |
| `gate_pass`（阈值 ≥4/5） | false | **true** |
| `interpretation` | physics triage | **physics_chain_ok_focus_on_policy** |

机器可读：

- [`oracle_gate.json`](../evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/oracle_gate.json)
- [`summary.json`](../evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/summary.json)
- [`episode_results.jsonl`](../evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/episode_results.jsonl)

面试可视化（成功 lift 画面，2026-07-20 补录；GT 仍 5/5）：

- 套件：[`evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_video_20260720/`](../evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_video_20260720/)
- 5 段场景 MP4：[`videos/trial_0.mp4`](../evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_video_20260720/videos/trial_0.mp4) … `trial_4.mp4`（约 25–29 s / 10 Hz）
- 作品集单条样例：[`docs/portfolio/media/e3p5_isaac_scripted_oracle_lift_success_trial0.mp4`](portfolio/media/e3p5_isaac_scripted_oracle_lift_success_trial0.mp4)
- 对照（ACT closelift-40 近静止失败）：[`evidence/e3p6_closelift40_5seed_home_20260720/videos/`](../evidence/e3p6_closelift40_5seed_home_20260720/videos/)

复现命令：

```bash
cd /home/ina/dev/ros2-arm-teleoperation-suite
bash scripts/run_isaac_scripted_oracle.sh \
  /home/ina/robot-sim-lab/robot-arm-episode-data-lab/evidence/e3p5_isaac_scripted_oracle_5x_lift_<NEW_TAG>
```

默认参数：`PICK_Z_OFFSET=0.010`、`GRIPPER_CLOSE_TARGET=0.40`、`GRIPPER_CLOSE_MAX=0.70`、
`TRIALS=5`、名义位姿、`validation_mode=lift`。

---

## 5. 关键工程教训（面试高频追问）

### 5.1 为什么 interface PASS ≠ task PASS？

E3 / oracle 都走同一执行栈。ACT 可完成有界步数与 safety OK，但物块高度不变。
必须用 **runtime GT**（`panda_continuous_gt_v*`）判 lift，不能用 `report.json.status=PASS`。

### 5.2 为什么专家指令完成也不等于物理成功？

v1 中 oracle FSM 报告 `all_phases_completed=true`，但 object z 未升。
**阶段完成**只说明命令发完；**lift** 必须看 privileged object pose。

### 5.3 为什么不能对 5 cm 方块用 `gripper_close_max=0.12`？

归一化夹爪：开度 `finger_pos/0.04`。方块宽 0.05 m → 侧夹稳态约 **0.625**。
阈值 0.12 只适合「几乎闭死」；侧夹会假失败。Oracle 套件显式提高到 0.70，并写进 runner，
避免与 ACT 诊断默认口径 silently 混用。

### 5.4 为什么夹爪要用 `apply_action` 而不是 `set_joint_positions`？

Isaac `set_joint_positions` 是关节瞬移；`apply_action` 走 articulation PD，接触时可产生
夹持力而不必穿透物体。v2 早期硬闭 + 低 pick 曾把方块打飞到桌面外（object_drift_xy>0.08）。

### 5.5 TCP / EE 帧

Isaac helper 暴露 `panda_hand`；发布契约 `panda_ee` 时使用本地 `+Z 0.10 m`
（与 URDF / MuJoCo site 对齐）。Pick 高度必须相对 **panda_ee** 与物块中心定义，
不能照搬「看起来差不多」的经验值。

---

## 6. 能证明 / 不能证明

**能证明（已实现 + 运行证据）**

- Isaac 名义红方块场景下，专家轨迹可稳定 lift（5/5）。
- 有可播放的成功 lift 视频（`…_v2b_video_…/videos/` + portfolio media 样例）。
- E3 ACT 失败不能再默认归因于「Isaac 根本抓不起」。
- 评测漏斗中插入 oracle 门禁可缩短归因路径。

**不能证明**

- ACT / 任意 checkpoint 的任务成功率。
- MuJoCo↔Isaac 接触参数已标定等价（摩擦是工程可用，非真机材料标定）。
- Sim2Real 或真机部署。
- 完整 E4 泛化矩阵。

---

## 7. 下一步（当前接力点）

E3.5 之后已经完成定向 close→lift 数据、40-episode release、5-epoch ACT 和 5-seed Isaac smoke。
结果仍为 reach/grasp/lift=`0/0/0`，5/5 `HOME_NO_CLOSE`，详见
[`smoke5_gate.json`](../evidence/e3p6_closelift40_5seed_home_20260720/smoke5_gate.json)。

1. **不开完整 E4**，也不继续普通下降或同类 close→lift 扩采；
2. 下一归因聚焦 home→对准→闭合的观测/阶段建模；
3. 暂不优先加 `observation.ft`（当前失败发生在接触前，夹爪始终为 1.0）；
4. 若再产生候选模型，仍先过小规模真实 lift gate，再决定是否扩大 suite。

接力文档：[`E2_SINGLE_RED_DATA_EXPANSION_RUNBOOK.md`](E2_SINGLE_RED_DATA_EXPANSION_RUNBOOK.md) §1、
[`EMBODIED_POLICY_EVALUATION_SOP.md`](EMBODIED_POLICY_EVALUATION_SOP.md) §4.2 P0.5。

---

## 8. 面试 60–90 秒口述稿（可直接背）

> “E3 里 ACT 在 Isaac 上 20 个 seed 全部失败、没有有效 lift。我没有继续堆同类数据，
> 也没有直接开 E4 泛化矩阵，而是加了一层 E3.5：用固定专家抓取轨迹在名义红方块上连跑 5 次，
> 用同一套 continuous GT 看能不能 lift。第一轮专家指令都跑完了，但物块高度不变——说明是
> pick 偏高、夹爪硬设和摩擦/GT 闭合阈值问题。修好 pick、改成 PD 夹爪、补摩擦并调整
> 方块侧夹的 closed 阈值后，第二轮 lift 5/5，画面上也能看到方块被抬起。这样我就把问题从
> ‘仿真坏了’收敛到‘模型 home 到对准闭合策略’。后续 close→lift 40 集训出的 ACT 在 5-seed
> 上仍近静止、夹爪不开，说明 offline loss 不等于任务成功；下一步聚焦对准-闭合，而不是盲目扩采。”

---

## 9. 产物清单

| 路径 | 内容 |
|---|---|
| 上游 `scripts/isaac_scripted_oracle.py` | 专家轨迹 ROS 节点 |
| 上游 `isaac_sim_adapter/.../scripted_oracle.py` | 可单测的 waypoint 规划 |
| 上游 `scripts/run_isaac_scripted_oracle.sh` | 5-trial 编排 + GT + gate |
| 上游 `tests/test_scripted_oracle.py` | 无 Isaac 单测（11 passed） |
| 中游 `evidence/..._v2b_.../` | 通过套件（JSON） |
| 中游 `evidence/..._v2b_video_.../` | 通过套件 + 成功 lift 视频 |
| 中游 `docs/portfolio/media/e3p5_..._trial0.mp4` | 面试可直接打开的样例 clip |
| 中游 `evidence/..._20260720/`（无 v2） | v1 失败对照 |
| 下游 `docs/portfolio/INTERVIEW_PREP.md` | FAQ 固化（E3.5） |
