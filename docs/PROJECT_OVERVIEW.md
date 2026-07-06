# Project Overview

状态：P0 面试 / 作品集入口文档。本文档说明 `robot-arm-episode-data-lab` 在三仓库机械臂具身数据闭环中的中游职责。

## 1. Role in the Three-Repo Loop

本仓库是三仓库链路中的**中游数据实验室**：

```text
上游 ros2-arm-teleoperation-suite
  MuJoCo / ROS 2 teleop / safety / servo / recorder
  -> raw episode

中游 robot-arm-episode-data-lab
  schema / validation / release / replay / baseline training / handoff
  -> validated dataset + policy replay bundle

下游 ros2-moveit-pybullet-bridge
  MoveIt / PyBullet execution validation / grasp evaluation / Sim2Real-readiness
```

中游的价值不是展示复杂算法，而是把机械臂交互过程变成可检查、可训练、可复现、可交付给下游评估的 episode dataset。

## 2. What This Repository Owns

| 职责 | 当前实现 / 文档 |
|---|---|
| Canonical Panda schema | `configs/robot_schemas/panda.yaml` |
| 上游 episode adapter | `training/scripts/adapt_upstream_panda_dataset.py` |
| dataset inspection | `training/scripts/inspect_dataset.py` |
| dataset release | `training/scripts/prepare_dataset_release.py` |
| legacy PyBullet 采集样例 | `scripts/collect_episode.py`, `scripts/validate_dataset.py` |
| replay / visualization 样例 | `scripts/visualize_episode.py`, `training/scripts/replay_policy.py` |
| minimal baseline training | `training/scripts/train_act_smoke.py` |
| offline evaluation | `training/scripts/evaluate_policy.py` |
| downstream handoff bundle | `training/scripts/prepare_bridge_handoff.py` |

## 3. Inputs

主要输入分为两类：

| 输入 | 来源 | 用途 |
|---|---|---|
| MuJoCo / ROS 2 raw Panda episode | 上游 `ros2-arm-teleoperation-suite` | 通过 adapter 转为 canonical Panda dataset |
| legacy PyBullet episode | 本仓库历史采集链路 | 保留为本地可复现采集与评测样例 |

上游 raw episode 可能包含：

- `observation.state[7]`
- `observation.gripper[1]`
- `observation.ee_pose[7]`
- `observation.ft[6]`
- `observation.images.*`
- `action[8]`，常见语义为 `ee_pose_gripper`
- `timestamp` / `frame_index` / `episode_index` / `task`

中游 adapter 必须显式声明 action 语义，禁止把 `action[8]` 静默截断成 `action[7]`。

## 4. Canonical Panda Schema

当前主 schema：

```text
configs/robot_schemas/panda.yaml
```

核心字段：

| 字段 | 维度 | 必需 | 说明 |
|---|---:|---|---|
| `observation.state` | 8 | yes | 7 个 Panda 关节位置 + 1 个 gripper opening |
| `observation.ee_pose` | 7 | yes | `[x, y, z, qx, qy, qz, qw]` |
| `action` | 7 | yes | 默认 `ee_delta_gripper`: delta xyz + delta rpy + gripper cmd |
| `timestamp` | scalar | yes | 帧时间戳 |
| `frame_index` | scalar | yes | 帧索引 |
| `episode_index` | scalar | yes | episode 索引 |
| `task` | string | yes | 任务标签或语言指令 |
| `observation.object_pose` | 7 | optional | 物体位姿 |
| `observation.ft` | 6 | optional | 力 / 力矩 |
| `observation.images.*` | image | optional | scene / wrist / tactile RGB |

Optional modality 缺失时应产生 warning，不应直接导致 dataset inspection fail。

## 5. Dataset Validation

Validation 的目标是尽早发现数据不可训练或不可交付的问题：

- required 字段缺失。
- shape / dtype 不符合 schema。
- `action_type` 和训练脚本期望不一致。
- `frame_index`、`timestamp`、`episode_index` 不可解释。
- optional modality 缺失但未记录 warning。
- dataset release 缺少 `manifest.json` 或 `inspection_report.json`。

最小命令：

```bash
python3 training/scripts/inspect_dataset.py \
  --dataset /tmp/panda_mock_dataset \
  --schema configs/robot_schemas/panda.yaml
```

## 6. Baseline Training

当前训练只用于证明最小工程闭环：

```text
dataset release -> linear_smoke policy -> metrics -> offline eval -> replay JSONL
```

默认 policy：

```text
linear_smoke: observation.state -> action
```

输出：

- `checkpoint.npz`
- `metrics.json`
- `normalization.json`
- `config_resolved.yaml`
- `eval.json`
- `predicted_actions.jsonl`

这些输出用于验证接口、shape、action 语义和 handoff，不用于宣称高质量抓取策略。

## 7. Replay / Bridge Handoff

本仓库不启动下游 ROS 2 runtime，也不直接控制真实机械臂。它只输出中立的 replay / handoff 文件：

```text
bridge_handoff/
├── predicted_actions.jsonl
├── dataset_manifest.json
├── dataset_inspection_report.json
├── replay_check.json
└── handoff_manifest.json
```

下游 `ros2-moveit-pybullet-bridge` 负责消费这些动作流，并在 MoveIt / PyBullet 中评估：

- 轨迹执行误差。
- 坐标系转换风险。
- 抓取接触稳定性。
- 仿真参数敏感性。
- Sim2Real-readiness 风险。

## 8. Out of Scope

当前明确不做：

- 不启动 ROS 2 runtime。
- 不做真实机械臂控制。
- 不训练复杂模型或大模型。
- 不承诺 policy 效果。
- 不宣称完成真实机械臂 Sim2Real。
- 不把 MuJoCo 和 PyBullet 的物理结果说成完全等价。

