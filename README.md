# robot-arm-episode-data-lab

![PyBullet robot-arm episode replay](assets/gifs/demo_replay.gif)

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
- [x] 展示 GIF：`assets/gifs/demo_replay.gif`
- [x] pytest 测试：`pytest -q`
- [x] GitHub Actions CI：`.github/workflows/ci.yml`
- [x] LICENSE：`LICENSE`

### Phase 1 HAL + IK + 笛卡尔

- [x] 任务 1：PyBullet 控制逻辑审计：`docs/phase1_task1_pybullet_audit.md`
- [ ] 任务 2：RobotControl 抽象基类：`core/hal.py`
- [ ] 任务 3：PyBulletRobot 控制封装：`core/pybullet_robot.py`
- [ ] 任务 4：HAL smoke demo：`scripts/run_cartesian_demo.py`
- [ ] 任务 5：IK 求解封装：`core/ik.py`
- [ ] 任务 6：笛卡尔直线插补：`core/trajectory.py`
- [ ] 任务 8：采集脚本接入 cartesian_ik 模式：`collect_episode.py --control-mode cartesian_ik`

### Phase 1.5 任务可信度（广撒网）

- [ ] Task FSM：`agents/task_fsm.py`
- [ ] Evaluator Agent：`agents/evaluator.py`
- [ ] Motion planner 模块：`agents/motion_planner.py`
- [ ] 成功 pick/lift GIF：`assets/gifs/demo_pick_success.gif`

### Phase 2 批量数据 + LeRobot（广撒网）

- [ ] 批量采集脚本：`scripts/batch_collect.py`
- [ ] 数据集目录 ≥ 20 episode：`dataset/v1/`
- [ ] LeRobot 真导出：`export_lerobot_style.py`
- [ ] 数据集 README：`dataset/v1/README.md`

### Phase 3 展示与迁移叙事（广撒网）

- [ ] 面试讲稿：`docs/interview_walkthrough.md`
- [ ] ROS/MoveIt 迁移设计：`docs/migration_ros2_moveit.md`
- [x] 广撒网路线图文档：`docs/portfolio_roadmap_broad.md`

<!-- AUTO_STATUS_END -->


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

## 广撒网 4 周路线

基线完成后向求职作品集升级，见 [docs/portfolio_roadmap_broad.md](docs/portfolio_roadmap_broad.md)
（工程化 → HAL/IK → 任务评测 → 批量 LeRobot → 面试材料）。

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
