# Three-Repo Documentation Closure Plan

状态：项目管理文档收口计划。本文档用于指导三个机械臂仓库在面试 / 作品集投递前补齐必要文档。它不是功能开发计划，也不要求立刻统一仿真器、重构代码或扩展复杂模型。

## 0. 总体原则

三个仓库共同表达一条机械臂具身数据闭环：

```text
上游 MuJoCo / ROS 2 interaction
-> 中游 simulator-independent episode schema + minimal training
-> 下游 PyBullet Sim-to-Sim / Sim2Real-readiness evaluation
```

文档收口的目标是让面试官在 5-10 分钟内看懂：

- 三个仓库分别负责什么。
- MuJoCo 和 PyBullet 为什么共存。
- observation / action / state / metadata 如何跨仓库传递。
- baseline training 为什么只是最小闭环，不是复杂模型能力展示。
- 下游为什么是 Sim-to-Sim / Sim2Real-readiness，而不是已完成真实机械臂 Sim2Real。
- 当前没有实机验证，哪些模块未来需要替换。

当前不做：

- 不建议现在做灵巧手。
- 不建议精修前端界面。
- 不建议深入复杂模型。
- 不建议无限扩功能。
- 不把仿真结果包装成真实机械臂验证结果。
- 不把 MuJoCo / PyBullet 后端差异解释成架构错误。

## 1. 文档优先级定义

| 优先级 | 含义 | 验收标准 |
|---|---|---|
| P0 | 影响面试表达、项目可信度、最低可演示闭环 | README / overview / architecture / data flow 口径一致 |
| P1 | 能增强作品集可信度，但不是马上必须 | demo guide、troubleshooting、interview notes 有可引用证据 |
| P2 | 当前求职边际收益低，可暂缓 | 长稳报告、完整实机迁移细节、前端说明、复杂训练报告 |

## 2. 三仓库文档矩阵

| 仓库 | 当前定位 | P0 文档 | P1 文档 | P2 文档 |
|---|---|---|---|---|
| `ros2-arm-teleoperation-suite` | 上游：MuJoCo / ROS 2 teleop 与 raw episode 来源 | README、PROJECT_OVERVIEW、ARCHITECTURE、DATA_FLOW、DEMO_GUIDE | TROUBLESHOOTING、INTERVIEW_NOTES、ROADMAP | real hardware bring-up、安全认证、长稳报告 |
| `robot-arm-episode-data-lab` | 中游：episode schema、validation、replay、baseline training、handoff | README、PROJECT_OVERVIEW、DATA_FLOW、TRAINING_PIPELINE、SIM_BACKENDS_AND_TRANSFER | DEMO_GUIDE、TROUBLESHOOTING、INTERVIEW_NOTES、ROADMAP | 大规模训练报告、复杂策略文档 |
| `ros2-moveit-pybullet-bridge` | 下游：PyBullet 执行验证、MoveIt 闭环、Sim2Real-readiness | README、PROJECT_OVERVIEW、ARCHITECTURE、SIM2REAL_EVALUATION、PANDA_JSONL_REPLAY | TROUBLESHOOTING、DEMO_GUIDE、INTERVIEW_NOTES、ROADMAP | HOC 前端精修、完整 Panda backend、真实机器人接入 |

## 3. 上游文档收口：`ros2-arm-teleoperation-suite`

### 3.1 README.md

目标：把项目定位从“成熟工业系统”收敛为“software-only early-stage prototype / simulation stack”。

必须说明：

- 使用 MuJoCo 作为上游仿真后端。
- 负责 teleop input、safety monitor、MoveIt Servo、`ros2_control`、虚拟驱动、MuJoCo physics、camera bridge、LeRobot recorder。
- 输出 raw episode，不负责 dataset curation 和 policy training。
- 当前没有真实机械臂安全认证或实机控制。

建议新增首段：

```text
This repository is an early-stage software simulation stack for ROS 2 robot-arm teleoperation and episode recording. It uses MuJoCo as the upstream interaction backend and produces raw multimodal episodes for downstream dataset processing. It is not a certified real-robot control product.
```

验收标准：

- README 首屏能看出“上游 / MuJoCo / software simulation”。
- 不把 MuJoCo 成功抓取说成真实机械臂成功。
- 不把 training quality 放在本仓库内主张。

### 3.2 docs/PROJECT_OVERVIEW.md

目标：用一页说明它在三仓库链路中的职责。

建议结构：

```text
# Project Overview
## Role in the Three-Repo Loop
## What This Repository Owns
## What This Repository Does Not Own
## Main Runtime Path
## Raw Episode Output
## Current Limitations
```

重点写清：

- 输入：keyboard / gamepad / synthetic generator。
- 运行链路：teleop -> safety -> servo -> control -> MuJoCo -> recorder。
- 输出：HuggingFace / LeRobot-style raw episode。
- 边界：不做数据清洗、训练、下游风险验证。

### 3.3 docs/ARCHITECTURE.md

目标：把 V2 七层架构整理成面试可读版。

必须包含：

- L0 teleop input。
- L1 safety monitor。
- L2 MoveIt Servo。
- L3 `ros2_control`。
- L4 virtual drive / CANopen mock。
- L5 MuJoCo。
- L6 camera / perception。
- L7 recorder。

验收标准：

- Mermaid 图或表格中明确 MuJoCo 位于上游 physics server。
- 不把 PyBullet 放进这个仓库的运行主线。

### 3.4 docs/DATA_FLOW.md

目标：解释 raw episode 怎么产生，并与中游 schema 对齐。

必须列出 recorder 字段：

| 字段 | 维度 | 去向 |
|---|---|---|
| `observation.state` | `[7]` | 中游 adapter 合并 gripper 后变 `[8]` |
| `observation.gripper` | `[1]` | 合并进 canonical state |
| `action` | `[8]` | 标记为 `ee_pose_gripper` |
| `observation.ee_pose` | `[7]` | 中游 required |
| `observation.ft` | `[6]` | 中游 optional |
| `observation.images.*` | image | 中游 optional |

必须提醒：

```text
Do not silently truncate action[8] into action[7].
```

### 3.5 docs/DEMO_GUIDE.md

目标：只保留稳定、可解释的演示。

建议包含：

- 启动 full system。
- 开启 recorder。
- M6 perception recorder validation。
- M7 grasp monitor validation。
- 录制或检查 raw episode。

不建议把真实硬件、复杂 policy inference、灵巧手放入当前 demo。

### 3.6 docs/TROUBLESHOOTING.md

目标：把抓取和 ROS 2 通信排障沉淀下来。

优先收录：

- DDS / UDP socket 限制。
- MuJoCo model path。
- gripper contact hold。
- `grasp_assist_attached` 与物理抓取边界。
- recorder 缺失相机或同步失败。

### 3.7 docs/INTERVIEW_NOTES.md

目标：帮助你主动讲边界。

必须有问答：

- 为什么上游用 MuJoCo？
- 为什么不直接接真机？
- `grasp_assist` 能不能算真实抓取？
- 上游 recorder 和中游 dataset schema 怎么对齐？
- 这个仓库展示的能力是什么？

### 3.8 docs/ROADMAP.md

目标：把未来工作分清 P0 / P1 / P2。

P0：README 降调、DATA_FLOW、DEMO_GUIDE。  
P1：更多 recorder samples、M7 排障补图。  
P2：真实 CAN、实机 gripper、真实安全认证、复杂 policy deployment。

## 4. 中游文档收口：`robot-arm-episode-data-lab`

### 4.1 README.md

目标：把根 README 从“PyBullet 采集平台”收敛为“中游数据闭环核心仓库”。

必须说明：

- 本仓库是 simulator-independent data lab。
- 负责 schema、inspection、release、validation、replay、baseline training、offline evaluation、bridge handoff。
- legacy PyBullet / KUKA episode 仍可保留为本地采集样例，但主线说明应对齐 Panda schema。
- 训练模块是最小闭环，不是大模型训练平台。

建议新增首段：

```text
This repository is the middle layer of a robot-arm embodied data loop. It standardizes episodes from upstream simulators, validates dataset contracts, runs minimal baseline training/evaluation, and exports neutral replay handoff bundles for downstream Sim-to-Sim / Sim2Real-readiness validation.
```

### 4.2 docs/PROJECT_OVERVIEW.md

目标：一页讲清中游职责。

建议结构：

```text
# Project Overview
## Role in the Three-Repo Loop
## Inputs
## Canonical Panda Schema
## Dataset Validation
## Baseline Training
## Replay / Bridge Handoff
## Out of Scope
```

必须强调：

- 不启动 ROS 2 runtime。
- 不做真机控制。
- 不训练复杂模型。
- 不承诺 policy 效果。

### 4.3 docs/DATA_FLOW.md

目标：把 raw episode 到 handoff 的链路画清楚。

建议 Mermaid：

```mermaid
flowchart LR
    RAW[MuJoCo raw episode] --> ADAPT[adapter]
    ADAPT --> SCHEMA[canonical Panda schema]
    SCHEMA --> INSPECT[inspect dataset]
    INSPECT --> RELEASE[dataset release]
    RELEASE --> TRAIN[linear smoke training]
    TRAIN --> EVAL[offline eval]
    EVAL --> REPLAY[predicted_actions.jsonl]
    REPLAY --> HANDOFF[bridge_handoff]
```

必须列出：

- raw fields。
- adapted fields。
- required / optional fields。
- action type conversion。
- fail-fast 条件。

### 4.4 docs/TRAINING_PIPELINE.md

目标：把最小训练闭环讲清楚。

必须说明：

- 输入：dataset release。
- policy：`linear_smoke`，`observation.state -> action`。
- 输出：`checkpoint.npz`、`metrics.json`、`normalization.json`、`eval.json`、`predicted_actions.jsonl`。
- 指标：train loss、val loss、MAE、RMSE、per-dim error、smoothness proxy、success summary。

禁止表述：

- “训练了可用抓取策略”。
- “完成 ACT / Diffusion Policy”。
- “可直接上真机”。

### 4.5 docs/SIM_BACKENDS_AND_TRANSFER.md

状态：已新增。

后续可补：

- 加一张三仓库跨后端链路图。
- 加一节“如何用这份文档回答面试追问”。
- 在 docs/README.md 中加入入口。

### 4.6 docs/DEMO_GUIDE.md

目标：给中游最小闭环一套可复制命令。

建议包含：

```bash
python3 training/scripts/make_mock_panda_dataset.py --output /tmp/panda_mock_dataset
python3 training/scripts/inspect_dataset.py --dataset /tmp/panda_mock_dataset --schema configs/robot_schemas/panda.yaml
python3 training/scripts/prepare_dataset_release.py ...
python3 training/scripts/train_act_smoke.py ...
python3 training/scripts/evaluate_policy.py ...
python3 training/scripts/replay_policy.py ...
python3 training/scripts/prepare_bridge_handoff.py ...
```

验收标准：

- 10 分钟内能跑通 mock chain。
- 每一步都有 PASS / FAIL 或 JSON 产物。

### 4.7 docs/TROUBLESHOOTING.md

目标：集中记录数据链路常见失败。

优先写：

- `action[8]` vs `action[7]`。
- `observation.state[7]` vs `[8]`。
- optional modality missing。
- schema_id mismatch。
- action_type mismatch。
- timestamp/frame count mismatch。
- checkpoint 文件名和实际训练产物不一致。

### 4.8 docs/INTERVIEW_NOTES.md

目标：把中游讲成工程能力，而不是算法夸张。

必须覆盖：

- 为什么中游放训练？
- 为什么只做 baseline？
- 为什么要 dataset release？
- 为什么 replay JSONL 不直接启动 ROS 2？
- 为什么 schema 比模型更重要？

### 4.9 docs/ROADMAP.md

目标：把后续任务收口。

P0：

- README 主定位更新。
- `checkpoint.npz` 文档一致性修正。
- DEMO_GUIDE 最小链路。
- TROUBLESHOOTING schema/action mismatch。

P1：

- 使用一小段真实上游 recorder 数据跑 adapter。
- 保存 sample reports。
- docs/README 导航补齐。

P2：

- ACT / Diffusion Policy。
- 大规模训练。
- 云端实验追踪。
- 复杂可视化。

## 5. 下游文档收口：`ros2-moveit-pybullet-bridge`

### 5.1 README.md

目标：把下游定位从“大而全平台”收敛为“PyBullet-based Sim-to-Sim / Sim2Real-readiness validation”。

必须说明：

- 当前稳定主线是 iiwa7 legacy validation backend。
- Panda JSONL replay 是正在接入的新增路径。
- Real-Source 当前是 randomized PyBullet 或 LeRobot replay proxy，不是真实机械臂。
- 不在本仓库训练 policy。

建议新增首段：

```text
This repository is the downstream validation layer for robot-arm replay and control actions. It uses PyBullet for lightweight execution checks, MoveIt trajectory validation, distribution-shift monitoring, and Sim2Real-readiness analysis. Current real-source modes are simulated or replay-based proxies, not physical robot validation.
```

### 5.2 docs/PROJECT_OVERVIEW.md

目标：一页说明下游职责。

建议结构：

```text
# Project Overview
## Role in the Three-Repo Loop
## Stable Legacy Backend: iiwa7
## Panda Replay Integration Status
## What PyBullet Validates
## What This Repository Does Not Claim
```

### 5.3 docs/ARCHITECTURE.md

目标：保留现有架构，但突出下游评估层。

必须包含：

- MoveIt planning。
- `FollowJointTrajectory` / `/bridge/command`。
- PyBullet `SimSource` / `RealSource`。
- `dist_monitor`。
- `risk_engine`。
- `PolicyRunner`。
- HOC 作为辅助，不是主线。

### 5.4 docs/SIM2REAL_EVALUATION.md

目标：成为下游核心文档。

必须解释：

- 当前为什么叫 Sim-to-Sim / Sim2Real-readiness。
- `RealSource` 是什么，不是什么。
- KL / W1 / MMD 分别看什么。
- tracking error 和 execution RMSE 怎么解释。
- 抓取稳定性评估看哪些信号。
- 迁移实机需要替换哪些模块。

建议加入表格：

| 评估项 | 当前可评估 | 不能证明 |
|---|---|---|
| 轨迹执行误差 | PyBullet joint tracking | 真实电机响应 |
| 分布偏移 | randomized proxy | 真实环境 domain gap 全覆盖 |
| 接触参数敏感性 | 仿真接触变化 | 真实抓取稳定成功率 |
| runtime safety | software guard | 真实功能安全认证 |

### 5.5 docs/PANDA_JSONL_REPLAY.md

目标：把中游 handoff 如何进入下游说清楚。现有 `PANDA_JSONL_REPLAY_ROADMAP.md` 可作为基础，建议补成更面向交付的文档。

必须包含：

- handoff bundle 目录。
- `predicted_actions.jsonl` 字段。
- loader 检查项。
- `JsonlActionReplayPolicy` 只读取 action，不解释 action。
- `PandaActionAdapter` 当前状态：`hold` / `mock_ik`。
- 未完成：真实 Panda IK / MoveIt adapter / Panda PyBullet backend。

### 5.6 docs/DEMO_GUIDE.md

目标：明确两条演示路线。

路线 A：稳定 iiwa7 MoveIt-PyBullet demo。

```bash
ros2 launch pybullet_bridge portfolio_demo.launch.py sim_mode:=GUI
ros2 launch moveit_config m2_iiwa_demo.launch.py sim_mode:=GUI
```

路线 B：Panda JSONL replay 离线/单元测试路径。

```text
load handoff -> validate rows -> policy returns ee_delta_gripper -> adapter hold/mock_ik -> health diagnostics
```

必须说明：

- 路线 B 目前不等于完整 Panda 抓取 runtime。
- iiwa7 backend 是 legacy validation evidence。

### 5.7 docs/TROUBLESHOOTING.md

目标：记录下游最容易被追问的问题。

优先写：

- joint order mismatch。
- action dim mismatch。
- `ee_delta_gripper` 被误当 joint target。
- frame / end-effector link mismatch。
- PyBullet URDF 加载失败。
- MoveIt planning 成功但执行偏差。
- RealSource 被误解成真机。
- contact/friction 参数不可跨后端直接等价。

### 5.8 docs/INTERVIEW_NOTES.md

目标：准备下游面试追问。

必须覆盖：

- 为什么下游用 PyBullet？
- 为什么保留 iiwa7 legacy backend？
- Panda JSONL 现在到哪一步？
- 什么是 Sim2Real-readiness？
- 如何解释 RealSource？
- 如果迁移实机，先替换什么？

### 5.9 docs/ROADMAP.md

目标：防止继续无限扩功能。

P0：

- README 边界降调。
- SIM2REAL_EVALUATION。
- PANDA_JSONL_REPLAY 状态说明。
- TROUBLESHOOTING action/frame/RealSource。

P1：

- Panda handoff loader 单元测试复验。
- `panda_jsonl_replay` strategy smoke。
- 生成一份 Panda replay check report。

P2：

- 完整 Panda PyBullet backend。
- MoveIt Panda config。
- `moveit_ik` adapter。
- 实机 `real_source:=ros2`。
- HOC 前端精修。

## 6. 三仓库文档一致性检查清单

每次更新 README 或项目介绍时，检查以下口径是否一致。

| 检查项 | 正确口径 |
---|---|
| 仿真后端 | 上游 MuJoCo，下游 PyBullet，中游仿真器无关 |
| 当前阶段 | Sim-to-Sim / Sim2Real-readiness，不是实机 Sim2Real |
| 训练能力 | 最小 baseline training，不是复杂策略效果 |
| RealSource | randomized PyBullet / LeRobot replay proxy，不是真机 |
| Panda schema | 中游主线，bridge 正在接入 |
| iiwa7 | 下游 legacy validation backend |
| 抓取稳定性 | 可排障、可评估，不保证真实抓取成功 |
| 实机迁移 | 需要替换硬件接口、夹爪、传感器、安全、标定 |

## 7. 推荐落地顺序

### Day 1-2：三仓库 README 降调

产出：

- 上游 README：software-only MuJoCo upstream。
- 中游 README：simulator-independent data lab。
- 下游 README：PyBullet validation / Sim2Real-readiness。

验收：

- 三个 README 不互相抢职责。
- 任何一个 README 都不宣称已完成实机验证。

### Day 3-4：每仓 PROJECT_OVERVIEW

产出：

- 三份一页 overview。
- 每份都有 owns / does not own。

验收：

- 面试官只看 overview 能知道仓库边界。

### Day 5-6：DATA_FLOW / TRAINING / SIM2REAL

产出：

- 上游 DATA_FLOW。
- 中游 DATA_FLOW + TRAINING_PIPELINE。
- 下游 SIM2REAL_EVALUATION + PANDA_JSONL_REPLAY。

验收：

- 能从 raw episode 追到 handoff，再追到 downstream validation。

### Day 7-8：DEMO_GUIDE / TROUBLESHOOTING

产出：

- 每仓一份稳定 demo guide。
- 每仓一份 troubleshooting。

验收：

- 出问题时能从文档定位是 schema、sim backend、action adapter、MoveIt 还是 contact 参数问题。

### Day 9-10：INTERVIEW_NOTES / ROADMAP

产出：

- 三仓 interview notes。
- 三仓 roadmap。

验收：

- 能讲清 30 秒、2 分钟、5 分钟版本。
- P0/P1/P2 不再混杂。

## 8. 最小文档包

如果时间只够做最小集，优先完成：

```text
ros2-arm-teleoperation-suite/
├── README.md
├── docs/PROJECT_OVERVIEW.md
├── docs/DATA_FLOW.md
└── docs/INTERVIEW_NOTES.md

robot-arm-episode-data-lab/
├── README.md
├── docs/PROJECT_OVERVIEW.md
├── docs/DATA_FLOW.md
├── docs/TRAINING_PIPELINE.md
└── docs/SIM_BACKENDS_AND_TRANSFER.md

ros2-moveit-pybullet-bridge/
├── README.md
├── docs/PROJECT_OVERVIEW.md
├── docs/SIM2REAL_EVALUATION.md
└── docs/PANDA_JSONL_REPLAY.md
```

这个最小包已经足够支撑面试主线：上游交互数据、中游数据训练闭环、下游迁移评估。

## 9. 面试中的总回答

> 我把三个仓库按上游、中游、下游拆开，不是为了堆功能，而是为了让机械臂具身数据链路的职责清晰。上游用 MuJoCo 承担 ROS 2 teleop、控制栈、多模态观测和 raw episode 产生；中游用 simulator-independent schema 做数据校验、release、最小 baseline training、offline eval 和 replay handoff；下游用 PyBullet 做轻量执行验证、接触参数排查、MoveIt 轨迹误差和 Sim2Real-readiness 风险分析。当前没有实机验证，所以我不会说已经完成 Sim2Real；我展示的是系统集成、数据工程、仿真评估、排障和迁移边界意识。
