#!/usr/bin/env bash
# SmolVLA S3 paired open-loop → Pass/Hold/No-Go via frozen eval_gate_v2.
# Does NOT launch Isaac. Does NOT claim task success.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BASE="${SMOLVLA_BASE_DIR:-/root/autodl-tmp/smolvla_s3/smolvla_base}"
VLM="${SMOLVLA_VLM_DIR:-/root/autodl-tmp/smolvla_s3/smolvlm2_500m}"
LORA="${S3_LORA_DIR:-}"
RELEASE="${S3_RELEASE_DIR:-$ROOT/data/releases/smolvla_s3_abs_eef_rgb_v1_griptiming}"
DATA_ROOT="${S3_DATA_ROOT:-/root/autodl-tmp/data}"
GATE="${S3_EVAL_GATE:-$ROOT/configs/smolvla_s3/eval_gate_v2.yaml}"
CONFIG="${S3_CONFIG:-$ROOT/configs/smolvla_s3/lora_train.yaml}"
PROSPECTIVE_MANIFEST="${S3_PROSPECTIVE_EVAL_MANIFEST:-}"
OUT="${S3_OPENLOOP_OUT:-$ROOT/runs/smolvla_s3/openloop_$(date -u +%Y%m%dT%H%M%SZ)}"
STRIDE="${S3_OPENLOOP_STRIDE:-1}"
MAX_FRAMES="${S3_OPENLOOP_MAX_FRAMES:-0}"
INFERENCE_MODE="${S3_OPENLOOP_INFERENCE_MODE:-canonical_first_action}"

usage() {
  cat <<'EOF'
Usage (AutoDL, after formal LoRA checkpoint exists):

  export SMOLVLA_BASE_DIR=/root/autodl-tmp/smolvla_s3/smolvla_base
  export SMOLVLA_VLM_DIR=/root/autodl-tmp/smolvla_s3/smolvlm2_500m
  export S3_LORA_DIR=/path/to/checkpoints/001000/pretrained_model
  export S3_DATA_ROOT=/root/autodl-tmp/data
  ./scripts/run_smolvla_s3_open_loop.sh

Optional: S3_OPENLOOP_OUT, S3_OPENLOOP_STRIDE, S3_OPENLOOP_MAX_FRAMES,
          S3_OPENLOOP_INFERENCE_MODE, S3_EVAL_GATE, S3_CONFIG,
          S3_PROSPECTIVE_EVAL_MANIFEST

Canonical Pass evaluation uses S3_OPENLOOP_STRIDE=1 and
S3_OPENLOOP_MAX_FRAMES=0 (complete episodes), with
S3_OPENLOOP_INFERENCE_MODE=canonical_first_action.
queued_diagnostic consumes the policy queue but can never Pass the canonical gate.
Frozen eval_gate_v2 also requires a run-specific prospective manifest for Pass.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "$LORA" || ! -d "$LORA" ]]; then
  echo "[s3-openloop] FATAL: set S3_LORA_DIR to LoRA pretrained_model dir" >&2
  usage
  exit 2
fi
if [[ ! -f "$LORA/adapter_model.safetensors" ]]; then
  echo "[s3-openloop] FATAL: missing adapter_model.safetensors under $LORA" >&2
  exit 2
fi
if [[ ! -d "$BASE" || ! -d "$VLM" ]]; then
  echo "[s3-openloop] FATAL: base/vlm dirs missing" >&2
  exit 2
fi

mkdir -p "$OUT"
echo "[s3-openloop] base=$BASE"
echo "[s3-openloop] vlm=$VLM"
echo "[s3-openloop] lora=$LORA"
echo "[s3-openloop] data=$DATA_ROOT"
echo "[s3-openloop] out=$OUT"
echo "[s3-openloop] inference_mode=$INFERENCE_MODE"
if [[ -n "$PROSPECTIVE_MANIFEST" ]]; then
  echo "[s3-openloop] prospective_manifest=$PROSPECTIVE_MANIFEST"
fi

ARGS=(
  --base-dir "$BASE"
  --vlm-dir "$VLM"
  --lora-dir "$LORA"
  --release-dir "$RELEASE"
  --data-root "$DATA_ROOT"
  --eval-gate "$GATE"
  --train-config "$CONFIG"
  --output-dir "$OUT"
  --stride "$STRIDE"
  --max-frames-per-episode "$MAX_FRAMES"
  --inference-mode "$INFERENCE_MODE"
)
if [[ -n "$PROSPECTIVE_MANIFEST" ]]; then
  ARGS+=(--prospective-eval-manifest "$PROSPECTIVE_MANIFEST")
fi

python training/scripts/run_smolvla_s3_open_loop.py "${ARGS[@]}" \
  2>&1 | tee "$OUT/open_loop_console.log"

echo "[s3-openloop] done. See $OUT/s3_open_loop_report.json"
