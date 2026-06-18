# 具身智能机械臂知识库

本文档面向 `robot-arm-episode-data-lab` 项目，整理具身智能机械臂方向的核心概念、技术路线、工程模块和学习资料。目标不是写成论文综述，而是作为后续实现 HAL、IK、RRT、抓取、数据采集、LeRobot 转换和模仿学习的项目知识底座。

## 1. 一句话理解具身智能机械臂

具身智能机械臂系统不是单纯的视觉识别模型，也不是单纯的机械臂控制程序，而是一个持续闭环：

```text
语言/任务目标
  -> 感知环境
  -> 估计状态
  -> 规划动作
  -> 执行控制
  -> 观察物理反馈
  -> 记录数据与评估结果
  -> 改进策略
```

对于当前项目，最小闭环可以表达为：

```text
PyBullet 场景
  -> RGB 图像 + joint state + ee pose + object pose
  -> action
  -> stepSimulation
  -> episode 落盘
  -> validate + replay
```

这个闭环已经具备进入模仿学习数据工程的基本形态。

## 2. 技术地图

### 2.1 传统机器人栈

传统机械臂系统通常拆为：

- 机器人模型：URDF、关节、连杆、末端执行器、关节限制。
- 正运动学 FK：从关节角计算末端位姿。
- 逆运动学 IK：从末端目标位姿求关节角。
- 运动规划：在配置空间中找无碰撞路径，典型方法包括 RRT、PRM、RRT-Connect、RRT*。
- 轨迹处理：插值、速度/加速度限制、时间参数化。
- 控制执行：关节位置控制、速度控制、力矩控制、阻抗控制。
- 感知：RGB/RGB-D、物体检测、位姿估计、场景建图。
- 数据记录：图像、状态、动作、任务标签、成功率、失败原因。

MoveIt 2 是 ROS 2 生态中常见的机械臂运动规划平台，覆盖运动规划、操作、3D 感知、运动学、控制等能力。OMPL 是常用的采样式运动规划库，包含 RRT、PRM 等规划器，但它自身不绑定碰撞检测或可视化，需要和外部系统集成。

### 2.2 学习型机器人栈

学习型机械臂系统更关注数据和策略：

- Observation：图像、深度、关节状态、末端位姿、任务语言。
- Action：关节目标、末端位姿目标、相对位移、夹爪开合。
- Demonstration：人类遥操作或专家策略产生的轨迹。
- Policy：从 observation 到 action 的模型。
- Imitation Learning：用专家轨迹学习策略。
- Reinforcement Learning：通过 reward 与环境交互优化策略。
- Evaluation：成功率、完成时间、碰撞次数、轨迹平滑度、泛化能力。

LeRobot 的定位很接近这条线：它提供真实机器人学习所需的模型、数据集、工具、模仿学习和强化学习能力，并强调数据集共享与预训练模型复用。

### 2.3 具身智能 / VLA 路线

Vision-Language-Action（VLA）模型把视觉、语言和动作统一到一个策略中：

```text
camera image + language instruction + robot state -> robot action
```

代表性方向：

- RT-1：使用大规模真实机器人数据训练 Robotics Transformer，强调数据规模、任务多样性和模型容量。
- RT-2：把视觉语言模型和机器人动作结合，把动作表示为 token，让模型获得更强的语义泛化能力。
- Diffusion Policy：把动作序列生成建模为条件扩散过程，在机器人视觉运动策略中表现出较强的多模态动作建模能力。
- ACT / Action Chunking：一次预测一段动作 chunk，常用于降低实时推理抖动，提高动作连续性。

对本项目而言，短期不用直接训练 VLA，但数据结构应为后续模型留下入口：图像、状态、动作、语言指令、任务结果必须按 step 对齐。

## 3. 机械臂数据结构知识

### 3.1 一个 episode 应该包含什么

推荐基础字段：

```text
episode_xxxxxx/
├── images/
│   ├── 000000.png
│   ├── 000001.png
│   └── ...
├── states.npy
├── actions.npy
├── ee_poses.npy
├── object_poses.npy
└── metadata.json
```

字段含义：

- `images/`：视觉观察，通常来自固定相机、腕部相机或多相机系统。
- `states.npy`：机器人本体状态，例如关节角、关节速度、夹爪状态。
- `actions.npy`：控制器下发的目标动作。
- `ee_poses.npy`：末端执行器位姿，常用 `[x, y, z, qx, qy, qz, qw]`。
- `object_poses.npy`：目标物体位姿，用于仿真评估或监督信号。
- `metadata.json`：任务名、语言指令、控制模式、成功标签、失败原因、相机参数、机器人型号。

### 3.2 数据对齐原则

每个 step 应满足：

```text
images/000123.png
states[123]
actions[123]
ee_poses[123]
object_poses[123]
```

关键原则：

- 图像帧数等于所有数组第一维长度。
- action 应明确表示“当前 step 下发的目标”还是“下一 step 的目标”。
- metadata 中记录 `control_mode`，例如 `joint_position`、`cartesian_ik`、`teleop_joint`、`teleop_ee`。
- 训练数据不要混入失败原因不明、帧数不齐或相机漂移的样本。

### 3.3 LeRobot 对齐点

LeRobot 文档中强调真实机器人学习的典型流程：

```text
teleoperate -> record dataset -> train policy -> evaluate/replay
```

它支持用遥操作采集数据、保存 LeRobotDataset、训练策略并回放 episode。对当前项目来说，最重要的映射是：

```text
当前项目字段                  LeRobot 视角
images/*.png                  observation.images.*
states.npy                    observation.state
actions.npy                   action
metadata.language_instruction task / instruction
metadata.success              evaluation label
```

后续做 `export_lerobot_style.py` 时，应优先保证：

- observation 和 action 帧级对齐。
- action 维度稳定。
- 相机命名稳定。
- 任务语言统一，例如 `"reach the cube"`、`"pick up the red cube"`。
- episode 级 success/failure 标签明确。

## 4. 动作表示知识

### 4.1 Joint Space Action

关节空间动作直接指定每个电机/关节的目标位置：

```text
action[t] = [joint_1_target, joint_2_target, ..., joint_n_target]
```

优点：

- 简单稳定。
- 不需要额外运动学模型。
- 很适合作为项目早期数据格式。

缺点：

- 对任务语义不直观。
- 同一个末端移动目标，在不同机器人上关节动作不同。
- 后续迁移到不同机械臂时复用性较弱。

当前项目 V1 默认就是 joint-space action。

### 4.2 End-Effector Space Action

末端空间动作指定夹爪或工具中心点的目标位姿：

```text
action[t] = [x, y, z, qx, qy, qz, qw, gripper]
```

优点：

- 对 pick-and-place 等任务更直观。
- 更接近人类描述：“移动到 cube 上方 10cm”。
- 有利于任务规划和跨机器人迁移。

缺点：

- 需要 FK/IK 和机器人模型。
- 可能出现 IK 不可达或多解。
- 需要处理奇异点、关节限制和碰撞。

Phase 1 的 HAL + IK + 笛卡尔插补就是从 joint-space 走向 EE-space 的第一步。

### 4.3 Absolute / Relative / Delta Action

三种常见动作编码：

- Absolute：动作直接表示目标值。
- Relative：动作表示相对当前状态的偏移。
- Delta：动作表示相对上一条动作的增量。

项目建议：

- V1/V2 用 absolute joint action，最容易验证。
- Phase 1 后可记录 absolute EE target，便于解释。
- 模仿学习阶段可额外导出 relative action，因为偏移量更容易归一化，模型训练更稳定。
- 避免过早使用 delta action，因为误差会随时间累积，调试成本更高。

## 5. 控制与规划知识

### 5.1 HAL 的意义

HAL（Hardware Abstraction Layer）把上层算法和底层机器人接口隔开：

```text
Planner / IK / Policy
        |
  RobotControl
        |
PyBulletRobot / RealRobot
```

这样做的价值：

- 上层算法不需要知道 PyBullet body id 或真实电机协议。
- 后续接真机时，只需要新增 `RealRobot` 实现。
- 数据采集脚本能复用同一套 `get_state()`、`set_action()`、`step()` 接口。

### 5.2 IK 的工程要点

IK 输入：

```text
target_position = [x, y, z]
target_orientation = [qx, qy, qz, qw]
```

IK 输出：

```text
target_joint_positions = [q1, q2, ..., qn]
```

工程注意事项：

- 目标点要在工作空间内。
- 输出要截断到可控关节数量。
- 要检查关节限制。
- 对不可达目标应返回失败状态或抛出清晰异常。
- 先做位置 IK，再逐步加入姿态约束。

### 5.3 RRT / OMPL / MoveIt 的位置

RRT 解决的是“从起点到终点如何绕开障碍”的问题。它不是 IK，也不是控制器。

典型关系：

```text
Task goal
  -> target pose
  -> IK / sampling
  -> motion planning in configuration space
  -> trajectory
  -> controller
```

OMPL 提供采样式运动规划算法，但不负责碰撞检测和可视化。MoveIt 则把机器人模型、规划场景、碰撞检测、运动学、轨迹处理和 ROS 2 接口整合起来。

当前项目建议：

- Phase 1：先做无避障的笛卡尔直线插补 + IK。
- Phase 2：自己实现简化 RRT，并用 PyBullet 做碰撞检测。
- 后续：理解 MoveIt/OMPL 的工程边界，为简历和迁移做铺垫。

## 6. 感知与任务理解知识

### 6.1 视觉输入类型

常见输入：

- 固定 RGB 相机：最简单，适合早期数据闭环。
- RGB-D 相机：能获得深度，利于物体定位和抓取点估计。
- Wrist camera：安装在末端，适合近距离操作。
- 多相机：提高遮挡鲁棒性，但标定和同步更复杂。

当前项目建议保持固定 RGB，相机参数写进 metadata。

### 6.2 语言指令

具身智能数据中，语言指令通常是 episode 级或 task 级条件：

```json
{
  "language_instruction": "reach the cube",
  "task_name": "reach_cube"
}
```

早期即使不用语言模型，也应该记录语言字段。这样后续可以对齐 VLA 或 LeRobot 的 task 字段。

### 6.3 成功判定

常见成功指标：

- reach：末端与目标距离小于阈值。
- pick：物体 z 轴抬升超过阈值。
- place：物体最终位置接近目标区域。
- no_collision：没有发生异常碰撞。
- stable：物体最终速度接近 0，姿态稳定。

当前项目可先做：

```text
reach_success = distance(ee_position, object_position) < threshold
```

抓取阶段再加入：

```text
pick_success = object_z_after - object_z_before > threshold
```

## 7. 模仿学习知识

### 7.1 行为克隆

Behavior Cloning 是最基础的模仿学习：

```text
dataset: (observation, action)
model: observation -> action
loss: predicted_action vs expert_action
```

优点：

- 简单。
- 和当前 episode 数据结构天然兼容。
- 适合展示数据工程价值。

缺点：

- 容易受到分布偏移影响。
- 失败恢复能力弱。
- 数据质量决定上限。

### 7.2 Action Chunking

Action Chunking 一次预测一段未来动作：

```text
observation[t] -> action[t:t+H]
```

价值：

- 减少每一步独立预测导致的抖动。
- 对机械臂连续控制更友好。
- ACT、Diffusion Policy、部分 VLA 策略都和 action chunk 思路相关。

### 7.3 Diffusion Policy

Diffusion Policy 把动作生成建模为条件扩散过程。它适合多峰动作分布：同一个任务可能有多种合理抓取路径，扩散模型能更自然地建模这种多样性。

项目启发：

- 数据中要保留连续动作序列，而不是只存最终结果。
- 动作要平滑、频率稳定、时间对齐。
- 可视化 replay 很重要，因为模型学到的是轨迹行为。

### 7.4 VLA 模型

VLA 模型使用图像、语言和机器人状态生成动作。RT-2 的关键启发是：可以把机器人动作编码成模型可输出的 token，从而把互联网规模视觉语言预训练和机器人控制结合。

项目启发：

- 语言指令不要等到最后才补。
- 数据字段命名要稳定。
- action representation 是核心设计问题。
- 先做小而干净的数据集，比大而混乱的数据集更适合作品集。

## 8. 工程路线与当前项目映射

### 8.1 当前已经具备

- PyBullet 仿真环境。
- RGB 图像采集。
- joint state 和 action 落盘。
- ee pose 和 object pose 落盘。
- metadata。
- dataset validator。
- episode replay GIF。

这已经覆盖了机器人学习数据工程的核心入门闭环。

### 8.2 Phase 1 应补齐

- `RobotControl` HAL。
- `PyBulletRobot`。
- IK。
- 笛卡尔直线插补。
- `cartesian_ik` 控制模式。

对应知识点：

```text
joint action -> EE target -> IK -> joint target -> episode action
```

### 8.3 Phase 2 应补齐

- RRT。
- PyBullet collision checking。
- 障碍物场景。
- 规划失败原因标注。

对应知识点：

```text
configuration space
collision-free path
sampling-based planning
planning success rate
```

### 8.4 Phase 3 应补齐

- gripper。
- pick success evaluation。
- object z-axis success label。
- failure type。

对应知识点：

```text
grasp execution
physical contact
automatic evaluation
critic agent
```

### 8.5 Phase 4-5 应补齐

- batch collection。
- dataset statistics。
- LeRobot-style export。
- policy training placeholder。
- dashboard / report。

对应知识点：

```text
dataset scale
data quality
train/eval split
policy interface
```

## 9. 面试表达模板

可以这样讲：

> 这个项目不是单纯跑 PyBullet demo，而是围绕具身智能机械臂的数据闭环来设计。我先用 PyBullet 构建最小桌面任务，按 step 对齐保存 image、state、action、末端位姿和物体位姿，再用 validator 和 replay 保证数据可检查、可展示。后续通过 HAL 把 PyBullet 控制细节隔离出来，加入 IK、笛卡尔插补和 RRT，使动作从简单 joint trajectory 逐步升级到更接近真实机械臂任务的控制链路。数据结构也预留了语言指令、success label 和 LeRobot 导出路径，方便继续扩展到模仿学习或 VLA 风格策略。

## 10. 推荐学习顺序

1. 先掌握当前项目的数据闭环：episode、metadata、validate、replay。
2. 学 FK/IK 与关节空间/末端空间动作。
3. 学 HAL 抽象，把控制接口和仿真后端隔离。
4. 学 RRT 和碰撞检测，理解配置空间规划。
5. 学 LeRobot 数据格式和模仿学习流程。
6. 学 ACT、Diffusion Policy、RT-1/RT-2 等策略模型的高层思想。
7. 最后再考虑多 Agent、VLA、真机迁移和大规模数据。

## 11. 参考资料

- LeRobot Documentation: <https://huggingface.co/docs/lerobot/index>
- LeRobot Imitation Learning on Real-World Robots: <https://huggingface.co/docs/lerobot/il_robots>
- LeRobot Action Representations: <https://huggingface.co/docs/lerobot/action_representations>
- MoveIt 2 Documentation: <https://moveit.picknik.ai/main/index.html>
- OMPL Documentation: <https://ompl.kavrakilab.org/>
- A Survey of Embodied Learning for Object-Centric Robotic Manipulation: <https://arxiv.org/abs/2408.11537>
- LeRobot: An Open-Source Library for End-to-End Robot Learning: <https://arxiv.org/abs/2602.22818>
- RT-1: Robotics Transformer for Real-World Control at Scale: <https://arxiv.org/abs/2212.06817>
- RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control: <https://arxiv.org/abs/2307.15818>
- Diffusion Policy: Visuomotor Policy Learning via Action Diffusion: <https://arxiv.org/abs/2303.04137>
