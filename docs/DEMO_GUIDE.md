# Demo Guide

状态：P0 最低可演示闭环。目标是在 10 分钟内跑通 mock Panda dataset 到 bridge handoff 的中游链路。

## 1. Demo Scope

本 demo 展示：

- 生成最小 Panda episode dataset。
- 按 `configs/robot_schemas/panda.yaml` 做 dataset inspection。
- 创建 dataset release。
- 跑 CPU-only baseline training。
- 生成 offline eval。
- 导出 replay JSONL。
- 打包 bridge handoff bundle。

本 demo 不展示：

- ROS 2 runtime。
- MuJoCo GUI。
- PyBullet 执行画面。
- 真实机械臂控制。
- 复杂模型训练。

## 2. Commands

使用临时目录，避免污染仓库：

```bash
export PANDA_DEMO_ROOT="/tmp/panda_p0_demo_$(date +%s)"
mkdir -p "$PANDA_DEMO_ROOT"
```

生成 mock dataset：

```bash
python3 training/scripts/make_mock_panda_dataset.py \
  --output "$PANDA_DEMO_ROOT/raw"
```

检查 schema：

```bash
python3 training/scripts/inspect_dataset.py \
  --dataset "$PANDA_DEMO_ROOT/raw" \
  --schema configs/robot_schemas/panda.yaml
```

创建 release：

```bash
python3 training/scripts/prepare_dataset_release.py \
  --input "$PANDA_DEMO_ROOT/raw" \
  --output "$PANDA_DEMO_ROOT/release" \
  --schema configs/robot_schemas/panda.yaml \
  --release-id panda_p0_demo_v0
```

训练 baseline：

```bash
python3 training/scripts/train_act_smoke.py \
  --dataset "$PANDA_DEMO_ROOT/release" \
  --schema configs/robot_schemas/panda.yaml \
  --output "$PANDA_DEMO_ROOT/train"
```

离线评估：

```bash
python3 training/scripts/evaluate_policy.py \
  --dataset "$PANDA_DEMO_ROOT/release" \
  --checkpoint "$PANDA_DEMO_ROOT/train/checkpoint.npz" \
  --schema configs/robot_schemas/panda.yaml \
  --output "$PANDA_DEMO_ROOT/train/eval.json"
```

导出 replay JSONL：

```bash
python3 training/scripts/replay_policy.py \
  --dataset "$PANDA_DEMO_ROOT/release" \
  --checkpoint "$PANDA_DEMO_ROOT/train/checkpoint.npz" \
  --schema configs/robot_schemas/panda.yaml \
  --output "$PANDA_DEMO_ROOT/train/predicted_actions.jsonl"
```

打包 bridge handoff：

```bash
python3 training/scripts/prepare_bridge_handoff.py \
  --dataset "$PANDA_DEMO_ROOT/release" \
  --replay "$PANDA_DEMO_ROOT/train/predicted_actions.jsonl" \
  --schema configs/robot_schemas/panda.yaml \
  --output "$PANDA_DEMO_ROOT/train/bridge_handoff" \
  --handoff-id panda_p0_demo_bridge_v0
```

## 3. Expected Outputs

```text
$PANDA_DEMO_ROOT/
├── raw/
│   ├── frames.jsonl
│   └── manifest.json
├── release/
│   ├── frames.jsonl
│   ├── inspection_report.json
│   └── manifest.json
└── train/
    ├── checkpoint.npz
    ├── config_resolved.yaml
    ├── eval.json
    ├── metrics.json
    ├── normalization.json
    ├── predicted_actions.jsonl
    └── bridge_handoff/
```

## 4. Acceptance Criteria

| Step | Expected |
|---|---|
| mock dataset | prints `Status`-like completion and writes frames |
| inspect | `Status: PASS` |
| release | `Status: PASS` |
| training | `Status: PASS` and writes `checkpoint.npz` |
| eval | writes `eval.json` |
| replay | writes `predicted_actions.jsonl` |
| handoff | writes `handoff_manifest.json` |

Warnings about missing optional images or tactile streams are acceptable for mock data.

## 5. Interview Script

可以这样讲：

> 这个 demo 不启动机器人 runtime，而是验证中游数据闭环。我先生成一个最小 Panda episode，按统一 schema 检查 required / optional 字段，然后固定成 dataset release。训练只用 CPU 线性 baseline，目标是产出 checkpoint、metrics、eval 和 replay JSONL。最后打包 handoff，交给下游 MoveIt / PyBullet bridge 做执行验证和 Sim2Real-readiness 风险分析。

