# SmolVLA S3 第二轮 Grip-Timing 采集方案（Round-2 Plan）

**状态**：Round-2 正式采集、独立 v2 release、真实 GPU preflight、一次 1000-step AutoDL LoRA 与 v2 canonical open-loop 均已完成；最终 **Hold / 默认停止**  
**日期**：2026-07-23  
**范围**：仅数据方案（upstream 采集 → midstream 新 release 准备）。**不**训练、**不** LoRA、**不** Isaac、**不** AutoDL 开训。  
**权威 Hold 证据**：`runs/smolvla_s3/openloop_full_stride1_20260723T055500Z/`（stride=1 全帧）

---

## 0. 直接结论

v1 griptiming + α64 已把 EE 推到 Pass 带、grip balanced ≈0.713（Pass 带），但仍 **Hold**：`timing / smooth / sat` 未过。Timing 审计已排除 select_action chunk[0]、50-step 标签窗、obs↔action[7] 行错位；根因类别是 **模型相对 expert `action[7]` 过早闭合**（signed close offset ≈ **−65 帧 / −6.5 s**）。

第二轮应优先通过 **下降全程开爪 + 降低真实位姿步长上限 + 到位后单次闭合** 改写标签分布，而不是改 LoRA 超参或进 Isaac。Round-1 已有约 4.7 s 的稳定 pick-open 段；直接把静止 hold 拉到 7 s 会增加 `n_obs_steps=1` 下“近同观测、不同未来 action chunk”的歧义，因此不作为首选变量。
`max_data_fix_retries: 1` **已用尽**（v0→v1）；本轮是 **超额二次 data-fix**，必须单独人工批准采集，且采集完成 ≠ 自动批准重训。

---

## 1. Hold 失败 → 示范必须改什么

| Pass 失败项 | 当前证据（LoRA, full stride=1） | 示范侧应对（非超参） |
|---|---|---|
| **timing** | `close_offset_signed = −65` 帧（≈−6.5 s）；pred 在高位下降段早于 expert 闭合 | 以几何而非绝对帧号验收：下降段保持开爪，首次闭合须在 `xy_error≤0.02 m` 且 `eef_z-object_z≤0.03 m` |
| **smooth** | `action_smoothness_ee_step_l2_p90 ≈ 0.103`（门限 0.05；expert ≈0.008） | `_stream_pose_toward` 的 `duration` 主要是 deadline；首选把 `pose_step_m` 从 0.003 降至 0.001，实测验证后再决定是否动 acceleration |
| **sat** | `raw_gripper_oob_ratio ≈ 0.205`（门限 0.10）；pred 多帧出 [0,1] | 标签须全程有界且仅有一次单调 open→close；保留 3 s 平滑 ramp，禁止抖动/回开（标签有界本身不保证模型 raw OOB 改善） |

**不改**：schema、`absolute_eef_gripper_v0`、fps=10、scene 320×240、500 Hz sim、`grasp_assist_enabled=false`、`validation_mode=lift`、chunk_size=50。

---

## 2. Round-1 配方复原（证据）

### 2.1 产物

| 项 | 值 | 证据类型 |
|---|---|---|
| Upstream trees | `.../data/e2_red_500hz_seed54_griptiming10_20260722` + `seed55_...` | 已实现（目录 + release SOURCES） |
| Midstream release | `data/releases/smolvla_s3_abs_eef_rgb_v1_griptiming`（20 eps / 6445 frames） | 已实现 |
| Seeds | 54 / 55；`config/randomization.yaml` 注释写明 griptiming | 已实现 |
| Gate | `upstream_gate=batch_generator`；`success=true`；lift 验收 | 已实现（meta + logs） |
| Accept rate | seed54：**10/10 after 10 attempts** | 已实现（collect.log） |
| Pre-close hold | 日志 `Pre-close open hold (3.00s)`（脚本默认 0.5，Round-1 **显式改为 3.0**） | 已实现（batch log） |
| Open@pick | 约 **49 帧 ≈ 4.9 s** 开爪停在 pick（含 trim） | 已实现（parquet 审计） |
| first_close | seed54 均值 **158.6**；seed55 **160.3**（10 Hz） | 已实现 |
| Camera | scene 240×320 @ 10 Hz；真实 MuJoCo renderer | 已实现 |
| Action | LeRobot v2.1 `action[8]` abs-EEF+gripper；`action_type=ee_pose_gripper` | 已实现 |
| grasp_assist | `false`（训练硬约束；日志 `grasp_assist_attached=False`） | 已实现 |
| 适配路径 | **不经** ACT `adapt_upstream_panda_dataset`；直接 `prepare_smolvla_s3_release.py` 钉元数据 | 已实现 |

### 2.2 Round-1 等价采集命令（复原；勿再跑到同名目录）

入口：上游 `scripts/run_batch_preflight_smoke.sh`。关键环境（与日志一致处加粗）：

```bash
# 已实现复原要点（Round-1）。新一轮请用 §4 新目录/新 seed。
export BATCH_PREFLIGHT_OBJECTS=object_red_box
export BATCH_PREFLIGHT_EPISODES=10
export BATCH_PREFLIGHT_MAX_ATTEMPTS=3
export BATCH_PREFLIGHT_RANDOMIZE=true
export BATCH_PREFLIGHT_HEADLESS=true
export BATCH_PREFLIGHT_CAPTURE_MODE=portfolio
export BATCH_PREFLIGHT_SCENE_USE_MUJOCO_RENDERER=true
export BATCH_PREFLIGHT_GRASP_ASSIST=false
export BATCH_PREFLIGHT_ENABLE_GRASP_MONITOR=false   # 与 E2 训练采一致；Round-1 脚本默认 true，建议 Round-2 固定 false
export BATCH_PREFLIGHT_VALIDATION_MODE=lift
export BATCH_PREFLIGHT_PRE_CLOSE_HOLD=3.0           # Round-1 实测
export BATCH_PREFLIGHT_CLOSE_DURATION=3.0           # 推断：默认值；close→lift 间隔与 grasp_pause 一致
export BATCH_PREFLIGHT_GRASP_PAUSE=3.0              # 推断：默认值
export BATCH_PREFLIGHT_HOVER_HEIGHT=0.08             # 日志 hover_z-object_z≈0.08
export BATCH_PREFLIGHT_CAMERA_WIDTH=320
export BATCH_PREFLIGHT_CAMERA_HEIGHT=240
export BATCH_PREFLIGHT_CAMERA_RATE=10.0
# hover/descend/lift/post_lift：未在日志字面钉死 → 沿用脚本默认
# HOVER=4 DESCEND=4 LIFT=10 POST_LIFT=8 APPROACH_XY=0（→ fallback hover_duration）
```

`randomization.yaml`：`seed: 54` 然后 `55`；红块 `x=[0.35,0.43]` `y=[-0.14,0.14]` yaw `±15°`。

Release（已执行，勿重跑覆盖）：

```bash
cd /home/ina/robot-sim-lab/robot-arm-episode-data-lab
python3 training/scripts/prepare_smolvla_s3_release.py \
  --release-id smolvla_s3_abs_eef_rgb_v1_griptiming \
  --output-dir data/releases/smolvla_s3_abs_eef_rgb_v1_griptiming \
  --source /home/ina/dev/ros2-arm-teleoperation-suite/data/e2_red_500hz_seed54_griptiming10_20260722 \
  --source /home/ina/dev/ros2-arm-teleoperation-suite/data/e2_red_500hz_seed55_griptiming10_20260722
```

---

## 3. Round-2 数据集目标与成功标准

### 3.1 目标（数据集层，不是任务成功）

构造 **late-close / long-open-at-pick** 的 abs-EEF+RGB 示范，使下一轮（若批准）LoRA 更难把「接近/下降」误学成闭合。

### 3.2 建议规模

| 项 | 建议 |
|---|---|
| Accepted episodes | **20**（seed **56**×10 + seed **57**×10），与 v1 同规模便于对照 |
| 新 upstream 目录 | `e2_red_500hz_seed56_griptiming_lateclose10_YYYYMMDD` + `seed57_...` |
| 新 release（仅提案） | `smolvla_s3_abs_eef_rgb_v2_griptiming_lateclose` |
| 与 v1 关系 | **禁止覆盖** v0/v1；v2 为独立 immutable；是否 `v1∪v2` 合并留给重训决议 |

### 3.3 采集验收（通过才算「可备 release」）

每条 accepted episode：

1. `success=true`，`upstream_gate=batch_generator`，`safety_estop=false`，`drive_fault=false`
2. `grasp_assist_enabled:=false`；日志无 synthetic fallback
3. scene mp4 320×240 @ 10 Hz，`ffprobe` 可读
4. **QA（Round-2 专用）**（采集后由 `audit_smolvla_griptiming_dataset.py` 只读自检）：
   - 下降接近区（`0.03<eef_z-object_z≤0.22 m`）开爪帧 **≥30**（Round-1 全量最大值 27；验证 smoke=33）
   - pick 几何区稳定开爪 **≥4.5 s**
   - 首次闭合位于 `xy_error≤0.02 m`、`eef_z-object_z≤0.03 m`
   - debounced 闭合边沿 **≤1**、回开边沿 **0**
   - `action[7]` ∈ [0,1]，单调 open→close；中间 ramp 占比仅报告、不设硬上限（平滑闭合不是 saturation）
   - 单 episode `action[:3]` 相邻步长 L2 p90 **≤0.008 m**
5. 批次 accept/attempt ≥ 0.90；连续 3 reject → 停采诊断物理

### 3.4 「值得再训+open-loop」的最低条（仍需另批人工批准）

仅当：

- v2 release `validate_smolvla_s3_release.py` pass；
- §3.3 QA 在 train split 上均值达标；
- 用户 **显式** 批准超额 data-fix 后的一次 LoRA（本方案不启动）。

预期 open-loop 改善方向（推断，非保证）：`|close_offset|` 显著缩小（目标量级 ≤15–20 帧再谈 Pass）、`raw_gripper_oob_ratio`↓、smooth p90↓；EE 不显著回退。

---

## 4. Round-2 精确采集命令（copy-paste）

### 4.1 采集前审计（只读）

```bash
cd /home/ina/dev/ros2-arm-teleoperation-suite
git status --short
rg -n 'seed:|initial_pos_range|yaw_range_deg_by_object|griptiming' config/randomization.yaml
rg -n 'update_rate: 500' src/teleop_bringup/config/control_rate_sim.yaml

# 输出目录不得已存在
STAMP=$(date +%Y%m%d)
test ! -e data/e2_red_500hz_seed56_griptiming_lateclose10_${STAMP}
test ! -e data/e2_red_500hz_seed57_griptiming_lateclose10_${STAMP}
```

将 `config/randomization.yaml` 的 `seed:` 设为 **56**（第二批改为 **57**）。可微调 spawn（相对 54/55 平移，仍在桌面工作区），例如保持 `x=[0.35,0.43]` `y=[-0.14,0.14]` 或略移 `x=[0.36,0.44]`——**不要**回到普通下降包 seed 46–51。

### 4.2 可选：1-ep smoke（timeout + nuke）

仅当需要验证 launch 参数时：

```bash
cd /home/ina/dev/ros2-arm-teleoperation-suite
source /opt/ros/jazzy/setup.bash
source install/setup.bash

export BATCH_PREFLIGHT_OUTPUT_ROOT=/tmp/e2_red_seed56_griptiming_lateclose1_smoke
export BATCH_PREFLIGHT_LOG_DIR=/tmp/e2_red_seed56_griptiming_lateclose1_smoke_logs
export BATCH_PREFLIGHT_OBJECTS=object_red_box
export BATCH_PREFLIGHT_EPISODES=1
export BATCH_PREFLIGHT_MAX_ATTEMPTS=3
export BATCH_PREFLIGHT_RANDOMIZE=true
export BATCH_PREFLIGHT_HEADLESS=true
export BATCH_PREFLIGHT_CAPTURE_MODE=portfolio
export BATCH_PREFLIGHT_SCENE_USE_MUJOCO_RENDERER=true
export BATCH_PREFLIGHT_GRASP_ASSIST=false
export BATCH_PREFLIGHT_ENABLE_GRASP_MONITOR=false
export BATCH_PREFLIGHT_VALIDATION_MODE=lift
export BATCH_PREFLIGHT_CAMERA_WIDTH=320
export BATCH_PREFLIGHT_CAMERA_HEIGHT=240
export BATCH_PREFLIGHT_CAMERA_RATE=10.0
# Round-2 首选单变量：保持 Round-1 hold/close，降低实际位姿步长上限
export BATCH_PREFLIGHT_SEED=55
export BATCH_PREFLIGHT_PRE_CLOSE_HOLD=3.0
export BATCH_PREFLIGHT_CLOSE_DURATION=3.0
export BATCH_PREFLIGHT_GRASP_PAUSE=3.0
export BATCH_PREFLIGHT_HOVER_DURATION=4.0
export BATCH_PREFLIGHT_HOVER_HEIGHT=0.20
export BATCH_PREFLIGHT_DESCEND_DURATION=8.0
export BATCH_PREFLIGHT_APPROACH_XY_DURATION=0.0
export BATCH_PREFLIGHT_POSE_STEP_M=0.001
export BATCH_PREFLIGHT_POSE_CMD_RATE_HZ=100.0
export BATCH_PREFLIGHT_POSE_MAX_ACCELERATION_MPS2=0.5
export BATCH_PREFLIGHT_LIFT_DURATION=10.0
export BATCH_PREFLIGHT_POST_LIFT_HOLD=8.0
export BATCH_PREFLIGHT_BATCH_TIMEOUT_S=600
export BATCH_PREFLIGHT_DATASET_WAIT_S=90

timeout 700s bash scripts/run_batch_preflight_smoke.sh
# Nuke-on-done（AGENTS 8.7）
pkill -9 -f "teleop_bringup" || true
pkill -9 -f "mujoco_sim" || true
pkill -9 -f "lerobot_recorder" || true
pkill -9 -f "servo_node" || true
pkill -9 -f "ros2_control" || true
pkill -9 -f "batch_generator" || true
```

Smoke 通过条件：日志出现 `Pre-close open hold (3.00s)`、`lift validation passed`、真实 renderer，并通过 §3.3 QA。它只验证配方，不计入正式 seed56/57。

### 4.3 正式批次（确认开采后）

对 seed56、seed57 各跑一次（改 `seed:` 与目录名）：

```bash
cd /home/ina/dev/ros2-arm-teleoperation-suite
source /opt/ros/jazzy/setup.bash
source install/setup.bash

STAMP=$(date +%Y%m%d)
SEED=56   # 然后 57
OUT=data/e2_red_500hz_seed${SEED}_griptiming_lateclose10_${STAMP}
LOG=evidence/e2_red_500hz_seed${SEED}_griptiming_lateclose10_${STAMP}

# 编辑 config/randomization.yaml → seed: ${SEED}

export BATCH_PREFLIGHT_OUTPUT_ROOT="$(pwd)/${OUT}"
export BATCH_PREFLIGHT_LOG_DIR="$(pwd)/${LOG}"
export BATCH_PREFLIGHT_SEED="${SEED}"             # 与目录/meta/episode_results 身份一致
export BATCH_PREFLIGHT_OBJECTS=object_red_box
export BATCH_PREFLIGHT_EPISODES=10
export BATCH_PREFLIGHT_MAX_ATTEMPTS=3
export BATCH_PREFLIGHT_RANDOMIZE=true
export BATCH_PREFLIGHT_HEADLESS=true
export BATCH_PREFLIGHT_CAPTURE_MODE=portfolio
export BATCH_PREFLIGHT_SCENE_USE_MUJOCO_RENDERER=true
export BATCH_PREFLIGHT_GRASP_ASSIST=false
export BATCH_PREFLIGHT_ENABLE_GRASP_MONITOR=false
export BATCH_PREFLIGHT_VALIDATION_MODE=lift
export BATCH_PREFLIGHT_CAMERA_WIDTH=320
export BATCH_PREFLIGHT_CAMERA_HEIGHT=240
export BATCH_PREFLIGHT_CAMERA_RATE=10.0
export BATCH_PREFLIGHT_PRE_CLOSE_HOLD=3.0
export BATCH_PREFLIGHT_CLOSE_DURATION=3.0
export BATCH_PREFLIGHT_GRASP_PAUSE=3.0
export BATCH_PREFLIGHT_HOVER_DURATION=4.0
export BATCH_PREFLIGHT_HOVER_HEIGHT=0.20
export BATCH_PREFLIGHT_DESCEND_DURATION=8.0
export BATCH_PREFLIGHT_APPROACH_XY_DURATION=0.0
export BATCH_PREFLIGHT_POSE_STEP_M=0.001
export BATCH_PREFLIGHT_POSE_CMD_RATE_HZ=100.0
export BATCH_PREFLIGHT_POSE_MAX_ACCELERATION_MPS2=0.5
export BATCH_PREFLIGHT_LIFT_DURATION=10.0
export BATCH_PREFLIGHT_POST_LIFT_HOLD=8.0
export BATCH_PREFLIGHT_BATCH_TIMEOUT_S=1200
export BATCH_PREFLIGHT_DATASET_WAIT_S=90

timeout 1400s bash scripts/run_batch_preflight_smoke.sh

pkill -9 -f "teleop_bringup" || true
pkill -9 -f "mujoco_sim" || true
pkill -9 -f "lerobot_recorder" || true
pkill -9 -f "servo_node" || true
pkill -9 -f "ros2_control" || true
pkill -9 -f "batch_generator" || true
```

### 4.4 定性示范指引（batch_generator FSM 语义）

虽为脚本示教，执行者/审计者应按此理解「该学什么」：

1. **接近与下降全程开爪**（`action[7]=1`）；禁止下降中途闭合。  
2. **到达 pick 后**维持 Round-1 的 `pre_close_hold=3s`；先增加有几何变化的开爪下降样本，不堆叠 7 s 静态重复帧。  
3. **接触/对准稳定后**再闭合；闭合一次到底，保留已验证的 `close_duration=3s` 平滑 ramp，随后 `grasp_pause` 再抬升。  
4. **validation=lift**：抬升成功即可；不要为凑 place 拉长运输。  
5. 拒绝「更短 hold 刷 accept」——那会重现 v1 早闭过拟合。

---

## 5. Midstream：inspect → **新** release（提案命令，本方案不执行）

S3 路径 **不是** ACT ee_delta adapter。采集验收后：

```bash
cd /home/ina/robot-sim-lab/robot-arm-episode-data-lab

# 只读 QA；exit 0 才可继续，exit 2=结构失败，exit 3=Round-2 目标失败
python3 training/scripts/audit_smolvla_griptiming_dataset.py \
  --profile round2 \
  --source /home/ina/dev/ros2-arm-teleoperation-suite/data/e2_red_500hz_seed56_griptiming_lateclose10_<STAMP> \
  --evidence-dir /home/ina/dev/ros2-arm-teleoperation-suite/evidence/e2_red_500hz_seed56_griptiming_lateclose10_<STAMP> \
  --source /home/ina/dev/ros2-arm-teleoperation-suite/data/e2_red_500hz_seed57_griptiming_lateclose10_<STAMP> \
  --evidence-dir /home/ina/dev/ros2-arm-teleoperation-suite/evidence/e2_red_500hz_seed57_griptiming_lateclose10_<STAMP> \
  --json-out runs/smolvla_s3/griptiming_round2_validation_<STAMP>/round2_dataset_audit.json

# 新目录；拒绝覆盖 v1
test ! -e data/releases/smolvla_s3_abs_eef_rgb_v2_griptiming_lateclose

python3 training/scripts/prepare_smolvla_s3_release.py \
  --release-id smolvla_s3_abs_eef_rgb_v2_griptiming_lateclose \
  --output-dir data/releases/smolvla_s3_abs_eef_rgb_v2_griptiming_lateclose \
  --source /home/ina/dev/ros2-arm-teleoperation-suite/data/e2_red_500hz_seed56_griptiming_lateclose10_<STAMP> \
  --source /home/ina/dev/ros2-arm-teleoperation-suite/data/e2_red_500hz_seed57_griptiming_lateclose10_<STAMP>

python3 training/scripts/validate_smolvla_s3_release.py \
  --release-dir data/releases/smolvla_s3_abs_eef_rgb_v2_griptiming_lateclose
```

可选后续（**另批批准**）：是否把 v1 与 v2 合成更大 release，或 **仅用 v2** 重训以避免早闭标签继续主导。

**不要**把 ACT `e2_500hz_*_closelift` / `ee_delta` 混进 S3。

---

## 6. 明确禁止 / 停止条件

| 停止 / 禁止 | 原因 |
|---|---|
| 未获「确认开采」就跑 §4.3 | 此次仅批准受限验证，不含正式 20-episode 采集 |
| 覆盖 `smolvla_s3_abs_eef_rgb_v0` / `v1_griptiming` | immutable |
| `grasp_assist_enabled:=true` | AGENTS 训练硬约束 |
| 混入旧 1000 Hz / 合成画面 / ACT ee_delta | 契约破坏 |
| 因 QA 未达标仍进 release 或催训 | 无效 data-fix |
| 未过 open-loop Pass 进 Isaac / S4 | AGENTS 硬禁止 |
| 采集完成后自动 LoRA / AutoDL | 配额已用尽；需再次批准 |
| 盲改 α / lr / steps「试试看」 | 禁止盲目重训 |
| 无 timeout 的常驻 ROS；收尾不做 nuke | AGENTS 8.7 |

---

## 7. 风险与运维

- **CPU**：500 Hz + portfolio RGB；`nice`/`ionice` 已在 preflight 脚本内；勿并行第二仿真。  
- **时长**：`pose_step_m=0.001` 会延长运动阶段；`BATCH_TIMEOUT` / 外层 `timeout` 已放宽。  
- **配额**：`max_data_fix_retries: 1` 已用尽——本轮是 **显式超额**。AGENTS / canonical facts 已记录 S3 Hold 与“仅允许定向 data-fix”的边界；本次单-episode smoke 只记在本文件和 audit 产物中，不提升为 canonical Pass。  
- **证据落盘**：upstream `evidence/...` + midstream 本文件；Hold 报告路径保持只读引用。

---

## 8. 证据分级

| 断言 | 分级 |
|---|---|
| Hold：EE≈0.055、grip≈0.713、fail timing/smooth/sat、offset −65 | **已实现**（`openloop_full_stride1_.../s3_open_loop_summary.json`） |
| Timing 非 chunk/标签窗/行错位 | **已实现**（timing audit + 子代理结论） |
| Round-1：seed54/55、20 ep、lift、pre_close=3s、abs-EEF release | **已实现**（logs + manifest + parquet） |
| Round-1 部分时长默认（hover/lift 等） | **基于证据的推断**（脚本默认 + 时间线相容） |
| `pose_step_m=0.001` + `hover_height=0.20` 能越过 Round-1 的下降开爪分布且维持 lift | **已实现（受限 1-ep smoke：33 帧、lift pass）** |
| 7 s 静态 hold 可能增加单观测条件下的未来 chunk 歧义 | **基于证据的推断**（checkpoint `n_obs_steps=1`、`chunk_size=50`） |
| 一般 BC「晚闭样本可纠早闭」 | **通用背景知识**（不证明本仓 Pass） |

---

## 9. 2026-07-23 受限验证结果

验证产物：`runs/smolvla_s3/griptiming_round2_validation_20260723/`。

| 数据 | 结构门禁 | open descent | stable pick-open | first close | EE step p90 | 结论 |
|---|---:|---:|---:|---:|---:|---|
| Round-1 seed54（10 ep） | Pass | mean 21.2 / max 25 | mean 4.71 s | mean 158.6 | mean 0.00881 | Round-2 Fail |
| Round-1 seed55（10 ep） | Pass | mean 23.4 / max 27 | mean 4.73 s | mean 160.3 | mean 0.00830 | Round-2 Fail |
| smoke A：step=0.001、hover=0.12 | Pass，lift 1/1 | 24 | 6.50 s | 227 | 0.00700 | Fail：未越过 Round-1 max |
| smoke B：step=0.001、hover=0.20、descend deadline=8 | Pass，lift 1/1 | **33** | **6.00 s** | **226** | **0.00795** | **Round-2 Pass** |
| 正式 seed56（10 ep） | Pass，10/10 | mean 32.7 / min 30 | mean 6.14 s | mean 225.8 | mean 0.00754 / max 0.00800 | **Round-2 Pass** |
| 正式 seed57（10 ep） | Pass，10/10 | mean 35.2 / min 31 | mean 6.20 s | mean 233.1 | mean 0.00732 / max 0.00800 | **Round-2 Pass** |

说明：

- 30 帧门槛在验证后冻结：高于 Round-1 20 条 episode 的最大值 27，且 smoke B 达到 33；40 是验证前假设，已撤销。
- `gripper_intermediate_fraction` 保留为报告项，不再误作失败门禁。3 s 单调 ramp 是平滑标签；真正门禁是 [0,1] 范围、一次 close、零 reopen。
- 正式 seed56/57 联合 QA 已通过；报告为 `runs/smolvla_s3/griptiming_round2_validation_20260723/round2_dataset_audit.json`。
- 这证明 20 条新示范达到冻结的数据目标，但不证明重训或 open-loop 会改善。
- 独立 v2 release、一次正式 LoRA 与同口径 canonical open-loop 已完成；结果 Hold，未进入 Isaac。

---

## 10. Release / 训练接力状态

独立 `smolvla_s3_abs_eef_rgb_v2_griptiming_lateclose` 已创建并 validate Pass：

- 20 episodes / 7,765 frames
- train / validation / benchmark = 12 / 4 / 4
- `release_content_sha256=4774e44f6946dcd37046012375cd3ac1d74cf4fd2758179506a8227d818d9ff0`
- 本地 mock-preflight Pass（不用于授权）；AutoDL RTX 4090 D 非 mock GPU preflight Pass：`runs/smolvla_s3/preflight_v2_lateclose_20260723T155700Z/preflight_report.json`
- seed56/57 已合并为单一 LeRobot v3.0 根并实际加载通过：20 episodes / 7,765 frames / `action[8]`
- 一次正式 LoRA 已完成：1000 steps，batch 4，bf16，LoRA `r=64 / alpha=64 / dropout=0.05`，targets `q_proj/v_proj`
- 最终 checkpoint config audit 全项 Pass：`runs/smolvla_s3/train_v2_lateclose_20260723T160000Z/run_metadata.json`
- adapter SHA256：`c9b93c4d994539c240b795242663f3758a578343ee245dfd20697180b129fe6d`

v2 最终 checkpoint 已完成与 v1 相同的 canonical 全帧 `stride=1` open-loop：

- validation + benchmark：8 episodes / 3,108 frames，完整覆盖；
- gate：`hold`，失败项 `timing / smooth / sat`；
- EE RMSE `0.066865 m`，gripper balanced accuracy `0.720313`；
- close offset `-68.625` 帧 / `-6.862 s`，8/8 episode 均提前闭合；
- smoothness p90 `0.119612 m`，raw gripper OOB `0.210746`；
- 报告：`runs/smolvla_s3/openloop_v2_lateclose_full_stride1_20260723T161000Z/`。

相对 v1，gripper balanced accuracy 仅改善 `+0.00756`；EE RMSE `+0.01212 m`、提前量 `+3.625` 帧、smoothness `+0.01666 m`、OOB `+0.00604`，均退化。Round-2 late-close data-fix 没有修复策略时序。当前默认停止，禁止自动第三次 data-fix / 扩采 / 重训；未过 open-loop Pass 不得进入 Isaac。
