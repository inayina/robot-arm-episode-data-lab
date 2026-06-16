# robot-arm-episode-data-lab

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

第一阶段只使用 PyBullet 快速跑通数据闭环，不接入 ROS2、MoveIt、Isaac Sim 或真实机械臂硬件。

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

## 5. 明确不做的内容

第一阶段不做：

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

本项目第一阶段只关注 PyBullet 中的最小机械臂数据采集闭环。

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

当以上命令能生成有效 `episode`、校验通过并创建回放文件时，项目第一阶段达到验收标准。

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
