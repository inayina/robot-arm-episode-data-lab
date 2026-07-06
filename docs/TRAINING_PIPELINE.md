# Training Pipeline

状态：P0 最小训练闭环文档。本文档只描述当前仓库内可复现的 baseline training，不宣称复杂模型效果。

## 1. Purpose

训练模块的目标是证明中游具备完整工程闭环：

```text
dataset -> validation -> release -> baseline training -> offline evaluation -> replay export -> bridge handoff
```

它不是为了展示大模型训练、SOTA policy、真实抓取成功率，也不是为了替代下游 MoveIt / PyBullet / 真机执行验证。

## 2. Input

训练输入应是已经通过 inspection 的 Panda dataset release：

```text
data/exports/panda_demo_delta_release/
├── frames.jsonl
├── inspection_report.json
└── manifest.json
```

`manifest.json` 中关键字段：

| 字段 | 说明 |
|---|---|
| `dataset_format` | 当前为 `panda_release_v0` |
| `release_id` | 稳定 release 名称 |
| `schema_id` | 应与 `panda_ee_delta_gripper_v0` 对齐 |
| `robot` | `panda` |
| `action_type` | 默认训练要求 `ee_delta_gripper` |
| `training_contract.state_key` | 默认 `observation.state` |
| `training_contract.action_key` | 默认 `action` |

## 3. Baseline Policy

当前 baseline：

```text
linear_smoke: observation.state -> action
```

实现：

```text
training/policies/linear_policy.py
training/scripts/train_act_smoke.py
```

它使用 CPU-only NumPy 线性回归和 ridge regularization，主要检查：

- state / action shape 是否可训练。
- train / val split 是否可生成。
- checkpoint 和 normalization 是否可保存。
- 后续 evaluation / replay 是否能消费同一个 checkpoint。

## 4. Training Output

训练命令：

```bash
python3 training/scripts/train_act_smoke.py \
  --dataset data/exports/panda_demo_delta_release \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke
```

输出：

```text
training/reports/panda_act_smoke/
├── checkpoint.npz
├── config_resolved.yaml
├── metrics.json
└── normalization.json
```

`metrics.json` 适合写进作品集的字段：

| 指标 | 说明 | 面试表达 |
|---|---|---|
| `train_loss` | train MSE | 用于确认训练链路可运行 |
| `val_loss` | validation MSE | 用于发现最小过拟合 / 数据切分问题 |
| `train_mae` | train mean absolute error | 比 loss 更直观 |
| `val_mae` | validation mean absolute error | 用于对比 train / val |
| `num_frames` | 训练帧数 | 说明数据规模，不夸大 |
| `state_dim` | 输入维度 | schema contract 证据 |
| `action_dim` | 输出维度 | action contract 证据 |
| `action_type` | action 语义 | 防止 action 维度误读 |

不建议夸大为：

- “训练出了可用抓取策略”。
- “完成 ACT / Diffusion Policy”。
- “可直接迁移到真实机械臂”。

## 5. Offline Evaluation

命令：

```bash
python3 training/scripts/evaluate_policy.py \
  --dataset data/exports/panda_demo_delta_release \
  --checkpoint training/reports/panda_act_smoke/checkpoint.npz \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke/eval.json
```

`eval.json` 应用于回答：

- policy 输出 shape 是否正确。
- 整体 MAE / RMSE 是否可计算。
- 每一维 action 的误差是否异常。
- predicted action 是否过于抖动。
- dataset / checkpoint / schema 是否匹配。

评价边界：

```text
offline eval only != runtime success
```

也就是说，offline error 低不等于 PyBullet 抓取成功，更不等于真机成功。

## 6. Replay Export

命令：

```bash
python3 training/scripts/replay_policy.py \
  --dataset data/exports/panda_demo_delta_release \
  --checkpoint training/reports/panda_act_smoke/checkpoint.npz \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke/predicted_actions.jsonl
```

每行 JSONL 至少包含：

```json
{
  "timestamp": 0.033,
  "episode_index": 0,
  "frame_index": 1,
  "task": "pick_lift",
  "robot": "panda",
  "schema_id": "panda_ee_delta_gripper_v0",
  "release_id": "panda_demo_delta_v0",
  "action_type": "ee_delta_gripper",
  "action": [0.001, 0.0, -0.002, 0.0, 0.0, 0.01, 0.0]
}
```

这个文件是中游和下游之间的最小动作接口。下游可以把它接入 MoveIt / PyBullet replay，但本仓库不负责 runtime execution。

## 7. Bridge Handoff

命令：

```bash
python3 training/scripts/prepare_bridge_handoff.py \
  --dataset data/exports/panda_demo_delta_release \
  --replay training/reports/panda_act_smoke/predicted_actions.jsonl \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke/bridge_handoff \
  --handoff-id panda_demo_delta_bridge_v0
```

输出：

```text
bridge_handoff/
├── predicted_actions.jsonl
├── dataset_manifest.json
├── dataset_inspection_report.json
├── replay_check.json
└── handoff_manifest.json
```

handoff 的验收标准：

- replay 文件能逐行解析。
- 每帧包含 `schema_id`、`release_id`、`action_type`、`episode_index`、`frame_index`。
- action dim 与 schema 一致。
- dataset inspection report 可追溯。
- handoff manifest 说明它是下游验证输入，不是实机执行许可。

