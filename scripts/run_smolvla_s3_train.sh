#!/usr/bin/env bash
# SmolVLA S3 formal LoRA train entry (human-gated). Does NOT call from preflight.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CONFIG="${S3_CONFIG:-$ROOT/configs/smolvla_s3/lora_train.yaml}"
RELEASE="${S3_RELEASE_DIR:-$ROOT/data/releases/smolvla_s3_abs_eef_rgb_v0}"
PREFLIGHT_REPORT="${S3_PREFLIGHT_REPORT:-}"
OUT="${S3_TRAIN_OUT:-$ROOT/runs/smolvla_s3/train_$(date -u +%Y%m%dT%H%M%SZ)}"
CONFIRM="${S3_I_UNDERSTAND_BILLING:-0}"

usage() {
  cat <<'EOF'
Usage (AutoDL, after REAL preflight Pass + human approval):

  export S3_PREFLIGHT_REPORT=/path/to/preflight_report.json
  export S3_I_UNDERSTAND_BILLING=1
  export SMOLVLA_S3_EXECUTE_TRAIN=1   # only on approved GPU host
  ./scripts/run_smolvla_s3_train.sh

This script never auto-starts from preflight. Mock preflight cannot authorize train.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "$CONFIRM" != "1" ]]; then
  echo "[s3-train] FATAL: set S3_I_UNDERSTAND_BILLING=1 after human approval" >&2
  usage
  exit 2
fi

if [[ -z "$PREFLIGHT_REPORT" || ! -f "$PREFLIGHT_REPORT" ]]; then
  echo "[s3-train] FATAL: S3_PREFLIGHT_REPORT must point to REAL preflight_report.json" >&2
  exit 2
fi

# Refuse mock authorization
if python3 - "$PREFLIGHT_REPORT" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
if r.get("mode") == "mock-preflight" or r.get("distinction", "").startswith("MOCK"):
    raise SystemExit(3)
if not r.get("passed"):
    raise SystemExit(4)
PY
then
  :
else
  rc=$?
  if [[ $rc -eq 3 ]]; then
    echo "[s3-train] FATAL: mock preflight cannot authorize formal train" >&2
  else
    echo "[s3-train] FATAL: preflight report not passed" >&2
  fi
  exit 2
fi

python3 "$ROOT/training/scripts/validate_smolvla_s3_release.py" --release-dir "$RELEASE"

echo "[s3-train] config=$CONFIG"
echo "[s3-train] release=$RELEASE"
echo "[s3-train] out=$OUT"
echo "[s3-train] preflight=$PREFLIGHT_REPORT"

# Control-plane metadata always written.
python3 "$ROOT/training/scripts/run_smolvla_s3_control.py" \
  --mode train \
  --config "$CONFIG" \
  --release-dir "$RELEASE" \
  --output-dir "$OUT" \
  --preflight-report "$PREFLIGHT_REPORT" \
  --i-understand-billing

if [[ "${SMOLVLA_S3_EXECUTE_TRAIN:-0}" != "1" ]]; then
  echo "[s3-train] Prepared run_metadata only. Set SMOLVLA_S3_EXECUTE_TRAIN=1 on AutoDL to launch."
  exit 0
fi

# Real execute path (AutoDL): prefer official lerobot-train with frozen flags.
# shellcheck disable=SC1091
if [[ -f "$ROOT/configs/smolvla_s3/lora_train.yaml" ]]; then
  SEED=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG'))['train']['seed'])")
  STEPS=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG'))['train']['max_steps'])")
  BS=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG'))['train']['batch_size'])")
  R=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG'))['peft']['r'])")
  ALPHA=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG'))['peft']['lora_alpha'])")
  MODEL=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG'))['base_checkpoint']['model_id'])")
fi

DATASET_ROOT="${S3_DATASET_ROOT:-}"
if [[ -z "$DATASET_ROOT" ]]; then
  echo "[s3-train] FATAL: S3_DATASET_ROOT must point to mounted LeRobot v2.1 absolute-EEF trees" >&2
  exit 2
fi

mkdir -p "$OUT"
{
  echo "start=$(date -Is)"
  echo "seed=$SEED steps=$STEPS batch=$BS r=$R alpha=$ALPHA"
  echo "model=$MODEL"
  echo "dataset=$DATASET_ROOT"
} | tee "$OUT/train_launch.env"

# Official entry — adjust only within preflight-bound ranges recorded in run_metadata.
set -x
lerobot-train \
  --policy.path="$MODEL" \
  --dataset.root="$DATASET_ROOT" \
  --batch_size="$BS" \
  --steps="$STEPS" \
  --seed="$SEED" \
  --peft.method_type=LORA \
  --peft.r="$R" \
  --output_dir="$OUT" \
  2>&1 | tee "$OUT/train_log.txt"
set +x

echo "[s3-train] finished. Package logs + checkpoints before stopping the instance."
