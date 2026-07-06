# Phase 2 Roadmap: 双向 RRT + PyBullet 碰撞检测

本文档拆解 `design_10day.md` 中 Phase 2（Day 3–4）的实施任务：

> 纯 Python 双向 RRT 避障算法编写与 PyBullet 碰撞检测集成。

前提：Phase 1（HAL + IK + 笛卡尔）与 Phase 1.5（Task FSM + Evaluator）已完成。
数据格式仍以 `../dev/data_schema.md` 为准；默认 `--planner cartesian` 行为不得破坏。

## 1. 阶段目标

### 1.1 本阶段要完成

- 实现 PyBullet 配置空间碰撞检测，检测前后保存/恢复关节状态。
- 从 URDF 读取关节限位，供 RRT 采样与 clamp。
- 实现纯 Python 双向 RRT-Connect（关节空间，7-DOF）。
- 扩展 Motion Planner：`plan_rrt_segment` + 统一 `PlanningResult`。
- 障碍物场景 + `scripts/run_rrt_demo.py` 可视化 demo。
- 采集链路可选 `--planner rrt`；规划失败写入 metadata。
- Evaluator 运行时 `unexpected_collision` 检测。
- 单元测试 + headless PyBullet 集成测试。

### 1.2 本阶段不做

- 不做 RRT*、OMPL 或 MoveIt 接入。
- 不替换默认 Cartesian 规划器。
- 不提交 episode 二进制数据到 Git。

## 2. 推荐目录结构

```text
robot-arm-episode-data-lab/
├── core/
│   ├── collision.py
│   ├── joint_limits.py
│   └── rrt.py
├── agents/
│   └── motion_planner.py      # plan_rrt_segment, PlanningResult
├── scripts/
│   ├── run_rrt_demo.py
│   └── collect_episode.py     # --planner rrt, 障碍物场景
└── tests/
    ├── test_collision.py
    ├── test_rrt.py
    └── test_rrt_integration.py
```

## 3. Day 3：碰撞检测 + RRT 核心

### 3.1 任务 1：关节限位提取

目标文件：

- `core/joint_limits.py`

工作内容：

- 通过 `getJointInfo` 读取 lower/upper limit。
- 提供 `clamp()` 与 `sample_uniform()` 供 RRT 使用。

验收标准：

- [x] `get_joint_limits(robot_id, joint_indices)` 返回 7 维限位。
- [x] clamp 不超出 URDF 范围。

完成记录：

- 已实现 `JointLimits` dataclass 与 `get_joint_limits()`。

### 3.2 任务 2：PyBullet 碰撞检测

目标文件：

- `core/collision.py`

工作内容：

- `CollisionChecker.is_configuration_free()`：`reset_joint_positions` → `getClosestPoints` → 恢复状态。
- 支持 `ignore_pairs`（如 robot–cube 抓取阶段）。
- 自碰撞：非相邻 link 对检测。

验收标准：

- [x] home 配置无碰撞（不含 plane，避免固定基座误报）。
- [x] 已知侵入障碍物配置返回 False。
- [x] 检测后关节状态不变。

完成记录：

- 主 API：`p.getClosestPoints`；`tests/test_collision.py` 3 项通过。

### 3.3 任务 3：双向 RRT-Connect

目标文件：

- `core/rrt.py`

工作内容：

- `bidirectional_rrt_connect()`：采样、extend、双树互连。
- `resample_joint_path()`：按控制步数重采样关节路径。
- 失败原因：`start_in_collision` / `goal_in_collision` / `timeout`。

验收标准：

- [x] mock `is_free` 下 2D 开盒能找到路径。
- [x] 起点在碰撞区报告 `start_in_collision`。
- [x] 窄缝 mock 报告 `timeout`。

完成记录：

- 纯 Python 线性最近邻；`tests/test_rrt.py` 4 项通过。

## 4. Day 4：场景集成 + 作品集包装

### 4.1 任务 4：Motion Planner 扩展

目标文件：

- `agents/motion_planner.py`

工作内容：

- `PlanningResult(success, actions, failure_reason)`。
- `plan_rrt_segment()` 调用 RRT + 碰撞检测 + 重采样。
- `plan_cartesian_segment()` 同步返回 `PlanningResult`。

验收标准：

- [x] RRT 成功返回非空 `actions`。
- [x] 失败不 silent fallback。

完成记录：

- `tests/test_motion_planner.py` 覆盖 Cartesian `PlanningResult`。

### 4.2 任务 5：障碍物场景与 RRT Demo

目标文件：

- `scripts/collect_episode.py`（`setup_world(with_obstacles=True)`）
- `scripts/run_rrt_demo.py`

障碍物位置：`(0.52, 0.12, 0.10)`，halfExtents `[0.05, 0.05, 0.15]`。

验收命令：

```bash
python scripts/run_rrt_demo.py --seed 7
python scripts/run_rrt_demo.py --gui   # 可选视觉确认
python scripts/run_rrt_demo.py --seed 7 \
  --save-gif assets/gifs/demo_rrt_obstacle.gif
```

验收标准：

- [x] headless 规划成功，EE 误差 < 8 cm。
- [x] 退出码 0。
- [x] `--save-gif` 可生成 README 展示用绕障回放。

完成记录：

- 实测 EE 误差约 1.2 cm（seed=7）。

### 4.3 任务 6：采集链路 `--planner rrt`

目标文件：

- `scripts/collect_episode.py`

建议最小改法：

- 默认 `cartesian`；`rrt` 时加载障碍物并调用 `plan_rrt_segment`。
- metadata 扩展：`planning_mode`、`planning_success`、`planning_failure_reason`。

验收命令：

```bash
python scripts/collect_episode.py --task pick_and_lift --planner rrt \
  --num-steps 80 --output dataset_sample/episode_pick_rrt
python scripts/collect_episode.py --task pick_and_lift --num-steps 80 \
  --output dataset_sample/episode_pick_001   # 默认 cartesian 不变
```

验收标准：

- [x] RRT 模式能跑完 episode 落盘（规划成功时）。
- [x] 规划失败 metadata 含 `planning_failure_reason`。
- [x] 默认 cartesian 与 Phase 1 行为一致。

完成记录：

- `plan_segment_for_phase()` 统一调度；失败时 `evaluator.abort_with_reason()`。

### 4.4 任务 7：Evaluator 碰撞拦截

目标文件：

- `agents/evaluator.py`

工作内容：

- 可选注入 `CollisionChecker`。
- `inspect_step` 中调用 `has_environment_collision()` → `unexpected_collision`。

验收标准：

- [x] RRT 模式下 Evaluator 持有 collision_checker。
- [x] 失败原因可落盘到 metadata。

完成记录：

- 与 pick_and_lift `--planner rrt` 一并接入。

### 4.5 任务 8：集成测试

目标文件：

- `tests/test_rrt_integration.py`

工作内容：

- headless PyBullet：home → 无障碍 goal，RRT 应成功。

验收标准：

- [x] `pytest tests/test_rrt_integration.py` 通过。

## 5. 验收清单

Phase 2（design 10-day）完成时，应满足：

- [x] `core/collision.py` 配置空间碰撞检测，状态可恢复。
- [x] `core/joint_limits.py` 关节限位读取。
- [x] `core/rrt.py` 双向 RRT-Connect + 路径重采样。
- [x] `agents/motion_planner.py` 提供 `plan_rrt_segment` 与 `PlanningResult`。
- [x] `scripts/run_rrt_demo.py` 可独立演示绕障。
- [x] `collect_episode.py --planner rrt` 可选接入，默认 cartesian 不变。
- [x] metadata 含规划模式与失败原因（见 `../dev/data_schema.md`）。
- [x] `tests/test_collision.py`、`tests/test_rrt.py`、`tests/test_rrt_integration.py` 通过。
- [x] Evaluator `unexpected_collision` 运行时检测。

## 6. 风险与处理策略

### 6.1 固定基座与 ground 误碰撞

处理：碰撞检测 `obstacle_ids` 不含 plane；仅检测显式障碍物与自碰撞。

### 6.2 goal_in_collision

处理：IK 目标配置若与障碍物相交，RRT 前置检查返回 `goal_in_collision`；metadata 标注后中止。

### 6.3 性能

处理：7-DOF 线性最近邻 + max_iterations=2500–3000；headless 单次规划 < 5s。

## 7. 推荐执行顺序

1. `core/joint_limits.py` + `core/collision.py` + `test_collision.py`
2. `core/rrt.py` + `test_rrt.py`
3. `agents/motion_planner.py` 扩展
4. `setup_world(with_obstacles)` + `run_rrt_demo.py`
5. `collect_episode.py --planner rrt` + metadata
6. `evaluator.py` 碰撞拦截 + `test_rrt_integration.py`
7. 更新 `../dev/data_schema.md` 与本 roadmap

## 8. 后续阶段

Phase 2 完成后，按 `design_10day.md` 进入 **Phase 3（Day 5–6）**：夹爪控制优化与抓取物理验证。

广撒网路径中批量 LeRobot 见 [portfolio_roadmap.md](portfolio_roadmap.md)（与 design Phase 2 编号不同，见 [../README.md](../README.md) Phase 对照表）。

## 9. 面试表达重点

> Phase 1 的笛卡尔直线 + IK 无法绕开配置空间障碍。我在关节空间实现了双向 RRT-Connect，用 PyBullet `getClosestPoints` 作碰撞 oracle，通过 `CollisionChecker` 隔离仿真细节。采集链路用 `--planner rrt` 可选接入，规划失败原因写入 metadata，默认 Cartesian 行为保持不变，便于对比演示。
