# Simulation Backends and Transfer Boundary

本文档说明三个机械臂仓库中 MuJoCo、PyBullet 和中游 episode schema 的职责边界。当前设计不是要把所有仓库强行统一到同一个仿真器，而是把它整理成一条跨仿真后端的数据闭环：

```text
MuJoCo upstream interaction
-> simulator-independent episode schema
-> minimal training / replay handoff
-> PyBullet downstream validation
-> Sim-to-Sim / Sim2Real-readiness evaluation
```

当前阶段不宣称已经完成真实机械臂 Sim2Real。更准确的说法是：本作品集在软件仿真条件下验证数据、训练、回放、执行评估和迁移风险分析的工程流程。

## Repository Roles

| 仓库 | 主要后端 | 职责 |
|---|---|---|
| `ros2-arm-teleoperation-suite` | MuJoCo | 上游遥操作、控制栈、动力学仿真、传感器观测和 raw episode 产生 |
| `robot-arm-episode-data-lab` | 仿真器无关数据层 | 统一 observation / action / state / episode / metadata / training schema |
| `ros2-moveit-pybullet-bridge` | PyBullet | 下游轻量执行验证、接触参数排查、轨迹误差评估和 Sim2Real-readiness 分析 |

这个边界的重点是让上游和下游各自选择适合当前任务的仿真后端，同时由中游 schema 固定数据语义，避免把仿真器 API、模型格式和控制接口泄漏到训练与评估契约里。

## Why MuJoCo Upstream

上游使用 MuJoCo 的核心原因是它更适合做机械臂交互数据来源和控制栈仿真：

- 需要围绕 ROS 2 teleop、safety monitor、MoveIt Servo、`ros2_control`、虚拟驱动和 MuJoCo physics server 构建连续控制链路。
- 需要稳定发布 end-effector pose、force/torque、object pose、scene/wrist/tactile/depth 等多模态观测。
- 需要调试夹爪接触、接触保持、adaptive force、grasp monitor 等上游交互信号。
- 需要把 teleop 或 synthetic generator 的动作过程录成 raw episode，作为数据闭环的源头。

因此，MuJoCo 在这里不是“最终验证后端”，而是上游 runtime 和数据生产后端。它负责产生交互过程和观测证据。

## Why PyBullet Downstream

下游使用 PyBullet 的核心原因是它更适合做轻量、可脚本化、可重复的执行评估：

- MoveIt 规划结果可以通过 `JointTrajectory` / `/bridge/command` 快速进入 PyBullet 执行。
- 双源 PyBullet 可以构造 ideal sim 与 randomized real-proxy，便于做 KL / W1 / MMD 分布偏移监控。
- 接触参数、摩擦、payload、joint damping、actuator delay 等因素可以快速注入和复验。
- headless / DIRECT 模式适合 CI、单元测试和批量报告。
- 作为下游 bridge，它更关注“动作进入执行后会不会暴露风险”，而不是重新承担上游遥操作和数据录制职责。

因此，PyBullet 在这里是下游验证后端。它负责复核轨迹执行、接触稳定性、分布偏移、runtime safety guard 和迁移风险。

## Backend Responsibilities

| 问题 | MuJoCo upstream | 中游 schema | PyBullet downstream |
|---|---|---|---|
| 交互输入 | teleop / gamepad / synthetic generator | 记录 task、timestamp、action 语义 | 通常不产生 teleop 原始数据 |
| 控制链路 | safety -> servo -> control -> simulated drive | 保存 action type 和 state layout | 消费 replay / policy action 并验证执行 |
| 观测 | joint state、EE pose、FT、多相机、触觉、depth | 统一 observation keys 和维度 | 发布 sim/real proxy joint states、tracking error |
| 抓取 | 调试接触、夹持力、滑落诊断 | 保存 success / failure_reason / metadata | 做接触参数和执行风险复核 |
| 训练 | 不负责训练质量 | dataset release、baseline training、offline eval | 不重新训练，只做 runtime validation |
| 迁移评估 | 提供 source behavior | 提供可审计 handoff | 评估执行误差、分布偏移和风险 |

## Simulator-Independent Schema

中游 `robot-arm-episode-data-lab` 的职责是把不同仿真器产生的数据转成统一数据契约。核心原则是：训练和评估脚本不直接依赖 MuJoCo 或 PyBullet API，而依赖明确声明的 fields。

当前 Panda 主线 schema 包括：

| 字段 | 语义 |
|---|---|
| `observation.state` | 7 个 Panda joint positions + 1 个 gripper opening |
| `observation.ee_pose` | `[x, y, z, qx, qy, qz, qw]` |
| `observation.object_pose` | 可选目标物体位姿 |
| `observation.ft` | 可选 force/torque |
| `observation.images.*` | 可选 scene / wrist / tactile image streams |
| `action` | 明确声明 action type，例如 `ee_pose_gripper` 或 `ee_delta_gripper` |
| `timestamp` / `frame_index` / `episode_index` | 帧级对齐信息 |
| `task` / `metadata` | 任务标签、成功失败、失败原因、source 信息 |

上游 MuJoCo recorder 当前可能输出：

```text
observation.state[7]
observation.gripper[1]
action[8] = ee_pose_gripper
```

中游 adapter 的职责是显式转换：

```text
observation.state[8] = concat(observation.state[7], observation.gripper[1])
```

如果训练需要默认的 `ee_delta_gripper[7]`，必须显式派生或转换，不能把 `action[8]` 静默截断成 `action[7]`。这个规则正是中游屏蔽仿真器差异的关键。

## MuJoCo vs PyBullet Differences

跨仿真后端评估时，不能假设两个仿真器的数值行为完全一致。需要主动记录和解释以下差异。

| 维度 | MuJoCo | PyBullet | 对项目的影响 |
|---|---|---|---|
| 接触模型 | 更适合连续动力学和接触调参 | 更轻量，适合快速复验和 CI | 抓取成功率不能直接等价，需要记录接触条件 |
| 摩擦参数 | MJCF geom/material 参数 | URDF / `changeDynamics` 参数 | 同名摩擦值不一定有相同效果 |
| 关节控制接口 | MuJoCo actuator / simulated drive / ROS topics | PyBullet position control / trajectory relay | action 语义必须通过 schema 和 adapter 明确 |
| timestep / control frequency | 可与控制栈、physics loop、recorder 同步设计 | 常见 240 Hz physics + 100 Hz publish | replay 时要检查 timestamp、插值和控制频率 |
| 坐标系 | MuJoCo model / ROS frame bridge | URDF link / PyBullet world / MoveIt frame | 必须固定 base frame、EE link 和 quaternion convention |
| 模型格式 | MJCF | URDF / SRDF / MoveIt config | Panda 在两边需要 model alignment，不只是文件格式转换 |
| 夹爪建模 | 可做 contact hold、adaptive force、grasp debug | 更适合轻量接触参数扫描 | 下游评估应报告“风险和敏感性”，不是保证真实抓取 |

这些差异不是架构错误，而是迁移评估的一部分。项目要展示的是：我知道差异在哪里，并且通过 schema、adapter、validation 和报告把差异显式化。

## Current Evaluation Name

当前阶段建议使用以下表述：

- `Sim-to-Sim validation`
- `cross-simulator replay validation`
- `Sim2Real-readiness evaluation`
- `migration risk analysis`

不建议使用以下表述：

- 已完成真实机械臂 Sim2Real
- policy 已经可直接上真机
- MuJoCo 和 PyBullet 抓取结果可以直接互相证明
- 下游 Real-Source 已经是真实机械臂

更稳妥的表述是：

> 当前 Real-Source 是 randomized PyBullet 或 LeRobot replay proxy，用来构造可控偏移和验证监控链路。真实机械臂迁移仍需要硬件接口、传感器、夹爪、安全层和标定验证。

## Real Robot Replacement Points

未来迁移到真实机械臂时，需要替换或补齐以下模块。

| 替换点 | 当前仿真阶段 | 实机阶段需要 |
|---|---|---|
| 仿真后端 | MuJoCo / PyBullet physics | 真实机械臂和真实环境 |
| 控制接口 | simulated drive、PyBullet position control、trajectory relay | `ros2_control` hardware interface、厂商 SDK 或真实控制器 |
| 夹爪驱动 | simulated gripper / contact model / stub | 真实 gripper driver、力/位置/电流反馈 |
| 传感器输入 | virtual RGBD、FT、tactile、object pose | 真实相机、FT、触觉、外参和时间同步 |
| 安全层 | software safety monitor / risk engine | 物理急停、限位、速度限制、碰撞保护、操作流程 |
| 标定与坐标变换 | model frame / URDF / MJCF frame | hand-eye calibration、base/tool frame 标定、TF 校验 |
| 数据质量 | simulator-generated labels | 真实噪声、遮挡、延迟、失败样本和人工复核 |
| 验收方式 | scriptable sim tests | 低速、空载、单关节、受限空间、逐步 bring-up |

因此，实机迁移不是简单替换一个 simulator 参数，而是一次系统集成工作。

## Interview Answer Template

当面试官问：“为什么上游 MuJoCo、下游 PyBullet 不统一？”可以这样回答：

> 我现在没有把它当成架构错误，也没有急着统一仿真器。这个作品集的目标是展示一个跨仿真后端的数据闭环。上游 `ros2-arm-teleoperation-suite` 用 MuJoCo，是因为它更适合承载 ROS 2 teleop、safety、Servo、控制栈、多模态观测和交互数据录制；下游 `ros2-moveit-pybullet-bridge` 用 PyBullet，是因为它轻量、脚本化程度高，适合做 MoveIt 轨迹执行验证、接触参数排查、双源偏移注入和风险监控。
>
> 中间我用 `robot-arm-episode-data-lab` 作为仿真器无关的数据标准层，统一 observation、action、state、metadata 和 training schema。这样训练和评估不直接绑定 MuJoCo 或 PyBullet API，而是绑定明确的数据契约。
>
> 我也不会声称 MuJoCo 里成功就等于 PyBullet 或真实机械臂一定成功。两个后端在接触模型、摩擦、timestep、控制接口、坐标系和模型格式上都有差异。当前阶段我把它定义为 Sim-to-Sim / Sim2Real-readiness evaluation：先让数据、训练、replay、执行评估和风险分析闭环可审计；真正上实机时还要替换硬件接口、夹爪驱动、传感器输入、安全层和标定流程。

## Recommended Portfolio Wording

简历或 README 中建议使用：

> Cross-simulator embodied data loop for robot-arm manipulation: MuJoCo-based teleoperation and episode recording, simulator-independent episode schema and baseline training, and PyBullet-based replay validation for Sim2Real-readiness and migration risk analysis.

中文可以写成：

> 跨仿真后端的机械臂具身数据闭环：上游用 MuJoCo 产生遥操作和多模态 episode，中游用统一 schema 做数据校验、最小训练和 replay handoff，下游用 PyBullet 做轨迹执行、接触稳定性和 Sim2Real-readiness 风险评估。
