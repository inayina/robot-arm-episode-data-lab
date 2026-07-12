# 三仓机器人项目作品集事实母版

审计日期：2026-07-13  
项目定位：Panda 机械臂的多仓数据、训练、离线评估与 Sim2Sim / Sim2Real-readiness 验证闭环。  
本文件用途：为简历、README、作品集 PDF、面试话术、演示脚本、HR 沟通和技术追问提供统一事实来源。

## 候选人画像

候选人是自动化本科背景，具备三年成熟职场经验，正在转向机器人系统集成、测试验证、应用开发和具身工程化方向。这个项目体现的不是单一算法模块，而是把控制、通信、数据、训练、测试、运行验证和风险反馈拆清边界后串成最小工程闭环的能力。

可迁移能力需要如实表达：

- 上一份工作中的机器学习经验，可以迁移到机械臂数据分析、线性 baseline、MLP Behavior Cloning 和深度学习训练。
- 风控流程优化经验，可以迁移到三仓职责边界、数据 Gate、handoff 契约、风险识别和项目范围控制。
- 生成式 AI 应用经验，可以迁移到项目 RAG 知识助手、事实检索、引用溯源和文档一致性检查。
- 银行一线工作形成的流程意识、责任意识、沟通和业务理解能力，可以迁移到机器人项目的验证、交付和跨模块协作。

不得把银行经历包装成机器人商业项目，不使用客户数据、内部制度或敏感信息。

## 1. 一页式项目总览

| 项目项 | 内容 |
| --- | --- |
| 项目名称 | Panda 三仓机器人数据、训练与执行验证闭环 |
| 项目定位 | 软件仿真环境下，从上游 ROS 2/MuJoCo 采集，到中游数据 release/MLP BC/handoff，再到下游 PyBullet replay/monitor/risk 的最小闭环 |
| 目标岗位 | 机器人系统集成、测试验证、应用开发、具身数据/训练工程、技术交付 |
| 上游 | `ros2-arm-teleoperation-suite`：ROS 2/MuJoCo 仿真、遥操作/批采、安全与控制、episode recorder、上游 physical gate |
| 中游 | `robot-arm-episode-data-lab`：adapter、schema validation、release、EDA、MLP BC、offline evaluation、predicted action、bridge handoff、RAG |
| 下游 | `ros2-moveit-pybullet-bridge`：handoff loader、Panda JSONL replay、PandaActionAdapter、PyBullet replay、monitor/risk benchmark |
| 当前完成度 | 30 条 Panda MuJoCo 批采 episode 贯通 release、MLP BC、same-split linear comparison、handoff、下游 1-episode replay smoke |
| 核心技术栈 | ROS 2 Jazzy、MuJoCo、MoveIt Servo、ros2_control、PyBullet、Python、PyTorch、CUDA、pytest、JSONL/manifest、BM25 RAG |
| 核心实验结果 | 30 episodes / 71,737 frames；MLP 100 epochs；MLP test normalized MSE 0.2350，linear same-split test normalized MSE 0.5800；handoff 71,737 actions；latest archived downstream smoke 1/1 completed，mean/max latency 9.79/34.218 ms |
| 当前限制 | 不证明真实机械臂部署、真实 Sim2Real、稳定在线自主抓取、在线抓取成功率提升、大规模泛化或 ACT canonical 正式实验 |

100-150 字摘要：

本项目围绕 Franka Panda 机械臂搭建了一个三仓软件闭环：上游用 ROS 2 与 MuJoCo 完成遥操作/批采、控制、安全和 raw episode 录制；中游负责 schema 适配、数据检查、release、EDA、MLP BC 训练评估和 handoff；下游消费 handoff，在 PyBullet 中进行 JSONL replay、监控和风险验证。当前主实验使用 30 条 MuJoCo 批采 episode 验证了数据、训练、动作交付和 replay smoke 链路，但不声称实机部署或真实 Sim2Real。

## 2. 为什么做这个项目

机器人项目里，数据采集、模型训练和执行验证经常分散在不同脚本或 Demo 中。只展示一个机械臂动起来，不能说明数据格式是否稳定、动作语义是否一致、训练产物能否交付下游，也不能说明异常如何被发现。

因此本项目拆成三仓：

- 上游只关注任务输入、ROS 2 控制、MuJoCo 仿真交互、recorder 和 physical gate。
- 中游只关注数据 schema、release、EDA、训练、离线评估和 handoff。
- 下游只关注 handoff 消费、动作适配、PyBullet replay、monitor 和 risk。

这个设计重点不是追求复杂算法堆叠，而是证明候选人能把机器人系统中的控制流、数据流、验证流和职责边界梳理清楚，并用测试与产物管理证据。

## 3. 三仓架构与职责边界

| 仓库 | 输入 | 核心处理 | 输出 | 明确不负责 |
| --- | --- | --- | --- | --- |
| `ros2-arm-teleoperation-suite` | 任务目标、遥操作输入、batch generation 配置 | Safety Monitor、MoveIt Servo、ros2_control、MuJoCo、batch_generator、episode recorder、上游 physical gate | `episode_*/train/`、`meta.json`、raw episode、G0 validation | 中游 schema/release/training；下游 PyBullet replay/risk；真实机械臂部署 |
| `robot-arm-episode-data-lab` | 上游 Panda raw episode | adapter、schema validation、release、EDA、MLP BC、same-split baseline、offline metrics、predicted JSONL、bridge handoff、RAG | `frames.jsonl`、`manifest.json`、metrics、checkpoint、`predicted_actions.jsonl`、`bridge_handoff/` | ROS 2 实时控制；MuJoCo 物理执行；PyBullet replay 执行；实机控制 |
| `ros2-moveit-pybullet-bridge` | 中游 `bridge_handoff/` | handoff validation、JSONL replay、PandaActionAdapter、PolicyRunner、PyBullet replay、distribution monitor、risk aggregation | `benchmark_summary.json`、tracking/monitor/risk report、downstream feedback | raw episode 采集；数据清洗/release；模型训练；真实 Panda 驱动；完整 Sim2Real |

```mermaid
flowchart LR
    A["目标/遥操作"] --> B["ROS 2 安全与控制"]
    B --> C["MuJoCo episode"]
    C --> D["数据适配与质量检查"]
    D --> E["MLP BC 训练与离线评估"]
    E --> F["predicted action / bridge handoff"]
    F --> G["Panda PyBullet replay"]
    G --> H["tracking / drift / fault / risk benchmark"]
```

事实依据：三仓角色在上游 README 中明确列出（`ros2-arm-teleoperation-suite/README.md:3-15`），中游 README 和 AGENTS 定义中游 agent 与 Gate 边界（`robot-arm-episode-data-lab/README.md:20-23`，`AGENTS.md:43-84`），下游 README 与 AGENTS 定义 replay/risk 角色（`ros2-moveit-pybullet-bridge/README.md:3-6`，`docs/AGENTS.md:9-75`）。

Legacy 边界：中游 `agents/`、`core/` 是历史 PyBullet/KUKA 实现，不与 Panda training release 混用（`robot-arm-episode-data-lab/AGENTS.md:19`）。下游 iiwa/MoveIt 只作为历史回归证据，不是当前 Panda handoff 主线（`ros2-moveit-pybullet-bridge/docs/CURRENT_STATUS.md:19-34`）。

## 4. ros2-arm-teleoperation-suite：遥操作、控制、仿真与数据采集

### 项目目标

上游仓是软件仿真的 ROS 2/MuJoCo Panda 数据生产端。它负责从任务目标、遥操作或 batch generation 输入出发，经过安全、运动、控制和仿真链路，生成可被中游消费的 raw episode 与 `meta.json`。项目范围明确排除真实机械臂部署和 Sim2Real 证明（`docs/PROJECT_SCOPE_AND_ACCEPTANCE.md:11-28`）。

### 输入与输出

- 输入：任务目标、遥操作输入、batch generation 配置（`docs/AGENTS.md:13-16`）。
- 输出：`episode_*/train/` + `meta.json`，包含 `upstream_gate` 和 `success`（`docs/AGENTS.md:54-61`）。
- raw episode contract：上游 recorder 输出 HuggingFace/LeRobot-style episode，字段包括 `observation.state[7]`、`action[8]`、`observation.ee_pose[7]`、FT、gripper、image、timestamp、task、success、object_pose 等（`docs/INTER_REPO_CONTRACTS.md:21-60`）。

### ROS 2 分层链路

上游架构分为 L0 teleop input、L1 safety、L2 MoveIt Servo、L3 ros2_control、L4 CANopen/virtual servo、L5 MuJoCo、L6 perception、L7 recorder。架构图和 topic 链路见 `docs/ARCHITECTURE_V2.md:31-103` 与 `docs/ARCHITECTURE_V2.md:166-212`。

关键 topic：

- `/teleop/cmd_pose`、`/teleop/gripper_cmd`、`/teleop/record_trigger`
- `/safe_master_pose`、`/safety/status`、`/safety/estop`
- `/joint_target`、`/joint_states`
- `/sim/joint_effort_cmd`、`/sim/encoder_state`
- `/ee_pose`、`/ft_sensor`、camera topics

### safety monitor

Safety monitor 是强制串联节点，位于 teleop 和 servo 之间，处理 joint limit、workspace、velocity、watchdog 和 E-stop（`docs/ARCHITECTURE_V2.md:39-45`，`docs/AGENTS.md:26-31`）。上游不声称安全认证或真实硬件 functional safety（`docs/PROJECT_SCOPE_AND_ACCEPTANCE.md:22-28`）。

### MoveIt Servo

Motion Agent 使用 MoveIt Servo 做笛卡尔伺服，输出 `/joint_target`；实时栈不使用 RRT（`docs/AGENTS.md:24-33`）。这一点避免把 legacy RRT 或下游规划能力混到上游主线。

### ros2_control

ros2_control 作为 L3 控制层，包含 `controller_manager`、`cartesian_impedance_controller`、`joint_state_broadcaster` 和 `canopen_system`，目标控制频率在架构文档中记录为 1000 Hz（`docs/ARCHITECTURE_V2.md:47-55`，`docs/ARCHITECTURE_V2.md:150-162`）。

### MuJoCo

MuJoCo 是上游软件物理服务器，提供 Franka Panda 物理、FT 真值、虚拟相机和对象状态（`docs/ARCHITECTURE_V2.md:63-65`）。项目范围明确说 MuJoCo 是本仓物理服务器，sim-direct 与 CAN/vcan0 是不同运行模式（`docs/PROJECT_SCOPE_AND_ACCEPTANCE.md:32-50`）。

### batch generator / teleoperation

Task Planning Agent 实现在 `batch_generator.py` 或 L0 `teleop_input`，FSM 为 Hover -> Descend -> Close -> Lift -> Transport -> Place -> Release（`docs/AGENTS.md:9-17`）。批采开始前设置 `language_instruction` 和 `upstream_gate=batch_generator`（`docs/AGENTS.md:18-21`）。

### episode recorder

Recorder 订阅 gripper、teleop cmd、safety、drive status 和 record trigger，写入 episode（`src/lerobot_recorder/lerobot_recorder/recorder_node.py:46-83`）。它在停止录制时写入 `upstream_gate`，并输出 synchronized frames（`recorder_node.py:134-163`）。frame 字段包含 `observation.state`、`ee_pose`、`object_pose`、FT、gripper、action、timestamp、episode/frame index、task、language、success、safety/drive fault（`recorder_node.py:230-270`）。

### 上游物理 Gate

`batch_generator._validate_episode` 检查 target/language/gate/reset/motion/gripper close、对象 workspace、lift_delta 和 bin XY（`src/synth_data_gen/synth_data_gen/batch_generator.py:933-1019`）。测试覆盖了 place validation、wrong bin、lift-only、language timeout、workspace、motion failure、tracking error（`tests/test_batch_generator_validation.py:43-171`）。

### 自动化测试和验证

证据包括：

- 上游 G0 数据验证：`robot-arm-episode-data-lab/evidence/upstream/validate_dataset.json:1-...`，30/30 valid，`upstream_gate=batch_generator`。
- batch gate 单元测试：`ros2-arm-teleoperation-suite/tests/test_batch_generator_validation.py:43-171`。
- recorder、teleop、MuJoCo fallback、domain randomizer、quality gate 等测试存在于上游 `tests/` 与各包 `test/` 目录。

### 关键问题、解决方案与边界

| 问题 | 解决方案 | 证据 | 状态 |
| --- | --- | --- | --- |
| Teleop 指令不能直接进入控制器 | 增加 L1 safety monitor 串联 | `docs/ARCHITECTURE_V2.md:16-23` | 文档与代码结构支持 |
| Servo 与 RRT 表述混淆 | 明确 MoveIt Servo 不使用 RRT | `docs/AGENTS.md:29-33` | 已修正文档边界 |
| 训练数据不能依赖 grasp assist | full_system 默认要求训练级批采 `grasp_assist_enabled:false` | `docs/AGENTS.md:65-72` | 文档约束 |
| 上游是否负责训练 | 合同明确不负责 dataset curation/training/downstream replay | `docs/INTER_REPO_CONTRACTS.md:7-14` | 已分仓 |

### 本仓边界

已实现且验证：ROS 2/MuJoCo 软件仿真采集、batch physical gate、recorder 字段输出、上游 G0 30/30 valid。  
已实现但验证不完整：多模态 portfolio media 与完整 30 Hz acceptance 的强证据，需要附原始验证日志。  
当前未实现：真实 Panda 部署、真实 Sim2Real、在线自主策略成功率评估。

候选简历素材：

- 搭建 ROS 2 + MuJoCo Panda 上游采集栈，拆分 teleop、safety、MoveIt Servo、ros2_control、recorder 与 batch generation 职责。
- 设计 batch physical gate，将 lift/place、对象 workspace、motion convergence、gripper close 等检查前置到数据生产端。
- 建立 raw episode contract，输出 `episode_*/train/` 与 `meta.json`，供中游 adapter/release/training 消费。
- 使用 pytest 覆盖 batch validation、teleop、MuJoCo fallback、recorder 等关键路径，并明确软件仿真与实机部署边界。

## 5. robot-arm-episode-data-lab：数据、训练、评估与下游交付

### 项目目标

中游仓负责把上游 raw episode 变成可训练、可评估、可交付下游的稳定数据产物。README 明确当前范围是 adapter、inspection、release、EDA、MLP BC、predicted JSONL、handoff 和 RAG，不声称 real robot、completed Sim2Real 或 online rollout（`README.md:20-23`，`README.md:127-140`）。

### raw episode adapter

`training/adapters/upstream_m6.py` 定义上游 action type 为 `ee_pose_gripper`，派生 action type 为 `ee_delta_gripper`，并记录 `batch_generator` 属于已做 physical validation 的 gate（`training/adapters/upstream_m6.py:12-16`）。adapter 将上游 `observation.state[7] + observation.gripper[1]` 转成 canonical `observation.state[8]`（`upstream_m6.py:63-74`），将 action[8] 转成 `delta_xyz + delta_rpy + gripper`（`upstream_m6.py:77-104`）。

### observation/state/action 语义

Panda schema：

- `observation.state[8]`：`joint_position[7] + gripper_opening[1]`（`configs/robot_schemas/panda.yaml:23-31`）。
- `observation.ee_pose[7]`：position xyz + quaternion xyzw（`panda.yaml:32-39`）。
- `observation.object_pose[7]` 与 `observation.ft[6]`：optional（`panda.yaml:40-55`）。
- `action.ee_delta_gripper[7]`：`delta_xyz[3] + delta_rpy[3] + gripper_cmd[1]`（`panda.yaml:67-77`）。
- 上游兼容 action 为 `ee_pose_gripper[8]`（`panda.yaml:87-95`）。

### schema validation

`inspect_dataset.py` 检查 required/optional fields、language_instruction、success/safety_estop/drive_fault。关键边界：当 `filter_scope=training_split_only` 时，只把 physical gate 已在上游完成作为 warning，并只检查 training split 相关字段，不从 object_pose 重新推断 lift/place（`training/scripts/inspect_dataset.py:303-337`）。

### release

`prepare_dataset_release.py` 先调用 inspect，失败则拒绝创建 release；通过后复制 `frames.jsonl`，写 `inspection_report.json` 和 `manifest.json`（`training/scripts/prepare_dataset_release.py:43-79`）。release manifest 记录 action type、episode/frame 数、filter rules、upstream gate、physical validation、training contract（`prepare_dataset_release.py:95-163`）。

当前 canonical release：

- `data/exports/panda_30_release/manifest.json:2-47`
- `release_id=panda_30_release_v0`
- 30 episodes / 71,737 frames
- `filter_scope=training_split_only`
- `physical_validation_applied=true`
- image scene/wrist 缺失为 warning，不伪装成多模态训练

### EDA 与质量指标

`eda_low_dim_dataset.py` 计算 timestamp cadence、joint step、velocity、joint reversal、action step，并使用 `max_p99_joint_step_rad=0.02` 与 `max_axis_reversal_rate=0.10` 做质量 Gate（`training/scripts/eda_low_dim_dataset.py:22-94`）。

主实验 EDA 证据：`training/reports/panda_30_low_dim_eda.json` 显示 30 episodes / 71,737 frames，quality gate passed，30/30 accepted。另一个 `training/reports/panda_low_dim_eda.json` 只覆盖 3 条，不能作为 30 条主实验指标。

### 线性回归 baseline

`train_act_smoke.py` 文件名含 ACT，但脚本说明明确它实际是 CPU-only 岭回归线性策略，主要用于 CI/smoke、接口读取、schema 校验和 checkpoint 格式检查，并非真正 ACT（`training/scripts/train_act_smoke.py:1-18`）。同口径线性对比保存在 `docs/portfolio/linear_same_split_metrics.json`，使用与 MLP 相同 24/6 episode split。

### MLP Behavior Cloning

MLP 训练脚本使用 PyTorch，从 state 预测 action，支持 `--epochs`、`--batch-size`、`--lr`、`--device auto/cpu/cuda`（`training/scripts/train_mlp_policy.py:26-37`）。它按 episode 做 80/20 split，train-only normalization，避免 frame-level split 泄漏（`train_mlp_policy.py:78-95`，`train_mlp_policy.py:182-206`）。模型结构为两层 hidden dims `[128, 128]` + ReLU + Linear output（`training/policies/mlp_policy.py:19-44`）。训练保存 `mlp_policy.pth`、`mlp_metrics.json`、`scalers.npz`、`split_manifest.json` 和 `feature_contract.yaml`（`train_mlp_policy.py:139-176`）。

CUDA 设备由 `training/device.py` 选择，并记录 torch、CUDA、GPU 名称和显存（`training/device.py:6-31`）。

### offline evaluation 与 predicted action JSONL

当前 canonical evaluation 是离线 MSE/test loss 与 same-split baseline 对比，不等同任务成功率。`replay_mlp_policy.py` 加载 `mlp_policy.pth` 和 `scalers.npz`，对 release 全量 frames 生成 neutral replay JSONL（`training/scripts/replay_mlp_policy.py:39-120`）。

### bridge handoff

`prepare_bridge_handoff.py` 校验 predicted action JSONL 的 robot/schema/action_type/action_dim/finite/timestamp/frame count，并把 replay、dataset manifest、inspection report、replay check、handoff manifest 打包（`training/scripts/prepare_bridge_handoff.py:78-119`，`prepare_bridge_handoff.py:122-180`）。它还检查 gripper range，越界时写 warning，要求 bridge clamp 或 reject（`prepare_bridge_handoff.py:233-244`）。

Canonical handoff：`training/reports/panda_mlp_bc/bridge_handoff/handoff_manifest.json:1-36`，`handoff_id=panda_30_mlp_bridge_v0`，30 episodes / 71,737 actions，status PASS。`replay_check.json:21-32` 记录 3,275 个 gripper commands 超出 `[0, 1]`，没有 errors。

### RAG 项目知识助手

`scripts/rag_assistant.py` 是本地多仓 RAG CLI，读取 `configs/rag_sources.yaml`，按 include/exclude 规则加载三仓文档/代码，Markdown 按标题分块，Python 按 class/function/method 分块（`scripts/rag_assistant.py:47-75`，`scripts/rag_assistant.py:110-187`）。检索实现采用 BM25、symbol exact-match boost 和 source-file boost（`scripts/rag_assistant.py:219-234`）。当前检索已可用；本次调用时后半段 LLM 总结因网络/权限失败，因此本文以直接文件和产物审计为准。

### 自动化测试

中游测试覆盖 schema、adapter、dataset inspection、release、MLP training、replay policy、handoff、EDA、RAG 等，路径包括：

- `tests/test_upstream_m6_adapter.py`
- `tests/test_panda_dataset_inspection.py`
- `tests/test_dataset_release.py`
- `tests/test_train_mlp_policy.py`
- `tests/test_prepare_bridge_handoff.py`
- `tests/test_low_dim_eda.py`
- `tests/test_rag_assistant.py`

### 当前局限

已实现且验证：30 条 release、schema inspection、EDA、MLP BC、same-split linear comparison、predicted JSONL、handoff。  
已实现但验证不完整：LeRobot ACT 脚本存在，但未定位到 canonical 完整 ACT 训练产物。  
smoke/mock：`train_act_smoke.py` 是线性/ridge smoke，不是真 ACT。  
当前未实现：在线自主抓取成功率提升、实机部署、完整 Sim2Real、大规模训练、模型泛化充分验证。

候选简历素材：

- 设计 Panda 数据中游 pipeline，将上游 `state[7]+gripper` 与 `action[8]` 适配为 `state[8] -> ee_delta_gripper[7]` 训练契约。
- 构建 schema validation、release manifest、EDA quality gate 和 handoff manifest，明确上游 physical gate 与中游 training split filter 边界。
- 使用 PyTorch/CUDA 训练低维 MLP BC，并与同 episode split 的线性回归 baseline 比较离线预测误差。
- 生成 `predicted_actions.jsonl` 和 `bridge_handoff/`，将训练输出交付下游 PyBullet replay 与风险验证。

## 6. ros2-moveit-pybullet-bridge：策略重放、监控与风险验证

### 项目目标

下游仓消费中游 `bridge_handoff/`，在 PyBullet 中执行 Panda JSONL replay，输出 replay、monitor 和 risk 结果。README 明确本仓不采集 raw episode、不清洗数据、不训练模型、不执行 real-robot control，也不证明 completed Sim2Real（`ros2-moveit-pybullet-bridge/README.md:3-6`）。

### bridge handoff loader

`panda_handoff.py` 定义 expected format、robot、schema、action type 和 action dim：`panda_bridge_handoff_v0`、`panda`、`panda_ee_delta_gripper_v0`、`ee_delta_gripper`、7（`pybullet_bridge/pybullet_bridge/learning/panda_handoff.py:13-18`）。`load_handoff_bundle` 校验 manifest、replay_check 和 predicted JSONL（`panda_handoff.py:34-72`）。`load_action_jsonl` 校验 JSON、timestamp、action shape、finite values（`panda_handoff.py:75-127`，`panda_handoff.py:140-187`）。测试覆盖 valid bundle、manifest missing、failed replay check、bad shape、wrong robot/schema/action type、NaN（`pybullet_bridge/test/test_panda_handoff.py:46-93`）。

### PandaActionAdapter

`PandaActionAdapter` 将 `ee_delta_gripper[7]` 转成 bridge joint command，支持 `hold`、`mock_ik`、`pybullet_ik`（`pybullet_bridge/pybullet_bridge/learning/panda_action_adapter.py:43-52`）。它校验 action shape/finite、delta_xyz/rpy limits 和 gripper range（`panda_action_adapter.py:244-289`）。`pybullet_ik` 使用 PyBullet IK，并做 Jacobian SVD 奇异性检查（`panda_action_adapter.py:298-366`）。测试覆盖 hold、mock IK、gripper clamp、invalid actions、pybullet_ik、deadband/backlash/velocity/acceleration limit（`pybullet_bridge/test/test_panda_action_adapter.py:9-179`）。

### PolicyRunner

`PolicyRunner` 支持 `panda_jsonl_replay` strategy，要求 `panda_handoff_path`，创建 `JsonlActionReplayPolicy` 与 `PandaActionAdapter`，发布 `/bridge/command`（`pybullet_bridge/pybullet_bridge/learning/policy_runner.py:58-87`，`policy_runner.py:176-227`）。它订阅 `/bridge/sim/joint_states` 与 `/monitor/distribution_metrics`，记录 KL/W1/MMD shift 信息，并通过 health diagnostic 报告 inference latency、stalled/exception/fault（`policy_runner.py:229-380`）。测试覆盖 Panda replay hold/pybullet_ik command、metrics subscription、fault injection stalled health（`pybullet_bridge/test/test_policy_runner_node.py:160-323`）。

### JSONL replay

`JsonlActionReplayPolicy` 从 handoff bundle 或 JSONL 文件顺序 replay Panda actions，支持 loop，并保留 schema/action type/dim（`pybullet_bridge/pybullet_bridge/learning/jsonl_action_replay_policy.py:20-111`）。测试覆盖顺序 replay、hold last frame、reset/loop 和 schema guard（`pybullet_bridge/test/test_jsonl_action_replay_policy.py:45-90`）。

### PyBullet replay 与 benchmark

`scripts/benchmark_system.py` 支持 `--strategy panda_jsonl_replay` 和 `--panda-command-mode hold|mock_ik|pybullet_ik`，输出 latency、resource、health alarm、handoff/release id、timeseries rows、health events（`scripts/benchmark_system.py:439-491`，`scripts/benchmark_system.py:500-520`）。

Latest archived downstream smoke：`robot-arm-episode-data-lab/evidence/downstream/benchmark_summary.json` 显示 1/1 completed，mean/max latency 9.79/34.218 ms，`panda_command_mode=pybullet_ik`，`fault_injection=false`。

### tracking error、KL / W1 / MMD、risk engine

当前下游支持 distribution metrics：KL、Wasserstein-1、MMD，并做 shift detection（`dist_monitor/dist_monitor/metrics_core.py:1-127`）。测试证明 identical stream 近零、offset stream 检出差异（`dist_monitor/test/test_metrics_core.py:18-46`）。Risk aggregator 将 distribution_shift、tracking_error、dynamics_anomaly、comm_health、planning_failure 五维聚合为 R0-R3（`risk_engine/risk_engine/aggregator.py:1-96`），测试覆盖 low/high/critical/missing dimensions（`risk_engine/test/test_aggregator.py:27-64`）。

### nominal / randomized simulation、fault injection、watchdog、E-stop / Hold

已实现证据：PolicyRunner 有 fault injection 参数、watchdog timeout、stalled health；测试覆盖 fault injection stalled health（`policy_runner.py:80-83`，`policy_runner.py:250-333`，`test_policy_runner_node.py:280-323`）。下游 README 与 Current Status 记录 distribution/risk components 为已实现或部分验证（`README.md:19-28`，`docs/CURRENT_STATUS.md:19-34`）。  
当前证据不足：未定位到 canonical 主实验的完整 randomized/fault campaign 原始 JSON；旧 canonical 文档提到 94.399 ms fault alarm，但原始 benchmark summary 未在本次检索中定位。

### downstream feedback

下游 contract 要求对 handoff ambiguity、JSONL schema/action errors、normalization/action distribution issues、policy metadata gaps 回流中游；对 collection quality、frame/quaternion、gripper range、object placement 回流上游（`docs/INTER_REPO_CONTRACTS.md:80-97`）。

### 当前局限

- joint replay 不等于物理抓取成功。
- randomized PyBullet 不等于真实机器人。
- distribution monitoring 不等于已经完成 Sim2Real。
- Legacy iiwa / MoveIt 只能作为历史回归证据。

候选简历素材：

- 实现下游 Panda handoff loader 与 JSONL replay path，校验 manifest、schema、action type、action dim 和 finite action values。
- 构建 `PandaActionAdapter`，将 `ee_delta_gripper[7]` 转为 PyBullet/bridge joint command，并加入 action limit、gripper range、deadband/backlash/velocity/acceleration 保护。
- 使用 PolicyRunner 与 benchmark CLI 对 handoff replay 做 1-episode smoke，输出 latency、health、handoff/release id 等可追溯结果。
- 集成 KL/W1/MMD distribution metrics 与 risk aggregation，为 replay drift、fault 和 monitor 反馈提供结构化证据。

## 7. Canonical Experiment

### 实验目标

本实验 `panda_30_mlp_20260711` 主要验证：

- 上游 MuJoCo episode 到中游 release 的数据链路是否贯通。
- MLP BC 训练流程是否可用。
- 是否能生成标准化 predicted action JSONL。
- 是否能打包 handoff 并交付下游 replay/benchmark。

### 实验数据

| 字段 | 当前事实 | 证据 |
| --- | --- | --- |
| 数据来源 | 上游 `ros2-arm-teleoperation-suite` MuJoCo batch generation，不是实机数据，不是 mock | `evidence/upstream/validate_dataset.json:1-...`，`evidence/meta/run_summary.json:1-27` |
| episode 数 | 30 | `data/exports/panda_30_release/manifest.json:26` |
| frame 数 | 71,737 | `data/exports/panda_30_release/manifest.json:27` |
| G0 Gate | 30/30 valid，`upstream_gate=batch_generator` | `evidence/upstream/validate_dataset.json` |
| observation 维度 | `observation.state[8]`，`ee_pose[7]`，object_pose/ft optional present，images missing warning | `data/exports/panda_30_release/inspection_report.json`，`manifest.json:20-24` |
| action 语义 | `ee_delta_gripper[7]` | `configs/robot_schemas/panda.yaml:67-77`，`manifest.json:2` |
| 质量 Gate | 30/30 accepted，joint step P99 / reversal thresholds passed | `training/reports/panda_30_low_dim_eda.json` |

### 模型与训练

| 项 | 当前事实 | 证据 |
| --- | --- | --- |
| Linear Regression baseline | Ridge/linear same episode split normalized MSE | `docs/portfolio/linear_same_split_metrics.json` |
| MLP BC | 2 hidden layers `[128,128]`，ReLU，state -> action | `training/policies/mlp_policy.py:23-44` |
| Framework | PyTorch | `training/scripts/train_mlp_policy.py:51-53` |
| 训练设备 | CUDA，NVIDIA RTX PRO 500 Blackwell Generation Laptop GPU | `training/reports/panda_mlp_bc/mlp_metrics.json:46-54` |
| Epoch | 100 | `mlp_metrics.json:2-3` |
| Batch size | 脚本默认 32；canonical metrics 未直接记录 batch size，当前证据不足确认实际命令是否显式覆盖 | `training/scripts/train_mlp_policy.py:31-33` |
| Optimizer | Adam | `training/scripts/train_mlp_policy.py:115` |
| Learning rate | 0.001 | `mlp_metrics.json:4` |
| Checkpoint | `training/reports/panda_mlp_bc/mlp_policy.pth` | 文件存在；保存逻辑见 `train_mlp_policy.py:139-142` |
| 数据划分 | 24 train episodes / 6 test episodes，57,364 train frames / 14,373 test frames | `mlp_metrics.json:7-45` |

### 结果

| 模型 | 数据划分 | 指标 | 结果 | 证据路径 |
| --- | --- | --- | --- | --- |
| MLP BC | 24 train / 6 test episodes | train normalized MSE | 0.049142921178624864 | `training/reports/panda_mlp_bc/mlp_metrics.json:5` |
| MLP BC | 24 train / 6 test episodes | test normalized MSE | 0.2350177516977917 | `training/reports/panda_mlp_bc/mlp_metrics.json:6` |
| Linear ridge baseline | same 24/6 episode split | train normalized MSE | 0.5580591706337537 | `docs/portfolio/linear_same_split_metrics.json` |
| Linear ridge baseline | same 24/6 episode split | test normalized MSE | 0.5800455135789114 | `docs/portfolio/linear_same_split_metrics.json` |
| Downstream smoke | 1 episode | mean/max latency | 9.79 / 34.218 ms | `evidence/downstream/benchmark_summary.json` |

### 结论

在相同的小规模数据集、数据划分和离线评估口径下，MLP BC 获得了低于线性回归基线的动作预测误差，说明非线性模型对当前状态到动作映射具有更强拟合能力。

边界必须同时保留：

该结果不能直接证明在线抓取成功率、跨场景泛化能力或实机部署效果。MLP test loss 约为 train loss 的 4.78 倍，说明小数据泛化仍是主要风险。

### 下游交付

中游生成 `training/reports/panda_mlp_bc/predicted_actions.jsonl`，随后打包为 `training/reports/panda_mlp_bc/bridge_handoff/`。handoff manifest 声明 first consumer 为 `JsonlActionReplayPolicy`，runtime owner 为下游（`handoff_manifest.json:4-16`）。下游通过 `panda_jsonl_replay` + `pybullet_ik` 完成 latest archived 1-episode smoke（`evidence/downstream/benchmark_summary.json`）。

## 8. 项目中体现的工程能力

### 系统架构

- 三仓拆分：上游采集与控制，中游数据与训练，下游执行验证。
- 职责边界：Gate、schema、training、handoff、replay 的 owner 清晰。
- 数据和控制流：从 ROS 2 topic 到 episode，从 JSONL 到 PyBullet command。
- 跨仓接口：`INTER_REPO_CONTRACTS.md`、manifest、handoff bundle、feedback templates。

### 数据工程

- episode schema：Panda state/action/observation contract。
- adapter：`state[7]+gripper -> state[8]`，`action[8] -> ee_delta_gripper[7]`。
- validation：required/optional fields、success、safety_estop、drive_fault。
- release：不可变 release manifest、inspection report、training contract。
- 数据质量 Gate：上游 physical gate，中游 EDA joint step P99/reversal gate。

### 机器人系统

- ROS 2：topic、node、launch、PolicyRunner。
- MuJoCo：上游 Panda 软件仿真与 raw episode 生产。
- PyBullet：下游 replay 与 IK。
- MoveIt Servo：上游笛卡尔伺服，不混作 RRT。
- ros2_control：控制器与 hardware interface 框架。
- 机械臂状态与动作：joint state、ee pose、object pose、FT、gripper、ee delta action。

### 机器学习与深度学习

- EDA：timestamp、joint step、velocity、reversal、action distribution。
- baseline：线性/ridge，同 split 对比。
- MLP BC：PyTorch 两层 MLP，state -> action。
- CUDA：自动选择并记录 GPU。
- offline evaluation：train/test normalized MSE。
- 边界：小样本、过拟合风险、离线 loss 不等同在线任务成功率。

### 测试与验证

- pytest：adapter、schema、release、MLP、handoff、RAG、downstream loader/adapter/policy/risk。
- contract test：handoff loader 与 JSONL schema guard。
- benchmark：`benchmark_system.py` 输出 summary/timeseries/health。
- fault injection：PolicyRunner stalled health 测试。
- replay：Panda JSONL replay + PyBullet IK smoke。
- tracking/risk：KL/W1/MMD 与 risk aggregation。

### AI 应用

- RAG：本地多仓项目助手，读取三仓文档和代码。
- 文档分块：Markdown 按标题，Python 按 class/function/method。
- 检索：BM25、symbol boost、source-file boost。
- 引用溯源：每条回答要求给仓库、路径、函数/字段、行号。
- 事实与通用知识区分：AGENTS 规定必须检索项目事实，不能用行业惯例补全。
- 当前状态：本地检索可用；本次 LLM 总结阶段因网络/权限失败，文档以直接证据为准。

### 工程管理

- 项目取舍：先小闭环，再扩展 ACT、RL、实机。
- 范围控制：上中下游职责不重复实现。
- Legacy 与主线分离：KUKA/iiwa/旧 PyBullet 不抢占 Panda 主线。
- 证据管理：manifest、metrics、benchmark、commit hash、evidence registry。
- 文档与代码一致性：发现 README 路径和 canonical fault 数字需要同步。

## 9. 关键难点与排障案例

| 案例 | 问题现象 | 初始判断 | 根因 | 修改内容 | 验证方法 | 结果 | 经验总结 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| state/action 语义不一致 | 上游 `state[7]` 与训练 schema `state[8]` 不一致；上游 `action[8]` 不等于训练 `action[7]` | 可能在训练脚本里临时截断 | 应由中游 adapter 显式转换 | `upstream_m6.py` 增加 state/gripper 合并与 ee delta action 派生 | `tests/test_upstream_m6_adapter.py`，schema manifest | release 记录 `state_dim=8`、`action_dim=7` | 语义转换必须显式写进 adapter 和 manifest |
| 上游 Gate 与中游 validation 冲突 | 中游可能重复用 object_pose 判断物理成功 | 以为检查越多越安全 | lift/place 判定属于上游 physical gate | `filter_scope=training_split_only` 只检查 schema/success/safety/drive fault | `inspect_dataset.py:303-337`，`AGENTS.md:82-84` | 避免中游重判物理成败 | Gate owner 必须唯一 |
| Panda 与 Legacy KUKA 混用风险 | 老 GIF、`agents/`、`core/` 容易被误写成 Panda 主线 | 历史资产可复用 | 机器人、schema、任务线不同 | AGENTS/README 标记 Legacy 分流 | `AGENTS.md:19`，`README.md:142-144` | 当前主线只写 Panda release/training/handoff | 作品集要区分历史演进与当前证据 |
| MLP 输入维度适配 | MLP 训练需要稳定输入输出维度 | 可能由数据决定 | release contract 是训练入口 | 训练脚本从 manifest 读取 `training_contract` | `train_mlp_policy.py:69-76` | metrics 记录 `state_dim=8`、`action_dim=7` | 模型不应猜 schema |
| CUDA device 迁移 | CPU/GPU 环境不同，训练不可复现 | 只记录 loss 不够 | device 选择没有统一记录 | `training/device.py` 记录 selected、torch、CUDA、GPU | `mlp_metrics.json:46-54` | canonical 记录 CUDA 与 GPU | 训练产物需要记录运行环境 |
| prediction JSONL 与下游契约 | 下游 replay 需要 stable JSONL | 只输出 action array 不够 | 缺 robot/schema/action_type/release/task 等 guard | `replay_mlp_policy.py` 与 `prepare_bridge_handoff.py` 输出/校验 replay row | `test_prepare_bridge_handoff.py`，下游 `test_panda_handoff.py` | handoff PASS，但 gripper warning 保留 | 下游执行前必须 fail-fast |
| README 与实际代码不一致 | 下游 README code map 写 `pybullet_bridge/control/...` | 文档路径可能旧 | 实际源码在 `pybullet_bridge/pybullet_bridge/learning/...` | 本次只记录冲突，不修改 README | `rg --files` 与 README 对照 | 建议后续同步 | 作品集母版要优先代码路径 |
| 离线指标与在线任务结论边界 | MLP loss 低于 linear 容易被说成成功率提升 | 指标好看但不是 rollout | offline MSE 不等于物理抓取成功 | 文档中强制加边界声明 | `CANONICAL_EXPERIMENT.md:56-64`，`README.md:20-23` | 结论限制为拟合能力 | 项目可信度来自边界清楚 |
| RAG 根据行业经验补全事实 | 项目问答容易被通用知识污染 | 需要本地证据优先 | 通用回答无法说明当前实现 | AGENTS 要求调用 RAG 并区分事实类别 | `AGENTS.md:111-140`，`scripts/rag_assistant.py` | 本次 RAG 检索已调用，LLM 总结失败时改用直接审计 | AI 辅助也要有事实审查 |

## 10. 项目取舍

| 选择 | 原因 | 替代方案 | 为什么暂缓 |
| --- | --- | --- | --- |
| 先做 MLP BC，不直接做 ACT | 小规模低维数据更适合先验证数据、训练、handoff 链路 | LeRobot ACT / Diffusion Policy | ACT 需要更完整数据、环境和运行证据；当前未定位 canonical ACT 产物 |
| 先用 30 条小规模数据验证闭环 | 30 条足够暴露 schema、Gate、split、handoff、replay 问题 | 直接大规模采集 | 大规模前先确认接口稳定，避免批量产出错误数据 |
| 先做 offline evaluation | 离线 MSE 可快速验证 state-action 拟合与训练代码 | 直接 online rollout | online rollout 涉及控制、场景、物理成败和安全边界，不能由 loss 代替 |
| 不把 loss 等同任务成功率 | loss 衡量动作预测误差，不衡量抓取物理成功 | 宣称成功率提升 | 当前没有在线抓取成功率评测 |
| 暂缓强化学习 | 当前项目重点是数据闭环与验证，不是探索式策略优化 | RL | RL 需要环境 reward、稳定 rollout 和大量实验预算 |
| 暂缓实机 Sim2Real | 当前证据是软件仿真与 readiness | 真实 Panda 硬件验证 | 没有真实机械臂、安全验收和长期运行证据 |
| 不继续扩展更多仿真平台 | 先确保 MuJoCo -> 中游 -> PyBullet 的双仿真闭环稳定 | Isaac/Gazebo/更多后端 | 新平台会扩大接口维护成本 |
| 主线与 Legacy 分开 | Panda schema/action 与 KUKA/iiwa 历史实验不同 | 混合展示所有资产 | 混用会破坏作品集可信度 |

## 11. 作品集证据索引

| 能力/结论 | 证据文件 | 图片/报告 | 测试 | 可证明 | 不可证明 |
| --- | --- | --- | --- | --- | --- |
| 上游数据采集 | `evidence/upstream/validate_dataset.json`，`ros2-arm-teleoperation-suite/src/lerobot_recorder/lerobot_recorder/recorder_node.py` | `ros2-arm-teleoperation-suite/media/panda_teleop_trajectories_3d.png` | `ros2-arm-teleoperation-suite/tests/test_batch_generator_validation.py` | MuJoCo batch 30/30 valid，recorder 字段 | 实机数据采集 |
| 上游 physical gate | `ros2-arm-teleoperation-suite/src/synth_data_gen/synth_data_gen/batch_generator.py:933-1019` | `evidence/upstream/validate_dataset.json` | `tests/test_batch_generator_validation.py` | lift/place/workspace/motion gate | 下游物理抓取成功 |
| 中游 EDA | `training/reports/panda_30_low_dim_eda.json` | `assets/diagrams/eda_joint_step_p99_gate.png`，`assets/diagrams/eda_joint_reversals_distribution.png` | `tests/test_low_dim_eda.py` | 30 条 low-dim 质量 Gate | 泛化能力 |
| MLP 训练 | `training/reports/panda_mlp_bc/mlp_metrics.json`，`training/reports/panda_mlp_bc/mlp_policy.pth` | `assets/diagrams/mlp_bc_loss_comparison.png` | `tests/test_train_mlp_policy.py` | PyTorch/CUDA MLP BC 可训练 | 在线成功率 |
| baseline 对比 | `docs/portfolio/linear_same_split_metrics.json` | `assets/diagrams/mlp_bc_loss_comparison.png` | 相关计算产物，未定位专门测试 | 同 split 下 MLP test MSE 低于 linear | 任务成功率提升 |
| predicted action | `training/reports/panda_mlp_bc/predicted_actions.jsonl` | 无需图片 | `tests/test_replay_policy.py`，`tests/test_prepare_bridge_handoff.py` | 生成可校验 JSONL | 物理执行成功 |
| handoff | `training/reports/panda_mlp_bc/bridge_handoff/handoff_manifest.json`，`replay_check.json` | `assets/screenshots/bridge_handoff_bundle.png` | `tests/test_prepare_bridge_handoff.py` | 下游契约 PASS，71,737 actions | gripper range 已自动修复 |
| 下游 replay | `evidence/downstream/benchmark_summary.json` | 下游 `docs/assets/panda_replay_control_latency.png` 如与 JSON 对齐 | `pybullet_bridge/test/test_jsonl_action_replay_policy.py`，`test_policy_runner_node.py` | 1-episode PyBullet replay smoke | 真实机器人控制 |
| drift/risk | `dist_monitor/dist_monitor/metrics_core.py`，`risk_engine/risk_engine/aggregator.py` | 下游 distribution/risk 图如与数据对齐 | `dist_monitor/test/test_metrics_core.py`，`risk_engine/test/test_aggregator.py` | KL/W1/MMD 与 risk aggregation 实现 | completed Sim2Real |
| RAG | `scripts/rag_assistant.py`，`configs/rag_sources.yaml` | 无 | `tests/test_rag_assistant.py` | 本地多仓检索、BM25 分块 | LLM 总结始终可用 |
| CI 和测试 | 三仓 `tests/` 与 package tests | CI badge 只代表 GitHub workflow 状态 | 多个 pytest 文件 | 关键逻辑有自动化覆盖 | 长期稳定性 |

## 12. 面试话术

### 30 秒版本

这个项目是一个 Panda 机械臂三仓软件闭环。上游用 ROS 2 和 MuJoCo 做遥操作、批采、控制、安全和 raw episode 录制；中游做 schema 适配、release、EDA、MLP BC、离线评估和 handoff；下游消费 handoff，在 PyBullet 里做 JSONL replay、监控和风险验证。当前主实验用 30 条 MuJoCo 批采 episode 跑通了 71,737 frames 的 release、MLP 训练、predicted action 和下游 replay smoke，但我不会把它说成实机 Sim2Real 或在线抓取成功率。

### 3 分钟版本

我做这个项目是因为机器人 Demo 很容易只展示“机械臂动了”，但面试里更重要的是证明系统边界、数据契约和验证链路。于是我把它拆成三个仓库。上游负责 ROS 2/MuJoCo 的控制与采集，包括 safety monitor、MoveIt Servo、ros2_control、batch generator 和 recorder，并在上游完成 physical gate。中游负责把 raw episode 变成稳定训练数据：adapter 明确把 `state[7]+gripper` 转成 `state[8]`，把 `action[8]` 转成 `ee_delta_gripper[7]`，然后做 schema validation、release、EDA、MLP BC 和 handoff。下游负责加载 handoff，用 PandaActionAdapter 把 JSONL action 转成 PyBullet joint command，并输出 benchmark 和风险监控结果。

当前 canonical experiment 是 30 条 Panda MuJoCo 批采 episode，共 71,737 frames。MLP BC 用 24 条训练、6 条测试，100 epochs，CUDA 训练。在同一 episode split 下，MLP test normalized MSE 是 0.2350，线性 baseline 是 0.5800。这个结果说明非线性模型对当前状态到动作映射拟合更好，但不说明在线抓取成功率或实机效果。下游 smoke 证明 handoff 可以被 replay path 消费，latest archived run 是 1/1 episode completed，mean/max latency 9.79/34.218 ms。

项目里我最重视的是诚实边界：Gate 归上游，中游不重判物理成功；离线 loss 不等于任务成功率；PyBullet replay 不等于真实机器人；Legacy KUKA/iiwa 不和 Panda 主线混用。

### 10 分钟版本

1. 背景：机械臂项目需要同时管理控制、数据、训练、执行验证和风险反馈。单仓 Demo 容易把职责混在一起，所以我做了三仓闭环。
2. 上游：`ros2-arm-teleoperation-suite` 是 ROS 2/MuJoCo Panda 采集与控制栈。L0 输入，L1 safety，L2 MoveIt Servo，L3 ros2_control，L5 MuJoCo，L7 recorder。batch_generator 负责 FSM 和 physical gate，recorder 写 episode 与 `meta.json`。
3. 中游：`robot-arm-episode-data-lab` 是数据与训练仓。它不控制机器人，只做 adapter、schema、release、EDA、MLP BC、baseline、predicted JSONL、handoff 和 RAG。关键是 action/state 语义透明，manifest 写清 filter scope 与 training contract。
4. 下游：`ros2-moveit-pybullet-bridge` 是 replay 和验证仓。它 load handoff，校验 JSONL，用 `panda_jsonl_replay` 和 `PandaActionAdapter` 在 PyBullet 中执行，并接入 KL/W1/MMD 与 risk aggregation。
5. 实验结果：30 episodes / 71,737 frames，G0 30/30 valid，release PASS，MLP 100 epochs，MLP test MSE 0.2350，linear same split test MSE 0.5800，handoff 71,737 actions PASS，latest downstream smoke 1/1 completed。
6. 难点：state/action 语义不一致、Gate owner 冲突、gripper command 越界 warning、README 与代码路径不一致、RAG 不能用通用知识补项目事实。
7. 局限：没有实机、没有完整 Sim2Real、没有在线 rollout 成功率、没有大规模数据和 ACT canonical 结果。
8. 下一步：扩大数据、补齐 image/tactile modalities、正式 ACT/LeRobot 训练、下游更完整 fault/randomized campaign、最终在有真实硬件条件时做安全可控的 Sim2Real 验证。

## 13. 高频技术追问

1. 为什么要三仓拆分？  
答：因为采集控制、数据训练、执行验证的职责和失败模式不同。三仓让 Gate、schema、handoff 和 replay owner 清楚，避免一个仓库既改数据又改执行导致证据不可信。

2. state 和 observation 有什么区别？  
答：当前训练用的核心 state 是 `observation.state[8]`，即 7 个 Panda joint positions 加 1 个 gripper opening。observation 还可包含 ee_pose、object_pose、FT、images 等更广义观测。

3. action 是什么？  
答：中游和下游主线 action 是 `ee_delta_gripper[7]`：末端 `delta_xyz[3] + delta_rpy[3] + gripper_cmd[1]`。

4. 上游 action[8] 为什么要转？  
答：上游 recorder action 是目标 ee pose + gripper，训练/下游 replay 约定需要 ee delta + gripper。这个语义转换放在中游 adapter，不能让下游静默截断。

5. BC 学到的是什么？  
答：当前 MLP BC 学的是低维 `state[8]` 到 `ee_delta_gripper[7]` 的监督映射，不是在线规划器，也不是自主任务策略完整闭环。

6. 为什么 MLP 比线性回归好？  
答：在同 24/6 episode split 与 normalized MSE 口径下，MLP test 0.2350 低于 linear 0.5800，说明非线性映射拟合当前数据更强。

7. 30 条数据是否过少？  
答：对证明泛化确实过少；对验证 schema、release、training、handoff、replay 的工程闭环是有价值的小规模起点。

8. 100 epochs 是什么意思？  
答：训练脚本对 train split 遍历 100 轮优化 MSE。它不是 100 次任务执行，也不是 100 次在线 rollout。

9. 什么是 CUDA？  
答：这里指 PyTorch 使用 NVIDIA GPU 加速训练。metrics 记录 selected=cuda、torch CUDA version 和 GPU 型号。

10. loss 下降说明什么？  
答：说明模型在离线数据上的动作预测误差降低。它不能直接说明抓取成功率提升。

11. 为什么不能代表抓取成功？  
答：抓取成功涉及环境状态、接触、控制稳定性、误差累积和闭环反馈；当前指标只是单步/逐帧动作预测误差。

12. offline evaluation 与 online rollout 区别？  
答：offline evaluation 在已有数据上比较预测动作和记录动作；online rollout 是策略真的控制仿真或机器人完成任务。

13. replay 与 handoff 区别？  
答：handoff 是中游交付包，含 manifest、predicted JSONL、inspection、replay check；replay 是下游消费这个包并执行动作流。

14. Gate 为什么放在上游？  
答：lift/place 成败依赖物理执行和对象状态，发生在 MuJoCo/batch_generator 侧。中游只拿离线数据，不应重新推断物理成功。

15. 中游为什么不重新判断物理成功？  
答：避免重复 owner 和不一致判定。`filter_scope=training_split_only` 明确中游只检查 schema、success、safety_estop、drive_fault。

16. 下游为什么还要 action adapter？  
答：handoff action 是任务空间 delta，下游执行需要 joint command。PandaActionAdapter 做 action limit、gripper range、IK/hold/mock conversion。

17. 什么是 KL/W1/MMD？  
答：本项目中它们是下游 distribution monitor 的漂移指标，用于比较对齐后的状态/误差分布，不等于 Sim2Real 已完成。

18. 当前是不是具身 Agent？  
答：可以说是具身工程闭环的雏形，包含数据、策略和仿真执行验证；但不是稳定在线自主抓取 Agent。

19. 当前是否完成 Sim2Real？  
答：没有。当前是 Sim2Sim 与 Sim2Real-readiness，未完成真实机器人验证。

20. AI 在项目中承担了什么？  
答：Codex/生成式 AI 可用于辅助开发、审计、文档和 RAG，但项目价值要落到候选人的架构、取舍、验证和事实审查上。

21. 如何证明项目是自己做的？  
答：可以讲清三仓职责、关键代码路径、manifest 字段、实验 ID、loss 口径、handoff warning、事实冲突和下一步限制；这些细节不是只看 README 能背出来的。

22. ACT 完成了吗？  
答：当前证据不足以确认 canonical ACT 正式实验完成。`train_act_smoke.py` 是线性 smoke，`train_act_lerobot.py` 是代码路径但非主实验产物。

23. 为什么不用强化学习？  
答：当前目标是打通数据和验证闭环。RL 需要 reward、稳定 rollout 和更多实验预算，先暂缓。

24. gripper warning 是什么？  
答：handoff replay check 发现 3,275 个 gripper command 超出 `[0,1]`，下游执行前必须 clamp 或 reject。

25. images 缺失会影响什么？  
答：canonical MLP 是 low-dimensional baseline，没有使用 scene/wrist/tactile image。image 缺失作为 warning 记录，不能写成多模态训练。

26. 为什么下游 replay 不等于抓取？  
答：replay 验证动作流能被加载、适配并在 PyBullet 中执行；物体接触、抓取成功和任务完成需要额外物理评估。

27. latest downstream smoke 能证明什么？  
答：证明 latest archived handoff replay path 完成了 1 个 episode，并输出 latency/health summary。不能证明长期稳定或 fault campaign。

28. README 与代码冲突怎么办？  
答：按项目规则优先采用测试和代码，并在作品集母版记录冲突，后续再同步 README。

29. RAG 为什么重要？  
答：它降低三仓事实遗忘和跨仓接口误读风险，要求回答项目前先检索代码、测试、schema 和文档。

30. 这个项目最能体现什么能力？  
答：系统边界拆分、接口契约设计、数据质量治理、训练验证闭环、风险监控和诚实表达实验边界。

## 14. HR 视角说明

这个项目不是普通教程 Demo，因为它不是只展示一个机械臂动画，而是把机器人项目中容易混乱的采集、数据、训练、交付、执行验证和风险反馈拆成了可追溯的工程链路。每个仓库都有明确输入、输出和不负责事项，核心实验也有 manifest、metrics、handoff、benchmark 和 commit 证据。

它证明的可迁移能力包括：复杂系统拆解、跨模块接口管理、数据质量意识、测试验证意识、风险边界表达、文档和证据管理、使用 AI 辅助但不放弃事实审计。

更适合的岗位：机器人系统集成、测试验证、应用开发、具身数据/训练工程、技术交付。暂时不建议定位纯算法研究岗，因为当前贡献重点不是提出新算法，而是把数据、训练和执行验证串成可信闭环。

个人项目与公司项目的区别：这个项目没有真实客户现场、没有商业交付、没有生产环境 SLA，也没有真实硬件安全验收。进入公司后最希望补充真实机器人硬件调试、现场约束、团队协作流程、长期稳定性验证和真实业务需求下的交付经验。

## 15. 简历素材库

### 4 条完整版项目描述

1. 设计并实现 Panda 机械臂三仓软件闭环：上游 ROS 2/MuJoCo 负责 batch/teleop 采集与 physical gate，中游负责 schema/release/MLP BC/handoff，下游负责 PyBullet replay、monitor 和 risk benchmark。
2. 构建中游 Panda 数据管线，将上游 `state[7]+gripper` 与 `action[8]` 显式适配为 `state[8] -> ee_delta_gripper[7]`，并通过 schema validation、release manifest、EDA Gate 和 handoff check 管理数据质量。
3. 在 30 条 MuJoCo 批采 episode、71,737 frames 上训练低维 MLP Behavior Cloning，使用 CUDA/PyTorch、24/6 episode split，并与同 split 线性 baseline 对比离线 normalized MSE。
4. 打通 predicted action JSONL 到下游 `bridge_handoff/` 与 Panda PyBullet replay，结合 handoff loader、PandaActionAdapter、PolicyRunner、KL/W1/MMD 和 risk aggregation 输出可追溯 replay smoke 证据。

### 3 条精简版项目描述

1. 搭建 Panda 三仓 Sim2Sim 闭环，覆盖 ROS 2/MuJoCo 采集、中游 MLP BC 训练和 PyBullet replay 验证。
2. 设计 `state[8] -> ee_delta_gripper[7]` 数据契约、release manifest 和 bridge handoff，避免上下游 action 语义漂移。
3. 用 30 episodes / 71,737 frames 完成 MLP vs linear offline evaluation，并明确不把 loss 写成在线成功率。

### 1 句话项目概述

一个围绕 Franka Panda 的三仓机器人软件闭环项目，用 ROS 2/MuJoCo 采集数据，用中游训练和 handoff 交付动作，用 PyBullet replay 与风险监控验证执行链路。

### 技术栈

ROS 2 Jazzy、MuJoCo、MoveIt Servo、ros2_control、PyBullet、Python、PyTorch、CUDA、NumPy、pytest、JSONL、YAML/manifest、BM25 RAG。

### 项目关键词

Panda arm、ROS 2、MuJoCo、PyBullet、Behavior Cloning、MLP、dataset release、schema validation、handoff、PolicyRunner、risk monitoring、Sim2Sim、Sim2Real-readiness。

### 面向系统集成岗位版本

重点写三仓架构、ROS 2 topic/control chain、MoveIt Servo、ros2_control、MuJoCo/PyBullet 桥接、接口契约、handoff 和 feedback routing。

### 面向测试验证岗位版本

重点写 Gate、schema validation、pytest、EDA quality gate、replay check、benchmark summary、fault injection、risk aggregation 和证据边界。

### 面向具身数据/训练工程岗位版本

重点写 raw episode adapter、state/action contract、release、split、baseline、MLP BC、CUDA training、offline metrics、predicted action JSONL 和小样本限制。

## 16. 项目边界与诚实声明

当前未完成或证据不足的内容：

- 大规模训练数据：当前 canonical 是 30 episodes / 71,737 frames。
- 在线策略 rollout：未定位到主实验在线策略控制任务成功证据。
- 在线抓取成功率评测：没有任务成功率统计。
- ACT 正式实验：代码路径存在，但 canonical 完整训练产物证据不足。
- 强化学习：未实现为当前主线。
- 实机机械臂：当前项目证据不足，无法确认。
- 真实 Sim2Real：当前只能写 Sim2Sim / Sim2Real-readiness。
- 长期稳定性和生产环境验证：没有长期运行或现场证据。
- 商业客户现场交付：这是个人项目，不是公司客户项目。

这些限制不影响当前作品集作为“最小工程闭环”的价值，因为它已经证明了从数据生产、数据治理、模型训练、动作交付到下游 replay 验证的关键接口能被打通，并且每个结论都有代码、测试或产物边界。

## 附录：本次事实审计记录

### 引用过的代码、测试、配置和证据路径清单

上游：

- `ros2-arm-teleoperation-suite/README.md`
- `ros2-arm-teleoperation-suite/docs/AGENTS.md`
- `ros2-arm-teleoperation-suite/docs/ARCHITECTURE_V2.md`
- `ros2-arm-teleoperation-suite/docs/PROJECT_SCOPE_AND_ACCEPTANCE.md`
- `ros2-arm-teleoperation-suite/docs/INTER_REPO_CONTRACTS.md`
- `ros2-arm-teleoperation-suite/src/synth_data_gen/synth_data_gen/batch_generator.py`
- `ros2-arm-teleoperation-suite/src/lerobot_recorder/lerobot_recorder/recorder_node.py`
- `ros2-arm-teleoperation-suite/tests/test_batch_generator_validation.py`

中游：

- `robot-arm-episode-data-lab/README.md`
- `robot-arm-episode-data-lab/AGENTS.md`
- `robot-arm-episode-data-lab/docs/CLOSED_LOOP_RUNBOOK.md`
- `robot-arm-episode-data-lab/training/README_TRAINING.md`
- `robot-arm-episode-data-lab/configs/robot_schemas/panda.yaml`
- `robot-arm-episode-data-lab/training/adapters/upstream_m6.py`
- `robot-arm-episode-data-lab/training/scripts/inspect_dataset.py`
- `robot-arm-episode-data-lab/training/scripts/prepare_dataset_release.py`
- `robot-arm-episode-data-lab/training/scripts/eda_low_dim_dataset.py`
- `robot-arm-episode-data-lab/training/scripts/train_act_smoke.py`
- `robot-arm-episode-data-lab/training/scripts/train_mlp_policy.py`
- `robot-arm-episode-data-lab/training/policies/mlp_policy.py`
- `robot-arm-episode-data-lab/training/device.py`
- `robot-arm-episode-data-lab/training/scripts/replay_mlp_policy.py`
- `robot-arm-episode-data-lab/training/scripts/prepare_bridge_handoff.py`
- `robot-arm-episode-data-lab/scripts/rag_assistant.py`
- `robot-arm-episode-data-lab/data/exports/panda_30_release/manifest.json`
- `robot-arm-episode-data-lab/data/exports/panda_30_release/inspection_report.json`
- `robot-arm-episode-data-lab/training/reports/panda_30_low_dim_eda.json`
- `robot-arm-episode-data-lab/training/reports/panda_mlp_bc/mlp_metrics.json`
- `robot-arm-episode-data-lab/docs/portfolio/linear_same_split_metrics.json`
- `robot-arm-episode-data-lab/training/reports/panda_mlp_bc/bridge_handoff/handoff_manifest.json`
- `robot-arm-episode-data-lab/training/reports/panda_mlp_bc/bridge_handoff/replay_check.json`
- `robot-arm-episode-data-lab/evidence/upstream/validate_dataset.json`
- `robot-arm-episode-data-lab/evidence/downstream/benchmark_summary.json`
- `robot-arm-episode-data-lab/evidence/meta/run_summary.json`
- `robot-arm-episode-data-lab/evidence/meta/three_repo_commits.txt`
- `robot-arm-episode-data-lab/tests/test_upstream_m6_adapter.py`
- `robot-arm-episode-data-lab/tests/test_panda_dataset_inspection.py`
- `robot-arm-episode-data-lab/tests/test_dataset_release.py`
- `robot-arm-episode-data-lab/tests/test_train_mlp_policy.py`
- `robot-arm-episode-data-lab/tests/test_prepare_bridge_handoff.py`
- `robot-arm-episode-data-lab/tests/test_low_dim_eda.py`
- `robot-arm-episode-data-lab/tests/test_rag_assistant.py`

下游：

- `ros2-moveit-pybullet-bridge/README.md`
- `ros2-moveit-pybullet-bridge/docs/AGENTS.md`
- `ros2-moveit-pybullet-bridge/docs/INTER_REPO_CONTRACTS.md`
- `ros2-moveit-pybullet-bridge/docs/CURRENT_STATUS.md`
- `ros2-moveit-pybullet-bridge/pybullet_bridge/pybullet_bridge/learning/panda_handoff.py`
- `ros2-moveit-pybullet-bridge/pybullet_bridge/pybullet_bridge/learning/jsonl_action_replay_policy.py`
- `ros2-moveit-pybullet-bridge/pybullet_bridge/pybullet_bridge/learning/panda_action_adapter.py`
- `ros2-moveit-pybullet-bridge/pybullet_bridge/pybullet_bridge/learning/policy_runner.py`
- `ros2-moveit-pybullet-bridge/pybullet_bridge/pybullet_bridge/sensor_fusion_node.py`
- `ros2-moveit-pybullet-bridge/dist_monitor/dist_monitor/metrics_core.py`
- `ros2-moveit-pybullet-bridge/risk_engine/risk_engine/aggregator.py`
- `ros2-moveit-pybullet-bridge/scripts/benchmark_system.py`
- `ros2-moveit-pybullet-bridge/pybullet_bridge/test/test_panda_handoff.py`
- `ros2-moveit-pybullet-bridge/pybullet_bridge/test/test_jsonl_action_replay_policy.py`
- `ros2-moveit-pybullet-bridge/pybullet_bridge/test/test_panda_action_adapter.py`
- `ros2-moveit-pybullet-bridge/pybullet_bridge/test/test_policy_runner_node.py`
- `ros2-moveit-pybullet-bridge/dist_monitor/test/test_metrics_core.py`
- `ros2-moveit-pybullet-bridge/risk_engine/test/test_aggregator.py`

### 发现的项目事实冲突

| 冲突 | 当前处理 |
| --- | --- |
| `docs/portfolio/CANONICAL_EXPERIMENT.md` 提到 normal mean/max 17.626/49.508 ms 与 fault alarm 94.399 ms，但 latest archived `evidence/downstream/benchmark_summary.json` 是 mean/max 9.79/34.218 ms，且 `fault_injection=false` | 本文采用 latest archived JSON 作下游 smoke headline；旧 fault 数字只作为“原始 JSON 未定位”的冲突记录 |
| 下游 README code map 写 `pybullet_bridge/control/panda_action_adapter.py`、`pybullet_bridge/policy/jsonl_action_replay_policy.py`，实际代码位于 `pybullet_bridge/pybullet_bridge/learning/` | 本文引用实际代码路径，建议后续同步 README |
| `training/reports/panda_low_dim_eda.json` 是 3 条数据，`training/reports/panda_30_low_dim_eda.json` 才是 canonical 30 条 | 本文主实验只使用 `panda_30_low_dim_eda.json` |
| `train_act_smoke.py` 名称包含 ACT，但脚本实际是 ridge/linear smoke baseline | 本文明确标为 smoke/mock，不写成 ACT 已完成 |

### 无法确认的内容

- 当前项目证据不足，无法确认真实机械臂部署。
- 当前项目证据不足，无法确认真实 Sim2Real 已完成。
- 当前项目证据不足，无法确认稳定在线自主抓取。
- 当前项目证据不足，无法确认离线 loss 改善带来任务成功率提升。
- 当前项目证据不足，无法确认 canonical ACT 正式训练和下游在线 ACT runtime 已完成。
- 当前项目证据不足，无法确认旧文档中的 94.399 ms fault alarm 对应哪一个原始 benchmark JSON。

### 建议同步修改的 README 或 AGENTS 条目

- 下游 README 的 code map 路径建议从 `pybullet_bridge/control/...` 和 `pybullet_bridge/policy/...` 改为实际 `pybullet_bridge/pybullet_bridge/learning/...`。
- 中游 canonical 文档建议把旧 `17.626 / 49.508 ms`、`94.399 ms` 与 latest archived `9.79 / 34.218 ms` 的来源区分清楚。
- 中游 README 可在 EDA 处明确 `panda_30_low_dim_eda.json` 与 `panda_low_dim_eda.json` 的数据规模差异。
- AGENTS 已经清楚规定 RAG 调用和 Gate 边界，暂不建议修改核心规则。

### 最适合直接用于简历的部分

- 第 1 节一页式总览。
- 第 15 节简历素材库。
- 第 4/5/6 节各自的“候选简历素材”。

### 最适合用于面试复盘的部分

- 第 7 节 Canonical Experiment。
- 第 9 节关键难点与排障案例。
- 第 10 节项目取舍。
- 第 13 节高频技术追问。
