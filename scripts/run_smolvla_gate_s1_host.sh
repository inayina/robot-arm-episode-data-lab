#!/usr/bin/env bash
# Gate S1 host runner — must execute outside Cursor Agent sandbox (real /dev/nvidia*).
set -euo pipefail

MIDSTREAM="${MIDSTREAM:-/home/ina/robot-sim-lab/robot-arm-episode-data-lab}"
CONDA_SH="${CONDA_SH:-/home/ina/miniforge3/etc/profile.d/conda.sh}"
ENV_NAME="${ENV_NAME:-lerobot}"
MODEL_ID="${MODEL_ID:-lerobot/smolvla_base}"
DATASET_ID="${DATASET_ID:-lerobot/libero}"
LOCAL_DIR="${LOCAL_DIR:-$MIDSTREAM/checkpoints/smolvla_base_gate_s1}"
REPORT_JSON="${REPORT_JSON:-$MIDSTREAM/evaluation/examples/smolvla_gate_s1_report.json}"
REPORT_MD="${REPORT_MD:-$MIDSTREAM/docs/SMOLVLA_GATE_S1_OFFICIAL_REPRO.md}"
LOG="${LOG:-/tmp/smolvla_gate_s1_host.log}"
DONE="${DONE:-/tmp/smolvla_gate_s1_done}"

rm -f "$DONE"
: >"$LOG"
exec > >(tee -a "$LOG") 2>&1
echo "[gate_s1] start $(date -Is)"
echo "[gate_s1] nvidia-smi:"
nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv || {
  echo "[gate_s1] FATAL: nvidia-smi failed"
  echo fail >"$DONE"
  exit 1
}

# shellcheck disable=SC1090
source "$CONDA_SH"
conda activate "$ENV_NAME"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$HOME/.cache/pip}"
mkdir -p "$PIP_CACHE_DIR"

python - <<'PY'
import sys
import torch
print("python", sys.version.split()[0])
print("torch", torch.__version__, "cuda_available", torch.cuda.is_available())
if not torch.cuda.is_available():
    raise SystemExit("CUDA not available in this process")
print("gpu", torch.cuda.get_device_name(0))
PY

if [[ "${SKIP_PIP:-0}" != "1" ]]; then
  python -m pip install -U pip
  python -m pip install -U transformers huggingface_hub
  if [[ -d /home/ina/dev/lerobot ]]; then
    python -m pip install -e "/home/ina/dev/lerobot[smolvla]"
  else
    python -m pip install -U "lerobot[smolvla]"
  fi
else
  echo "[gate_s1] SKIP_PIP=1 — reuse current env packages"
fi

mkdir -p "$LOCAL_DIR" "$(dirname "$REPORT_JSON")" "$(dirname "$REPORT_MD")"

VLM_LOCAL_DIR="${VLM_LOCAL_DIR:-$MIDSTREAM/checkpoints/SmolVLM2-500M-Video-Instruct}"
SMOKE_ARGS=(
  --model-id "$MODEL_ID"
  --dataset-id "$DATASET_ID"
  --local-dir "$LOCAL_DIR"
  --report-json "$REPORT_JSON"
  --report-md "$REPORT_MD"
)
if [[ -f "$LOCAL_DIR/model.safetensors" ]]; then
  SMOKE_ARGS+=(--local-files-only)
  echo "[gate_s1] using existing $LOCAL_DIR/model.safetensors"
fi
if [[ -f "$VLM_LOCAL_DIR/model.safetensors" ]]; then
  SMOKE_ARGS+=(--vlm-local-dir "$VLM_LOCAL_DIR")
  echo "[gate_s1] using existing VLM $VLM_LOCAL_DIR"
fi

python "$MIDSTREAM/training/scripts/run_smolvla_gate_s1_smoke.py" "${SMOKE_ARGS[@]}"

echo ok >"$DONE"
echo "[gate_s1] done $(date -Is) report=$REPORT_JSON"
