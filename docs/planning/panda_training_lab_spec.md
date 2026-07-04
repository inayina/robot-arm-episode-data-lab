# SPEC: 改造 `robot-arm-episode-data-lab`，加入训练与统一 Panda 数据接口

状态：规划 SPEC。本文档用于记录当前改造方向；代码实现按后续任务分步落地。

## 背景

这个仓库应该成为我机器人作品集里的 **数据与训练实验室**。

当前作品集相关仓库：

* `ros2-arm-teleoperation-suite`：ROS 2 + MuJoCo + Franka Panda 遥操作、抓取、多模态录制。
* `robot-arm-episode-data-lab`：episode 数据处理、LeRobot 导出、训练与评估实验。
* `ros2-moveit-pybullet-bridge`：MoveIt + PyBullet Sim2Real 验证、分布偏移监控、风险引擎、PolicyRunner。

本次任务目标不是再创建一个新的训练仓库，而是在当前仓库中补齐：

1. episode schema 定义；
2. 数据集检查；
3. LeRobot 导出；
4. 策略训练；
5. 离线评估；
6. policy replay / rollout 接口。

当前统一主线机械臂使用 **Franka Panda**。本任务不要切换 UR3 / UR5。UR3 / UR5 只作为后续真实工业机械臂适配方向写进文档，不做代码迁移。

---

## 目标一：定义统一 Panda observation/action schema

新增一个明确的数据接口 schema，供数据导出、训练、评估、后续 policy replay 共用。

建议新增文件：

```text
configs/robot_schemas/panda.yaml
```

内容参考：

```yaml
robot: panda

joint_names:
  - panda_joint1
  - panda_joint2
  - panda_joint3
  - panda_joint4
  - panda_joint5
  - panda_joint6
  - panda_joint7

gripper:
  type: parallel_jaw
  command_range: [0.0, 1.0]
  meaning:
    0.0: closed
    1.0: open

observation:
  state:
    fields:
      - joint_position[7]
      - gripper_opening[1]
    dim: 8

  ee_pose:
    fields:
      - position_xyz[3]
      - orientation_xyzw[4]
    dim: 7

  object_pose:
    optional: true
    fields:
      - position_xyz[3]
      - orientation_xyzw[4]
    dim: 7

  ft:
    optional: true
    fields:
      - force_xyz[3]
      - torque_xyz[3]
    dim: 6

  images:
    optional: true
    scene_rgb: [480, 640, 3]
    wrist_rgb: [240, 320, 3]
    tactile_left_rgb: [240, 320, 3]
    tactile_right_rgb: [240, 320, 3]

action:
  default_type: ee_delta_gripper

  ee_delta_gripper:
    fields:
      - delta_xyz[3]
      - delta_rpy[3]
      - gripper_cmd[1]
    dim: 7

  joint_delta_gripper:
    fields:
      - joint_delta[7]
      - gripper_cmd[1]
    dim: 8
```

第一版保持简单、清楚、可解释，不要做过度抽象。

---

## 目标二：在本仓库内新增 training 模块

新增目录结构：

```text
training/
├── README_TRAINING.md
├── configs/
│   ├── train_act_smoke.yaml
│   └── evaluate_smoke.yaml
├── scripts/
│   ├── inspect_dataset.py
│   ├── train_act_smoke.py
│   ├── evaluate_policy.py
│   └── replay_policy.py
├── reports/
│   └── .gitkeep
└── policies/
    ├── __init__.py
    ├── base_policy.py
    └── dummy_policy.py
```

第一版不需要实现完整 ACT / Diffusion Policy 生产级训练。目标是先跑通一个轻量训练与评估闭环，证明数据接口、训练接口、评估接口是通的。

---

## 目标三：实现数据集检查脚本

新增：

```text
training/scripts/inspect_dataset.py
```

功能：

1. 接收 dataset 路径；
2. 读取元数据或样本文件；
3. 检查 required keys；
4. 根据 `configs/robot_schemas/panda.yaml` 检查维度；
5. 输出 PASS / FAIL 报告。

示例命令：

```bash
python training/scripts/inspect_dataset.py \
  --dataset data/exports/panda_demo \
  --schema configs/robot_schemas/panda.yaml
```

期望输出类似：

```text
Dataset: data/exports/panda_demo
Robot: panda
Episodes: 10
Frames: 1320

Required fields:
  observation.state: OK, dim=8
  action: OK, dim=7

Optional fields:
  observation.ee_pose: OK
  observation.object_pose: OK
  observation.images.scene: missing, optional

Status: PASS
```

---

## 目标四：实现 smoke training 脚本

新增：

```text
training/scripts/train_act_smoke.py
```

第一版可以是一个轻量监督学习 baseline，不必真的实现完整 ACT。重点是验证训练接口。

要求：

* 不依赖 GPU；
* 可以跑小样本数据；
* 加载 dataset；
* 划分 train / val；
* 对 observation/action 做简单 normalization；
* 训练一个小 MLP 或 dummy ACT-like placeholder；
* 保存 checkpoint；
* 保存训练指标 JSON。

示例命令：

```bash
python training/scripts/train_act_smoke.py \
  --dataset data/exports/panda_demo \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke
```

期望输出：

```text
training/reports/panda_act_smoke/
├── metrics.json
├── config_resolved.yaml
└── checkpoint.pt
```

`metrics.json` 示例：

```json
{
  "train_loss": 0.012,
  "val_loss": 0.018,
  "num_episodes": 10,
  "num_frames": 1320,
  "action_dim": 7,
  "state_dim": 8
}
```

---

## 目标五：实现离线评估脚本

新增：

```text
training/scripts/evaluate_policy.py
```

第一版先做离线评估，不做真实 rollout。

功能：

1. 加载 checkpoint；
2. 加载 validation dataset；
3. 预测 action；
4. 比较 predicted action 和 recorded action；
5. 输出评估指标。

指标包括：

* mean absolute action error；
* final state error，如果数据里有；
* smoothness proxy；
* success label，如果数据里有。

示例命令：

```bash
python training/scripts/evaluate_policy.py \
  --dataset data/exports/panda_demo \
  --checkpoint training/reports/panda_act_smoke/checkpoint.pt \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke/eval.json
```

---

## 目标六：实现 policy replay 导出接口

新增：

```text
training/scripts/replay_policy.py
```

这个脚本暂时不要直接控制 ROS 2，而是导出一个中立的动作文件，供 `ros2-moveit-pybullet-bridge` 的 PolicyRunner 后续消费。

示例输出：

```text
training/reports/panda_act_smoke/predicted_actions.jsonl
```

每一行格式：

```json
{
  "timestamp": 0.033,
  "robot": "panda",
  "action_type": "ee_delta_gripper",
  "action": [0.001, 0.0, -0.002, 0.0, 0.0, 0.01, 0.0]
}
```

这个文件就是本仓库 training 模块和 Sim2Real bridge 仓库之间的接口。

---

## 目标七：补充文档，说明仓库边界

新增或更新：

```text
README.md
training/README_TRAINING.md
docs/TRAINING_TO_SIM2REAL.md
```

文档里要明确说明：

```text
ros2-arm-teleoperation-suite
→ 负责 MuJoCo / teleop / grasping，产生 Panda 机器人 episode

robot-arm-episode-data-lab
→ 负责数据检查、LeRobot 导出、训练、评估、policy replay 文件导出

ros2-moveit-pybullet-bridge
→ 负责消费 replay / policy actions，做 Sim2Real 双源验证、分布偏移监控和风险闭环
```

加入这句话：

> This repository is not a robot runtime. It is the data, training, and evaluation lab. Robot execution belongs to `ros2-arm-teleoperation-suite` or `ros2-moveit-pybullet-bridge`.

也加入当前边界：

> 当前主线 robot schema 是 Franka Panda。UR3 / UR5 适配是后续工作，未来应通过新增 robot schema 文件实现，而不是直接修改现有 Panda schema。

---

## 不要做的事情

本任务不要添加：

* 真机械臂驱动；
* UR3 / UR5 模型迁移；
* ROS 2 runtime node；
* GPU 重训练依赖；
* 云端实验追踪；
* 复杂 Diffusion Policy 实现；
* 新的独立训练仓库。

第一阶段目标是：干净、可解释、可跑通的训练 / 评估接口。

---

## 验收标准

### AC1：Schema

存在：

```text
configs/robot_schemas/panda.yaml
```

并清楚定义 joint names、observation fields、action fields 和 optional modalities。

### AC2：Training 目录

存在：

```text
training/
```

并包含 scripts、configs、reports、policies 子目录。

### AC3：Dataset inspection

`inspect_dataset.py` 可以在 sample/mock dataset 上运行，并输出 PASS / FAIL 报告。

### AC4：Smoke training

`train_act_smoke.py` 可以在无 GPU 环境下跑通，并输出：

```text
checkpoint.pt
metrics.json
config_resolved.yaml
```

### AC5：Offline evaluation

`evaluate_policy.py` 可以加载 checkpoint 并输出：

```text
eval.json
```

### AC6：Policy replay export

`replay_policy.py` 可以按统一 Panda action schema 导出：

```text
predicted_actions.jsonl
```

### AC7：文档

`docs/TRAINING_TO_SIM2REAL.md` 能清楚解释三个仓库之间的关系：

* MuJoCo teleoperation 仓库；
* episode-data-lab；
* MoveIt-PyBullet Sim2Real bridge。

### AC8：不依赖新训练仓库

本次改造应把训练保留在 `robot-arm-episode-data-lab` 内部，不假设还有一个单独训练仓库。

---

## 建议提交顺序

1. 新增 `configs/robot_schemas/panda.yaml`。
2. 新增 `training/README_TRAINING.md`。
3. 新增 `docs/TRAINING_TO_SIM2REAL.md`。
4. 新增 `training/scripts/inspect_dataset.py`。
5. 如果还没有真实数据，新增一个 mock dataset generator。
6. 新增 smoke training 和 evaluation 脚本。
7. 新增 replay export 脚本。
8. 更新根目录 README，补一段 training 与 sim2real 的关系说明。

---

## 完成后面试表达目标

完成后，我应该能够这样解释：

> 我用 Franka Panda 作为操作臂项目的统一数据接口。MuJoCo 仓库负责产生机器人 episode，episode-data-lab 负责数据检查、LeRobot 导出、策略训练和离线评估，MoveIt-PyBullet bridge 则负责消费 policy/replay 动作并做 Sim2Real 风险验证。我刻意把训练和机器人运行时分开，是为了让 observation/action schema 清晰、可复用，也方便以后接入不同仿真或真实机械臂。
