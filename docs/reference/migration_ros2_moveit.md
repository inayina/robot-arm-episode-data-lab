# HAL → ROS2 / MoveIt 迁移设计

> 本文档为**设计级**说明，不要求仓库内已实现 ROS2 节点。用于面试中展示「仿真到真机 / ROS 栈」的迁移意识。

---

## 1. 迁移目标

将当前 PyBullet 采集平台平滑迁移到 ROS2 + MoveIt2 真机或仿真栈，同时满足：

1. **上层逻辑复用**：`agents/`（FSM、评测）、`core/trajectory.py`、`scripts/batch_collect.py` 的编排逻辑尽量不改；
2. **仅替换 HAL**：把 `PyBulletRobot` 换成 `Ros2Robot` 或 `MoveItRobot`；
3. **数据格式不变**：继续产出 `images/`、`states.npy`、`actions.npy`、`metadata.json` 等同构 episode，或同步录制 ROS bag 再离线转换。

---

## 2. 当前架构回顾

```text
agents/task_fsm.py          # 任务阶段与目标位姿
agents/motion_planner.py    # 笛卡尔段规划 + IK 调用
agents/evaluator.py         # success / 安全拦截
        │
        ▼
core/hal.py :: RobotControl # 抽象接口
        │
        ├── PyBulletRobot   # 当前实现
        └── RealRobot       # 未来实现（本设计）
```

`RobotControl` 当前接口：

| 方法 | 含义 | episode 字段对应 |
|------|------|------------------|
| `get_joint_positions()` | 读关节角 | `states.npy` |
| `get_end_effector_pose()` | 读末端位姿 | `ee_poses.npy` |
| `set_joint_positions()` | 关节位置控制 | `actions.npy` |
| `compute_ik()` | 逆解 | 生成 action 时使用 |
| `step()` | 推进一个控制周期 | 仿真专用；真机为 wait/sync |

---

## 3. 目标 ROS2 软件栈

```text
┌─────────────────────────────────────────────────────────┐
│  应用：collect_episode / batch_collect（Python）         │
├─────────────────────────────────────────────────────────┤
│  agents/ + core/trajectory + core/ik（可保留）           │
├─────────────────────────────────────────────────────────┤
│  HAL：Ros2Robot / MoveItRobot                           │
├─────────────────────────────────────────────────────────┤
│  ROS2                                                     │
│  ├── /joint_states        (sensor_msgs/JointState)       │
│  ├── /follow_joint_trajectory (control_msgs action)      │
│  ├── /compute_ik          (MoveIt MoveGroup service)     │
│  └── /camera/color/image_raw (sensor_msgs/Image)        │
├─────────────────────────────────────────────────────────┤
│  ros2_control + 硬件驱动 / Gazebo / Isaac Sim bridge     │
└─────────────────────────────────────────────────────────┘
```

---

## 4. 接口映射表

### 4.1 `RobotControl` → ROS2 / MoveIt

| RobotControl | PyBullet（现） | ROS2 / MoveIt（目标） |
|--------------|----------------|------------------------|
| `get_joint_positions()` | `getJointStates` | 订阅 `/joint_states` |
| `get_end_effector_pose()` | `getLinkState(ee)` | TF2 `base_link → ee_link` 或 MoveIt FK |
| `set_joint_positions(target)` | `POSITION_CONTROL` | `FollowJointTrajectory` action 或 `JointGroupPositionController` |
| `compute_ik(pos, orn)` | `calculateInverseKinematics` | MoveIt `GetPositionIK` service |
| `step()` | `stepSimulation()` | `rclpy` 定时器 tick / 等待轨迹完成 |

### 4.2 传感器与数据落盘

| episode 字段 | PyBullet（现） | ROS2（目标） |
|--------------|----------------|--------------|
| `images/*.png` | `getCameraImage` | 订阅相机 topic，按时间戳对齐 |
| `states.npy` | 关节读数 | `/joint_states.position` |
| `actions.npy` | 下发的目标关节 | 轨迹 goal / 控制指令 |
| `ee_poses.npy` | `getLinkState` | TF 或 MoveIt FK |
| `object_poses.npy` | `getBasePositionAndOrientation` | 物体 TF / 感知模块 |
| `metadata.json` | 脚本内生成 | 同结构，附 `rosbag_uri` 可选 |

### 4.3 任务与评测字段

| metadata 字段 | 现实现 | ROS 迁移说明 |
|---------------|--------|--------------|
| `language_instruction` | 字符串常量 | 可接 ROS2 topic / 参数服务器 |
| `success` | 物体 Z 抬升 | 可改为 MoveIt 碰撞检测 + 抓取力传感器 |
| `control_mode` | `task_fsm` / `joint_position` | 对应 MoveIt `planning_pipeline` 名称 |

---

## 5. 建议的 `Ros2Robot` 骨架

```python
# core/ros2_robot.py（设计草案，未纳入当前仓库）

class Ros2Robot(RobotControl):
    def __init__(self, node, joint_names: list[str], ee_link: str):
        self._node = node
        self._joint_names = joint_names
        self._ee_link = ee_link
        self._joint_state = None
        self._node.create_subscription(JointState, "/joint_states", self._cb, 10)
        self._traj_client = ActionClient(node, FollowJointTrajectory, "...")

    def get_joint_positions(self) -> np.ndarray:
        # 按 joint_names 顺序从 JointState 抽取
        ...

    def get_end_effector_pose(self) -> tuple[np.ndarray, np.ndarray]:
        # lookup_transform(base_link, ee_link)
        ...

    def set_joint_positions(self, target_positions: np.ndarray) -> None:
        # 发送 FollowJointTrajectory goal
        ...

    def compute_ik(self, target_position, target_orientation=None) -> np.ndarray:
        # 调用 MoveIt GetPositionIK
        ...

    def step(self) -> None:
        # 真机无仿真 step；可 spin_once 或等待轨迹反馈
        rclpy.spin_once(self._node, timeout_sec=0.01)
```

**关键点**：`collect_episode.py` 里把 `make_robot(world)` 换成工厂函数 `make_robot(backend="pybullet"|"ros2")` 即可切换后端。

---

## 6. MoveIt 集成路径

### 6.1 规划与执行替换关系

| 当前模块 | MoveIt 对应能力 |
|----------|-----------------|
| `interpolate_cartesian_line` | `MoveGroup.compute_cartesian_path` |
| `solve_ik` | `MoveGroup.set_pose_target` + `plan()` |
| `PickLiftTaskFSM` | MoveIt Task Constructor（MTC）或保留自研 FSM |
| `EvaluatorAgent` | MoveIt 碰撞矩阵 + 自定义 success 回调 |

### 6.2 推荐迁移顺序

1. **只换 HAL 读**：先 ROS 订阅 joint_states + 相机，仍用 PyBullet 发 action（混合调试）；
2. **换 HAL 写**：MoveIt 规划 + `FollowJointTrajectory` 执行；
3. **换评测**：真机力控 / 视觉位姿替代 Z 轴抬升启发式；
4. **保留 episode 导出**：ROS bag → 离线脚本转现有 episode 结构（复用 `validate_dataset.py`）。

---

## 7. 时间同步与对齐策略

真机/multi-topic 场景必须处理时间戳：

```text
控制周期 tick (例如 10 Hz)
    │
    ├─ 取最新 joint_states (或插值到 tick 时刻)
    ├─ 取最近一帧 camera (允许 ≤1 frame 延迟)
    ├─ 记录 action (本周期下发的 goal)
    └─ 写入 episode step i
```

建议在 `metadata.json` 增加：

- `clock_source`: `"sim"` | `"ros_sim_time"` | `"wall"`
- `control_hz`: 控制频率
- `max_sensor_latency_ms`: 对齐容忍度

---

## 8. 迁移风险与缓解

| 风险 | 缓解 |
|------|------|
| IK 解不一致（PyBullet vs MoveIt） | 采集前做 FK/IK 一致性标定；记录 solver 名称 |
| 轨迹跟踪误差 | `actions.npy` 存 **指令**，`states.npy` 存 **实测** |
| 相机与关节时间不对齐 | 固定控制频率 + 最近邻/插值对齐 |
| 仿真 grasp 无法迁移 | 真机阶段改为夹爪闭合信号 + 力阈值 |

---

## 9. 面试一句话

> 我把 PyBullet 控制封进 `RobotControl` HAL，上层 FSM 和数据落盘不依赖仿真器；迁到 ROS2 时只需实现 `Ros2Robot`，关节状态走 `/joint_states`，笛卡尔目标走 MoveIt IK 与 `FollowJointTrajectory`，episode 格式和校验脚本可原样复用。

---

## 10. 相关文档

- [interview_walkthrough.md](interview_walkthrough.md) — 面试讲稿
- [data_schema.md](data_schema.md) — episode 字段说明
- [AGENTS.md](../AGENTS.md) — 智能体职责划分
- [portfolio_roadmap_broad.md](portfolio_roadmap_broad.md) — 广撒网路线图
