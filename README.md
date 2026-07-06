# robot-arm-episode-data-lab

<!-- README_INTRO_START -->
本仓库是机械臂具身数据闭环的**中游数据实验室**：把上游 MuJoCo / ROS 2 遥操作与仿真交互产生的 raw episode，整理为 simulator-independent episode schema，并完成数据校验、release、回放、最小 baseline training、offline evaluation 与下游 PyBullet bridge handoff。

> 当前定位：作品集级 software simulation / data pipeline，不是成熟商业系统；训练模块用于证明 dataset → training → evaluation 的最小工程闭环，不宣称复杂模型效果或实机 Sim2Real 已完成。

## 三仓库链路

| 层级 | 仓库 | 职责 |
|---|---|---|
| 上游 | `ros2-arm-teleoperation-suite` | MuJoCo / ROS 2 teleop、控制栈、多模态 recorder，产生 raw episode |
| 中游 | `robot-arm-episode-data-lab` | 统一 schema、validation、release、replay、baseline training、handoff |
| 下游 | `ros2-moveit-pybullet-bridge` | PyBullet / MoveIt 执行验证、接触参数排查、Sim2Real-readiness 风险分析 |

```mermaid
flowchart LR
    A["上游：ros2-arm-teleoperation-suite<br/>MuJoCo / ROS 2 Teleop / Safety / Servo / ros2_control / Recorder"]
    B["中游：robot-arm-episode-data-lab<br/>Episode Schema / Validation / Replay / Baseline Training / Handoff"]
    C["下游：ros2-moveit-pybullet-bridge<br/>MoveIt / PyBullet / Grasp Evaluation / Sim2Real-readiness"]

    A -->|"raw episode<br/>teleop input / action / state / observation"| B
    B -->|"validated dataset<br/>policy output / replay JSONL / handoff bundle"| C
    C -.->|"execution risk<br/>grasp stability / frame error / contact sensitivity"| B
```

本仓库仍保留 legacy PyBullet pick-lift 采集、HAL 控制抽象、笛卡尔 IK、双向 RRT、FSM 评测、物理抓取与 LeRobot 导出样例，用于本地可复现 episode 数据闭环；Panda 主线以 `configs/robot_schemas/panda.yaml` 和 `training/` 下的最小训练链路为主。

三仓库总体架构见 [docs/THREE_REPO_ARCHITECTURE.md](docs/THREE_REPO_ARCHITECTURE.md)；跨仿真后端边界见 [docs/SIM_BACKENDS_AND_TRANSFER.md](docs/SIM_BACKENDS_AND_TRANSFER.md)，训练到下游评估的 handoff 见 [docs/TRAINING_TO_SIM2REAL.md](docs/TRAINING_TO_SIM2REAL.md)。

### Panda P0 主线媒体证据

![Panda P0 data loop](assets/diagrams/panda_p0_data_loop.png)

![Panda baseline training pipeline](assets/diagrams/panda_training_pipeline.png)

![Panda P0 demo terminal evidence](assets/screenshots/panda_p0_demo_terminal.png)

![Bridge handoff bundle](assets/screenshots/bridge_handoff_bundle.png)

![Data cleaning and LeRobot export flow](assets/diagrams/data_cleaning_lerobot_flow.png)

![Training methods matrix](assets/diagrams/training_methods_matrix.png)

### Legacy PyBullet / KUKA visual evidence

![关节轨迹回放](assets/gifs/demo_replay.gif)

![Pick-Lift 任务回放](assets/gifs/demo_pick_success.gif)

![RRT 绕障规划回放](assets/gifs/demo_rrt_obstacle.gif)

![Gripper URDF 实验回放](assets/gifs/demo_gripper_urdf.gif)

### 一分钟概览视频

[demo_overview.mp4](assets/videos/demo_overview.mp4)

**Colab 一键复现 →** [notebooks/portfolio_demo.ipynb](notebooks/portfolio_demo.ipynb)

**文档入口 → [docs/README.md](docs/README.md)**（开发先看 [docs/dev/quickstart.md](docs/dev/quickstart.md)）

### Legacy PyBullet / KUKA diagrams

![系统分层架构](assets/diagrams/architecture.png)

![pick_and_lift 数据流](assets/diagrams/data_flow_pick_lift.png)

![Episode 目录与 step 对齐](assets/diagrams/episode_structure.png)

### Legacy LeRobot export evidence

![LeRobot 导出目录](assets/screenshots/lerobot_export_tree.png)

![meta/info.json 字段](assets/screenshots/lerobot_meta_info.png)

![parquet episode 列结构](assets/screenshots/lerobot_parquet_schema.png)

项目状态与收口清单见 [docs/portfolio/project_status.md](docs/portfolio/project_status.md)。
<!-- README_INTRO_END -->

<!-- README_FOOTER_START -->
## 快速开始：Panda P0 data loop

```bash
PANDA_DEMO_ROOT="$(mktemp -d /tmp/panda_p0_demo.XXXXXX)"
python3 training/scripts/make_mock_panda_dataset.py --output "$PANDA_DEMO_ROOT/raw"
python3 training/scripts/inspect_dataset.py --dataset "$PANDA_DEMO_ROOT/raw" \
  --schema configs/robot_schemas/panda.yaml
python3 training/scripts/prepare_dataset_release.py \
  --input "$PANDA_DEMO_ROOT/raw" \
  --output "$PANDA_DEMO_ROOT/release" \
  --schema configs/robot_schemas/panda.yaml \
  --release-id panda_p0_demo_v0
python3 training/scripts/train_act_smoke.py \
  --dataset "$PANDA_DEMO_ROOT/release" \
  --schema configs/robot_schemas/panda.yaml \
  --output "$PANDA_DEMO_ROOT/train"
python3 training/scripts/evaluate_policy.py \
  --dataset "$PANDA_DEMO_ROOT/release" \
  --checkpoint "$PANDA_DEMO_ROOT/train/checkpoint.npz" \
  --schema configs/robot_schemas/panda.yaml \
  --output "$PANDA_DEMO_ROOT/train/eval.json"
python3 training/scripts/replay_policy.py \
  --dataset "$PANDA_DEMO_ROOT/release" \
  --checkpoint "$PANDA_DEMO_ROOT/train/checkpoint.npz" \
  --schema configs/robot_schemas/panda.yaml \
  --output "$PANDA_DEMO_ROOT/train/predicted_actions.jsonl"
python3 training/scripts/prepare_bridge_handoff.py \
  --dataset "$PANDA_DEMO_ROOT/release" \
  --replay "$PANDA_DEMO_ROOT/train/predicted_actions.jsonl" \
  --schema configs/robot_schemas/panda.yaml \
  --output "$PANDA_DEMO_ROOT/train/bridge_handoff" \
  --handoff-id panda_p0_demo_bridge_v0
```

完整说明见 [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md) 和 [training/README_TRAINING.md](training/README_TRAINING.md)。

## Legacy PyBullet episode sample

```bash
python -m pip install -r requirements.txt
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
python scripts/run_rrt_demo.py --seed 7
python scripts/collect_episode.py --task pick_and_lift --num-steps 40 \
  --output dataset_sample/episode_pick_ci --width 64 --height 48 --seed 7
python scripts/validate_dataset.py dataset_sample/episode_pick_ci
```

这部分是旧 KUKA / PyBullet 本地采集样例，用作历史演示和可复现 episode 证据；当前主线是 Panda schema / training / handoff。完整命令见 [docs/dev/quickstart.md](docs/dev/quickstart.md)。

## 文档导航

| 场景 | 文档 |
|------|------|
| 日常开发 | [docs/dev/](docs/dev/) |
| P0 项目总览 | [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) |
| P0 数据流 | [docs/DATA_FLOW.md](docs/DATA_FLOW.md) |
| P0 训练闭环 | [docs/TRAINING_PIPELINE.md](docs/TRAINING_PIPELINE.md) |
| 数据清洗 / LeRobot | [docs/DATA_CLEANING_AND_LEROBOT.md](docs/DATA_CLEANING_AND_LEROBOT.md) |
| 训练方式分层 | [docs/TRAINING_METHODS.md](docs/TRAINING_METHODS.md) |
| P0 最小演示 | [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md) |
| P0 排障表 | [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) |
| 规划 / 路线图 | [docs/planning/](docs/planning/) |
| 概念参考 | [docs/reference/](docs/reference/) |
| **能力学习与自检** | [docs/reference/learning_capability_alignment.md](docs/reference/learning_capability_alignment.md) |
| 面试材料 | [docs/portfolio/](docs/portfolio/) |
| 三仓库总体架构 | [docs/THREE_REPO_ARCHITECTURE.md](docs/THREE_REPO_ARCHITECTURE.md) |
| 跨仿真后端边界 | [docs/SIM_BACKENDS_AND_TRANSFER.md](docs/SIM_BACKENDS_AND_TRANSFER.md) |
| 训练与下游 handoff | [training/README_TRAINING.md](training/README_TRAINING.md), [docs/TRAINING_TO_SIM2REAL.md](docs/TRAINING_TO_SIM2REAL.md) |
| 三仓库文档收口 | [docs/planning/three_repo_documentation_plan.md](docs/planning/three_repo_documentation_plan.md) |
| 媒体资产计划 | [docs/planning/media_asset_plan.md](docs/planning/media_asset_plan.md) |
| 智能体规范 | [AGENTS.md](AGENTS.md) |

## 能力概览

| 领域 | 关键路径 |
|------|----------|
| HAL + IK + 笛卡尔 | `core/hal.py`, `core/ik.py`, `core/trajectory.py` |
| 仿真世界 + 落盘 | `core/world.py`, `core/episode_writer.py`, `core/collect_config.py` |
| RRT 避障 | `core/rrt.py`, `core/collision.py`, `scripts/run_rrt_demo.py` |
| 物理抓取 | `core/grasp.py`（constraint）、`core/gripper.py`（`--grasp-mode gripper_urdf`） |
| 任务 FSM + 评测 | `agents/task_fsm.py`, `agents/evaluator.py` |
| legacy 采集主入口 | `scripts/collect_episode.py`, `scripts/validate_dataset.py` |
| episode schema | [docs/dev/data_schema.md](docs/dev/data_schema.md), `configs/robot_schemas/panda.yaml` |
| dataset inspection / release | `training/scripts/inspect_dataset.py`, `training/scripts/prepare_dataset_release.py` |
| baseline training / evaluation | `training/scripts/train_act_smoke.py`, `training/scripts/evaluate_policy.py`, `training/scripts/replay_policy.py` |
| bridge handoff | `training/scripts/prepare_bridge_handoff.py`, [docs/TRAINING_TO_SIM2REAL.md](docs/TRAINING_TO_SIM2REAL.md) |

简历定位：**机械臂具身数据闭环中游：episode schema / validation / replay / baseline training / Sim2Real-readiness handoff**；收口优先级见 [project_status.md](docs/portfolio/project_status.md)。
<!-- README_FOOTER_END -->
