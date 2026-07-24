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
| `docs/portfolio/SIM2SIM_ISAAC_P5_EVIDENCE.md` | 中游 | 主线/evidence | 1 MuJoCo + 1 Isaac PoC episode | `training/scripts/compare_sim_backends.py` | 25 frames/backend + scene RGB | 最小 Sim2Sim 分布差异与接口缺口 | 抓取成功、阈值 gate、Sim2Real | keep |
| `docs/EMBODIED_POLICY_EVALUATION_SOP.md` | 中游 | 主线/process | 2026-07 ACT→Isaac 有界评测实战 | 手工固化自 preflight/smoke | `E2_ACT_BASELINE_PREFLIGHT.md` + `evidence/e3_act_*` | 日常评测协议、判定标签、止损与归因闭环 | 统计显著成功率、真机评测、Sim2Real | keep |
| `docs/EVALUATION_REPORT.md` | 中游 | 主线/evidence | 2026-07-20 三仓知识审计 + E0–E3.6 运行产物 | `project_knowledge audit` + 手工证据核对 | E3 nominal20、E3.5 oracle、E3.6 5-seed gate | 当前评测漏斗、Go/No-Go 与对外口径 | 真机、Sim2Real、learned-policy 成功 | keep |
| `docs/E2_E3_MODEL_CARD.md` | 中游 | 主线/evidence | 2026-07-19 30 vs 40-tight home/warm A/B | 手工固化 | `evidence/e3_act_random30_*` + `e3_act_random40_xyalign_tight_*` + checkpoint sha256 | E3 最终 ckpt 选型与止损；hash 可复核 | 任务成功率、真机、Sim2Real | keep |
| `docs/E3P5_ISAAC_SCRIPTED_ORACLE_EXPERIMENT.md` | 中游 | 主线/process | 2026-07-20 E3.5 oracle 实验全过程 | 手工固化 | v1/v2b evidence + 上游 `run_isaac_scripted_oracle.sh` | 物理链 vs 策略归因、面试 STAR | learned-policy 成功、Sim2Real | keep |
| `docs/portfolio/SMOLVLA_RECOVERY_V3_PORTFOLIO.md` | 中游 | 主线/evidence | 2026-07-24 Recovery v3 Pass + S4 授权口径 | 手工固化自 open-loop report | gate_v3 Pass report + checklist + runtime_s4 | 简历/面试可引用的 Pass 数字与禁止话术 | 任务成功、已跑 Isaac、Sim2Real | keep |
| `runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/` | 中游 | 主线/evidence | 2026-07-24 gate_v3 prospective | `run_smolvla_s3_open_loop.py` | fresh seeds 70–74 / 2593 frames | open-loop Pass、执行语义严重度 | 任务成功、Isaac rollout | keep |
| `evidence/downstream/smolvla_v3_ep0_benchmark_summary.json` | 中游(+下游镜像) | 主线/smoke | 2026-07-24 SmolVLA v3 handoff → PolicyRunner | `benchmark_system.py --strategy panda_jsonl_replay --launch-stack` | `runs/smolvla_s3/pybullet_smoke_v3_ep0/` | 1-ep PolicyRunner/`pybullet_ik` reuse smoke；`is_closed_loop=false` | 任务成功、closed-loop grasp、Sim2Real、Isaac Pass | keep |
| `evidence/downstream/smolvla_v3_ep0_risk_offline_20260724T215900Z.json` | 中游(+下游镜像) | 主线/readiness | 2026-07-24 offline RiskAggregator对照 | `scripts/run_offline_risk_readiness.py` | PolicyRunner timeseries + S4 trial reports | 六维风险 readiness对照；挂 bundle `appendix.risk_readiness` | 任务 go/no-go、Sim2Real、覆盖 `failure_lane` / ContinuousTaskEvaluator | keep |
| `evidence/smolvla_v3_eval_framework_20260724/` | 中游 | 主线/contract | 2026-07-24 P1 unified eval envelope | `training/scripts/normalize_unified_eval_report.py` | open-loop summary + PolicyRunner summary + `s4_gate.json` (+ optional risk appendix) | 三后端同一 `unified_eval_report_v0` 分栏；`claims_*=false` | 任务成功、Sim2Real、新指标 | keep |
| `training/smolvla_s3/runtime_s4.py` | 中游 | 主线/contract | S4 chunk10/K5/clip 合同 | 单测 `tests/test_smolvla_s3_runtime_s4.py` | CPU queue fixture | runtime 语义可测 | 真实 Isaac 延迟/成功率 | keep |
| `docs/portfolio/smolvla_recovery_v3_openloop_ee_vs_s2.png` | 中游 | 主线/data plot | 2026-07-24 v3 prospective EE vs S2 | `scripts/generate_smolvla_v3_portfolio_figures.py` | gate_v3 report + `eval_gate_v3.yaml` baselines | EE RMSE 0.0253 m、相对 S2 改善 ≈90.7% | 任务成功、Sim2Real | keep |
| `docs/portfolio/smolvla_v3_openloop_base_vs_lora_paired.png` | 中游 | 主线/data plot | 2026-07-24 base vs LoRA 成对指标 | `scripts/generate_smolvla_v3_portfolio_figures.py` | gate_v3 report（paired base/lora） | LoRA 相对 base 的离线指标改善 + latency p50/p95/max | 任务成功、闭环表现 | keep |
| `docs/portfolio/smolvla_v3_openloop_per_position.png` | 中游 | 主线/data plot | 2026-07-24 P0–P4 按位分解 | `scripts/generate_smolvla_v3_portfolio_figures.py` | gate_v3 report `per_episode_raw_results` | held-out 各随机位 EE/夹爪一致性（P4 最难） | 泛化保证、任务成功 | keep |
| `docs/portfolio/smolvla_s4_bounded5_funnel.png` | 中游 | 主线/data plot | 2026-07-24 S4 有界 funnel | `scripts/generate_smolvla_v3_portfolio_figures.py` | `s4_gate.json` | interface 5/5 → lift 0/5 → Hold | 任务成功、Sim2Real、扩种子依据 | keep |
| `docs/portfolio/smolvla_s4_bounded5_per_seed.png` | 中游 | 主线/data plot | 2026-07-24 S4 逐种子细节 | `scripts/generate_smolvla_v3_portfolio_figures.py` | `episode_results.jsonl` + `trials/seed_*/report.json` | 逐种子 subgoal / EE excursion / latency p50 | 任务成功、Sim2Real | keep |
| `docs/portfolio/smolvla_v3_downstream_policyrunner_timeseries.png` | 中游 | 主线/data plot | 2026-07-24 下游 PolicyRunner smoke 时序 | `scripts/generate_smolvla_v3_portfolio_figures.py` | 下游 `smolvla_v3_ep0_policyrunner_20260724T213800Z/benchmark_timeseries.csv` | 1-ep 命令时延分布（p50 7.7 ms / max 358 ms） | 任务成功、closed-loop、Sim2Real | keep |
| `docs/portfolio/smolvla_v3_eval_framework_summary.png` | 中游 | 主线/data plot | 2026-07-24 三后端 unified envelope 汇总 | `scripts/generate_smolvla_v3_portfolio_figures.py` | `evidence/smolvla_v3_eval_framework_20260724/*.json` | 三后端 gate 分栏一图（Pass/Smoke/Hold；`claims_*=false`） | 任务成功、Sim2Real | keep |
| `docs/SMOLVLA_V3_EVAL_SOP.md` | 中游 | 主线/process | 2026-07-24 v3 全链评测 SOP | 手工固化自 v3/S4/unified 运行 | gate_v3 + S4 + PolicyRunner + unified envelope 产物 | v3 主线评测复现步骤与止损点 | 任务成功、Sim2Real、自动扩种子授权 | keep |
| `evidence/e3p5_isaac_scripted_oracle_5x_lift_20260720/` | 中游 | 主线/evidence | 2026-07-20 oracle v1（失败对照） | `scripts/run_isaac_scripted_oracle.sh` | 名义红块 5 trials + continuous GT lift | 专家指令完成但 lift 0/5；物理 triage 起点 | 物理链已可用 | keep |
| `evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/` | 中游 | 主线/evidence | 2026-07-20 oracle v2b（权威通过） | 同上（修 pick/PD 夹爪/摩擦/GT close_max 后） | 5 trials + `oracle_gate.json` | lift 5/5、`gate_pass=true`、可聚焦 policy | ACT 任务成功、E4 泛化 | keep |
| `evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_video_20260720/` | 中游 | 主线/evidence | 2026-07-20 oracle v2b 成功 lift 视频补录 | `run_isaac_scripted_oracle.sh` + `isaac_scene_video_recorder.py` | 5×`videos/trial_*.mp4` + `oracle_gate.json` | 专家轨迹可视化 lift；与 ACT 近静止对照 | learned-policy 成功、Sim2Real | keep |
| `docs/portfolio/media/e3p5_isaac_scripted_oracle_lift_success_trial0.mp4` | 中游 | 主线/video | 自 video 套件 trial_0 复制 | 手工索引 | `…_v2b_video_…/videos/trial_0.mp4` | 面试可直接打开的成功样例 | 统计显著性、策略成功 | keep |
| `evidence/e3p6_closelift40_5seed_home_20260720/` | 中游 | 主线/evidence | 2026-07-20 close→lift 40-episode checkpoint home smoke | 上游 nominal suite + continuous GT | seeds 2200–2204、`smoke5_gate.json`、5 个真实视频 | interface 5/5；reach/grasp/lift 0/0/0；5/5 `HOME_NO_CLOSE` | E4 泛化、learned-policy lift、Sim2Real | keep |
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
