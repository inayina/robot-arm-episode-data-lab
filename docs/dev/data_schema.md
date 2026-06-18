# 数据结构说明

本项目将一次机器人任务执行过程保存为一个 `episode` 目录。所有逐步采集的数据都使用相同的 step index 对齐。

## Episode 目录结构

```text
episode_000001/
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

## 图像

路径格式：

```text
images/{step:06d}.png
```

字段含义：

- 固定 RGB 相机观测
- PNG 格式
- shape 为 `[H, W, 3]`
- dtype 为 `uint8`
- 与 `states.npy`、`actions.npy`、`ee_poses.npy`、`object_poses.npy` 按 step 对齐

## 状态

文件：

```text
states.npy
```

shape：

```text
[T, state_dim]
```

V1 含义：

- 机械臂可控关节位置

后续可扩展字段：

- 关节速度
- 夹爪状态
- 任务阶段标记

## 动作

文件：

```text
actions.npy
```

shape：

```text
[T, action_dim]
```

V1 含义：

- 发送给 PyBullet 位置控制器的目标关节位置

## 末端位姿

文件：

```text
ee_poses.npy
```

shape：

```text
[T, 7]
```

单步格式：

```text
[x, y, z, qx, qy, qz, qw]
```

## 物体位姿

文件：

```text
object_poses.npy
```

shape：

```text
[T, 7]
```

单步格式：

```text
[x, y, z, qx, qy, qz, qw]
```

## 元数据

文件：

```text
metadata.json
```

必要字段：

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

示例：

```json
{
  "episode_id": "episode_000001",
  "simulator": "pybullet",
  "task_name": "reach_cube",
  "num_steps": 100,
  "image_width": 640,
  "image_height": 480,
  "state_dim": 7,
  "action_dim": 7,
  "control_mode": "joint_position",
  "robot": "kuka_iiwa",
  "object": "cube",
  "camera": {
    "type": "fixed_rgb",
    "width": 640,
    "height": 480
  }
}
```

### pick_and_lift / 任务评测扩展字段

`task_name` 为 `pick_and_lift` 时常见扩展字段：

- `language_instruction`：任务语言描述
- `success`：是否判定任务成功
- `failure_reason`：失败原因（如 `insufficient_lift`、`planning_failed`）
- `object_z_lift`：物体 Z 轴抬升量
- `gripper_states`：逐步夹爪开闭标记
- `task_phases`：逐步 FSM 阶段名

### 运动规划扩展字段（`--planner rrt`）

- `planning_mode`：`cartesian` 或 `rrt`
- `planning_success`：本 episode 内各阶段规划是否全部成功
- `planning_failure_reason`：规划失败时的原因，例如：
  - `start_in_collision`
  - `goal_in_collision`
  - `timeout`
  - `ik_unreachable`
