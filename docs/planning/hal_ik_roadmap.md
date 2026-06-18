# Phase 1 Roadmap: HAL + IK + Cartesian Interpolation

本文档用于拆解 `design_10day.md` 中 Phase 1 的 2 天实施任务：

> HAL 接口定义、PyBullet IK 求解器与笛卡尔空间直线插补实现。

这里的 Phase 1 指 `baseline_plan.md` 中 V0/V1/V2 作品集基线完成后的增强阶段，
不是推翻现有采集脚本。当前数据格式仍以 `../dev/data_schema.md` 为准。

Phase 1 的目标不是做完整抓取系统，而是在现有 PyBullet 数据采集闭环之上，补齐一层清晰的机器人控制抽象，并让机械臂可以从“预设关节轨迹”升级为“按末端位姿目标生成动作”。

## 1. 阶段目标

### 1.1 本阶段要完成

- 定义 `RobotControl` 硬件抽象接口，隔离上层算法与 PyBullet 细节。
- 实现 `PyBulletRobot`，封装关节读写、末端位姿读取、位置控制和仿真步进。
- 实现 IK 求解封装（Phase 1 使用 PyBullet 内建 IK；阻尼/冗余参数留待后续）。
- 实现笛卡尔空间直线插补，将起点末端位姿和目标末端位姿拆成连续 waypoint。
- 提供一个最小 demo，让机械臂沿笛卡尔直线轨迹靠近 cube。
- 保持现有 `episode` 数据格式不被破坏，继续写出 `images/`、`states.npy`、`actions.npy`、`ee_poses.npy`、`object_poses.npy` 和 `metadata.json`。

### 1.2 本阶段不做

- 不做 RRT 避障。
- 不做真实夹爪抓取闭环。
- 不接 ROS2、MoveIt、Isaac Sim 或真实机械臂。
- 不追求复杂任务成功率，只追求控制抽象、IK、插补链路可运行、可解释、可验证。

## 2. 推荐目录结构

Phase 1 建议新增以下模块：

```text
robot-arm-episode-data-lab/
├── core/
│   ├── __init__.py
│   ├── hal.py
│   ├── pybullet_robot.py
│   ├── ik.py
│   └── trajectory.py
├── scripts/
│   ├── collect_episode.py
│   └── run_cartesian_demo.py
└── hal_ik_roadmap.md
```

各文件职责：

- `core/hal.py`：定义 `RobotControl` 抽象基类。
- `core/pybullet_robot.py`：实现 PyBullet 版本机器人控制器。
- `core/ik.py`：IK 求解封装与输入校验；底层调用 `PyBulletRobot.compute_ik`。
- `core/trajectory.py`：实现笛卡尔直线插补和姿态插值工具。
- `scripts/run_cartesian_demo.py`：最小可运行 demo，用于验证 Phase 1 控制链路。
- `scripts/collect_episode.py`：后续可选择新增 `--control-mode cartesian_ik`，让数据采集复用 Phase 1 能力。

## 3. Day 1: HAL 抽象与 PyBulletRobot

### 3.1 任务 1：梳理现有 PyBullet 控制逻辑

输入文件：

- `scripts/collect_episode.py`
- `../dev/collection_pipeline.md`
- `../dev/data_schema.md`

工作内容：

- 找出当前脚本中直接调用 PyBullet 的部分。
- 区分环境创建、机器人控制、相机采集、数据保存四类逻辑。
- 保留现有数据采集行为，避免重构过大导致 V1 数据闭环失稳。

验收标准：

- 能明确列出哪些函数应该进入 `PyBulletRobot`。
- 原有命令仍可运行：

```bash
python scripts/collect_episode.py --output dataset_sample/episode_000001 --num-steps 12
python scripts/validate_dataset.py dataset_sample/episode_000001
```

完成记录：

- 审计文档：`../reference/pybullet_audit.md`
- 结论：`joint_positions`、`link_pose`、`apply_action` 的核心能力应进入
  `PyBulletRobot`；`resetJointState` 初始化片段应沉淀为
  `reset_joint_positions`；IK 后续由 `calculateInverseKinematics` 封装为
  `compute_ik`。
- 保留在采集层：环境连接/断开、plane/cube 创建、相机渲染、episode 落盘、
  metadata 生成和 V1 `smooth_trajectory`。

### 3.2 任务 2：定义 `RobotControl` 抽象基类

目标文件：

- `core/hal.py`

建议接口：

```python
class RobotControl(ABC):
    @abstractmethod
    def get_joint_positions(self) -> np.ndarray:
        pass

    @abstractmethod
    def get_end_effector_pose(self) -> tuple[np.ndarray, np.ndarray]:
        pass

    @abstractmethod
    def set_joint_positions(self, target_positions: np.ndarray) -> None:
        pass

    @abstractmethod
    def compute_ik(
        self,
        target_position: np.ndarray,
        target_orientation: np.ndarray | None = None,
    ) -> np.ndarray:
        pass

    @abstractmethod
    def step(self) -> None:
        pass
```

设计要求：

- 接口只描述机器人控制能力，不暴露 PyBullet body id、joint id 等底层细节。
- 返回值统一使用 `numpy.ndarray`，便于与 `states.npy`、`actions.npy` 对齐。
- 末端位姿统一为 position + quaternion，格式与现有 `ee_poses.npy` 一致。

验收标准：

- `core/hal.py` 可被导入。
- 抽象方法命名清晰，和现有数据字段一致。

### 3.3 任务 3：实现 `PyBulletRobot`

目标文件：

- `core/pybullet_robot.py`

工作内容：

- 接收 PyBullet client、robot id、可控关节列表、末端 link id。
- 封装 `getJointState` 读取关节角度。
- 封装 `getLinkState` 读取末端位姿。
- 封装 `setJointMotorControlArray` 下发目标关节位置。
- 封装 `calculateInverseKinematics` 计算 IK。
- 提供 `reset_joint_positions`，用于确定性初始化。

验收标准：

- 现有关节位置读取结果 shape 与 `state_dim` 一致。
- 下发目标关节位置后，仿真 step 若干次，`get_joint_positions()` 能观察到关节状态变化。
- `get_end_effector_pose()` 返回 `[x, y, z]` 和 `[qx, qy, qz, qw]`。

### 3.4 任务 4：写最小 HAL smoke test

建议文件：

- `scripts/run_cartesian_demo.py`

工作内容：

- 启动 PyBullet DIRECT。
- 加载 KUKA iiwa、地面、cube。
- 初始化 `PyBulletRobot`。
- 读取初始 joint state 和 ee pose。
- 给一个小幅关节目标，step 仿真并打印前后状态摘要。

验收命令：

```bash
python scripts/run_cartesian_demo.py --num-steps 60
```

验收标准：

- 脚本退出码为 0。
- 输出包含初始末端位置、结束末端位置、关节维度。
- 不生成大量临时文件。

## 4. Day 2: IK 与笛卡尔直线插补

### 4.1 任务 5：实现 IK 求解封装

目标文件：

- `core/ik.py`

建议函数：

```python
def solve_ik(
    robot: RobotControl,
    target_position: np.ndarray,
    target_orientation: np.ndarray | None = None,
) -> np.ndarray:
    ...
```

工作内容：

- 对输入 position/orientation 做 shape 校验。
- 调用 `robot.compute_ik()` 得到目标关节角。
- 保证输出 shape 与当前可控关节数量一致。
- 对异常目标给出清晰错误信息。

验收标准：

- 给定当前末端附近 5-10 cm 的目标点，IK 能返回合法关节向量。
- IK 输出可以直接作为 `actions.npy` 的一帧 action。
- 对错误输入，如 position 不是 3 维，能抛出明确异常。

### 4.2 任务 6：实现笛卡尔直线插补

目标文件：

- `core/trajectory.py`

建议函数：

```python
def interpolate_cartesian_line(
    start_position: np.ndarray,
    end_position: np.ndarray,
    num_waypoints: int,
    start_orientation: np.ndarray | None = None,
    end_orientation: np.ndarray | None = None,
) -> list[tuple[np.ndarray, np.ndarray | None]]:
    ...
```

工作内容：

- 对 position 做线性插值。
- 姿态可以在 Phase 1 先保持起点姿态不变。
- 确保包含起点和终点。
- 确保 `num_waypoints >= 2`。

验收标准：

- waypoints 数量等于 `num_waypoints`。
- 第一帧等于起点，最后一帧等于终点。
- 相邻 waypoint 的距离变化平滑，没有明显跳变。

### 4.3 任务 7：串联 Cartesian -> IK -> Joint Control

目标文件：

- `scripts/run_cartesian_demo.py`

工作内容：

- 读取当前末端位姿作为起点。
- 设置目标点，例如向 cube 方向移动 8-12 cm。
- 生成 20-50 个笛卡尔 waypoint。
- 对每个 waypoint 调用 IK。
- 将 IK 输出作为关节目标下发给 `PyBulletRobot`。
- 每个 waypoint 内 step 若干次，让机器人跟踪目标。

验收命令：

```bash
python scripts/run_cartesian_demo.py --num-waypoints 30 --steps-per-waypoint 8
```

验收标准：

- 脚本退出码为 0。
- 末端位置从起点向目标点移动。
- 每一步 action shape 稳定。
- 没有破坏现有数据采集脚本。

### 4.4 任务 8：把 Phase 1 能力接入采集链路

目标文件：

- `scripts/collect_episode.py`

建议最小改法：

- 保留现有默认预设关节轨迹。
- 新增可选参数：

```bash
--control-mode joint_position
--control-mode cartesian_ik
```

`joint_position` 保持当前行为，`cartesian_ik` 使用 Phase 1 的插补 + IK 链路生成 actions。

验收命令：

```bash
python scripts/collect_episode.py --output dataset_sample/episode_000001 --num-steps 30 --control-mode cartesian_ik
python scripts/validate_dataset.py dataset_sample/episode_000001
python scripts/visualize_episode.py dataset_sample/episode_000001
```

验收标准：

- `states.npy`、`actions.npy`、`ee_poses.npy`、`object_poses.npy` 第一维都等于图像帧数。
- `metadata.json` 中记录 `control_mode: "cartesian_ik"`。
- GIF 能正常生成，便于放进作品集讲解。

## 5. 验收清单

Phase 1 完成时，应满足：

- [x] `core/hal.py` 定义清晰的 `RobotControl` 抽象接口。
- [x] `core/pybullet_robot.py` 实现 PyBullet 机器人控制封装。
- [x] `core/ik.py` 提供 IK 求解入口，并有输入校验。
- [x] `core/trajectory.py` 提供笛卡尔直线插补。
- [x] `scripts/run_cartesian_demo.py` 可以独立验证 HAL + IK + 插补链路。
- [x] `scripts/collect_episode.py` 默认行为保持兼容。
- [x] 可选 `cartesian_ik` 模式能生成合法 episode。
- [x] `scripts/validate_dataset.py` 对新 episode 返回成功。
- [x] `scripts/visualize_episode.py` 能生成回放 GIF。
- [x] README 或后续文档能说明 Phase 1 的工程价值。

## 6. 风险与处理策略

### 6.1 IK 目标不可达

风险：

- 目标点离机械臂太远，IK 返回结果不稳定。

处理：

- Phase 1 只选择当前末端附近的小位移目标。
- demo 中打印目标点、实际末端点和误差。

### 6.2 姿态插值复杂度过高

风险：

- 四元数插值和姿态约束会拉高实现复杂度。

处理：

- Phase 1 姿态先保持不变。
- 后续再补充 slerp 或更严格的末端姿态约束。

### 6.3 过度重构破坏已有数据闭环

风险：

- 把 `collect_episode.py` 一次性拆太多，可能破坏当前已验证的 V1/V2 流程。

处理：

- 先新增 `core/` 和 `run_cartesian_demo.py`。
- 采集脚本只做小范围接入，默认 `joint_position` 行为不变。

## 7. 推荐执行顺序

1. 新增 `core/hal.py` 和 `core/__init__.py`。
2. 从 `collect_episode.py` 中抽出机器人控制相关逻辑，形成 `core/pybullet_robot.py`。
3. 新增 `scripts/run_cartesian_demo.py`，先验证 HAL 可以控制机械臂。
4. 新增 `core/ik.py`，封装 IK 输入校验与输出截断。
5. 新增 `core/trajectory.py`，实现笛卡尔直线插补。
6. 扩展 `run_cartesian_demo.py`，串联 waypoint、IK 和关节控制。
7. 可选扩展 `collect_episode.py --control-mode cartesian_ik`。
8. 运行采集、校验、回放三条命令，更新 README/文档说明。

## 8. 广撒网后续阶段

Phase 1 完成后，若目标是多方向求职（控制 / 具身 AI / 数据工程 / 机器人软件），
请继续执行 [portfolio_roadmap.md](portfolio_roadmap.md)：

- **Phase 0.5**（可与 Phase 1 并行前半段）：CI、pytest、config、README GIF
- **Phase 1.5**：`agents/` FSM + evaluator + pick/lift + success 标签
- **Phase 2**：批量采集 20+ episode + LeRobot 真导出
- **Phase 3**：面试讲稿 + ROS/MoveIt 迁移设计文档

广撒网 **最低可投递线** = Phase 0.5 + Phase 1 + Phase 1.5 + Phase 2 + Phase 3；
design 10-day **Phase 2 RRT** 已实现，见 [rrt_roadmap.md](rrt_roadmap.md)；ROS2 真接入为可选加分项。

## 9. 面试表达重点

Phase 1 完成后，可以这样描述项目能力：

> 在 PyBullet 机械臂数据采集项目中，我将底层仿真控制抽象为 `RobotControl` HAL 接口，并实现了 PyBullet 版本控制器。上层轨迹模块通过笛卡尔直线插补生成末端 waypoint，再通过 IK 转换为关节动作，最终复用原有 episode 数据链路保存 image、state、action 和 pose。这样既保留了最小数据闭环的稳定性，也为后续 RRT、抓取策略和真机迁移预留了清晰接口。
