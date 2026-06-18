# 面试讲稿：机械臂 Episode 数据采集平台

> 预计讲解时长：3–5 分钟。面向机器人软件 / 具身智能 / 数据工程岗位。
>
> **讲稿前学习准备**：[learning_capability_alignment.md](../reference/learning_capability_alignment.md)（能力矩阵、阶段自检题、岗位路径）。

---

## 1. 30 秒电梯陈述（给 HR 或非技术面）

我做了一个 **PyBullet 机械臂仿真数据采集平台**：能自动执行 pick-lift 任务，同步保存图像、关节状态、动作和位姿，并自动打上成功/失败标签。项目带 **pytest + CI 数据门禁**，已批量采集 20+ 条 episode，并导出 **LeRobot 兼容格式**，适合作为求职作品集中的「仿真 + 数据闭环」样例。

---

## 2. 要解决什么问题？（1 分钟）

真实机器人数据采集成本高、迭代慢。求职作品需要先证明三件事：

1. **能搭仿真环境**，快速产生可复现的演示数据；
2. **数据结构规范**，图像、状态、动作、位姿按 step 严格对齐；
3. **能说明扩展路径**，从仿真 demo 迁移到真机 / ROS / 模仿学习框架。

本项目刻意把范围控制在「**最小但完整的数据闭环**」，而不是堆满 RRT、真机或训练代码。

---

## 3. 系统架构（1 分钟）

![系统分层架构](../../assets/diagrams/architecture.png)

```mermaid
flowchart TB
    subgraph 应用层
        CE[collect_episode.py]
        BC[batch_collect.py]
        VD[validate_dataset.py]
        EX[export_lerobot_style.py]
    end

    subgraph 智能体层
        FSM[task_fsm.py]
        MP[motion_planner.py]
        EV[evaluator.py]
    end

    subgraph 核心层
        TR[trajectory.py]
        IK[ik.py]
        HAL[hal.py]
        PBR[pybullet_robot.py]
        GR[grasp.py]
        GP[gripper.py]
    end

    subgraph 数据层
        EP[episode 目录]
        LR[lerobot_export]
    end

    CE --> FSM
    FSM --> MP
    MP --> TR
    MP --> IK
    IK --> HAL
    HAL --> PBR
    CE --> GR
    CE --> GP
    GR --> EV
    GP --> EV
    EV --> CE
    CE --> EP
    BC --> CE
    VD --> EP
    EX --> LR
```

**分层原则**：

| 层级 | 模块 | 职责 |
|------|------|------|
| HAL | `RobotControl` / `PyBulletRobot` | 隔离 PyBullet 细节，预留真机实现 |
| 核心 | `trajectory` + `ik` | 笛卡尔插补与 IK，生成关节 action |
| 智能体 | FSM + Evaluator | 编排 pick-lift 阶段，自动打 success 标签 |
| 数据 | episode + LeRobot 导出 | 多模态对齐落盘，对接下游训练框架 |

---

## 4. 关键设计决策（1 分钟）

### 4.1 为什么先做 HAL，而不是直接写 PyBullet 调用？

`collect_episode.py` 里原本散落着 `getJointState`、`setJointMotorControlArray` 等调用。抽成 `RobotControl` 后，上层只关心「读关节 / 读末端 / 下发目标 / 解 IK」，未来换 `RealRobot` 或 ROS2 驱动时不必改 FSM 和采集逻辑。

### 4.2 为什么用 FSM + Evaluator，而不是一条硬编码轨迹？

硬编码关节轨迹无法表达「任务是否成功」。`PickLiftTaskFSM` 把任务拆成 reach → approach → close_gripper → lift；`EvaluatorAgent` 在 episode 末判定 `success = not aborted ∧ grasp_established ∧ object_z_lift ≥ 阈值`，并写入 `failure_reason`（如 `grasp_failed`、`object_slipped`），让数据集自带监督信号，适合具身 AI / 数据工程叙事。

### 4.3 数据如何保证对齐？

每个仿真 step 固定顺序：**下发 action → 推进仿真 → 写 states/actions/poses → 存 PNG**。`validate_dataset.py` 检查帧数、数组维度、metadata 一致性，CI 中对样例 episode 自动跑门禁。

---

## 5. 一键复现命令（30 秒）

```bash
python -m pip install -r requirements.txt
python scripts/validate_dataset.py dataset/v1
python scripts/visualize_episode.py dataset_sample/episode_pick_001
```

批量采集与 LeRobot 导出：

```bash
python scripts/batch_collect.py --output dataset/v1 --num-episodes 20 --seed 42
python scripts/export_lerobot_style.py dataset/v1 --output dataset/v1/lerobot_export
```

![LeRobot 导出目录](../../assets/screenshots/lerobot_export_tree.png)

![parquet episode 列结构](../../assets/screenshots/lerobot_parquet_schema.png)

---

## 6. 数据集与字段（30 秒）

![Episode 目录与 step 对齐](../../assets/diagrams/episode_structure.png)

每个 episode 目录结构见 `../dev/data_schema.md`。Phase 1.5 之后 metadata 额外包含：

- `success` / `failure_reason` / `object_z_lift`
- `language_instruction`（如 `"pick up the cube"`）
- `gripper_states` / `task_phases`
- `grasp_mode` / `grasp_established`（物理抓取：`constraint` 默认，或实验性 `gripper_urdf`）

默认 `--grasp-mode constraint`（PyBullet fixed constraint）；`--grasp-mode gripper_urdf` 时 `state_dim`/`action_dim`=9（7 臂 + 2 指关节）。CI 与批量采集默认 constraint；`gripper_urdf` 由 `tests/test_gripper.py` 覆盖。

---

## 7. 已知局限（30 秒，主动说加分）

| 局限 | 说明 | 后续改进 |
|------|------|----------|
| 默认 constraint 非 finger 力闭合 | `grasp_mode=constraint` 用 `createConstraint` 固定 cube 与 EE | 已提供 `--grasp-mode gripper_urdf` 实验分支；真机走 gripper action + 力阈值 |
| `gripper_urdf` 仍为 MVP | 简化平行夹爪 URDF，靠 contact 法向力 latch，成功率低于 constraint | 调摩擦/几何/力阈值；或工业 gripper 模型 |
| RRT + 物理抓取 | `--planner rrt` 可跑完 episode，但绕障后抓取更易 `object_slipped` | 调 grasp 时机 / 夹爪几何 |
| 仿真成功率 | cartesian 模式较稳；物理抓取失败会写入 `grasp_failed` / `object_slipped` | cube 位姿扰动、重采 batch |
| 未接真机 / ROS | 仅有 HAL 抽象与迁移设计文档 | 见 `../reference/migration_ros2_moveit.md` |

**面试话术**：「默认用 PyBullet fixed constraint；另有 `gripper_urdf` 实验模式做 finger 接触抓取。Evaluator 要求 `grasp_established` 且抬升达标才算 success，并区分 `grasp_failed` 与 `insufficient_lift`。真机侧替换为 gripper action + 力阈值，HAL 与 FSM 接口不变。」

---

## 8. 按岗位强调的重点

### 控制 / 运动规划

- `RobotControl` HAL、`PyBulletRobot` 封装
- 笛卡尔直线插补 + `calculateInverseKinematics`
- FSM 分阶段目标位姿

### 具身 AI / 数据工程

- image-state-action episode 对齐
- `success` 标签 + `language_instruction`
- 批量采集 `batch_collect.py`
- LeRobot v2.1 parquet 导出

### 软件工程

- pytest 单元测试 + GitHub Actions CI
- `configs/default.yaml` 配置驱动
- `validate_dataset.py` 数据门禁
- 模块分层：`core/` / `agents/` / `scripts/`

### ROS / 真机

- HAL 与 `ros2_control` / MoveIt 映射设计（文档级）
- 上层 FSM / 采集逻辑可复用，仅替换 HAL 实现

---

## 9. 简历一句话（可直接粘贴）

> 基于 PyBullet 实现 HAL 解耦的机械臂仿真采集平台：笛卡尔插补 + IK 生成 action，FSM 驱动 pick-lift 任务与自动 success 评测，批量采集 20+ 多模态 episode 并导出 LeRobot 格式；含 pytest/CI 与数据校验门禁。

---

## 10. 常见追问与参考答案

**Q：为什么不用 ROS2？**  
A：作品集第一阶段优先 10 秒内跑通数据闭环；HAL 已预留接口，迁移路径写在 `migration_ros2_moveit.md`。

**Q：success 怎么判定？**  
A：`success = not aborted ∧ grasp_established ∧ object_z_lift ≥ 阈值`（默认约 3 cm）。未建立抓取为 `grasp_failed`，抓取后滑落为 `object_slipped`，有抓取但抬升不足为 `insufficient_lift`。

**Q：LeRobot 导出能直接训练吗？**  
A：导出为 v2.1 布局（parquet + `videos/.../observation.images.main/*.mp4` + meta/info.json），含 state/action/ee_pose/language_instruction；默认将固定相机 PNG 序列编码为 MP4。

**Q：和真实 LeRobot 数据集差在哪？**  
A：差在真实硬件噪声、多相机、更复杂任务分布；本项目重点是**格式兼容 + 采集管线可解释**。
