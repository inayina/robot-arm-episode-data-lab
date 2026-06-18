# 开发快速上手

## 环境

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 测试

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
```

## 核心 Demo

```bash
# HAL + 笛卡尔 + IK smoke test
python scripts/run_cartesian_demo.py

# 双向 RRT 绕障（可加 --gui；headless 生成展示 GIF）
python scripts/run_rrt_demo.py --seed 7
python scripts/run_rrt_demo.py --seed 7 \
  --save-gif assets/gifs/demo_rrt_obstacle.gif

# Pick-lift 任务（默认 Cartesian 规划；物理 constraint 抓取）
python scripts/collect_episode.py --task pick_and_lift \
  --output dataset_sample/episode_pick_001 --num-steps 80 --seed 7

# CI 同款快速验证（64×48）
python scripts/collect_episode.py --task pick_and_lift --num-steps 40 \
  --output dataset_sample/episode_pick_ci --width 64 --height 48 --seed 7
python scripts/validate_dataset.py dataset_sample/episode_pick_ci
# 期望 metadata：grasp_mode=constraint, grasp_established=true, success=true

# Pick-lift + RRT 避障（带障碍物场景；抓取可能 object_slipped）
python scripts/collect_episode.py --task pick_and_lift --planner rrt \
  --output dataset_sample/episode_pick_rrt --num-steps 80
```

## 数据工具链

本地 episode 数据默认不提交 Git，需在本机生成。

```bash
# Phase 0.5 统一样例（100 步、640×480）
python scripts/collect_episode.py --config configs/default.yaml \
  --output dataset_sample/episode_000001 --num-steps 100 --width 640 --height 480
python scripts/validate_dataset.py dataset_sample/episode_000001

# 批量
python scripts/batch_collect.py --output dataset/v1 --num-episodes 20 --seed 42

# 校验与回放
python scripts/validate_dataset.py dataset_sample/episode_pick_001
python scripts/visualize_episode.py dataset_sample/episode_pick_001

# LeRobot 导出
python scripts/export_lerobot_style.py dataset/v1 --output dataset/v1/lerobot_export
```

## 配置

默认配置：`configs/default.yaml`。CLI 参数覆盖 config 同名字段：

```bash
python scripts/collect_episode.py --config configs/default.yaml --num-steps 80
```

## 下一步读什么

- 模块怎么拆： [architecture.md](architecture.md)
- 数据格式： [data_schema.md](data_schema.md)
- 采集模式与规划器： [collection_pipeline.md](collection_pipeline.md)
- Day 1 抓取 spec： [../planning/day1_grasp_spec.md](../planning/day1_grasp_spec.md)
