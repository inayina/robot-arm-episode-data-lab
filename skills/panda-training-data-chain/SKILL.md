---
name: panda-training-data-chain
description: Use when developing this repository's Panda data, training, offline evaluation, dataset inspection, upstream adapter, or replay export pipeline. Apply it before editing Panda schema, training scripts, LeRobot export paths, or docs that define boundaries with ros2-arm-teleoperation-suite and ros2-moveit-pybullet-bridge.
---

# Panda Training Data Chain

This repository is the data, training, and offline evaluation lab. It is not a ROS 2 runtime.

## Start Here

Read these files before changing the Panda pipeline:

- `docs/planning/panda_training_data_chain_roadmap.md`
- `configs/robot_schemas/panda.yaml`
- `docs/dev/upstream_downstream_contracts.md`
- `docs/reference/integration_with_bridge.md`

## Core Rules

- Keep Panda as the current main robot schema.
- Do not migrate Panda work to UR3/UR5; future robots need separate schema files.
- Do not add ROS 2 runtime nodes, MoveIt execution, or real robot drivers here.
- Do not silently mix KUKA/iiwa PyBullet episodes with Panda training datasets.
- Do not silently truncate upstream `action[8]` to `ee_delta_gripper[7]`.
- Treat missing optional modalities as warnings, not hard failures.

## Data Contract

Canonical schema:

```text
configs/robot_schemas/panda.yaml
```

Required first-pass fields:

- `observation.state[8]`: 7 Panda joint positions plus gripper opening.
- `observation.ee_pose[7]`: xyz plus xyzw quaternion.
- `action[7]`: default `ee_delta_gripper`.
- `timestamp`, `frame_index`, `episode_index`, `task`.

Upstream compatibility:

- `ros2-arm-teleoperation-suite` currently records `observation.state[7]` plus `observation.gripper[1]`.
- Its current `action[8]` is pose plus gripper and should be labeled `ee_pose_gripper`.
- Derive `ee_delta_gripper[7]` explicitly before training a delta-action policy.

Downstream handoff:

- First replay artifact is neutral JSONL.
- Bridge owns execution, limits, collision checks, distribution-shift monitoring, and risk closure.

## Development Workflow

1. Preserve existing PyBullet/KUKA behavior unless the task explicitly targets it.
2. Add schema-aware tests for every new training/data script.
3. Prefer small, inspectable JSON reports and manifests.
4. Keep large datasets and generated training reports out of Git.
5. Run focused tests before summarizing changes.

Useful checks:

```bash
python3 -c "import yaml; yaml.safe_load(open('configs/robot_schemas/panda.yaml', encoding='utf-8'))"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_panda_schema.py tests/test_validate_dataset.py tests/test_joint_names.py -q
```

For Phase 1 dataset inspection:

```bash
python3 training/scripts/make_mock_panda_dataset.py --output /tmp/panda_mock_dataset
python3 training/scripts/inspect_dataset.py --dataset /tmp/panda_mock_dataset --schema configs/robot_schemas/panda.yaml
```

For Phase 2 upstream adaptation:

```bash
python3 training/scripts/adapt_upstream_panda_dataset.py \
  --input /path/to/upstream/episode_000000/train \
  --output data/exports/panda_demo \
  --schema configs/robot_schemas/panda.yaml
```

Use `--derive-ee-delta-action` only when you explicitly want to convert upstream pose+gripper actions into `ee_delta_gripper[7]`.

For Phase 3 dataset releases:

```bash
python3 training/scripts/prepare_dataset_release.py \
  --input data/exports/panda_demo_delta \
  --output data/exports/panda_demo_delta_release \
  --schema configs/robot_schemas/panda.yaml \
  --release-id panda_demo_delta_v0
```

Train/eval scripts should consume release directories with `manifest.json`, not ad hoc temporary adapter outputs.

For Phase 4 smoke training:

```bash
python3 training/scripts/train_act_smoke.py \
  --dataset data/exports/panda_demo_delta_release \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke
```

Smoke training requires `action_type=ee_delta_gripper`; reject `ee_pose_gripper` releases until they are explicitly converted.

For Phase 5 offline evaluation:

```bash
python3 training/scripts/evaluate_policy.py \
  --dataset data/exports/panda_demo_delta_release \
  --checkpoint training/reports/panda_act_smoke/checkpoint.npz \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke/eval.json
```

For Phase 6 replay export:

```bash
python3 training/scripts/replay_policy.py \
  --dataset data/exports/panda_demo_delta_release \
  --checkpoint training/reports/panda_act_smoke/checkpoint.npz \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke/predicted_actions.jsonl
```

For Phase 7 bridge handoff:

```bash
python3 training/scripts/prepare_bridge_handoff.py \
  --dataset data/exports/panda_demo_delta_release \
  --replay training/reports/panda_act_smoke/predicted_actions.jsonl \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke/bridge_handoff \
  --handoff-id panda_demo_delta_bridge_v0
```
