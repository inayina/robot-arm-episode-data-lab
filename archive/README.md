# Archive Index

本目录是中游仓库 **legacy / 历史资产** 的索引入口，不是 Panda P0 主线的日常开发路径。

## Panda P0 主线（当前默认）

```text
configs/robot_schemas/panda*.yaml
training/adapters/upstream_m6.py
training/scripts/inspect_dataset.py
training/scripts/prepare_dataset_release.py
training/scripts/adapt_upstream_panda_dataset.py
training/scripts/train_act_*.py
docs/PROJECT_OVERVIEW.md
docs/DATA_FLOW.md
docs/TRAINING_PIPELINE.md
docs/DATA_CLEANING_AND_LEROBOT.md
```

## Legacy PyBullet / KUKA 代码路径

代码仍保留在仓库根目录以便 CI 与历史 demo 可复现，但应视为 **archive runtime**，不要与 Panda training release 混用。

**隔离方式（2026-07-27）**：

- 目录标记：`core/LEGACY_KUKA.md`、`agents/LEGACY_KUKA.md`
- CI job：`.github/workflows/ci.yml` → **`legacy-kuka-pybullet`**（与 `panda-contract-and-test` 分离）
- 配置：`configs/default.yaml` → `robot: kuka_iiwa`

| 路径 | 说明 |
|---|---|
| `core/` | HAL、IK、RRT、PyBullet world、episode writer（Legacy KUKA） |
| `agents/` | legacy task FSM / evaluator（PyBullet 采集链路） |
| `scripts/collect_episode.py` | legacy 单 episode 采集 |
| `scripts/batch_collect.py` | legacy 批量采集 |
| `scripts/validate_dataset.py` | legacy episode 目录校验（非 Panda release） |
| `scripts/run_rrt_demo.py` | RRT 绕障 demo |
| `configs/default.yaml` | legacy KUKA / PyBullet 配置 |

## Legacy 文档

历史设计文档已归档到 [docs/legacy_pybullet/README.md](../docs/legacy_pybullet/README.md)。

已完成的规划类文档见 [docs/archive/README.md](../docs/archive/README.md)。

## 边界提醒

- legacy PyBullet episode **不得** 直接进入 Panda `prepare_dataset_release.py`。
- 上游 MuJoCo raw episode 应通过 `training/scripts/adapt_upstream_panda_dataset.py` 适配后再 inspection / release。
- 物理抓取/放置判定在上游 `batch_generator` + grasp monitor；中游只做 schema + training split 过滤。
