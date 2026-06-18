# 数据结构说明

本项目将一次机器人任务执行过程保存为一个 `episode` 目录。所有逐步采集的数据都使用相同的 step index 对齐。

## Episode 目录结构

![Episode 目录与 step 对齐](../../assets/diagrams/episode_structure.png)

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

V1 含义（`state_dim=7`，默认 reach / joint 轨迹）：

- 机械臂 7 个可控关节位置（KUKA iiwa revolute joints）

`grasp_mode=gripper_urdf` 时（`state_dim=9`）：

- 前 7 维：臂关节位置（与上相同）
- 后 2 维：平行夹爪指关节位置（prismatic，`simple_gripper.urdf`）
- 布局与 `core/world.py` 的 `state_vector()` 一致：`concat(arm, fingers)`

`metadata.gripper_states` 是逐步 **开闭标记**（1=开、0=合），与 `states` 里的指关节连续数值不同；两种模式都会写入该字段。

后续可扩展字段：

- 关节速度
- 任务阶段标记（当前已在 `metadata.task_phases`）

## 动作

文件：

```text
actions.npy
```

shape：

```text
[T, action_dim]
```

V1 含义（`action_dim=7`）：

- 发送给 PyBullet 位置控制器的目标关节位置（仅臂关节）

`grasp_mode=gripper_urdf` 时（`action_dim=9`）：

- 前 7 维：臂关节目标
- 后 2 维：指关节目标（`FINGER_OPEN_POSITION` / `FINGER_CLOSE_POSITION`）
- 由 `collect_episode._combine_arm_and_gripper_action()` 拼接

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
- `grasp_mode`：抓取实现方式，例如 `constraint`（PyBullet fixed constraint）或 `gripper_urdf`（平行夹爪 URDF；此时 `state_dim`/`action_dim` 通常为 9 = 7 臂关节 + 2 指关节）
- `grasp_established`：是否建立物理抓取
- `grasp_established_at_step`：首次抓取成功的 step 索引（可选）
- `aborted`：episode 内是否触发 Evaluator 步进拦截（`true` 时通常 `success=false`）

`failure_reason` 在物理抓取模式下还可能为 `grasp_failed`、`object_slipped`。

### 评测闭环（pick_and_lift）

`agents/evaluator.py` 在采集时负责 **步进安全检查** 与 **episode 末 success 标签**：

```text
success = not aborted ∧ grasp_established ∧ object_z_lift ≥ 阈值（默认 0.03 m）
```

步进检查（`inspect_step`）常见 `failure_reason`：

| 值 | 触发条件 |
|----|----------|
| `object_fell_below_table` | 物体 Z 低于桌面阈值 |
| `joint_delta_spike` | 相邻步关节变化过大 |
| `unexpected_collision` | RRT 模式下环境碰撞（`--planner rrt`） |
| `grasp_failed` | LIFT 阶段仍未建立抓取 |
| `object_slipped` | 抓取后 cube 相对 EE 距离超阈值 |

episode 末未拦截但抬升不足时写入 `insufficient_lift`。规划失败时写入 `planning_failure_reason`（可与 `failure_reason` 相同，如 `timeout`）。

`validate_dataset.py` 对 `task_name=pick_and_lift` 额外检查：`success` / `failure_reason` / `grasp_established` / `grasp_mode` / `aborted` 一致性与已知 `failure_reason` 枚举。

### 运动规划扩展字段（`--planner rrt`）

- `planning_mode`：`cartesian` 或 `rrt`
- `planning_success`：本 episode 内各阶段规划是否全部成功
- `planning_failure_reason`：规划失败时的原因，例如：
  - `start_in_collision`
  - `goal_in_collision`
  - `timeout`
  - `ik_unreachable`

### LeRobot 导出说明

`scripts/export_lerobot_style.py` 从 episode 的 `state_dim` / `action_dim` 推断 feature shape，并默认将 `images/*.png` 编码为 LeRobot v2.1 MP4：

```text
videos/chunk-000/observation.images.main/episode_000000.mp4
```

`meta/info.json` 中 `features["observation.images.main"]` 为 `dtype: video`；可用 `--no-export-videos` 跳过（仅需 parquet 时）。`gripper_urdf`（9 维）导出时 joint 名为泛化 `joint_0` … `joint_8`；混用 7 维与 9 维 episode 的 dataset 需分开导出或统一 `grasp_mode`。
