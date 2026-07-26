#!/usr/bin/env bash
# P1-1: sync vs async-double-buffer S4 queue timing (real LoRA, no Isaac).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-/home/ina/miniforge3/envs/lerobot/bin/python}"
BASE="${SMOLVLA_BASE_DIR:-$ROOT/checkpoints/smolvla_base_gate_s1}"
VLM="${SMOLVLA_VLM_DIR:-$ROOT/checkpoints/SmolVLM2-500M-Video-Instruct}"
LORA="${S3_LORA_DIR:-$ROOT/runs/smolvla_s3/recovery_v3_lora_20260723T125632Z/lerobot_run/checkpoints/005705/pretrained_model}"
RELEASE="${S3_RELEASE_DIR:-$ROOT/data/releases/smolvla_s3_recovery_v3_prospective_eval10_gate_v3_20260724b}"
DATA_ROOT="${S3_DATA_ROOT:-/home/ina/dev/ros2-arm-teleoperation-suite/data}"
OUT="${S3_QUEUE_BENCH_OUT:-$ROOT/runs/smolvla_s3/queue_runtime_bench_$(date -u +%Y%m%dT%H%M%SZ)}"
N_TICKS="${S3_QUEUE_BENCH_TICKS:-150}"

mkdir -p "$OUT"
echo "[queue-bench] out=$OUT ticks=$N_TICKS"
"$PYTHON" training/scripts/bench_smolvla_s4_queue_runtime.py \
  --base-dir "$BASE" \
  --vlm-dir "$VLM" \
  --lora-dir "$LORA" \
  --release-dir "$RELEASE" \
  --data-root "$DATA_ROOT" \
  --output-dir "$OUT" \
  --n-ticks "$N_TICKS" \
  --i-understand-diagnostic-only \
  2>&1 | tee "$OUT/console.log"
exit "${PIPESTATUS[0]}"
