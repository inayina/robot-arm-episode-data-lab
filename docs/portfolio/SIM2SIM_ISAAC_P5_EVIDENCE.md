# MuJoCo–Isaac Sim2Sim P5 Evidence

**日期**：2026-07-17  
**状态**：`EVIDENCE_ONLY`  
**样本量**：每个 backend 1 episode / 25 frames  
**生成脚本**：`training/scripts/compare_sim_backends.py`

## 直接结论

P5 已跑通“同一 recorder contract → 同一中游 adapter/schema → 离线分布比较”的最小链路，但当前结果不能作为质量 gate。两边 raw action、task、action semantics、帧数、分辨率和声明的 `scene_id` 相同；实际 joint、EE、object、FT、gripper 和 RGB 分布存在明显差异。

其中最重要的发现是：匹配的 `scene_id` 字符串并不代表物理初态已经对齐。Isaac 与 MuJoCo 的关节初态、目标物体位置、夹爪开度、相机外观和 FT 测量语义仍不同。

## 对照配置

| 项目 | MuJoCo reference | Isaac candidate |
|---|---|---|
| simulator version | 3.10.0 | 6.0.0.0 |
| task | `isaac_panda_poc` | `isaac_panda_poc` |
| action semantics | `ee_pose_gripper_cmd_v1` | `ee_pose_gripper_cmd_v1` |
| fixed EE command | `[0.389, 0.005, 0.457, 0.922, 0.026, 0.387, 0.006]` | 相同 |
| fixed gripper command | `0.5` | 相同 |
| recorder | portfolio, 5 s, 5 Hz | portfolio, 5 s, 5 Hz |
| scene RGB | 320×240 | 320×240 |
| frames/video packets | 25 / 25 | 25 / 25 |
| upstream gate | `teleop` | `teleop` |

两次运行的 Servo 均保持 pause，因此本报告主要比较 backend 初态/观测 contract，不是闭环轨迹跟踪实验。Isaac P4 尚未消费 `/sim/joint_effort_cmd`，不能把本结果解释为两个控制器动态性能的公平对比。

## Raw contract 数值结果

| Field | Dim | normalized trajectory L2 RMSE | mean W1 | max abs mean shift |
|---|---:|---:|---:|---:|
| `action` | 8 | 0 | 0 | 0 |
| `observation.ee_pose` | 7 | 0.405494 | 0.0881732 | 0.386935 |
| `observation.ft` | 6 | 11.5715 | 2.89628 | 10.4859 |
| `observation.gripper` | 1 | 0.5 | 0.5 | 0.5 |
| `observation.object_pose` | 7 | 0.123011 | 0.0264924 | 0.100010 |
| `observation.state` | 7 | 1.55081 | 0.313314 | 1.46600 |

关键逐轴差异：

- joint mean shift（Isaac−MuJoCo）：`[0.012, 0.2162, 0, -0.455, 0, 1.466, -0.044]` rad；
- object position shift：约 `[0.10001, 0.06998, 0.01524]` m；
- FT mean shift：约 `[4.031, -2.773, 10.486, 0, 0.080, 0.008]`，但两边 sensor frame/实现语义尚未严格对齐；
- gripper observation shift：`-0.5`，表明初始开度/归一化配置不一致；
- raw action W1 为 0，证明输入命令本身一致。

## Timing 与 RGB

| Backend | duration | effective FPS | mean dt | dt std | max dt |
|---|---:|---:|---:|---:|---:|
| MuJoCo | 4.7984 s | 5.0016 | 199.934 ms | 0.797 ms | 202.307 ms |
| Isaac | 4.8523 s | 4.9461 | 202.180 ms | 3.703 ms | 209.213 ms |

RGB 使用每秒 1 帧采样、最多 1024 个共享 quantile 点估计每通道 Wasserstein-1：

| Backend | sampled frames | luminance mean | luminance std | RGB mean |
|---|---:|---:|---:|---|
| MuJoCo | 5 | 0.213997 | 0.133339 | `[0.214070, 0.213944, 0.214305]` |
| Isaac | 5 | 0.418829 | 0.173255 | `[0.285619, 0.444194, 0.559811]` |

RGB W1 为 `[0.074024, 0.230216, 0.345208]`，Isaac 场景明显更亮且蓝/绿通道分布更高。该差异包含灯光、材质、相机 pose 和 renderer 的综合影响，当前不能归因于单一参数。

## Adapted schema 结果

两个 raw episode 都通过同一个 `upstream_m6` adapter：

```bash
python3 training/scripts/adapt_upstream_panda_dataset.py \
  --input <raw_dataset> --output <adapted_dataset> \
  --schema configs/robot_schemas/panda.yaml \
  --derive-ee-delta-action --inspect
```

两边均为 1 episode / 25 frames，schema inspection `PASS`。适配后的 action[7] 分布不再相同（trajectory L2 RMSE `0.803397`），因为 `ee_delta_gripper` 是根据各自观测到的 EE pose 与相同 absolute command 派生；这正是初态/坐标差异传入训练 action 的证据。

## 复现比较

```bash
python3 training/scripts/compare_sim_backends.py \
  --reference /tmp/mujoco_p5_episode \
  --candidate /tmp/isaac_p4_episode \
  --reference-label mujoco \
  --candidate-label isaac \
  --json-output /tmp/p5_sim2sim_raw.json \
  --markdown-output /tmp/p5_sim2sim_raw.md \
  --video-sample-fps 1.0
```

临时 raw/parquet/video 与完整 JSON 位于 `/tmp`，不提交仓库。本文件保留本次运行的可审计摘要；脚本与测试是可复现的长期产物。

## 不能证明

- 不证明 Isaac 或 MuJoCo 抓取成功；两边 `physical_validation_applied=false`。
- 不证明控制跟踪性能相当；Isaac effort command adapter 尚未完成。
- 不证明 FT 可直接比较；sensor frame、gravity compensation 和测量位置尚未对齐。
- 不证明泛化、稳定性或 Sim2Real；每边只有一个 5 秒 episode。
- 不应据此设置 KL/W1 风险阈值；至少需要场景/初态对齐后采集多 episode baseline。

## 下一步校准顺序

1. 对齐 Panda 默认 joint pose、gripper opening 和 object initial pose；
2. 明确并转换 EE/FT canonical frame；
3. 对齐 camera extrinsics、lighting/material baseline；
4. 实现 Isaac `/sim/joint_effort_cmd` 消费，再运行相同闭环 command；
5. 每 backend 至少采集 5–10 个相同 seed/task episode 后校准分布阈值。
