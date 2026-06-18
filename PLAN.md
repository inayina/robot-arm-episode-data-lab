# robot-arm-episode-data-lab

<!-- AUTO_STATUS_START -->
## 自动进度快照

> 这个区块由 `python scripts/update_project_docs.py` 根据仓库文件自动生成；
> 手动修改会在下次运行时被覆盖。

### 作品集基线

- [x] V0 最小样例：`dataset_sample/v0/`
- [x] V1 episode 数据闭环：`dataset_sample/episode_000001/`
- [x] 数据校验脚本：`scripts/validate_dataset.py`
- [x] 回放 GIF 脚本：`scripts/visualize_episode.py`
- [x] 数据结构与采集流程文档：`docs/data_schema.md`, `docs/collection_pipeline.md`

### Phase 0.5 工程与展示（广撒网）

- [x] config 接入采集脚本：`collect_episode.py --config configs/default.yaml`
- [ ] 统一样例 episode：`dataset_sample/episode_000001/`（100 步、640×480）
- [x] 展示 GIF：`assets/gifs/demo_replay.gif`
- [x] pytest 测试：`pytest -q`
- [x] GitHub Actions CI：`.github/workflows/ci.yml`
- [x] LICENSE：`LICENSE`

### Phase 1 HAL + IK + 笛卡尔

- [x] 任务 1：PyBullet 控制逻辑审计：`docs/phase1_task1_pybullet_audit.md`
- [x] 任务 2：RobotControl 抽象基类：`core/hal.py`
- [x] 任务 3：PyBulletRobot 控制封装：`core/pybullet_robot.py`
- [x] 任务 4：HAL smoke demo：`scripts/run_cartesian_demo.py`
- [x] 任务 5：IK 求解封装：`core/ik.py`
- [x] 任务 6：笛卡尔直线插补：`core/trajectory.py`
- [x] 任务 8：采集脚本接入 cartesian_ik 模式：`collect_episode.py --control-mode cartesian_ik`

### Phase 1.5 任务可信度（广撒网）

- [x] Task FSM：`agents/task_fsm.py`
- [x] Evaluator Agent：`agents/evaluator.py`
- [x] Motion planner 模块：`agents/motion_planner.py`
- [x] 成功 pick/lift GIF：`assets/gifs/demo_pick_success.gif`

### Phase 2 批量数据 + LeRobot（广撒网）

- [x] 批量采集脚本：`scripts/batch_collect.py`
- [x] 数据集目录 ≥ 20 episode：`dataset/v1/`
- [x] LeRobot 真导出：`export_lerobot_style.py`
- [x] 数据集 README：`dataset/v1/README.md`

### Phase 3 展示与迁移叙事（广撒网）

- [x] 面试讲稿：`docs/interview_walkthrough.md`
- [x] ROS/MoveIt 迁移设计：`docs/migration_ros2_moveit.md`
- [x] 广撒网路线图文档：`docs/portfolio_roadmap_broad.md`

<!-- AUTO_STATUS_END -->


## 1. 项目背景

`robot-arm-episode-data-lab` 是一个用于求职作品集的机械臂仿真数据采集项目。

项目重点不是构建完整机械臂控制系统，而是用最小可运行的 PyBullet 环境展示一条清晰的数据采集闭环：

- 机械臂仿真环境搭建
- `image-state-action-episode` 数据结构设计
- 具身智能 / 模仿学习数据采集意识
- 机器人任务过程数据记录
- `episode` 数据完整性校验
- 轨迹回放与可视化
- 后续扩展到 LeRobot / Isaac Sim / MoveIt 的工程意识

本计划中的“第一阶段”指作品集基线阶段：只使用 PyBullet 快速跑通数据闭环，
不接入 ROS2、MoveIt、Isaac Sim 或真实机械臂硬件。

与 `design.md` / `roadmap.md` 的关系：

- `PLAN.md` 描述当前已经跑通或正在巩固的 V0/V1/V2 数据闭环基线。
- `design.md` 描述基线完成后的 10 天游标架构，是后续增强方向。
- `roadmap.md` 拆解 `design.md` 的 Phase 1，即在当前数据闭环之上新增 HAL、
  IK 和笛卡尔插补能力。
- 当前数据格式以 `docs/data_schema.md` 和已验证脚本为准，后续增强必须保持
  兼容。

## 2. V0 最小版本

目标：验证 PyBullet 机械臂环境可以正常加载、渲染图像并读取关节状态。

V0 包含：

- 初始化 PyBullet
- 加载地面平面
- 加载 PyBullet 示例机械臂
- 放置一个 cube 操作对象
- 配置固定 RGB 相机
- 保存一张相机图像
- 保存当前机械臂关节状态

期望输出：

```text
dataset_sample/v0/
├── image.png
├── joint_state.npy
└── metadata.json
```

验收命令：

```bash
python scripts/collect_episode.py --mode v0 --output dataset_sample/v0
```

验收标准：

- PyBullet 能正常启动
- 生成 `image.png`
- 生成 `joint_state.npy`
- 图像中能看到机械臂和 cube
- 关节状态维度与机械臂可控关节数量一致

## 3. V1 作品集可用版本

目标：生成一个完整 `episode`，形成可用于作品集展示的数据样本。

期望目录结构：

```text
dataset_sample/episode_000001/
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

V1 包含：

- 初始化 PyBullet 桌面任务场景
- 放置一个 cube 操作对象
- 控制机械臂执行一段简单的预设关节轨迹
- 每一步同步采集 RGB 图像、关节状态、末端位姿、物体位姿和动作
- 保存 `episode` 元数据
- 保证所有数据的帧数对齐

任务保持简单：机械臂沿预设轨迹靠近 cube，不要求真实抓取成功，不要求复杂规划，也不要求闭环控制。

验收命令：

```bash
python scripts/collect_episode.py --output dataset_sample/episode_000001 --num-steps 100
```

验收标准：

- `images/` 中生成连续命名的 PNG 帧
- `states.npy` shape 为 `[T, state_dim]`
- `actions.npy` shape 为 `[T, action_dim]`
- `ee_poses.npy` shape 为 `[T, 7]`
- `object_poses.npy` shape 为 `[T, 7]`
- `metadata.json` 记录 `episode` 基本信息
- `T` 与图像帧数一致

## 4. V2 面试可讲版本

目标：让项目从“能跑”升级为“能解释、能检查、能展示”。

V2 包含：

- `scripts/validate_dataset.py`
- `scripts/visualize_episode.py`
- `docs/data_schema.md`
- `docs/collection_pipeline.md`
- README 使用说明和作品集表达

验收命令：

```bash
python scripts/validate_dataset.py dataset_sample/episode_000001
python scripts/visualize_episode.py dataset_sample/episode_000001
```

验收标准：

- 校验脚本能对正常 `episode` 返回成功
- 校验脚本能发现缺失文件、图像帧不连续、数组长度不一致、元数据字段缺失等问题
- 回放脚本能生成带标注的 GIF
- README 能说明项目定位、运行命令、数据结构和后续扩展方向

## 5. 基线阶段明确不做的内容

作品集基线阶段不做：

- ROS2
- DDS
- MoveIt
- `ros2_control`
- Isaac Sim
- 真实机械臂硬件
- 强化学习训练
- 大规模数据集采集
- 复杂抓取规划
- 多相机系统
- 分布式数据采集系统
- 完整机器人控制栈

本项目基线阶段只关注 PyBullet 中的最小机械臂数据采集闭环。HAL、IK、
RRT、夹爪闭环、批量采集和 LeRobot 标准化导出属于 `design.md` 描述的后续
增强阶段。

## 6. 推荐仓库结构

```text
robot-arm-episode-data-lab/
├── README.md
├── PLAN.md
├── requirements.txt
├── configs/
│   └── default.yaml
├── scripts/
│   ├── collect_episode.py
│   ├── validate_dataset.py
│   ├── visualize_episode.py
│   └── export_lerobot_style.py
├── docs/
│   ├── data_schema.md
│   └── collection_pipeline.md
├── dataset_sample/
│   └── episode_000001/
└── assets/
    ├── screenshots/
    └── gifs/
```

## 7. 每个脚本的职责

### `scripts/collect_episode.py`

创建 PyBullet 场景，执行预设轨迹，采集同步数据，并写出 V0 或 V1 数据。

主要职责：

- 创建 PyBullet 仿真环境
- 加载机械臂、地面和 cube
- 配置固定相机
- 执行预设动作序列
- 每一步采集 image、state、action、ee pose、object pose
- 保存 `episode` 文件
- 写入 `metadata.json`

### `scripts/validate_dataset.py`

检查 `episode` 文件完整性、图像帧连续性、数组帧数对齐、位姿维度和必要元数据字段。

### `scripts/visualize_episode.py`

读取一个 `episode` 并生成带标注的 GIF 回放，标注内容包括 step index、动作摘要和物体位置摘要。

### `scripts/export_lerobot_style.py`

后续扩展预留脚本，用于说明当前字段如何映射到更接近 LeRobot 风格的数据格式。V1 不要求实现真实导出。

## 8. 数据结构设计

### 图像

路径：

```text
images/000000.png
images/000001.png
```

格式：

- PNG
- RGB
- shape 为 `[H, W, 3]`
- dtype 为 `uint8`
- 按 step index 与 state/action 对齐

### 状态

路径：

```text
states.npy
```

V1 内容：

```text
state[t] = [joint_positions...]
```

shape：

```text
[T, state_dim]
```

### 动作

路径：

```text
actions.npy
```

V1 内容：

```text
action[t] = [target_joint_positions...]
```

shape：

```text
[T, action_dim]
```

### 末端位姿

路径：

```text
ee_poses.npy
```

内容：

```text
[x, y, z, qx, qy, qz, qw]
```

shape：

```text
[T, 7]
```

### 物体位姿

路径：

```text
object_poses.npy
```

内容：

```text
[x, y, z, qx, qy, qz, qw]
```

shape：

```text
[T, 7]
```

### 元数据

路径：

```text
metadata.json
```

必要字段包括：

- `episode_id`
- `simulator`
- `task_name`
- `num_steps`
- `image_width`
- `image_height`
- `state_dim`
- `action_dim`
- `control_mode`
- `robot`
- `object`
- `camera`

## 9. 验收标准

V0：

```bash
python scripts/collect_episode.py --mode v0 --output dataset_sample/v0
```

V1：

```bash
python scripts/collect_episode.py --output dataset_sample/episode_000001 --num-steps 100
```

V2：

```bash
python scripts/validate_dataset.py dataset_sample/episode_000001
python scripts/visualize_episode.py dataset_sample/episode_000001
```

当以上命令能生成有效 `episode`、校验通过并创建回放文件时，项目作品集基线
阶段达到验收标准。之后可以进入 `roadmap.md` 中的 HAL + IK + Cartesian
Interpolation 增强阶段。

## 10. 作品集定位

简历中可以这样表达：

> 基于 PyBullet 搭建机械臂桌面任务仿真环境，实现 `image-state-action episode` 数据采集流程，支持 RGB 图像、关节状态、末端位姿、物体位姿、动作和元数据的同步保存，并实现 `episode` 数据完整性校验与轨迹回放。

重点突出：

- 机械臂仿真环境搭建
- `image-state-action` 数据采集
- `episode` 数据结构设计
- 数据完整性校验
- 轨迹回放与可视化
- 模仿学习数据闭环意识
- 后续可扩展到 LeRobot / Isaac Sim / MoveIt

该项目不强调复杂控制算法，而强调机器人数据工程、仿真采集流程、数据质量验证和作品集可解释性。

## 11. 广撒网求职路线图（4 周增补）

基线 V0/V1/V2 完成后，若目标是 **控制 / 具身 AI / 仿真数据 / 机器人软件**
等多方向广撒网投递，按下面顺序推进。详细任务、验收命令与裁剪策略见
[docs/portfolio_roadmap_broad.md](docs/portfolio_roadmap_broad.md)。

### 11.1 阶段总览

| 阶段 | 时间 | 目标 | 必做 |
|------|------|------|------|
| Phase 0.5 工程与展示 | W1 前 2–3 天 | CI、pytest、config 接入、README GIF | 是 |
| Phase 1 HAL/IK/笛卡尔 | W1 后 2–3 天 | 见 `roadmap.md` | 是 |
| Phase 1.5 任务可信度 | W2 | FSM + evaluator + success 标签 + pick/lift | 是 |
| Phase 2 批量数据 + LeRobot | W3 | 20+ episode、真导出、language_instruction | 是 |
| Phase 3 展示与迁移叙事 | W4 | 讲稿、架构图、ROS/MoveIt 迁移设计文档 | 是 |
| RRT / ROS2 真接入 | 可选 | 仅作加分，不阻塞投递 | 否 |

### 11.2 Phase 0.5：工程与展示

在动控制代码之前，先让仓库 **可复现、可展示、样例与文档一致**：

- 接入 `configs/default.yaml`（`collect_episode.py --config`）
- 重生成 `dataset_sample/episode_000001/`（与 README 步数/分辨率一致）
- 新增 `assets/gifs/demo_replay.gif`，README 顶部嵌入
- 新增 `tests/` + `pytest`，GitHub Actions CI
- 根目录 `LICENSE`（建议 MIT）
- Git 按阶段提交，便于 reviewer 看演进

验收：

```bash
python scripts/collect_episode.py --config configs/default.yaml --output dataset_sample/episode_000001
python scripts/validate_dataset.py dataset_sample/episode_000001
pytest -q
```

### 11.3 Phase 1.5：任务可信度（`agents/`）

将 `AGENTS.md` 中的三层职责落实为 **可 import 的薄模块**（不必接 LLM）：

```text
agents/
├── task_fsm.py      # reach → approach → grasp → lift
├── motion_planner.py  # 复用 core/trajectory + core/ik
└── evaluator.py     # 碰撞/奇异拦截、success、failure_reason
```

扩展 `metadata.json`：`success`、`failure_reason`、`language_instruction`（Phase 2
正式写入采集逻辑）。

验收：至少 **1 条** `metadata.success == true` 的 pick/lift episode + GIF 放入
`assets/gifs/`。

### 11.4 Phase 2：批量数据 + LeRobot

- `scripts/batch_collect.py`：`--num-episodes`、`--seed`
- `dataset/v1/`：≥ 20 episode，documented success rate
- 实现 `export_lerobot_style.py` **真实导出**（非仅 manifest 占位）
- `dataset/v1/README.md` 说明字段与统计

### 11.5 Phase 3：展示与迁移叙事

- `docs/interview_walkthrough.md`：3–5 分钟面试讲稿
- README：架构图、Skills 矩阵、Quick Start ≤ 3 命令
- `docs/migration_ros2_moveit.md`：`RobotControl` HAL → ros2_control / MoveIt
  映射（文档级即可，满足 ROS 岗「迁移意识」）

### 11.6 广撒网最低可投递线

全部满足即可开始投递：

1. Phase 0.5 完成（CI + pytest + README GIF）
2. Phase 1 完成（`cartesian_ik` episode 可 validate + visualize）
3. Phase 1.5 完成（≥ 1 成功 pick/lift GIF）
4. Phase 2 完成（≥ 20 episode + LeRobot 导出可加载）
5. Phase 3 完成（讲稿 + migration 文档）

### 11.7 简历表述升级（广撒网版）

基线版（当前）：

> 基于 PyBullet 搭建机械臂桌面任务仿真环境，实现 image-state-action episode
> 数据采集、校验与回放。

广撒网版（Phase 0.5–3 完成后）：

> 基于 PyBullet 实现 HAL 解耦的机械臂仿真采集平台：笛卡尔插补 + IK 生成 action，
> FSM 驱动 pick-lift 任务与自动 success 评测，批量采集 20+ 多模态 episode 并导出
> LeRobot 格式；含 pytest/CI 与数据校验门禁。

面试分角色强调：

- **控制 / 规划**：HAL、IK、笛卡尔轨迹、可选 RRT
- **具身 AI / 数据**：episode 对齐、success 标签、LeRobot、language instruction
- **软件工程**：pytest、CI、config、模块分层、migration 设计
