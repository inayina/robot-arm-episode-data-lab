# 数据采集流程

目标：按 step 严格对齐的 `image-state-action episode` 闭环。格式见 [data_schema.md](data_schema.md)。

## 1. 环境初始化

`scripts/collect_episode.py` 默认 PyBullet DIRECT 模式，从 `configs/default.yaml` 读参数，CLI 可覆盖。

```bash
python scripts/collect_episode.py --config configs/default.yaml --output dataset_sample/episode_000001
python scripts/collect_episode.py --task pick_and_lift --planner rrt --num-steps 80
python scripts/collect_episode.py --task pick_and_lift --grasp-mode gripper_urdf --num-steps 40 --seed 7
```

`grasp_mode`、`planner` 也可写入 `configs/default.yaml`（见 [quickstart.md](quickstart.md) §配置）。

场景组成：

- 地面 + KUKA iiwa + cube
- `--planner rrt` 时额外加载障碍物 box
- 固定 RGB 相机

## 2. 控制与规划模式

| 模式 | 触发方式 | 动作来源 |
|------|----------|----------|
| `joint_position` | 默认 / config | 预设平滑关节轨迹 |
| `cartesian_ik` | `--control-mode cartesian_ik` | 笛卡尔直线 + IK |
| `task_fsm` | `--task pick_and_lift` | FSM 分段目标 → Motion Planner |

Pick-lift 规划器（`--planner`）：

| 值 | 行为 |
|----|------|
| `cartesian` | 每阶段笛卡尔直线 + IK（默认，与 Phase 1 一致） |
| `rrt` | 关节空间双向 RRT-Connect + PyBullet 碰撞检测 |

规划失败时 metadata 写入 `planning_failure_reason`，episode 优雅中止。

## 2.1 pick_and_lift 抓取链路

`--task pick_and_lift` 在 `CLOSE_GRIPPER` 阶段尝试建立物理抓取，**不再**每帧调用 `sync_object_to_grasp_offset`（kinematic demo，无 CLI，仅测试/对照保留）。

### 模式 A：`constraint`（默认）

`core/grasp.py` 的 `ConstraintGraspController`：

```text
reach / approach（gripper_open）
    → CLOSE_GRIPPER：每步 try_grasp()（contact 或 EE–cube 距离阈值）
    → createConstraint(JOINT_FIXED)：cube base ↔ EE link
    → LIFT：约束随 EE 运动；Evaluator 检查 grasp_failed / object_slipped
    → episode 结束：release() 移除约束
```

### 模式 B：`gripper_urdf`（实验）

`core/gripper.py`：`attach_gripper()` 将 `assets/urdf/simple_gripper.urdf` 固定到 EE（`GRIPPER_MOUNT_OFFSET_Z=-0.055`），`GripperGraspController` 驱动两指 prismatic 关节：

```text
REACH / APPROACH：open()（指关节目标 0.025 m）
    → CLOSE_GRIPPER：close() + try_grasp()（contact 法向力 ≥ grasp_force_threshold，默认 1.0 N）
    → LIFT：保持闭合；靠摩擦/contact 携带 cube（无 fixed constraint）
    → episode 结束：不调用 release()（与 constraint 模式不同）
```

| 实现 | `metadata.grasp_mode` | `state_dim` / `action_dim` | 说明 |
|------|----------------------|----------------------------|------|
| **默认** | `constraint` | 7 / 7 | PyBullet fixed constraint |
| **实验** | `gripper_urdf` | 9 / 9 | 7 臂 + 2 指；见 `tests/test_gripper.py` |
| legacy | — | — | `world.sync_object_to_grasp_offset`（无 `--grasp-mode kinematic`） |

启用夹爪 URDF 模式：

```bash
python scripts/collect_episode.py --task pick_and_lift \
  --grasp-mode gripper_urdf \
  --output dataset_sample/episode_pick_gripper --num-steps 40 --seed 7
```

**success 判定**（`agents/evaluator.py`，`require_grasp_established=True`）：

```text
success = not aborted ∧ grasp_established ∧ object_z_lift ≥ 阈值
```

常见 `failure_reason`：`grasp_failed`、`object_slipped`、`insufficient_lift`。字段详见 [data_schema.md](data_schema.md)。

**验证命令**（与 CI 同款 seed）：

```bash
python scripts/collect_episode.py --task pick_and_lift --num-steps 40 --seed 7 \
  --output dataset_sample/episode_pick_phys
python scripts/validate_dataset.py dataset_sample/episode_pick_phys
python -c "import json; m=json.load(open('dataset_sample/episode_pick_phys/metadata.json')); \
print(m['grasp_mode'], m['grasp_established'], m['success'])"
```

`--planner rrt` 与抓取正交：episode 可落盘，但绕障后 EE 姿态可能导致 `object_slipped`。

**测试覆盖**：CI 仅验证 `grasp_mode=constraint`；`gripper_urdf` 由 `pytest tests/test_gripper.py` 覆盖。

## 3. 仿真步进（每 frame）

1. 计算/读取目标关节位置（action）
2. `apply_action` → PyBullet 位置控制 + 子步进
3. 读取 joints / ee_pose / object_pose
4. Evaluator 步进检查（关节突变、落桌、意外碰撞、**抓取滑落**）
5. 渲染 RGB 并追加到数组

## 4. Episode 落盘

```text
episode_xxx/
├── images/{step:06d}.png
├── states.npy
├── actions.npy
├── ee_poses.npy
├── object_poses.npy
└── metadata.json
```

pick_and_lift 额外字段：`success`、`failure_reason`、`grasp_mode`、`grasp_established`、`planning_mode`、`planning_success` 等。

## 5. 校验与回放

```bash
python scripts/validate_dataset.py dataset_sample/episode_pick_001
python scripts/visualize_episode.py dataset_sample/episode_pick_001
```

## 6. 批量与导出

```bash
python scripts/batch_collect.py --output dataset/v1 --num-episodes 20
python scripts/export_lerobot_style.py dataset/v1 --output dataset/v1/lerobot_export
```

批量采集默认 `grasp_mode=constraint`、`planner=cartesian`（可在 `configs/default.yaml` 修改）。LeRobot 导出对 7 维与 9 维 episode 混排时需留意 joint 命名，见 [data_schema.md](data_schema.md) §LeRobot 导出说明。

本地数据目录见 `.gitignore`，需在本机重新生成。
