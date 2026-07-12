# Upstream and Downstream Contracts

`robot-arm-episode-data-lab` sits between runtime data capture and Sim2Real
execution. It accepts raw Panda episodes, validates and exports datasets, trains
lightweight policies inside this repository, and publishes neutral policy replay
files for downstream validation.

This repository no longer assumes a separate training repository. Training,
offline evaluation, and replay export live under the planned `training/` module.

## Upstream Inputs

### From `ros2-arm-teleoperation-suite`

Preferred raw input: Franka Panda episodes produced by MuJoCo / teleoperation /
grasping pipelines.

Canonical robot schema:

```text
configs/robot_schemas/panda.yaml
```

Required upstream raw fields:

| Field | Shape/type | Notes |
|---|---|---|
| `observation.state` | float32 `[7]` | 7 Panda joint positions from upstream recorder |
| `observation.gripper` | float32 `[1]` | gripper opening/state; adapter combines it with joint state |
| `action` | float32 `[8]` | upstream `ee_pose_gripper`: target EE pose plus gripper command |
| `observation.ee_pose` | float32 `[7]` | EE pose `[x, y, z, qx, qy, qz, qw]` |
| `timestamp` | float64 | synchronized frame timestamp |
| `frame_index` | int64 | frame index |
| `episode_index` | int64 | episode index |
| `task` | string | task label or language instruction |

Optional modalities include `observation.object_pose`, `observation.ft`, scene
RGB, wrist RGB, and tactile RGB streams. Missing optional modalities must be
reported by dataset inspection, not silently treated as required failures.

This repository adapts upstream raw rows into the training-facing schema:

```text
observation.state[8] = concat(observation.state[7], observation.gripper[1])
action[8]            = ee_pose_gripper
action[7]            = ee_delta_gripper only when explicitly derived
```

Never silently truncate upstream `action[8]` into training `action[7]`.

### Local PyBullet Episodes

This repository may also keep its original PyBullet episode format:

```text
episode_000001/
├── images/
├── states.npy
├── actions.npy
├── ee_poses.npy
├── object_poses.npy
└── metadata.json
```

Before mixing PyBullet and ROS 2/MuJoCo data, export or adapt both into the
explicit Panda schema. Do not silently concatenate incompatible action/state
layouts.

## In-Repository Training Output

Producer and trainer: `robot-arm-episode-data-lab`

Planned smoke training output:

```text
training/reports/panda_act_smoke/
├── checkpoint.npz
├── config_resolved.yaml
├── metrics.json
└── normalization.json
```

Training configs should point to a declared dataset/schema pair, not to an ad
hoc episode directory. Dataset releases should be immutable once used for a
training run. Large datasets stay outside Git.

## Downstream Replay Handoff

Consumer: `ros2-moveit-pybullet-bridge`

The replay interface is a neutral JSONL action stream:

```text
training/reports/panda_act_smoke/predicted_actions.jsonl
```

Each line:

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

Bridge handoff bundles are produced by:

```bash
python3 training/scripts/prepare_bridge_handoff.py \
  --dataset data/exports/panda_demo_delta_release \
  --replay training/reports/panda_act_smoke/predicted_actions.jsonl \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke/bridge_handoff \
  --handoff-id panda_demo_delta_bridge_v0
```

Bundle contents:

```text
bridge_handoff/
├── predicted_actions.jsonl
├── dataset_manifest.json
├── dataset_inspection_report.json
├── replay_check.json
└── handoff_manifest.json
```

The bridge owns robot execution, Sim2Real dual-source validation, distribution
shift monitoring, and risk closure. This repository only promises that the
exported replay file satisfies the declared Panda action schema.

## Feedback Back to Upstream

Middle-layer inspection, release, training, and handoff results should feed
back into `ros2-arm-teleoperation-suite` as lightweight feedback artifacts.
Use `docs/templates/upstream_feedback_report.yaml` for:

- missing or malformed upstream fields;
- per-task success-rate and rejection-reason summaries;
- action/state dimension issues;
- language-instruction issues;
- collection or validation tuning suggestions.

Do not copy full cleaned releases, training caches, checkpoint binaries, or
derived `state[8]` / `ee_delta_gripper[7]` datasets back into the upstream repo.

## Out of Scope

- No new standalone training repository.
- No ROS 2 runtime node in this repository.
- No real robot driver here.
- No UR3 / UR5 migration in the Panda schema.
- No GPU-only training dependency in the first pass.

Related planning document:
[panda_training_lab_spec.md](../archive/planning/panda_training_lab_spec.md).

Detailed implementation roadmap:
[panda_training_data_chain_roadmap.md](../archive/planning/panda_training_data_chain_roadmap.md).

Three-repo contract index:
[INTER_REPO_CONTRACTS.md](../INTER_REPO_CONTRACTS.md).
