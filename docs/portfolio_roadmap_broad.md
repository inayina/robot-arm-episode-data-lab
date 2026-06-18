# 广撒网求职路线图（4 周）

本文档是 `PLAN.md` 的增补计划，面向 **控制 / 具身 AI / 仿真数据 / 机器人软件**
等多方向同时投递。原则：**先保证可复现与可展示，再叠控制深度与数据规模**。

与现有文档的关系：

- `PLAN.md` V0/V1/V2：已完成的作品集基线，不再推翻。
- `roadmap.md` Phase 1：HAL + IK + 笛卡尔插补，广撒网 **必做**。
- 本文档：在 Phase 1 之上追加工程化、任务可信度、批量数据与面试材料。

明确 **广撒网阶段不做**（用设计文档替代实现即可）：

- 完整 ROS2 / DDS 栈
- Isaac Sim 真接入
- 真实机械臂硬件
- 大规模 RL 训练
- 复杂 RRT 避障（可选加分，非必做）

---

## 总览：4 周节奏

| 周 | 主题 | 核心产出 | 简历可写 |
|----|------|----------|----------|
| W1 | 工程可信 + Phase 1 | CI、pytest、config 接入、HAL/IK/笛卡尔 | 模块化控制 + 质量门禁 |
| W2 | 任务闭环 + Agent 骨架 | success 标签、pick/lift、evaluator FSM | 闭环任务 + 自动评测 |
| W3 | 数据规模 + LeRobot | 批量采集、20+ episode、真导出 | 模仿学习数据工程 |
| W4 | 展示 + 迁移叙事 | README GIF、讲稿、ROS/MoveIt 迁移设计 | 30 秒看懂 + 5 分钟讲清 |

---

## Phase 0.5：工程与展示（W1 前 2–3 天）

目标：让 reviewer **clone 后 5 分钟内跑通**，且样例与文档一致。

### 任务清单

| ID | 任务 | 产出 | 验收命令 |
|----|------|------|----------|
| 0.5.1 | 接入 `configs/default.yaml` | `collect_episode.py` 读 YAML | 改 yaml 中 `num_steps` 后采集步数变化 |
| 0.5.2 | 统一样例 episode | `dataset_sample/episode_000001/` 与 README 一致（建议 100 步、640×480） | `validate_dataset` 通过 |
| 0.5.3 | 展示资产 | `assets/gifs/demo_replay.gif` | README 顶部可嵌入 |
| 0.5.4 | 最小测试 | `tests/test_validate_dataset.py`, `tests/test_trajectory.py` | `pytest -q` 通过 |
| 0.5.5 | CI | `.github/workflows/ci.yml` | push 后自动 validate + pytest |
| 0.5.6 | LICENSE | `LICENSE`（建议 MIT） | 仓库根目录可见 |
| 0.5.7 | 提交叙事 | 按阶段分 commit（V0/V1/Phase0.5…） | `git log` 可读 |

### 验收标准（Phase 0.5 完成）

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/collect_episode.py --config configs/default.yaml --output dataset_sample/episode_000001
python scripts/validate_dataset.py dataset_sample/episode_000001
python scripts/visualize_episode.py dataset_sample/episode_000001
pytest -q
```

---

## Phase 1：HAL + IK + 笛卡尔（W1 后 2–3 天）

与 `roadmap.md` 完全一致，广撒网 **全部必做**。完成后默认仍保留 `joint_position` 模式。

关键验收（Phase 1 完成）：

```bash
python scripts/run_cartesian_demo.py --num-waypoints 30 --steps-per-waypoint 8
python scripts/collect_episode.py --output dataset_sample/episode_cartesian_001 \
  --num-steps 30 --control-mode cartesian_ik
python scripts/validate_dataset.py dataset_sample/episode_cartesian_001
python scripts/visualize_episode.py dataset_sample/episode_cartesian_001
```

面试一句话：

> 将 PyBullet 控制抽象为 `RobotControl` HAL，上层用笛卡尔插补 + IK 生成关节 action，并复用原有 episode 落盘链路。

---

## Phase 1.5：任务可信度（W2）

目标：从「录一段关节轨迹」升级为「有可判定结果的任务 demo」。

### 任务清单

| ID | 任务 | 产出 | 说明 |
|----|------|------|------|
| 1.5.1 | 任务 FSM | `agents/task_fsm.py` | reach → approach → close_gripper → lift |
| 1.5.2 | 评测 Agent | `agents/evaluator.py` | 距离阈值 + 物体 Z 轴抬升判定 success |
| 1.5.3 | 夹爪控制 | 扩展 state/action 或 metadata | 至少 open/close 二值状态 |
| 1.5.4 | success 标签 | `metadata.success`, `metadata.failure_reason` | validate 可选校验字段 |
| 1.5.5 | 任务升级 | `task_name: pick_and_lift` | 允许低成功率，需 1 条成功 GIF |
| 1.5.6 | 采集编排 | `scripts/collect_episode.py` 调用 agents | 保持 episode 格式兼容 |

### 验收标准（Phase 1.5 完成）

```bash
python scripts/collect_episode.py --task pick_and_lift --output dataset_sample/episode_pick_001
python scripts/validate_dataset.py dataset_sample/episode_pick_001
# metadata.success 为 true 的 episode 至少 1 个
python scripts/visualize_episode.py dataset_sample/episode_pick_001
cp dataset_sample/episode_pick_001/replay.gif assets/gifs/demo_pick_success.gif
```

面试一句话：

> 用轻量 FSM 编排 pick-lift 阶段，Evaluator 按物体抬升量自动打 success 标签并写入 metadata。

---

## Phase 2：批量数据 + LeRobot 导出（W3）

目标：对接 **具身 AI / 数据工程** 岗位关键词，不必追求训练 SOTA。

### 任务清单

| ID | 任务 | 产出 | 说明 |
|----|------|------|------|
| 2.1 | 批量采集 | `scripts/batch_collect.py` | 支持 `--num-episodes`, `--seed` |
| 2.2 | 数据集目录 | `dataset/v1/` 下多 episode | 建议 ≥ 20 条，成功 ≥ 5 条 |
| 2.3 | 数据集级校验 | `scripts/validate_dataset.py --dataset dataset/v1` 或新脚本 | 统计 success rate |
| 2.4 | LeRobot 真导出 | 扩展 `export_lerobot_style.py` | 输出可被 LeRobot 加载的结构 |
| 2.5 | 语言指令字段 | `metadata.language_instruction` | 如 `"pick up the cube"` |
| 2.6 | 数据集 README | `dataset/v1/README.md` | episode 数、成功率、字段说明 |

### 验收标准（Phase 2 完成）

```bash
python scripts/batch_collect.py --output dataset/v1 --num-episodes 20 --seed 42
python scripts/validate_dataset.py dataset/v1  # 或等价数据集校验命令
python scripts/export_lerobot_style.py dataset/v1 --output dataset/v1/lerobot_export
```

简历可写：

> 批量采集 20+ pick-lift episode，带 success 标签与 language instruction，并导出 LeRobot 兼容格式。

---

## Phase 3：展示与迁移叙事（W4）

目标：**HR / 非技术面 30 秒看懂**，技术面 **5 分钟讲清架构与扩展**。

### 任务清单

| ID | 任务 | 产出 |
|----|------|------|
| 3.1 | 面试讲稿 | `docs/interview_walkthrough.md` |
| 3.2 | 架构图 | README 内 mermaid 或 `assets/diagrams/architecture.png` |
| 3.3 | 一键复现块 | README「Quick Start」≤ 3 条命令 |
| 3.4 | 迁移设计 | `docs/migration_ros2_moveit.md` | HAL → ros2_control / MoveIt 映射，**文档即可** |
| 3.5 | 能力矩阵 | README「Skills demonstrated」表格 | PyBullet / IK / 数据 schema / LeRobot / CI |
| 3.6 | 可选加分 | 1 分钟屏幕录制链接或 Colab notebook | 放 README |

### 验收标准（Phase 3 完成）

- README 顶部有 demo GIF（joint + cartesian + pick 至少其一）
- 新同事仅看 README 可在 10 分钟内跑通 validate + visualize
- `docs/interview_walkthrough.md` 覆盖：问题、设计、命令、局限、扩展

---

## 广撒网最低可投递线

满足以下 **全部** 即可开始投递（RRT / ROS2 实现非必须）：

- [x] V0/V1/V2 基线（已完成）
- [ ] Phase 0.5：CI + pytest + config + README GIF
- [ ] Phase 1：HAL + IK + cartesian_ik episode
- [ ] Phase 1.5：至少 1 条 `success: true` 的 pick/lift GIF
- [ ] Phase 2：≥ 20 episode + LeRobot 导出骨架可加载
- [ ] Phase 3：interview_walkthrough + migration 设计文档

---

## 按岗位微调（可选加分，不阻塞投递）

| 岗位倾向 | 在最低线之上优先加 |
|----------|-------------------|
| 运动规划 / 控制 | `roadmap` 简化 RRT demo；`run_cartesian_demo` 误差日志 |
| 具身 AI / VLA | language_instruction + LeRobot + 简单 behavior cloning 推理 demo |
| 仿真 / 感知 | 第二相机或 depth 占位字段 + domain randomization 文档 |
| ROS / 真机 | 深化 `migration_ros2_moveit.md`；`RealRobot` HAL stub 类 |

---

## 风险与裁剪

| 风险 | 裁剪策略 |
|------|----------|
| pick 成功率低 | 保留 success 判定；多 seed 批量采，展示「数据工程 + 评测」而非「100% 成功」 |
| LeRobot API 变动 | 导出 manifest + 最小 parquet/npz；README 注明版本 |
| 时间不够 | 保 Phase 0.5 + Phase 1 + 1 条成功 GIF；Phase 2 可先 10 episode |

---

## 更新进度

自动进度见 `README.md` / `PLAN.md` / `docs/project_status.md` 中的快照区块。
手动勾选本文档后，运行：

```bash
python scripts/update_project_docs.py
```
