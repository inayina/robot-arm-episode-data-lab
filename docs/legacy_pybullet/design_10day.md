# 轻量化机械臂闭环仿真平台 - 系统设计文档 (design_10day.md)

## 1. 项目定位与核心原则

本文档描述的是作品集基线完成后的增强版系统设计。当前可运行基线以
`baseline_plan.md`、`../dev/data_schema.md` 和 `scripts/collect_episode.py` 为准；
本设计文档用于指导后续逐步加入 HAL、IK、RRT、抓取评测、批量采集和
LeRobot 导出能力。

* **轻量高效**：基于 PyBullet 的纯 Python 单体架构，摆脱复杂的 ROS 通信配置，实现零 DDS 网络开销，环境 10 秒内快速启动。
* **算法解耦**：在保持现有数据闭环稳定的前提下，逐步加入核心运动学（IK）、路径规划（RRT）以及抓取逻辑，提升调试效率。
* **数据闭环**：原生设计端到端的数据流，每一步动作（Action）与状态（State）均按帧严格对齐并落盘，并为后续实验看板与下游模仿学习框架（如 LeRobot）预留接口。

---

## 2. 系统架构（三层分层设计）

```text
┌──────────────────────────────────────────────────────┐
│                   应用层 (Apps)                       │
│   run_pick_place.py  │  batch_collect.py  │  demo     │
├──────────────────────────────────────────────────────┤
│                   核心层 (Core)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐   │
│  │ Planner  │ │   IK     │ │  RRT     │ │Gripper │   │
│  │(轨迹插补)│ │(运动学)  │ │(避障)    │ │(抓取)  │   │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘   │
├──────────────────────────────────────────────────────┤
│                   接口层 (HAL)                        │
│            RobotControl 抽象基类                      │
│   ┌──────────────┐    ┌──────────────┐               │
│   │ PyBulletRobot│    │  RealRobot   │ (物理真机预留)│
│   └──────────────┘    └──────────────┘               │
├──────────────────────────────────────────────────────┤
│                   数据层 (Data)                       │
│   Episode 格式: images/ + states.npy + actions.npy    │
│   + ee_poses.npy + object_poses.npy + metadata.json   │
└──────────────────────────────────────────────────────┘
```

## 3. 关键模块详细设计

### 3.1 硬件抽象层 (HAL)

通过 `RobotControl` 抽象基类，将机械臂的底层控制（如角度读写、末端位姿获取）进行标准化封装：

* 仿真环境直接对接 PyBullet 的引擎接口。
* 真实硬件迁移时，上层算法无需变动，仅需继承该基类并实现对应的真机驱动接口，实现高度的软硬件解耦。

### 3.2 数据链路层与对齐规范

每个采集周期（Episode）均包含以下结构，确保多模态数据流的时间戳严格对齐。
增强阶段必须保持当前 V1/V2 数据格式兼容：

* `images/`：按帧保存的 RGB 图像；RGB-D 可作为后续扩展。
* `states.npy`：当前帧的关节角度（Joint Angles），shape 为 `[T, state_dim]`。
* `actions.npy`：控制器下发的控制目标（Joint Target 或 Cartesian IK 生成的 Joint Target），shape 为 `[T, action_dim]`。
* `ee_poses.npy`：当前帧末端位姿，单帧格式为 `[x, y, z, qx, qy, qz, qw]`。
* `object_poses.npy`：当前帧操作对象位姿，单帧格式为 `[x, y, z, qx, qy, qz, qw]`。
* `metadata.json`：存储全局元数据。当前必要字段以 `../dev/data_schema.md` 为准；语言指令（Language Instruction）、任务成功/失败标签（Success Label）和失败原因分类（Error Type）属于后续自动评测与批量采集阶段的扩展字段。

---

## 4. 基线之后的 10 天实施路线图

* **Phase 1 (Day 1-2)**：HAL 接口定义、带阻尼 IK 求解器与笛卡尔空间直线插补实现。
* **Phase 2 (Day 3-4)**：纯 Python 双向 RRT 避障算法编写与 PyBullet 碰撞检测集成。实施拆解见 [rrt_roadmap.md](rrt_roadmap.md)。
* **Phase 3 (Day 5-6)**：夹爪控制优化与基于物理状态变化的自动化抓取验证。
* **Phase 4 (Day 7-8)**：批量数据自动化采集脚本编写与实验管理看板（Dashboard）对接。
* **Phase 5 (Day 9-10)**：转换为标准的 LeRobot / Hugging Face Datasets 格式并完成全链路跑通。

**广撒网求职路径**：若目标是多方向投递而非完整 10 天增强栈，见
[portfolio_roadmap.md](portfolio_roadmap.md)。该路径将 Phase 0.5
（CI/展示）、Phase 1.5（任务评测）、Phase 2（批量 LeRobot）、Phase 3（面试材料）与
上文 Phase 1 合并为 **4 周最低可投递线**；RRT 与 ROS2 真接入降为可选加分项。

执行原则：

* Phase 1 只做 HAL、IK 和笛卡尔插补，不做 RRT、真实抓取闭环或批量数据系统。
* 每个阶段都必须保持 `scripts/collect_episode.py` 的默认 `joint_position` 行为兼容。
* 新能力通过可选参数、独立 demo 或新增模块接入，避免破坏已经验证过的
  V0/V1/V2 数据闭环。
