# Training Module

This module is the in-repository Panda data, training, offline evaluation, and replay-export workspace.

Concept docs:

- `docs/DATA_CLEANING_AND_LEROBOT.md` - data cleaning, release, LeRobot/HF export boundaries.
- `docs/TRAINING_METHODS.md` - inspection-only, linear smoke, MLP BC, and future training tiers.
- `docs/TRAINING_PIPELINE.md` - P0 baseline training/eval/replay/handoff pipeline.

Current scope:

- Inspect datasets against `configs/robot_schemas/panda.yaml`.
- Generate small mock Panda datasets for tests and smoke runs.
- Keep optional modalities as warnings when absent.
- Prepare dataset releases before training.
- Export replay JSONL / bridge handoff bundles for downstream validation.
- Keep ROS 2 runtime execution in upstream/downstream repositories.
- Generate low-dimensional EDA for timestamp cadence, joint steps, velocity,
  reversals, and state/action distributions.

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

Run state-only EDA before training:

```bash
python3 training/scripts/eda_low_dim_dataset.py \
  --dataset data/exports/panda_demo_delta_release \
  --output training/reports/panda_low_dim_eda.json
```

Run CPU-only smoke training:

```bash
python3 training/scripts/train_act_smoke.py \
  --dataset data/exports/panda_demo_delta_release \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke
```

Run PyTorch MLP Behavioral Cloning training (requires PyTorch):

```bash
python3 training/scripts/train_mlp_policy.py \
  --dataset data/exports/panda_demo_delta_release \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_mlp_bc \
  --epochs 100 \
  --test-ratio 0.2
```

MLP BC uses an episode-level 80/20 development/test split, never a frame-level
split. Normalization statistics are computed from development episodes only;
the final test split is not used for early stopping or model selection.

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
