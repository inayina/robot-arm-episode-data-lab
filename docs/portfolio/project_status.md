# Project Status

本文档由 `scripts/update_project_docs.py` 自动生成。

文档索引：[docs/README.md](../README.md) · 总体架构：[THREE_REPO_ARCHITECTURE.md](../THREE_REPO_ARCHITECTURE.md) · 最小演示：[DEMO_GUIDE.md](../DEMO_GUIDE.md)

> **当前定位**：机械臂具身数据闭环中游已具备 legacy PyBullet 采集、Panda schema、dataset inspection / release、baseline training、offline evaluation 与 bridge handoff 文档链路；
> 当前仍属于 software simulation / Sim-to-Sim readiness，不宣称真实机械臂 Sim2Real 已完成。

## P0 主线状态

| 项目项 | 状态 | 证据 |
|---|---|---|
| Panda canonical schema | x | `configs/robot_schemas/panda.yaml` |
| Dataset inspection / release | x | `training/scripts/inspect_dataset.py`, `training/scripts/prepare_dataset_release.py` |
| Baseline training / eval / replay | x | `checkpoint.npz`, `metrics.json`, `eval.json`, `predicted_actions.jsonl` |
| Bridge handoff bundle | x | `bridge_handoff/` contract for downstream bridge |
| P0 文档入口 | x | overview / data flow / cleaning / training methods / demo / troubleshooting |
| 三仓库架构与跨后端说明 | x | upstream MuJoCo, middle schema, downstream PyBullet |

## Legacy PyBullet / KUKA 保留范围

| 能力 | 当前定位 | 证据 |
|---|---|---|
| PyBullet pick-lift collection | 历史可复现 episode 样例，不再作为 README 主线 | `scripts/collect_episode.py`, `scripts/validate_dataset.py` |
| HAL / IK / RRT / grasp evaluator | 控制与仿真基础能力证据 | `core/hal.py`, `core/ik.py`, `core/rrt.py`, `agents/evaluator.py` |
| LeRobot-style export | legacy dataset export evidence | `scripts/export_lerobot_style.py`, `scripts/export_to_lerobot.py` |
| 旧规划文档 | reference / historical planning | `docs/legacy_pybullet/` |

## 当前不做

- 不做灵巧手。
- 不扩复杂模型或大规模训练。
- 不精修前端界面。
- 不把 Sim-to-Sim / readiness 包装成真实机械臂 Sim2Real。
- 不继续无限扩功能；优先保证 schema、数据流、训练输入输出、handoff 和面试表达一致。

## 验收命令

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
PANDA_DEMO_ROOT="$(mktemp -d /tmp/panda_demo.XXXXXX)"
python3 training/scripts/make_mock_panda_dataset.py --output "$PANDA_DEMO_ROOT/raw"
python3 training/scripts/inspect_dataset.py --dataset "$PANDA_DEMO_ROOT/raw" --schema configs/robot_schemas/panda.yaml
```

更完整的 P0 demo 命令见 [DEMO_GUIDE.md](../DEMO_GUIDE.md)。

## 更新方式

```bash
python scripts/update_project_docs.py
```

如已启用 `.githooks/pre-commit`，提交前会自动刷新
`README.md` 与 `docs/portfolio/project_status.md`。
