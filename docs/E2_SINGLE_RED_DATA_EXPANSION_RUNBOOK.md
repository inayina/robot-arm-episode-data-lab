# E2 单红块数据扩充与阶段均衡 ACT Runbook

状态日期：2026-07-20  
适用范围：Panda、单红方块、MuJoCo 500 Hz 采集、scene-only LeRobot ACT、Isaac nominal 有界 A/B。  
目标读者：接手当前工作区的 Codex / AI 助手与项目维护者。

## 1. 直接结论与当前接力点

**不要继续采同类下降轨迹，也不要直接开完整 E4。** E3.5 Isaac scripted oracle
**已通过（v2b lift 5/5）**；完整实验过程见
[`E3P5_ISAAC_SCRIPTED_ORACLE_EXPERIMENT.md`](E3P5_ISAAC_SCRIPTED_ORACLE_EXPERIMENT.md)
（面试取材主文档）。

E3 事实（已关闭）：`evidence/e3_nominal20_home_30ep_gt_v1_20260719/` → **0/20**，
reach/grasp 各失败一半，**无有效 lift**。继续跑同一 ACT 无收益。

| 优先动作 | 入口 | 通过条件 |
|---|---|---|
| ~~E3.5 scripted oracle~~ | 上游 `scripts/run_isaac_scripted_oracle.sh` | **已通过** ≥4/5 lift（v2b 5/5） |
| **下一 ROI** | **模型无关评测框架**（Adapter 契约 / Benchmark 规范 / VLA V0）；ACT 仅 diagnostic hold | 见下方链接；**不开 E4、不盲训** |
| 禁止 | 普通下降扩采 / 完整 E4 100+ / 盲扫权重 / 下载 VLA 大权重 | — |

框架文档入口：

- [`POLICY_ADAPTER_CONTRACT.md`](POLICY_ADAPTER_CONTRACT.md)
- [`SINGLE_BLOCK_GENERALIZATION_BENCHMARK.md`](SINGLE_BLOCK_GENERALIZATION_BENCHMARK.md)
- [`VLA_GATE_V0_COMPATIBILITY_AUDIT.md`](VLA_GATE_V0_COMPATIBILITY_AUDIT.md)
- [`ACT_HOME_NO_CLOSE_HYPOTHESIS_MATRIX.md`](ACT_HOME_NO_CLOSE_HYPOTHESIS_MATRIX.md)

**Closelift 数据/模型（已落地）**

| 项 | 路径 / 事实 |
|---|---|
| 上游 raw | `.../e2_red_500hz_seed52_closelift5_20260720` + `seed53_...`（各 5 accepted） |
| Release | `data/releases/e2_500hz_random35_closelift_20260720/` |
| **权威 episode 数** | **40**（命名含 `random35` 为历史别名；见 release `PROVENANCE.md`） |
| Checkpoint | `data/e2_500hz_act_random35_closelift_5epoch_20260720/checkpoint.pt` |
| sha256 | `bc4a8fc49d24e9c22e8337ae9376fe189344235405d91e1034bcb7fe332785c3` |
| 5-seed 证据 | `evidence/e3p6_closelift40_5seed_home_20260720/smoke5_gate.json` → lift **0/5** |



2026-07-20 首次 5×（v1）：`evidence/e3p5_isaac_scripted_oracle_5x_lift_20260720/` —  
oracle 阶段 PASS，但 GT **lift 0/5**（pick 偏高 + 硬 `set_joint_positions` 空合）。

2026-07-20 **物理修复后**（v2b）：`evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/` —  
**reach/grasp/lift 5/5，`gate_pass=true`**（`physics_chain_ok_focus_on_policy`）。  
修复要点：`pick_z_offset=0.010`、夹爪改 PD `apply_action`、物块摩擦、oracle GT  
`gripper_close_max=0.70`（5 cm 方块侧夹 ≈0.62）。

历史权重扫描证据（已排除“只改权重即可解决”）：

| checkpoint | context/close/transport 权重 | 真实 Isaac 20-action 结果 |
|---|---:|---|
| 原 3-epoch tiny | uniform | 20 步全程张开、近静止，task FAIL |
| aggressive | `2/4/3` | 第 3 步过早闭合，18/20 动作限幅，task FAIL |
| context-first | `4/2/1.5` | 20 步全程张开、近静止，task FAIL |

权重只能改变已有样本频率，不能创造缺失的视觉—动作对应；**且必须先过 oracle 物理门禁**。
暂不优先加 `observation.ft`（多数 rollout 在接触前已错位）。

## 2. 已有产物：不要从零重做

### 上游 `ros2-arm-teleoperation-suite`

- seed 42 accepted 数据：
  `/home/ina/dev/ros2-arm-teleoperation-suite/data/e2_red_500hz_yaw10_random10_strict_20260719`
  （实际保留 5 条 accepted）。
- seed 43 accepted 数据：
  `/home/ina/dev/ros2-arm-teleoperation-suite/data/e2_red_500hz_seed43_random5_strict_20260719`
  （5 条 accepted）。
- 当前待采配置：
  `/home/ina/dev/ros2-arm-teleoperation-suite/config/randomization.yaml`，seed 44，
  red-box `x=[0.38,0.44]`、`y=[-0.14,0.16]`、yaw `[-15°,15°]`。
- 仿真 controller manager：500 Hz；MuJoCo encoder：500 Hz。

### 中游 `robot-arm-episode-data-lab`

- 已合并的 10 条 adapted：`data/e2_500hz_random10_adapted`。
- 已发布的 10 条 release：`data/releases/e2_500hz_random10_20260719`。
- uniform checkpoint：`data/e2_500hz_act_tiny_3epoch_20260719/checkpoint.pt`。
- aggressive 失败实验：`data/e2_500hz_act_stagebalanced_3epoch_20260719/checkpoint.pt`。
- context-first 失败实验：
  `data/e2_500hz_act_stagebalanced_v2_3epoch_20260719/checkpoint.pt`。
- A/B 证据：
  `evidence/e3_act_stagebalanced_500hz_20action_20260719/` 与
  `evidence/e3_act_stagebalanced_v2_500hz_20action_20260719/`。

这些 checkpoint 都可作为失败归因证据，但都不是成功模型。

## 3. 不可违反的边界

1. 训练数据必须 `grasp_assist_enabled=false`。
2. 必须使用真实 MuJoCo Renderer；发现 `synthetic fallback` 立即停止，禁止把合成替代画面当训练视频。
3. 不混入旧 1000 Hz episode；新增数据只能来自当前 post-fix 500 Hz 路径。
4. 上游 `batch_generator._validate_episode` 是物理 lift/place 主 gate；失败尝试必须 discard。
5. 中游只检查 schema、success/safety/drive flags；不得从 `observation.object_pose` 重新推导成功。
6. `closed_transport` 只是 gripper close→release 的时序标签，不是物理运输成功证明。
7. validation 必须保持 episode-level split，且不得使用训练采样权重。
8. 不覆盖已有 dataset、release、checkpoint 或 evidence；所有新输出使用新目录。
9. 不使用假视频。Isaac 有界脚本当前不生成 MP4，不得声称已有 Isaac 失败视频。
10. 工作树可能包含用户未提交改动。禁止 `git reset --hard`、`git checkout --` 或清理无关文件。

## 4. 下一位 AI 的执行顺序

```text
E3.5 oracle 已通过（v2b lift 5/5）
  → 已补「对准→闭合→抬升」阶段数据（40-ep closelift；目录名 random35 为别名）
  → 新模型 5-seed Isaac smoke：**lift 0/5**（HOME_NO_CLOSE）→ 未达标
  → **禁止**完整 E4；先诊断 home 接近/闭合为何近静止
```

完整 E4（100+）建议远程；**禁止**在 5-seed 小回归未达标时开完整 E4。
每一步失败时停止，不要绕过 gate 继续下游。

## 5. Step A：采集前审计

```bash
cd /home/ina/dev/ros2-arm-teleoperation-suite
git status --short
rg -n 'seed:|initial_pos_range|yaw_range_deg_by_object|object_red_box' \
  config/randomization.yaml
rg -n 'update_rate: 500' src/teleop_bringup/config/control_rate_sim.yaml
rg -n 'encoder_publish_rate", 500.0' \
  src/mujoco_sim/mujoco_sim/mujoco_sim_node.py
```

预期：seed 44；red-box `x=[0.38,0.44]`、`y=[-0.14,0.16]`、yaw `±15°`；sim control 与
encoder 均为 500 Hz。如果不一致，先报告差异，不要擅自覆盖配置。

输出目录不得已经存在：

```bash
test ! -e /home/ina/dev/ros2-arm-teleoperation-suite/data/e2_red_500hz_seed44_approach10_20260719
test ! -e /home/ina/dev/ros2-arm-teleoperation-suite/evidence/e2_red_500hz_seed44_approach10_20260719
```

若目录已存在，先只读检查是否是已完成批次；不要删除，改用新的明确 run tag。

## 6. Step B：采集 seed 44 新增 10 条

使用有 timeout、自动真实 renderer 检查和退出清理的 canonical 脚本：

```bash
cd /home/ina/dev/ros2-arm-teleoperation-suite
source /opt/ros/jazzy/setup.bash
source install/setup.bash

export BATCH_PREFLIGHT_OUTPUT_ROOT=/home/ina/dev/ros2-arm-teleoperation-suite/data/e2_red_500hz_seed44_approach10_20260719
export BATCH_PREFLIGHT_LOG_DIR=/home/ina/dev/ros2-arm-teleoperation-suite/evidence/e2_red_500hz_seed44_approach10_20260719
export BATCH_PREFLIGHT_OBJECTS=object_red_box
export BATCH_PREFLIGHT_EPISODES=10
export BATCH_PREFLIGHT_MAX_ATTEMPTS=3
export BATCH_PREFLIGHT_RANDOMIZE=true
export BATCH_PREFLIGHT_HEADLESS=true
export BATCH_PREFLIGHT_CAPTURE_MODE=portfolio
export BATCH_PREFLIGHT_SCENE_USE_MUJOCO_RENDERER=true
export BATCH_PREFLIGHT_GRASP_ASSIST=false
export BATCH_PREFLIGHT_ENABLE_GRASP_MONITOR=false
export BATCH_PREFLIGHT_CAMERA_WIDTH=320
export BATCH_PREFLIGHT_CAMERA_HEIGHT=240
export BATCH_PREFLIGHT_CAMERA_RATE=10.0
export BATCH_PREFLIGHT_BATCH_TIMEOUT_S=900
export BATCH_PREFLIGHT_DATASET_WAIT_S=90

timeout 1100s bash scripts/run_batch_preflight_smoke.sh
```

这里 `episodes=10` 指 10 条 accepted；每条最多 3 次尝试。不要把 rejected attempt 手动复制进输出。

## 7. Step C：采集验收

```bash
cd /home/ina/dev/ros2-arm-teleoperation-suite

rg -n 'verified real MuJoCo scene renderer|Accepted Episode|Batch progress|completed successfully' \
  evidence/e2_red_500hz_seed44_approach10_20260719
rg -n 'synthetic fallback|drive_fault|joint_limit:panda_joint7|Overrun detected' \
  evidence/e2_red_500hz_seed44_approach10_20260719 || true
jq '{valid,episodes,total_frames,errors,warnings}' \
  evidence/e2_red_500hz_seed44_approach10_20260719/dataset_validation.json
```

验收条件：

- 10 条 accepted，dataset validation PASS；
- 所有训练 episode 的 `success=true`、`safety_estop=false`、`drive_fault=false`；
- 日志确认真实 MuJoCo scene renderer；
- 320×240、10 Hz 视频实际存在并能由 `ffprobe` 读取；
- 没有 joint7 fault 或周期性 `>100 ms` write overrun；
- accepted / attempts 低于 0.90 或出现连续 3 次 rejected 时，停止并先做物理诊断。

随机抽一条真实视频检查：

```bash
find data/e2_red_500hz_seed44_approach10_20260719 -type f -name '*.mp4' -print | head
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,avg_frame_rate,nb_frames \
  -of default=noprint_wrappers=1 \
  "<上一步输出的一条真实 mp4 路径>"
```

不得生成替代视频来“补齐”缺失录像。

## 8. Step D：适配、合并、检查与 release

在中游执行：

```bash
cd /home/ina/robot-sim-lab/robot-arm-episode-data-lab

python3 training/scripts/adapt_upstream_panda_dataset.py \
  --input /home/ina/dev/ros2-arm-teleoperation-suite/data/e2_red_500hz_seed44_approach10_20260719 \
  --output data/e2_500hz_seed44_approach10_adapted \
  --schema configs/robot_schemas/panda.yaml \
  --derive-ee-delta-action \
  --inspect

python3 training/scripts/merge_adapted_datasets.py \
  --input data/e2_500hz_random10_adapted \
  --input data/e2_500hz_seed44_approach10_adapted \
  --output data/e2_500hz_random20_adapted

python3 training/scripts/inspect_dataset.py \
  --dataset data/e2_500hz_random20_adapted \
  --schema configs/robot_schemas/panda.yaml \
  --json-output evidence/e2_500hz_random20_inspection.json

python3 training/scripts/prepare_dataset_release.py \
  --input data/e2_500hz_random20_adapted \
  --output data/releases/e2_500hz_random20_20260719 \
  --schema configs/robot_schemas/panda.yaml \
  --release-id e2_500hz_random20_20260719 \
  --description "20 post-fix 500 Hz accepted randomized real-rendered MuJoCo red-box episodes; seeds 42/43/44"
```

release 验收：

```bash
jq '{release_id,num_episodes,num_frames,action_type,filter_rules,inspection,video_fps}' \
  data/releases/e2_500hz_random20_20260719/manifest.json
```

必须看到 `num_episodes=20`、`action_type=ee_delta_gripper`、
`upstream_gate=batch_generator`、`filter_scope=training_split_only` 和 inspection PASS。

## 9. Step E：同 split 的 5-epoch 训练 A/B

先训练 uniform 基线：

```bash
cd /home/ina/robot-sim-lab/robot-arm-episode-data-lab

timeout 900s /home/ina/miniforge3/envs/lerobot/bin/python \
  training/scripts/train_act_lerobot.py \
  --dataset data/releases/e2_500hz_random20_20260719 \
  --schema configs/robot_schemas/panda.yaml \
  --output data/e2_500hz_random20_act_uniform_5epoch_20260719 \
  --epochs 5 --chunk-size 50 --n-obs-steps 1 \
  --batch-size 8 --lr 0.0001 --seed 42 --validation-fraction 0.2 \
  --cache-root /tmp/e2_500hz_random20_scene_cache_20260719 \
  --device cuda
```

再训练 context-first 阶段均衡组；除了 sampler 外其余参数完全相同：

```bash
timeout 900s /home/ina/miniforge3/envs/lerobot/bin/python \
  training/scripts/train_act_lerobot.py \
  --dataset data/releases/e2_500hz_random20_20260719 \
  --schema configs/robot_schemas/panda.yaml \
  --output data/e2_500hz_random20_act_stagebalanced_5epoch_20260719 \
  --epochs 5 --chunk-size 50 --n-obs-steps 1 \
  --batch-size 8 --lr 0.0001 --seed 42 --validation-fraction 0.2 \
  --cache-root /tmp/e2_500hz_random20_scene_cache_20260719 \
  --device cuda \
  --stage-balanced-sampling \
  --grasp-context-frames 10 \
  --grasp-context-weight 4.0 \
  --closing-weight 2.0 \
  --transport-weight 1.5 \
  --stage-closed-threshold 0.12 \
  --stage-open-threshold 0.95
```

比较时至少保存：训练 history、validation raw/normalized L1、gripper accuracy、action RMSE、
sampling profile、checkpoint SHA-256、GPU/torch/CUDA 和 elapsed time。离线指标不是任务成功率。

```bash
jq '{release_id,training_history,validation_l1_loss,validation_l1_loss_normalized,gripper_open_close_accuracy,action_rmse,sampling,device}' \
  data/e2_500hz_random20_act_uniform_5epoch_20260719/metrics.json
jq '{release_id,training_history,validation_l1_loss,validation_l1_loss_normalized,gripper_open_close_accuracy,action_rmse,sampling,device}' \
  data/e2_500hz_random20_act_stagebalanced_5epoch_20260719/metrics.json
sha256sum data/e2_500hz_random20_act_*_5epoch_20260719/checkpoint.pt
```

## 10. Step F：真实 Isaac 20-action diagnostic A/B

这一步只验证 checkpoint loading、online inference、bounded execution、安全和明显的策略退化；
它不是完整 E3，也不能用来声称 pick/place 成功。

对两个 checkpoint 分别运行，下例为 stage-balanced 组：

```bash
cd /home/ina/dev/ros2-arm-teleoperation-suite

timeout 180s env \
  CHECKPOINT=/home/ina/robot-sim-lab/robot-arm-episode-data-lab/data/e2_500hz_random20_act_stagebalanced_5epoch_20260719/checkpoint.pt \
  MAX_ACTIONS=20 \
  DRY_RUN=false \
  ARM_COMMAND_MODE=position \
  MAX_JOINT_EXCURSION_RAD=2.0 \
  MAX_EE_EXCURSION_M=0.6 \
  INFERENCE_RATE_HZ=2.0 \
  POLICY_STARTUP_TIMEOUT_S=45.0 \
  POLICY_RUNTIME_TIMEOUT_S=70 \
  scripts/run_isaac_act_smoke.sh \
  evidence/e3_random20_stagebalanced_20action_20260719
```

uniform 组只替换 checkpoint 与 evidence 目录。不要修改安全阈值来掩盖发散。

生成中游汇总：

```bash
cd /home/ina/robot-sim-lab/robot-arm-episode-data-lab

python3 training/scripts/summarize_isaac_act_evaluation.py \
  --evidence /home/ina/dev/ros2-arm-teleoperation-suite/evidence/e3_random20_stagebalanced_20action_20260719 \
  --checkpoint data/e2_500hz_random20_act_stagebalanced_5epoch_20260719/checkpoint.pt \
  --release data/releases/e2_500hz_random20_20260719 \
  --output evidence/e3_random20_stagebalanced_20action_20260719
```

## 11. 决策与止损规则

| 观察 | 结论 | 下一步 |
|---|---|---|
| 全程 gripper≈1、EE 近静止、object 不动 | 仍未学到 approach/close | 检查数据时序和 chunk 执行；不要继续扫权重 |
| 前 1–3 步直接 close，随后大动作/大量 clip | sampler 仍过补偿 | 不推广 checkpoint；保留 uniform，对阶段标签/时序做诊断 |
| 先出现合理 approach，再 close，但 object 不动 | 接触/场景域或动作执行问题 | 做连续 contact/object evaluator，不用 endpoint 猜 lift |
| object endpoint 不变 | task FAIL | 不得声称抓取成功 |
| interface/execution FAIL 或 E-stop | 系统/安全失败 | 先修执行链，禁止扩大 rollout |
| 两组均能稳定接近并在合理位置闭合 | 数据扩充有效 | 再扩到 30 条，并开始连续任务 evaluator |

本阶段不要直接增加蓝圆柱或绿球。单红块 nominal 行为尚未成立时，多物体只会增加归因维度。

## 12. 强制物理收尾

任何 ROS/MuJoCo/Isaac 命令结束后，AI 必须自己执行，不能交给用户：

```bash
cd /home/ina/dev/ros2-arm-teleoperation-suite
./scripts/stop_stack.sh || true
pkill -9 -f '[t]eleop_bringup' || true
pkill -9 -f '[m]ujoco_sim' || true
pkill -9 -f '[l]erobot_recorder' || true
pkill -9 -f '[s]ervo_node' || true
pkill -9 -f '[r]os2_control' || true
pkill -9 -f '[i]saac_panda_backend.py' || true
pgrep -af '[t]eleop_bringup|[m]ujoco_sim|[l]erobot_recorder|[s]ervo_node|[r]os2_control|[i]saac_panda_backend.py' || true
```

最终 `pgrep` 不得返回实际仿真/ROS 进程。

## 13. AI 交接汇报模板

每次接力至少报告：

```text
已实现：<代码/配置/运行产物与路径>
文档声明，代码未确认：<若无则写无>
基于证据的推断：<明确不是直接事实>
通用背景知识：<若使用>

采集：accepted/attempts、真实视频数量/分辨率/FPS、gate、fault/overrun
release：id、episodes、frames、schema/action、inspection
训练：split、epochs、sampling、离线指标、checkpoint hash、GPU
Isaac：actions、interface/execution、safety、clip、gripper、EE、object endpoint、task
限制：是否有连续 evaluator、是否有真实 Isaac 视频、是否完整 E2/E3
清理：stop_stack 与 pgrep 结果
```

任何缺少直接证据的项目事实必须写：`当前项目证据不足，无法确认。`
