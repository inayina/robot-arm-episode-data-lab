# Training Module

This module is the in-repository Panda data, training, offline evaluation, and replay-export workspace.

Current scope:

- Inspect datasets against `configs/robot_schemas/panda.yaml`.
- Generate small mock Panda datasets for tests and smoke runs.
- Keep optional modalities as warnings when absent.
- Keep ROS 2 runtime execution in upstream/downstream repositories.

First smoke commands:

```bash
python3 training/scripts/make_mock_panda_dataset.py --output /tmp/panda_mock_dataset
python3 training/scripts/inspect_dataset.py \
  --dataset /tmp/panda_mock_dataset \
  --schema configs/robot_schemas/panda.yaml
```

Adapt an upstream M6 recorder dataset:

```bash
python3 training/scripts/adapt_upstream_panda_dataset.py \
  --input /path/to/upstream/episode_000000/train \
  --output data/exports/panda_demo \
  --schema configs/robot_schemas/panda.yaml
```

By default, upstream `action[8]` is preserved as `ee_pose_gripper`.
Use `--derive-ee-delta-action` only when a delta-action dataset is required.

Prepare a dataset release:

```bash
python3 training/scripts/prepare_dataset_release.py \
  --input data/exports/panda_demo_delta \
  --output data/exports/panda_demo_delta_release \
  --schema configs/robot_schemas/panda.yaml \
  --release-id panda_demo_delta_v0
```

Run CPU-only smoke training:

```bash
python3 training/scripts/train_act_smoke.py \
  --dataset data/exports/panda_demo_delta_release \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke
```

Run offline evaluation:

```bash
python3 training/scripts/evaluate_policy.py \
  --dataset data/exports/panda_demo_delta_release \
  --checkpoint training/reports/panda_act_smoke/checkpoint.npz \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke/eval.json
```

Export neutral replay JSONL for downstream bridge validation:

```bash
python3 training/scripts/replay_policy.py \
  --dataset data/exports/panda_demo_delta_release \
  --checkpoint training/reports/panda_act_smoke/checkpoint.npz \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke/predicted_actions.jsonl
```

Package the bridge handoff bundle:

```bash
python3 training/scripts/prepare_bridge_handoff.py \
  --dataset data/exports/panda_demo_delta_release \
  --replay training/reports/panda_act_smoke/predicted_actions.jsonl \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke/bridge_handoff \
  --handoff-id panda_demo_delta_bridge_v0
```
