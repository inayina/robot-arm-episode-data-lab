# Project Status

本文档由 `scripts/update_project_docs.py` 自动生成，用于减少手动同步进度文档的成本。

广撒网 4 周详细任务见 [portfolio_roadmap_broad.md](portfolio_roadmap_broad.md)。

## 作品集基线

- [x] V0 最小样例：`dataset_sample/v0/`
- [x] V1 episode 数据闭环：`dataset_sample/episode_000001/`
- [x] 数据校验脚本：`scripts/validate_dataset.py`
- [x] 回放 GIF 脚本：`scripts/visualize_episode.py`
- [x] 数据结构与采集流程文档：`docs/data_schema.md`, `docs/collection_pipeline.md`

## Phase 0.5 工程与展示（广撒网）

- [x] config 接入采集脚本：`collect_episode.py --config configs/default.yaml`
- [ ] 统一样例 episode：`dataset_sample/episode_000001/`（100 步、640×480）
- [x] 展示 GIF：`assets/gifs/demo_replay.gif`
- [x] pytest 测试：`pytest -q`
- [x] GitHub Actions CI：`.github/workflows/ci.yml`
- [x] LICENSE：`LICENSE`

## Phase 1 HAL + IK + 笛卡尔

- [x] 任务 1：PyBullet 控制逻辑审计：`docs/phase1_task1_pybullet_audit.md`
- [x] 任务 2：RobotControl 抽象基类：`core/hal.py`
- [x] 任务 3：PyBulletRobot 控制封装：`core/pybullet_robot.py`
- [x] 任务 4：HAL smoke demo：`scripts/run_cartesian_demo.py`
- [x] 任务 5：IK 求解封装：`core/ik.py`
- [x] 任务 6：笛卡尔直线插补：`core/trajectory.py`
- [x] 任务 8：采集脚本接入 cartesian_ik 模式：`collect_episode.py --control-mode cartesian_ik`

## Phase 1.5 任务可信度（广撒网）

- [x] Task FSM：`agents/task_fsm.py`
- [x] Evaluator Agent：`agents/evaluator.py`
- [x] Motion planner 模块：`agents/motion_planner.py`
- [x] 成功 pick/lift GIF：`assets/gifs/demo_pick_success.gif`

## Phase 2 批量数据 + LeRobot（广撒网）

- [x] 批量采集脚本：`scripts/batch_collect.py`
- [x] 数据集目录 ≥ 20 episode：`dataset/v1/`
- [x] LeRobot 真导出：`export_lerobot_style.py`
- [x] 数据集 README：`dataset/v1/README.md`

## Phase 3 展示与迁移叙事（广撒网）

- [x] 面试讲稿：`docs/interview_walkthrough.md`
- [x] ROS/MoveIt 迁移设计：`docs/migration_ros2_moveit.md`
- [x] 广撒网路线图文档：`docs/portfolio_roadmap_broad.md`

## 更新方式

```bash
python scripts/update_project_docs.py
```

如已启用 `.githooks/pre-commit`，提交前会自动刷新本文件以及
`README.md`、`PLAN.md`、`roadmap.md` 中的自动进度快照。
