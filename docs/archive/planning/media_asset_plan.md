# Media Asset Plan

> **归档**：当前媒体主线已由 canonical experiment 与 Panda HOC 取代；本文仅保留规划历史。

状态：作品集媒体资产补充计划。目标是让 README 首屏和面试材料的视觉证据对齐当前 Panda / P0 中游主线，而不是继续以 legacy PyBullet/KUKA GIF 为主。

## 1. 当前问题

README 的文字主线已经切到：

```text
Panda schema -> dataset validation/release -> baseline training -> offline eval -> replay handoff
```

但旧媒体资产仍主要来自 legacy PyBullet/KUKA：

- `assets/gifs/demo_replay.gif`
- `assets/gifs/demo_pick_success.gif`
- `assets/gifs/demo_rrt_obstacle.gif`
- `assets/gifs/demo_gripper_urdf.gif`
- `assets/diagrams/architecture.png`
- `assets/diagrams/data_flow_pick_lift.png`

这些资产可以保留，但应降级为 legacy visual evidence。当前主线需要自己的架构图、数据链路图、训练链路图和命令运行证据。

## 2. P0 已补充资产

| 文件 | 类型 | 用途 | 生成方式 |
|---|---|---|---|
| `assets/diagrams/panda_p0_data_loop.png` | diagram | README 首屏说明 Panda P0 数据闭环 | `scripts/generate_portfolio_assets.py` |
| `assets/diagrams/panda_training_pipeline.png` | diagram | 说明 baseline training / eval / replay / handoff | `scripts/generate_portfolio_assets.py` |
| `assets/screenshots/panda_p0_demo_terminal.png` | terminal-style screenshot | 展示 P0 demo 命令链路 PASS | `scripts/generate_portfolio_assets.py` |
| `assets/screenshots/bridge_handoff_bundle.png` | artifact screenshot | 展示 handoff bundle 结构和下游边界 | `scripts/generate_portfolio_assets.py` |
| `assets/diagrams/data_cleaning_lerobot_flow.png` | diagram | 展示 raw episode、cleaning、release、LeRobot/HF export 的边界 | `scripts/generate_portfolio_assets.py` |
| `assets/diagrams/training_methods_matrix.png` | diagram | 展示 inspection-only、linear smoke、MLP BC、未来 ACT/Diffusion 的分层 | `scripts/generate_portfolio_assets.py` |

验收标准：

- README 首屏先展示 P0 主线资产。
- legacy GIF 保留在后面，标题明确为 legacy PyBullet/KUKA。
- 图片不宣称真实机械臂验证。
- 图片里的字段与 `configs/robot_schemas/panda.yaml`、`training/README_TRAINING.md` 一致。

## 3. P1 后续可补资产

| 资产 | 用途 | 不做什么 |
|---|---|---|
| `assets/videos/panda_p0_data_loop.mp4` | 30-60 秒录屏，展示 mock dataset -> inspect -> train -> handoff | 不做花哨剪辑 |
| `assets/screenshots/panda_schema_yaml.png` | 展示 `panda.yaml` 的 state/action 字段 | 不把 YAML 截太长 |
| `assets/screenshots/eval_metrics_json.png` | 展示 `eval.json` 中 MAE/RMSE/per-dim error | 不夸大模型效果 |
| `assets/screenshots/replay_jsonl_sample.png` | 展示 replay JSONL 每行 action contract | 不说可直接上真机 |
| `assets/diagrams/sim_backend_boundary.png` | MuJoCo / schema / PyBullet 后端边界图 | 不建议统一仿真器 |

## 4. P2 暂缓资产

| 资产 | 暂缓原因 |
|---|---|
| 精修前端看板截图 | 当前求职边际收益低 |
| 复杂模型训练曲线大图 | 当前不做大规模训练 |
| 真机照片或实机视频 | 当前没有实机验证，不能伪装 |
| 灵巧手演示图 | 当前明确不做灵巧手 |

## 5. 生成命令

```bash
python3 scripts/generate_portfolio_assets.py
python3 scripts/update_project_docs.py
```

生成后建议检查：

```bash
file assets/diagrams/panda_p0_data_loop.png
file assets/diagrams/panda_training_pipeline.png
file assets/diagrams/data_cleaning_lerobot_flow.png
file assets/diagrams/training_methods_matrix.png
file assets/screenshots/panda_p0_demo_terminal.png
file assets/screenshots/bridge_handoff_bundle.png
```
