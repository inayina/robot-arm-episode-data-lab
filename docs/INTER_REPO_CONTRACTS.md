# Inter-Repo Interface Contracts

This repository is the middle data and training repository in the three-repo robot-arm
loop. It imports upstream raw Panda episodes, validates and adapts schema,
creates immutable dataset releases, trains/evaluates policies, exports
runtime-facing handoff bundles, and sends lightweight feedback upstream.

## Repository Roles

| Repository | Role | Owns | Does not own |
|---|---|---|---|
| `ros2-arm-teleoperation-suite` | Upstream runtime and capture | ROS 2/MuJoCo runtime, raw episodes, recorder schema, upstream validation | Dataset release, training, bridge runtime |
| `robot-arm-episode-data-lab` | Middle data/training repository | Raw import, schema adaptation, filtering, release manifests, ACT/Diffusion training, checkpoint/export, feedback reports | ROS 2 runtime nodes, MuJoCo control loop, raw episode collection |
| `/home/ina/ros2_ws/src/ros2-moveit-pybullet-bridge` | Downstream bridge/runtime | MoveIt/PyBullet replay, deployment validation, runtime monitoring, feedback summaries | Dataset cleaning/release, policy training, raw collection |

## Gate A: Upstream Raw Import

Input producer: `ros2-arm-teleoperation-suite`

Expected upstream raw frame fields:

| Field | Shape/type | Middle action |
|---|---|---|
| `observation.state` | float32 `[7]` | Combine with `observation.gripper[1]` into training `state[8]` |
| `observation.gripper` | float32 `[1]` | Preserve as gripper state and combine into canonical state |
| `action` | float32 `[8]` | Treat as `ee_pose_gripper` unless explicitly converted |
| `observation.ee_pose` | float32 `[7]` | Required for deriving `ee_delta_gripper[7]` |
| `observation.object_pose` | float32 `[7]` | Privileged filter/debug field |
| `task` / `language_instruction` | string | Required for default multi-task training |
| `success` | bool | Default release requires all frames true |
| `safety_estop`, `drive_fault` | bool | Default release excludes true rows |
| `episode_*/meta.json: upstream_gate` | string | `batch_generator` => physical validation already upstream; midstream uses `filter_scope=training_split_only` |

Cleaning boundary:

- Upstream `batch_generator` + grasp monitor own physical accept/reject before `stop_success`.
- Middle repo owns schema/shape/action semantics and training split filtering only.
- Middle repo must not re-derive lift/place success from `observation.object_pose`.

Import gate:

```bash
python3 training/scripts/adapt_upstream_panda_dataset.py \
  --input <upstream_episode_train_dir> \
  --output <adapted_dataset_dir>

python3 training/scripts/inspect_dataset.py \
  --dataset <adapted_dataset_dir> \
  --schema configs/robot_schemas/panda_multi_task.yaml \
  --json-output <adapted_dataset_dir>/inspection_report.json
```

Pass condition:

- no missing required fields;
- no unsafe rows in default training release;
- non-empty `language_instruction`;
- `action[8]` is preserved or explicitly converted to `ee_delta_gripper[7]`;
- no silent `state[7] -> state[8]` or `action[8] -> action[7]` reinterpretation.

## Gate B: Dataset Release and Training

Release producer: `robot-arm-episode-data-lab`

```bash
python3 training/scripts/prepare_dataset_release.py \
  --input <adapted_dataset_dir> \
  --output <release_dir> \
  --schema configs/robot_schemas/panda_multi_task.yaml \
  --release-id <release_id>
```

Release manifest should record:

- raw source repo/path/commit when available;
- schema id and action type;
- language/action/state dimensions;
- filter rules and counts;
- `upstream_gate`, `filter_scope`, and `physical_validation_applied`;
- `has_success_labels` and default `success=true` requirement.

Training/evaluation output should stay in this repo and remain traceable to a
release manifest:

```text
training/reports/<run_id>/
├── checkpoint.npz
├── config_resolved.yaml
├── metrics.json
├── normalization.json
├── eval.json
└── predicted_actions.jsonl
```

## Gate C: Handoff to Downstream Bridge

Consumer: `/home/ina/ros2_ws/src/ros2-moveit-pybullet-bridge`

```bash
python3 training/scripts/prepare_bridge_handoff.py \
  --dataset <release_dir> \
  --replay training/reports/<run_id>/predicted_actions.jsonl \
  --schema configs/robot_schemas/panda_multi_task.yaml \
  --output training/reports/<run_id>/bridge_handoff \
  --handoff-id <handoff_id>
```

Bundle contract:

```text
bridge_handoff/
├── predicted_actions.jsonl
├── dataset_manifest.json
├── dataset_inspection_report.json
├── replay_check.json
└── handoff_manifest.json
```

Handoff manifest must declare schema id, action type/dim, observation keys,
normalization files, source release id, policy id, expected runtime topic, and
control rate. Downstream owns runtime execution and may reject any ambiguous
bundle.

## Gate D: Feedback Loop

Feedback from this repository back to upstream should use:

```text
docs/templates/upstream_feedback_report.yaml
```

Feedback from downstream bridge back to this repository should use:

```text
docs/templates/downstream_replay_summary.yaml
```

Allowed feedback artifacts are small reports, contract updates, tuning
suggestions, and tiny regression fixtures. Full dataset releases, training
caches, checkpoint binaries, wandb/tensorboard directories, replay videos, and
large rollout logs must not be copied across repos.

## Related Docs

- `docs/THREE_REPO_ARCHITECTURE.md`
- `docs/dev/upstream_downstream_contracts.md`
- `docs/DATA_FLOW.md`
- `docs/TRAINING_PIPELINE.md`
- `docs/TRAINING_TO_SIM2REAL.md`
