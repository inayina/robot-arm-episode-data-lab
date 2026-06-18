# 能力对齐学习手册

> 面向 **AI 辅助开发** 场景：代码可以借助 AI 生成，但面试、答辩、改 bug、接真机时，你必须能独立讲清「为什么这样设计、每一层在干什么、如何验证」。
>
> 本文档把仓库 **已实现能力** 映射到 **应掌握的概念、必读代码、动手验证、自检问题**。概念背景见 [knowledge_base.md](knowledge_base.md)；面试 3–5 分钟版见 [interview_walkthrough.md](../portfolio/interview_walkthrough.md)。

---

## 1. 怎么用这份文档

### 1.1 推荐阅读顺序

```text
1. 跑通 quickstart（30 分钟）
2. 按本文「阶段学习单元」逐块阅读 + 做自检题
3. 对照 tests/ 理解「什么行为被锁死」
4. 用「AI 辅助开发后的真掌握流程」复盘你参与/未参与的模块
5. 按目标岗位跳读「岗位能力路径」
```

### 1.2 AI 辅助开发时的底线

| 可以交给 AI | 你必须自己掌握 |
|-------------|----------------|
|  boilerplate、测试骨架、文档初稿 | 数据流从 FSM → planner → HAL → episode 的完整链路 |
|  RRT / 碰撞检测的实现细节 | RRT 与 IK、笛卡尔插补的**分工边界** |
|  LeRobot 导出格式对照 | observation / action 对齐原则与 metadata 语义 |
|  CI / pytest 配置 | 为什么 CI 只校验样例 episode、本地 dataset 为何不提交 Git |

**判断标准**：关掉 AI，能否在 15 分钟内向同事讲清一次 `collect_episode.py --task pick_and_lift` 从启动到落盘发生了什么；能否指出改 `--planner rrt` 时哪三个文件必看。

### 1.3 能力掌握四级（自评用）

| 级别 | 含义 | 检验方式 |
|------|------|----------|
| L0 知道有 | 听说过模块名 | 能在 README 里找到路径 |
| L1 能跑 | 会执行命令、看 GIF | quickstart 命令无报错 |
| L2 能讲 | 能解释数据流与设计取舍 | 回答本文自检题 ≥ 80% |
| L3 能改 | 能小改参数/逻辑并通过测试 | 完成「动手实验清单」至少 3 项 |

作品集投递建议：**核心模块 L2，至少一个模块 L3**（例如改 Evaluator 阈值或 RRT 参数并跑通 pytest）。

---

## 2. 能力总览矩阵

下表一行对应一个 **可写进简历 / 可面试展开** 的能力点。

| 能力域 | 仓库产出 | 核心概念 | 必读代码 | 验证命令 | 测试锚点 |
|--------|----------|----------|----------|----------|----------|
| 仿真数据闭环 | episode 目录结构 | step 对齐、多模态 observation | `scripts/collect_episode.py` | `validate_dataset.py` + `visualize_episode.py` | `tests/test_validate_dataset.py` |
| 配置驱动工程 | `configs/default.yaml` | CLI 覆盖、可复现 | `collect_episode.py` 配置加载段 | `--config configs/default.yaml` | CI workflow |
| HAL 抽象 | `core/hal.py`, `pybullet_robot.py` | 依赖倒置、真机预留 | `hal.py`, `pybullet_robot.py` | `run_cartesian_demo.py` | HAL smoke 手动 |
| 正/逆运动学 | `core/ik.py` | FK/IK、工作空间、奇异点 | `ik.py`, `pybullet_robot.compute_ik` | cartesian_ik 采集 | `test_trajectory.py` |
| 笛卡尔规划 | `core/trajectory.py` | 位姿插补、waypoint | `trajectory.py`, `motion_planner.plan_cartesian_segment` | `--control-mode cartesian_ik` | `test_motion_planner.py` |
| 任务编排 | `agents/task_fsm.py` | FSM、阶段目标 | `task_fsm.py` | `--task pick_and_lift` | `test_agents.py` |
| 自动评测 | `agents/evaluator.py` | Critic、success 标签 | `evaluator.py` | metadata.success | `test_agents.py` |
| 采样式规划 | `core/rrt.py` | 配置空间、RRT-Connect | `rrt.py`, `joint_limits.py` | `run_rrt_demo.py` | `test_rrt.py` |
| 碰撞检测 | `core/collision.py` | 配置空间可行性 oracle | `collision.py` | `--planner rrt` | `test_collision.py` |
| 规划调度 | `agents/motion_planner.py` | PlanningResult、失败语义 | `motion_planner.py` | cartesian vs rrt 对比 | `test_rrt_integration.py` |
| 批量数据工程 | `batch_collect.py` | 种子、成功率统计 | `batch_collect.py` | 20+ episode | 本地 `dataset/v1` |
| LeRobot 对接 | `export_lerobot_style.py` | observation/action 映射 | 导出脚本 + `data_schema.md` | export 后结构检查 | 手动 |
| 展示与复现 | `assets/gifs/*.gif` | replay 作为行为证据 | `visualize_episode.py`, `run_rrt_demo.py --save-gif` | 生成 GIF | 目视 |
| 软件质量 | pytest + CI | 回归、数据门禁 | `tests/`, `.github/workflows/ci.yml` | `pytest -q` | 全绿 |

---

## 3. 阶段学习单元

每个单元包含：**学习目标 → 概念 → 仓库映射 → 必读片段 → 动手 → 自检题**。

### 3.1 基线：Episode 数据闭环（V0/V1）

**学习目标（L2）**：说清一个 step 里 image / state / action / pose 如何对齐；能读懂 `metadata.json` 每个关键字段。

**核心概念**

- Episode = 一次任务执行的完整轨迹
- 对齐：`images/000123.png` ↔ `states[123]` ↔ `actions[123]`
- action 在本项目中 = **关节位置目标**（position control），不是力矩

**仓库映射**

| 概念 | 位置 |
|------|------|
| 目录规范 | [data_schema.md](../dev/data_schema.md) |
| 采集主循环 | `scripts/collect_episode.py` |
| 校验 | `scripts/validate_dataset.py` |
| GIF 回放 | `scripts/visualize_episode.py` |

**必读代码路径**

1. `collect_episode.py`：仿真循环（下发 action → step → 读状态 → 渲染 PNG → append 数组）
2. `validate_dataset.py`：`REQUIRED_ARRAYS`、`REQUIRED_METADATA_KEYS`
3. 打开 `dataset_sample/episode_000001/metadata.json`（或本地生成后查看）

**动手**

```bash
python scripts/collect_episode.py --config configs/default.yaml \
  --output dataset_sample/episode_000001 --num-steps 100 --width 640 --height 480
python scripts/validate_dataset.py dataset_sample/episode_000001
python scripts/visualize_episode.py dataset_sample/episode_000001
```

**自检题**

1. `actions.npy` 的 shape `[T, action_dim]` 里 T 与 PNG 张数必须满足什么关系？
2. `control_mode: joint_position` 与 `cartesian_ik` 在 metadata 里如何区分？action 语义变了吗？
3. 为什么 `.gitignore` 忽略 `dataset/` 但保留 `dataset_sample/` 的部分 metadata？

---

### 3.2 Phase 0.5：工程化与展示

**学习目标（L2）**：解释 CI 在 guard 什么；知道 config 与 CLI 的优先级。

**核心概念**

- 可复现：固定 seed、固定样例 episode 进 CI
- 展示资产：GIF 是「行为证据」，不是装饰

**仓库映射**

- `configs/default.yaml`
- `.github/workflows/ci.yml`（生成 `episode_000001` → validate → pytest）
- `assets/gifs/demo_replay.gif`
- `scripts/update_project_docs.py`（README 进度快照）

**动手**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
python scripts/update_project_docs.py   # 观察 README 自动区块变化
```

**自检题**

1. CI 为什么不提交 `dataset/v1/` 却能声称「批量能力已完成」？
2. pre-commit hook 与 `update_project_docs.py` 各解决什么问题？

---

### 3.3 Phase 1：HAL + IK + 笛卡尔插补

**学习目标（L2）**：画得出 `joint action → EE target → IK → joint target` 链路；能解释为何需要 HAL。

**核心概念**

| 概念 | 一句话 |
|------|--------|
| FK | 关节角 → 末端位姿 |
| IK | 末端目标 → 关节角（可能无解/多解） |
| 笛卡尔插补 | 在 **笛卡尔空间** 对 EE 做直线（或曲线）插值，每点 IK 一次 |
| HAL | 上层只依赖 `RobotControl`，不直接调用 PyBullet API |

**仓库映射**

| 模块 | 文件 |
|------|------|
| 抽象接口 | `core/hal.py` → `RobotControl` |
| PyBullet 实现 | `core/pybullet_robot.py` |
| IK 封装 | `core/ik.py` |
| 直线插值 | `core/trajectory.py` → `interpolate_cartesian_line` |
| Smoke demo | `scripts/run_cartesian_demo.py` |
| 审计笔记 | [pybullet_audit.md](pybullet_audit.md) |

**必读代码路径**

1. `RobotControl` 五个 abstract method 的语义
2. `plan_cartesian_segment`（`agents/motion_planner.py`）：waypoint → IK → actions 列表
3. `collect_episode.py` 中 `--control-mode cartesian_ik` 分支

**动手**

```bash
python scripts/run_cartesian_demo.py
python scripts/collect_episode.py --control-mode cartesian_ik \
  --output dataset_sample/episode_cartesian_001 --num-steps 80
python scripts/validate_dataset.py dataset_sample/episode_cartesian_001
```

**自检题**

1. IK 失败时项目如何处理？会 silent fallback 吗？
2. 笛卡尔直线插补是在 joint space 还是 Cartesian space？
3. 若接真机，你需要新写哪个类、哪些方法签名不能改？

**常见误区（AI 代码高发区）**

- 把 IK 输出直接当 measured state 写入 `states.npy`（应读仿真反馈后的实际关节角）
- 混淆 `set_joint_positions` 与 `apply_action`（后者含 stepSimulation）

---

### 3.4 Phase 1.5：FSM + Evaluator（任务可信度）

**学习目标（L2）**：逐步讲 pick-lift 四阶段；能解释 success 判定逻辑与局限。

**核心概念**

- **Task Planning Agent**（见 [AGENTS.md](../../AGENTS.md)）：FSM 产出阶段目标位姿
- **Evaluation Agent**：每步安全检查 + 结束 success 标签
- 仿真 constraint 抓取：`close_gripper` 阶段用 PyBullet `JOINT_FIXED` 约束 cube 与 EE（非 finger 力闭合）

**仓库映射**

| 阶段 | FSM | Evaluator |
|------|-----|-----------|
| reach | cube 上方 | 关节突变检测 |
| approach | 下降 | 物体掉桌检测 |
| close_gripper | 闭合 | `try_grasp()` → constraint |
| lift | 抬升 | Z 轴抬升 + `grasp_established` → success |

**必读代码**

- `agents/task_fsm.py`：`TaskPhase`、`PHASE_FRACTIONS`、`PickLiftTaskFSM`
- `core/grasp.py`：`ConstraintGraspController`、`try_grasp` / `release`
- `agents/evaluator.py`：`inspect_step`、`evaluate_success`（`grasp_failed` / `object_slipped`）
- `collect_episode.py`：`collect_pick_and_lift` 抓取编排

**动手**

```bash
python scripts/collect_episode.py --task pick_and_lift \
  --output dataset_sample/episode_pick_001 --num-steps 80
python scripts/visualize_episode.py dataset_sample/episode_pick_001 \
  --save-gif assets/gifs/demo_pick_success.gif
# 查看 metadata
python -c "import json; print(json.load(open('dataset_sample/episode_pick_001/metadata.json')))"
```

**自检题**

1. `language_instruction` 字段从哪来？对下游模仿学习有什么用？
2. `failure_reason` 有哪些枚举值？各对应什么触发条件？
3. 为什么 interview 里要主动说「constraint 抓取非真实夹爪」？

---

### 3.5 Phase 2（design）：RRT + 碰撞检测

**学习目标（L2）**：区分 IK / 笛卡尔 / RRT 三者职责；能口述 RRT-Connect 大致流程。

**核心概念**

```text
Task goal (EE pose)
  → IK 得到 goal configuration（关节角）
  → RRT 在 configuration space 找无碰撞路径
  → 重采样为 joint action 序列
  → position control 执行
```

| 概念 | 说明 |
|------|------|
| Configuration space | 向量 = 各关节角；障碍 = 某配置下发生碰撞 |
| Collision oracle | `CollisionChecker.is_configuration_free(q)` |
| RRT-Connect | 两棵随机树双向扩展直至连通 |
| 与 Cartesian 对比 | 直线在 EE 空间不可达时，RRT 在 joint space 绕障 |

**仓库映射**

| 文件 | 职责 |
|------|------|
| `core/joint_limits.py` | URDF 限位、采样 clamp |
| `core/collision.py` | reset joints → closest points → restore |
| `core/rrt.py` | `bidirectional_rrt_connect` |
| `agents/motion_planner.py` | `plan_rrt_segment` |
| `scripts/run_rrt_demo.py` | 独立绕障 demo + `--save-gif` |
| `collect_episode.py --planner rrt` | 带障碍物 pick-lift |

**必读代码**

1. `collision.py`：为何检测前后要 restore joint state
2. `rrt.py`：`_steer`、双树 connect 条件
3. `plan_rrt_segment`：goal_in_collision 等 failure_reason

**动手**

```bash
python scripts/run_rrt_demo.py --seed 7
python scripts/run_rrt_demo.py --seed 7 --save-gif assets/gifs/demo_rrt_obstacle.gif
python scripts/collect_episode.py --task pick_and_lift --planner rrt \
  --output dataset_sample/episode_pick_rrt --num-steps 80
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/test_rrt.py tests/test_collision.py tests/test_rrt_integration.py
```

**自检题**

1. 为什么 RRT 在 **关节空间** 而不是 EE 空间采样？
2. `ignore_pairs` 里为什么有 robot–cube？去掉会怎样？
3. 规划失败时 metadata 写哪些字段？episode 还会落盘吗？
4. `run_rrt_demo.py` 与 `collect_episode --planner rrt` 场景差异是什么？

**面试一句话**

> 笛卡尔 + IK 适合无障碍直线；我在关节空间实现 RRT-Connect，用 PyBullet 碰撞作 oracle，规划失败原因写入 metadata，默认 Cartesian 不变便于 A/B 对比。

---

### 3.6 Phase 2（portfolio）：批量采集 + LeRobot

**学习目标（L2）**：说明批量 pipeline；能对照 LeRobot 字段映射。

**核心概念**

- 数据工程：批量、seed、成功率、language_instruction 统一
- LeRobot：observation / action / task label 帧级对齐

**仓库映射**

- `scripts/batch_collect.py`
- `scripts/export_lerobot_style.py`
- `dataset/v1/README.md`（本地生成）

**动手**

```bash
python scripts/batch_collect.py --output dataset/v1 --num-episodes 20 --seed 42
python scripts/validate_dataset.py dataset/v1
python scripts/export_lerobot_style.py dataset/v1 --output dataset/v1/lerobot_export
```

**自检题**

1. 20 条 episode 里 success rate 如何统计？脚本还是 validate？
2. 导出后 observation.images 与原始 PNG 目录如何对应？
3. 若 HR 问「有没有训练 policy」，标准回答是什么？

---

### 3.7 Phase 3：展示、迁移叙事、软件工程

**学习目标（L1–L2）**：3 分钟讲稿；知道 ROS2 迁移文档在说什么（不要求真接 ROS）。

**仓库映射**

- [interview_walkthrough.md](../portfolio/interview_walkthrough.md)
- [migration_ros2_moveit.md](migration_ros2_moveit.md)
- [architecture.md](../dev/architecture.md)

**自检题**

1. HAL 如何映射到 `ros2_control` / MoveIt？
2. 项目 **刻意没做** 的三件事是什么？为什么？

---

## 4. 按岗位的能力路径

### 4.1 具身 AI / 数据工程（主推）

**必须 L2**：3.1、3.4、3.6  
**建议 L3 实验**：改 `language_instruction` 或 batch seed，重新 export 并 diff 结构

**简历关键词对齐**

- multimodal episode、step-aligned、success label、LeRobot export、dataset validation

**深度追问准备**

- action 是 absolute joint 还是 delta？为什么 V1 选 absolute？
- 失败 episode 要不要进训练集？

---

### 4.2 运动规划 / 机器人软件

**必须 L2**：3.3、3.5  
**建议 L3 实验**：改 `RRTConfig.step_size` 或 `max_iterations`，观察 success rate 与耗时

**简历关键词对齐**

- configuration-space planning、collision checking、RRT-Connect、IK、Cartesian interpolation

**深度追问准备**

- RRT 与 RRT* 区别？为什么本项目不做 RRT*？
- MoveIt 与本项目 planner 接口如何对应？

---

### 4.3 软件工程 / 平台

**必须 L2**：3.1、3.2、3.7  
**建议 L3 实验**：给 `validate_dataset.py` 增加一条 metadata 检查并补测试

**简历关键词对齐**

- pytest、CI gate、config-driven、module layering、agent architecture

---

## 5. AI 辅助开发后的「真掌握」流程

对每个你 **主要用 AI 生成** 的模块，按下面 6 步复盘（约 20 分钟/模块）：

```text
① 画数据流图（纸笔/Excalidraw，不贴 AI 生成的图）
② 只读该模块 + 直接单测，不读其它文件
③ 用自己的话写 5 条 bullet「输入/输出/失败模式」
④ 改一个常数（阈值、步长、迭代次数），预测结果再运行
⑤ 故意改错一行，看哪个测试红、报错信息是否可理解
⑥ 向空椅子讲 2 分钟（录音回放，查口胡）
```

**优先复盘模块（投入产出比最高）**

1. `collect_episode.py` 主循环
2. `agents/motion_planner.py`
3. `agents/evaluator.py`
4. `core/rrt.py` + `core/collision.py`

---

## 6. 动手实验清单（选做 → 升到 L3）

| ID | 实验 | 预期观察 | 涉及测试 |
|----|------|----------|----------|
| E1 | `--num-steps 40` vs `80` 采 pick-lift | 阶段步数分配变化，success 可能变 | validate |
| E2 | Evaluator `lift_threshold` 0.03 → 0.08 | success 变严格 | test_agents |
| E3 | RRT `step_size` 0.12 → 0.05 | 规划更慢或更细 | test_rrt_integration |
| E4 | 障碍物位置微调（`setup_world`） | RRT 失败率上升，metadata 有 reason | 手动 |
| E5 | 新增 metadata 字段 + validator 检查 | CI 能拦住不完整 episode | test_validate_dataset |
| E6 | batch 10 vs 20 episode | 统计 success rate 分布 | 手动 |

---

## 7. 测试 ↔ 能力对照（改代码前先跑）

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
```

| 测试文件 | 锁定的能力 |
|----------|------------|
| `test_validate_dataset.py` | schema、维度、PNG 命名 |
| `test_trajectory.py` | 笛卡尔插补几何 |
| `test_motion_planner.py` | Cartesian PlanningResult |
| `test_agents.py` | FSM 阶段、Evaluator 标签 |
| `test_rrt.py` | RRT 算法单元 |
| `test_collision.py` | 碰撞 oracle 正确性 |
| `test_rrt_integration.py` | headless PyBullet 端到端规划 |

**原则**：AI 改完任意 `core/` 或 `agents/` 文件，至少跑对应 test + 全量 `pytest -q`。

---

## 8. 概念 ↔ 文档 ↔ 代码 速查

| 想搞懂的问题 | 先看 | 再看代码 |
|--------------|------|----------|
| episode 里有什么 | [data_schema.md](../dev/data_schema.md) | `collect_episode.py` 落盘段 |
| 采集怎么选 planner | [collection_pipeline.md](../dev/collection_pipeline.md) | `plan_segment_for_phase` |
| 智能体分工 | [AGENTS.md](../../AGENTS.md) | `task_fsm`, `motion_planner`, `evaluator` |
| RRT 实施顺序 | [rrt_roadmap.md](../planning/rrt_roadmap.md) | `core/rrt.py` |
| 投递节奏 | [portfolio_roadmap.md](../planning/portfolio_roadmap.md) | `project_status.md` |
| 行业背景 | [knowledge_base.md](knowledge_base.md) | — |
| 面试怎么讲 | [interview_walkthrough.md](../portfolio/interview_walkthrough.md) | — |

---

## 9. 学习进度打卡表

复制到个人笔记，学完打勾：

```text
[ ] 基线 episode：能手绘目录结构 + 对齐关系
[ ] validate + visualize 命令熟练
[ ] 能解释 HAL 存在的理由（不看稿）
[ ] 能画 cartesian_ik 数据流
[ ] 能逐步讲 pick-lift FSM
[ ] 能解释 success / failure_reason
[ ] 能区分 cartesian planner 与 rrt planner
[ ] 能口述 RRT-Connect 与碰撞 oracle
[ ] 跑通 run_rrt_demo --save-gif
[ ] 跑通 batch_collect + export_lerobot_style
[ ] 读过 migration_ros2_moveit（文档级）
[ ] 完成 interview_walkthrough 模拟讲解 1 遍
[ ] pytest 全绿且知道每个 test 文件测什么
[ ] 完成动手实验清单 ≥ 3 项
```

**广撒网最低可投递线**（与 [portfolio_roadmap.md](../planning/portfolio_roadmap.md) 一致）：上表前 10 项建议全部打勾；RRT 相关（7–9）为 motion planning 向加分项，数据向可 L1 但需能一句话解释。

---

## 10. 外部学习资源（按需）

| 主题 | 资源 | 与本项目关系 |
|------|------|--------------|
| PyBullet | [PyBullet Quickstart](https://pybullet.org/wordpress/) | 仿真、URDF、getClosestPoints |
| 运动规划 | LaValle *Planning Algorithms*（RRT 章节） | `core/rrt.py` 算法对照 |
| 模仿学习数据 | [LeRobot Docs](https://github.com/huggingface/lerobot) | export 字段语义 |
| ROS2 迁移 | MoveIt 2 概念文档 | [migration_ros2_moveit.md](migration_ros2_moveit.md) 延伸阅读 |

---

## 11. 维护说明

- 仓库新增 Phase 或模块时，同步更新 **第 2 节矩阵** 与 **第 3 节对应单元**。
- 运行 `python scripts/update_project_docs.py` 只更新进度快照，**不会**自动更新本文；能力变更需手动修订本文档。
