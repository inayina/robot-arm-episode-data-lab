#!/usr/bin/env bash
# SmolVLA open-loop nuisance perturbation diagnostic (P1-0A / P1-0B).
# LoRA-only, H=1, gate_eligible=false. Does NOT rerun or replace clean Gate.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if [[ -x /home/ina/miniforge3/envs/lerobot/bin/python ]]; then
    PYTHON=/home/ina/miniforge3/envs/lerobot/bin/python
  else
    PYTHON=python3
  fi
fi

BASE="${SMOLVLA_BASE_DIR:-$ROOT/checkpoints/smolvla_base_gate_s1}"
VLM="${SMOLVLA_VLM_DIR:-$ROOT/checkpoints/SmolVLM2-500M-Video-Instruct}"
LORA="${S3_LORA_DIR:-$ROOT/runs/smolvla_s3/recovery_v3_lora_20260723T125632Z/lerobot_run/checkpoints/005705/pretrained_model}"
RELEASE="${S3_RELEASE_DIR:-$ROOT/data/releases/smolvla_s3_recovery_v3_prospective_eval10_gate_v3_20260724b}"
DATA_ROOT="${S3_DATA_ROOT:-/home/ina/dev/ros2-arm-teleoperation-suite/data}"
TRAIN_CFG="${S3_CONFIG:-$ROOT/configs/smolvla_s3/lora_train_recovery_v3_phaseaware50.yaml}"
PERT_CFG="${S3_PERTURBATION_CONFIG:-$ROOT/configs/smolvla_s3/openloop_perturbation.yaml}"
OUT="${S3_PERTURBATION_OUT:-$ROOT/runs/smolvla_s3/openloop_perturbation_$(date -u +%Y%m%dT%H%M%SZ)}"
LAYERS="${S3_PERTURBATION_LAYERS:-stage_anchors,close_window}"

if [[ ! -f "$LORA/adapter_model.safetensors" ]]; then
  echo "[perturb] FATAL: missing LoRA adapter under $LORA" >&2
  exit 2
fi
if [[ ! -d "$BASE" || ! -d "$VLM" ]]; then
  echo "[perturb] FATAL: base/vlm missing" >&2
  exit 2
fi

mkdir -p "$OUT"
echo "[perturb] python=$PYTHON"
echo "[perturb] base=$BASE"
echo "[perturb] vlm=$VLM"
echo "[perturb] lora=$LORA"
echo "[perturb] data=$DATA_ROOT"
echo "[perturb] out=$OUT"
echo "[perturb] layers=$LAYERS"

"$PYTHON" training/scripts/run_smolvla_s3_open_loop_perturbation.py \
  --base-dir "$BASE" \
  --vlm-dir "$VLM" \
  --lora-dir "$LORA" \
  --release-dir "$RELEASE" \
  --data-root "$DATA_ROOT" \
  --train-config "$TRAIN_CFG" \
  --perturbation-config "$PERT_CFG" \
  --output-dir "$OUT" \
  --slices benchmark \
  --layers "$LAYERS" \
  --i-understand-diagnostic-only \
  2>&1 | tee "$OUT/console.log"
exit "${PIPESTATUS[0]}"