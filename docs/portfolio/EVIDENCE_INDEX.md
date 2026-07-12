# Evidence Index - robot-arm-episode-data-lab

阶段 1 证据资产索引。状态只能是 `keep`, `regenerate`, `relabel`, `move_to_legacy`, `archive`, `delete`。

| 资产 | 当前仓库 | 主线/Legacy | 数据来源 | 生成脚本 | 输入产物 | 能证明 | 不能证明 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `assets/diagrams/architecture.png` | 中游 | Legacy/design | 历史架构说明 | 未定位 | 历史文档 | 早期系统设计 | Panda canonical release/training 已实现 | move_to_legacy |
| `assets/diagrams/data_cleaning_lerobot_flow.png` | 中游 | 主线/design | 中游数据清洗设计 | 未定位 | docs/schema | adapter/release 设计意图 | 运行成功或模型效果 | relabel |
| `assets/diagrams/data_flow_pick_lift.png` | 中游 | Legacy/design | KUKA/PyBullet 历史流程 | 未定位 | legacy docs | 历史 pick/lift 数据流 | Panda 主线 | move_to_legacy |
| `assets/diagrams/eda_joint_reversals_distribution.png` | 中游 | 主线 | Panda low-dim EDA | `training/scripts/eda_low_dim_dataset.py` / plotting script 待确认 | `training/reports/panda_30_low_dim_eda.json` | EDA 统计分布 | 任务成功率、实机能力 | keep |
| `assets/diagrams/eda_joint_step_p99_gate.png` | 中游 | 主线 | Panda low-dim EDA | `training/scripts/eda_low_dim_dataset.py` / plotting script 待确认 | `training/reports/panda_30_low_dim_eda.json` | joint step quality gate | 物理抓取成功 | keep |
| `assets/diagrams/episode_structure.png` | 中游 | Legacy/design | 历史 episode 结构 | 未定位 | legacy docs | 历史数据结构说明 | Panda schema contract | move_to_legacy |
| `assets/diagrams/mlp_bc_loss_comparison.png` | 中游 | 主线/data plot | 2026-07-12 rerun normalized MSE comparison | `scripts/plot_portfolio_results.py` | MLP: `training/reports/panda_mlp_bc/mlp_metrics.json`; Linear: `docs/portfolio/linear_same_split_metrics.json` | 同一 24/6 episode split 下 MLP bar 低于 Linear bar | 不能与 `panda_linear_bc/metrics.json` frame-split smoke MSE 混用；不能证明任务成功率 | keep |
| `assets/diagrams/panda_p0_data_loop.png` | 中游 | 主线/design | Panda P0 data loop | 未定位 | docs | 数据闭环设计 | 运行产物 | relabel |
| `assets/diagrams/panda_domain_randomization_distribution.png` | 中游 | 主线/data plot | copied from downstream Panda randomization plot | `scripts/plot_sim2sim_and_randomization.py` 待确认 | target object pose distribution for 30 episodes | object starting pose coverage | 泛化保证、Sim2Real、抓取成功率 | relabel |
| `assets/diagrams/panda_teleop_trajectories_3d.png` | 中游 | 主线/data plot | 上游 Panda trajectories | `scripts/plot_upstream_trajectories.py` | upstream `data/episodes_mlp` or adapted release | 轨迹覆盖/分布可视化 | 成功率、实机泛化 | keep |
| `assets/diagrams/panda_training_pipeline.png` | 中游 | 主线/design | training pipeline docs | 未定位 | docs/training scripts | 训练流程结构 | 已完成 ACT 或 online rollout | relabel |
| `assets/diagrams/three_repo_dataflow_diagram.png` | 中游 | 主线/design | 三仓流程 | 建议新建 canonical script | `THREE_REPO_CANONICAL_FACTS.md` | 三仓职责流 | benchmark 数字 | regenerate |
| `assets/diagrams/three_repo_run_evidence.png` | 中游 | 主线/evidence collage | 三仓运行产物 | 建议新建 canonical script | canonical metrics + benchmark JSON | 运行证据摘要 | 原始产物本身；实机能力 | regenerate |
| `assets/diagrams/training_methods_matrix.png` | 中游 | 主线/design | training method comparison | 未定位 | docs | 方法定位 | ACT 已完成 | relabel |
| `assets/diagrams/three_repo_canonical_dataflow.svg` | 中游 | 主线/design | phase-2 canonical facts | manual SVG from audit facts | `docs/portfolio/THREE_REPO_CANONICAL_FACTS.md` | 三仓职责边界与数据流 | 运行性能或实机能力 | keep |
| `assets/diagrams/three_repo_canonical_run_evidence.svg` | 中游 | 主线/evidence summary | phase-2 canonical facts and JSON artifacts | manual SVG from audit facts | canonical manifests, metrics, handoff, latest benchmark JSON | README 级运行证据摘要 | 原始产物本身、完整 Sim2Real、实机能力 | keep |
| `assets/gifs/demo_gripper_urdf.gif` | 中游 | Legacy | KUKA/PyBullet demo | 未定位 | legacy sim | 历史 URDF demo | Panda mainline | move_to_legacy |
| `assets/gifs/demo_pick_success.gif` | 中游 | Legacy | KUKA/PyBullet demo | 未定位 | legacy sim | 历史 pick success demo | Panda canonical success | move_to_legacy |
| `assets/gifs/demo_replay.gif` | 中游 | Legacy | KUKA/PyBullet replay | 未定位 | legacy sim | 历史 replay demo | Panda handoff replay | move_to_legacy |
| `assets/gifs/demo_rrt_obstacle.gif` | 中游 | Legacy | KUKA/PyBullet/RRT demo | 未定位 | legacy sim | 历史 RRT obstacle demo | Panda MoveIt Servo/downstream replay | move_to_legacy |
| `assets/screenshots/bridge_handoff_bundle.png` | 中游 | 主线/screenshot | handoff bundle terminal/file tree | 未定位 | `training/reports/panda_mlp_bc/bridge_handoff/` | bundle structure if run ID shown | replay success or latency | relabel |
| `assets/screenshots/lerobot_export_tree.png` | 中游 | Legacy/support | historical export screenshot | 未定位 | legacy export | 文件树示例 | current Panda release facts | move_to_legacy |
| `assets/screenshots/lerobot_meta_info.png` | 中游 | Legacy/support | historical metadata screenshot | 未定位 | legacy export | 元数据示例 | current schema validity | move_to_legacy |
| `assets/screenshots/lerobot_parquet_schema.png` | 中游 | Legacy/support | historical parquet screenshot | 未定位 | legacy export | schema 示例 | current Panda JSONL/release correctness | move_to_legacy |
| `assets/screenshots/panda_p0_demo_terminal.png` | 中游 | 主线/screenshot | terminal run | 未定位 | command output/run ID needed | 命令可运行性 if matched | benchmark validity without JSON | relabel |
| `assets/videos/demo_overview.mp4` | 中游 | Legacy/video | historical overview | 未定位 | legacy sim | 历史演示 | Panda canonical mainline | archive |

## Notes

- 数据图必须在阶段 2 补齐生成脚本和输入产物；无法追溯的图不应出现在 README 首页。
- README 首页建议只保留 3-5 个核心证据：release manifest/inspection, MLP metrics, handoff bundle, replay check warning, selected downstream benchmark reference。
- Legacy KUKA/PyBullet 资产应折叠到 Legacy 区域，不与 Panda canonical experiment 混排。
