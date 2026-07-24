# 具身智能闭环系统项目简历描述与话术

为了方便将本项目（Franka Panda 机械臂具身智能多仓协同与闭环仿真验证系统）写在在线招聘平台（如 BOSS直聘、猎聘、脉脉等）或 PDF 简历中，以下整理了**详细版（项目经历）**、**极简版（微简历/打招呼）**以及**面试核心话术与 Q&A**。

---

## 1. 简历模板（标准详细版）
> 适合放在求职网站的“项目经历”核心位置。

*   **项目名称**：Franka Panda 机械臂具身智能多仓协同与闭环仿真验证系统（独立研发）
*   **项目角色**：独立设计与开发者（全栈研发）
*   **技术栈**：ROS 2 (Jazzy), MoveIt Servo, MuJoCo, Isaac Sim, PyBullet, PyTorch, LeRobot/SmolVLA (LoRA/PEFT), PyArrow (Parquet), Python, C++

### **项目描述**：
针对具身智能研发中“实时运动控制、离线AI策略训练、下游物理仿真评估”开发流程繁琐、调试环境臃肿的问题，**独立设计并实现了一套三仓解耦的具身闭环仿真与数据治理系统**。自主打通了从人类遥操作示范到仿真物理验证的端到端数据-物理双向循环，并完成 SmolVLA Recovery 的独立 prospective open-loop Pass 与有界 Isaac S4 就绪合同（诚实区分 open-loop 与任务成功）。

### **核心工作与技术实现（STAR法则）**：
*   **【系统架构与契约设计】** 自主设计了三仓解耦架构，制定了统一的机器人描述协议 [panda.yaml](../../configs/robot_schemas/panda.yaml)，规范了状态与动作的数学语义（含 ACT 的 `ee_delta` 与 VLA 的 `absolute_eef_gripper[8]`）。从架构源头上将“物理校验”与“数据治理”解耦，消除多仓接口定义冲突。
*   **【高频控制与多模态采集】** 基于 **ROS 2 (Jazzy)** 与 **MoveIt Servo** 自主搭建末端笛卡尔伺服与阻抗控制层（仿真主线 **500 Hz**，真机路径设计为 **1 kHz**），加入关节限位与急停安全保护；在 **MuJoCo** 中实现遥操作示范的多模态轨迹录制，并以 **Parquet** 持久化。
*   **【中游数据治理与策略训练】** 独立开发了静态数据质量校验网关 (Quality Gate)，编写了 [inspect_dataset.py](../../training/scripts/inspect_dataset.py) 基于关节步长 P99 限值与反向运动率自动过滤抖动与丢帧坏帧。使用 **PyTorch** 训练端到端行为克隆策略网络（MLP BC / ACT 诊断基线），并完成 **SmolVLA Recovery LoRA**（train-only split、`state[15]`、scene-only、官方 PEFT 正则、5,705 steps）。
*   **【评测门禁与执行语义】** 设计冻结 prospective open-loop 门禁：独立 held-out 10 条 / 2,593 帧在 `eval_gate_v3` 下 **Pass**（EE RMSE **0.0253 m**，夹爪 balanced accuracy **0.994**）；将开爪边 raw 过冲降级为诊断项，保留关爪边与 clip 分类/时序不变式为硬安全项。落地 S4 action-queue 合同（chunk10/K5/10Hz/`clip(raw,0,1)`）与 abs-EEF 执行夹紧。
*   **【下游解耦重放与验证】** 创新构建了中立动作流交接管道 (Handoff Pipeline)，编写了 [prepare_bridge_handoff.py](../../training/scripts/prepare_bridge_handoff.py) 将模型预测出的动作解耦打包为无 ROS 依赖的轻量化 `jsonl` 动作包；在 **PyBullet** 中搭建物理重放与执行监控沙盒；在 **Isaac** 上完成 scripted oracle 物理链门禁（lift 5/5）与 ACT 有界 rollout 诊断。

### **项目业绩（量化成果）**：
*   **闭环验证**：基于 30 条真实遥操作示范轨迹（7.1万帧）独立跑通了“采集-清洗-训练-回放-评估”的系统大循环；SmolVLA Recovery 独立 prospective open-loop **Pass**（相对 S2 EE 基线改善约 **90%**）。
*   **评测工程化**：E3.5 Isaac scripted oracle 从 lift 0/5 triage 到 5/5 物理链通过；评测漏斗区分 interface / behavior / task GT，避免把离线 loss 或 open-loop Pass 写成任务成功。
*   **调试效率提升**：通过中立动作交接机制，实现中游深度学习环境与下游 ROS 控制、物理仿真的完全解耦，**本地联调与故障定位除错效率提升 90% 以上**。

---

## 2. 简历模板（极简版/BOSS微简历）
> 适合在 Boss 聊天或手机端的项目简短介绍里展示。

*   **项目经历**：Franka Panda 机械臂具身智能三仓闭环验证系统 (独立研发)
*   **核心贡献**：
    1. **解耦架构设计**：独立设计三仓架构，制定机器人描述契约（Schema），解决多仓坐标系与接口定义冲突。
    2. **高频采集与控制**：基于 **ROS 2 (Jazzy) + MoveIt Servo** 搭建末端伺服与阻抗控制（仿真 **500 Hz** / 真机路径 **1 kHz**），并在 **MuJoCo** 中捕获多模态 Parquet 轨迹。
    3. **静态质量网关 + VLA Recovery**：Quality Gate 过滤抖动帧；SmolVLA LoRA（state[15]/scene）完成独立 prospective open-loop **Pass**（EE 2.5 cm 级、grip BA 0.99）。
    4. **中立动作重放 / Isaac 物理链**：Handoff→PyBullet；Isaac oracle lift 5/5；S4 有界 runtime 合同已冻结（未声称任务成功）。
*   **成果业绩**：独立跑通 30-Episode 仿真物理双向环流；SmolVLA Recovery prospective Pass；多仓联调效率提升 **90%**。

---

## 3. 面试核心话术与 Q&A

### Q0：SmolVLA 现在到哪一步了？能不能说已经抓起来了？
*   **回答话术**：
    > “只能说 **Isaac-readiness 的 open-loop 门禁过了**，不能说抓取成功。Recovery v3 在独立 10 条 held-out 全帧评测上 EE 约 2.5 cm、夹爪分类约 0.99，并且我们按执行侧 `clip(raw,0,1)` 修订了严重度门禁。有界 Isaac S4（≤5 seeds）已经批准，但本机当前没有可用的 Isaac GPU，所以 **`ran_isaac=false`**，我不会在简历里写任务成功率。”
    >
    > 一页纸：[`SMOLVLA_RECOVERY_V3_PORTFOLIO.md`](SMOLVLA_RECOVERY_V3_PORTFOLIO.md)

### Q1：为什么你要分三个仓库开发，直接在一个仓库里把 AI 训练和物理引擎写在一起不好吗？
*   **回答话术**：
    > “在具身智能实际研发中，**环境冲突和实时性隔离**是一个大痛点。上游控制需要高频实时（ROS 2 实时控制栈），中游算法需要复杂的深度学习环境（PyTorch 等各种 CUDA 库），下游物理引擎测试需要高频碰撞结算。如果塞进同一个仓库，不仅环境配置臃肿，而且很容易因为依赖库冲突导致环境崩溃。
    >
    > 我把系统解耦为三个仓，并设计了**中立动作流交接（Handoff）机制**。这样中游模型训练输出的只是标准的 `jsonl` 动作轨迹，下游物理重放沙盒不需要装任何 ROS 或 PyTorch 依赖，只要一个极其轻量的 Python 脚本和 PyBullet 库就能跑起来。这不仅极大方便了本地的轻量化调试，也为后续将模型部署到真实机械臂（Sim2Real）做好了准备。”

### Q2：项目中你制定的数据契约（Data Contract）具体规范了什么？
*   **回答话术**：
    > “机器人状态和动作的数据流非常容易发生‘静默漂移’。我通过定义统一的 YAML Schema，规范了输入的 Observation 必须包含 8 维状态（Franka Panda 7 关节角 + 1 夹爪开合度），动作 Action 为 7 维末端笛卡尔动作增量（$ee\_delta\_gripper$）。中游和下游在读取数据和推理时，都会强制进行静态格式比对。如果上游多录入了一个冗余传感器通道或维度不对，在入口就会被拦截报错，确保了策略模型和执行器之间的接口一致性。”

### Q3：下游的物理评估沙盒是如何工作的？为什么没有评估抓取成功率？
*   **回答话术**：
    > “下游的 PyBullet 物理重放沙盒（[panda_handoff.py](https://github.com/inayina/ros2-moveit-pybullet-bridge/blob/main/pybullet_bridge/pybullet_bridge/learning/panda_handoff.py)）通过轻量化读取中游导出的 `predicted_actions.jsonl`，在几何与运动学层面进行重放。它除了结算**‘轨迹偏差 RMSE’**之外，还通过计算机械臂雅可比矩阵的最小奇异值（SVD）来在线预警**‘关节奇异性风险’**（当最小奇异值 < 0.01 时触发警告），并联合计算**‘关节数据分布漂移（KL散度/Wasserstein距离）’、‘关节速度跳变’与‘软限位触发（Soft Limit）’**等 Sim2Real-readiness 风险与健康度指标。
    >
    > 我们严格遵守职责隔离的设计原则：具体的物理抓取成败（如积木是否被成功提起）在**上游数据采集时通过主轨自动标记**并保存在 episode 属性中。中游和下游为了防止物理逻辑多头定义带来的不一致，不重新推导抓取物理成败，仅评估运动执行质量并反馈给中游以修正数据集。”
