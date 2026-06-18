# Phase 1 Task 1: PyBullet Control Audit

本文档对应 `hal_ik_roadmap.md` 的 Day 1 任务 1，用于梳理当前
`scripts/collect_episode.py` 中直接调用 PyBullet 的逻辑边界，为后续
`RobotControl` / `PyBulletRobot` 抽象提供迁移清单。

## 1. 当前脚本职责分类

### 1.1 环境创建

相关函数：

- `connect(gui)`
- `setup_world()`
- `get_controlled_joints(robot_id)`

直接 PyBullet 调用：

- `p.connect`
- `p.setAdditionalSearchPath`
- `p.resetSimulation`
- `p.setGravity`
- `p.loadURDF`
- `p.getQuaternionFromEuler`
- `p.getNumJoints`
- `p.getJointInfo`
- `p.resetJointState`
- `p.stepSimulation`
- `p.disconnect`

说明：

- `connect` 和 `setup_world` 负责仿真生命周期与场景搭建，不应直接并入
  `PyBulletRobot`。
- `get_controlled_joints` 与机器人结构有关，可以在后续保留为环境工具函数，
  也可以作为 `PyBulletRobot` 的构造辅助逻辑。

### 1.2 机器人控制

相关函数：

- `joint_positions(world)`
- `link_pose(robot_id, link_index)`
- `smooth_trajectory(step, num_steps, action_dim)`
- `apply_action(world, action, gui)`

直接 PyBullet 调用：

- `p.getJointStates`
- `p.getLinkState`
- `p.setJointMotorControlArray`
- `p.stepSimulation`

说明：

- `joint_positions`、`link_pose`、`apply_action` 是后续最应该迁移进
  `PyBulletRobot` 的控制能力。
- `smooth_trajectory` 是 V1 的动作生成策略，不属于 HAL。后续可以继续保留在
  采集脚本或迁移到 trajectory/task 层。
- `apply_action` 当前同时负责下发电机目标和推进仿真。后续 HAL 中建议拆为
  `set_joint_positions(...)` 与 `step()`，让上层可以明确控制采样节奏。

### 1.3 相机采集

相关函数：

- `render_rgb(camera)`

直接 PyBullet 调用：

- `p.computeViewMatrix`
- `p.computeProjectionMatrixFOV`
- `p.getCameraImage`

说明：

- 相机采集不属于 `PyBulletRobot`，应继续作为数据采集/传感器工具保留。
- 当前输出 RGB `uint8`，shape 为 `[H, W, 3]`，与 `../dev/data_schema.md` 保持一致。

### 1.4 数据保存

相关函数：

- `prepare_episode_dir(output_dir)`
- `save_png(path, rgb)`
- `collect_v0(output_dir, camera, gui)`
- `collect_episode(output_dir, num_steps, camera, gui)`
- `build_metadata(...)`

直接 PyBullet 调用：

- `collect_v0`、`collect_episode` 间接调用环境、控制和相机函数。
- 数据落盘本身不直接依赖 PyBullet。

说明：

- `collect_episode` 是当前闭环主流程，负责保证 images、states、actions、
  ee_poses、object_poses 和 metadata 同步写出。
- Phase 1 后续重构时应优先保持 `collect_episode` 的数据结构和 metadata 字段不变。

## 2. 建议进入 `PyBulletRobot` 的函数能力

后续 `core/pybullet_robot.py` 应吸收以下能力：

- 从 `joint_positions(world)` 迁移：
  - 使用 `p.getJointStates` 读取可控关节位置。
  - 返回 shape 为 `[state_dim]` 的 `np.ndarray`。
- 从 `link_pose(robot_id, link_index)` 迁移：
  - 使用 `p.getLinkState(..., computeForwardKinematics=True)` 读取末端位姿。
  - 对外返回 `(position, orientation)`，其中 position shape 为 `[3]`，
    orientation shape 为 `[4]`。
- 从 `apply_action(world, action, gui)` 迁移：
  - 使用 `p.setJointMotorControlArray` 下发目标关节位置。
  - 将仿真推进拆到独立 `step()`，避免控制接口隐式改变采样频率。
- 从 `setup_world()` 的初始化片段迁移：
  - 提供 `reset_joint_positions(target_positions)`，封装 `p.resetJointState`。
- 新增能力：
  - 使用 `p.calculateInverseKinematics` 实现 `compute_ik(...)`。

不建议进入 `PyBulletRobot` 的逻辑：

- PyBullet 连接和断开：`connect`、`p.disconnect`。
- 场景物体创建：plane、cube 的 `p.loadURDF`。
- 相机矩阵和渲染：`render_rgb`。
- episode 目录清理、PNG 保存、npy 保存和 metadata 生成。
- V1 预设动作策略：`smooth_trajectory`。

## 3. 当前数据行为保护点

后续改造必须保持：

- `states.npy` 和 `actions.npy` 为二维数组。
- `ee_poses.npy` 和 `object_poses.npy` 第二维为 7，格式为
  `[x, y, z, qx, qy, qz, qw]`。
- 图像帧从 `images/000000.png` 开始连续命名。
- `metadata.json` 中的 `num_steps`、`state_dim`、`action_dim` 与实际数组一致。
- 默认控制模式仍为 `joint_position`，除非显式新增 `cartesian_ik` 模式。

## 4. 验收命令

任务 1 不改变采集脚本行为，验收命令仍为：

```bash
python scripts/collect_episode.py --output dataset_sample/episode_000001 --num-steps 12
python scripts/validate_dataset.py dataset_sample/episode_000001
```

为避免开发时覆盖样例数据，也可以先使用临时目录做等价验证：

```bash
python scripts/collect_episode.py --output /tmp/robot_arm_phase1_task1_episode --num-steps 12
python scripts/validate_dataset.py /tmp/robot_arm_phase1_task1_episode
```
