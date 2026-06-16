# robot-arm-episode-data-lab

一个用于求职作品集的最小机械臂仿真数据采集项目。

本项目用 PyBullet 搭建一个简单桌面任务环境，采集机械臂执行过程中的 RGB 图像、关节状态、动作、末端位姿、物体位姿和元数据。项目重点是机器人数据采集、数据完整性校验和 `episode` 回放，而不是完整机械臂控制系统。

## 项目展示能力

- PyBullet 机械臂仿真环境搭建
- RGB 图像、关节状态、动作、末端位姿、物体位姿的同步采集
- `image-state-action-episode` 数据结构设计
- `episode` 元数据设计
- 数据完整性校验
- 带标注的轨迹回放
- 后续扩展到 LeRobot / Isaac Sim / MoveIt 的工程基础

## 明确不做

第一阶段不做 ROS2、DDS、MoveIt、`ros2_control`、Isaac Sim、真实机械臂硬件、强化学习训练、大规模数据集采集或完整机器人控制系统。

## 环境安装

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## V0 最小检查

生成一张渲染图像和一个关节状态文件：

```bash
python scripts/collect_episode.py --mode v0 --output dataset_sample/v0
```

期望输出：

```text
dataset_sample/v0/
├── image.png
├── joint_state.npy
└── metadata.json
```

## V1 采集一个 Episode

```bash
python scripts/collect_episode.py --output dataset_sample/episode_000001 --num-steps 100
```

期望输出：

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

## V2 校验和回放

校验采集到的 `episode`：

```bash
python scripts/validate_dataset.py dataset_sample/episode_000001
```

生成带标注的 GIF 回放：

```bash
python scripts/visualize_episode.py dataset_sample/episode_000001
```

输出文件：

```text
dataset_sample/episode_000001/replay.gif
```

## 数据字段

每个 `episode` 包含：

- `images/*.png`：固定 RGB 相机图像
- `states.npy`：机械臂关节位置，shape 为 `[T, state_dim]`
- `actions.npy`：目标关节位置，shape 为 `[T, action_dim]`
- `ee_poses.npy`：末端位姿 `[x, y, z, qx, qy, qz, qw]`，shape 为 `[T, 7]`
- `object_poses.npy`：cube 位姿 `[x, y, z, qx, qy, qz, qw]`，shape 为 `[T, 7]`
- `metadata.json`：仿真器、任务、相机、维度和 `episode` 元数据

详细说明见 [docs/data_schema.md](docs/data_schema.md) 和 [docs/collection_pipeline.md](docs/collection_pipeline.md)。

## 作品集定位

简历中可以这样表达：

> 基于 PyBullet 搭建机械臂桌面任务仿真环境，实现 `image-state-action episode` 数据采集流程，支持 RGB 图像、关节状态、末端位姿、物体位姿、动作和元数据的同步保存，并实现 `episode` 数据完整性校验与轨迹回放。

面试中重点说明：

- 为什么先用 PyBullet 快速跑通最小数据闭环
- 如何保证图像、状态、动作和位姿按 step 对齐
- `validate_dataset.py` 如何发现缺失文件和帧数不一致
- `visualize_episode.py` 如何把采集结果变成可展示材料
- 后续如何扩展到 LeRobot 数据格式、Isaac Sim 合成数据、MoveIt 轨迹生成或 ROS2 执行日志

这个项目应被表达为机器人数据工程和仿真采集流程项目，而不是完整控制算法项目。
