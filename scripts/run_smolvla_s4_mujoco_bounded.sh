#!/usr/bin/env bash
# Thin midstream launcher for bounded SmolVLA → MuJoCo H2 closed-loop control.
# Delegates to upstream scripts/run_mujoco_smolvla_s4.sh (≤5 seeds).
set -euo pipefail
MIDSTREAM="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM="${UPSTREAM:-/home/ina/dev/ros2-arm-teleoperation-suite}"
export MIDSTREAM
export SEEDS="${SEEDS:-1 2 3 4 5}"
export DUMP_TELEMETRY="${DUMP_TELEMETRY:-true}"
export RECORD_SCENE_VIDEO="${RECORD_SCENE_VIDEO:-false}"
export DEVICE="${DEVICE:-cuda}"
export LORA_DIR="${LORA_DIR:-${MIDSTREAM}/runs/smolvla_s3/recovery_v3_lora_20260723T125632Z/lerobot_run/checkpoints/005705/pretrained_model}"
export BASE_DIR="${BASE_DIR:-${MIDSTREAM}/checkpoints/smolvla_base_gate_s1}"
export VLM_DIR="${VLM_DIR:-${MIDSTREAM}/checkpoints/SmolVLM2-500M-Video-Instruct}"
exec bash "${UPSTREAM}/scripts/run_mujoco_smolvla_s4.sh" "$@"
