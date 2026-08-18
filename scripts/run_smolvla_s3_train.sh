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

DATASET_ROOT="${S3_DATASET_ROOT:-}"
if [[ -n "$DATASET_ROOT" ]]; then
  echo "[s3-train] validating train-only root against release splits: $DATASET_ROOT"
  python3 "$ROOT/training/scripts/validate_smolvla_s3_release.py" \
    --release-dir "$RELEASE" \
    --train-root "$DATASET_ROOT" \
    --include-split "${S3_INCLUDE_SPLIT:-train}"
fi

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

# Real execute path (AutoDL): pass every auditable frozen field to the official CLI.
cfg_value() {
  python3 - "$CONFIG" "$1" <<'PY'
import json
import sys

import yaml

value = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
for part in sys.argv[2].split("."):
    value = value[part]
print(json.dumps(value, separators=(",", ":")) if isinstance(value, (list, dict)) else value)
PY
}

cfg_value_or() {
  python3 - "$CONFIG" "$1" "$2" <<'PY'
import json
import sys

import yaml

value = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
try:
    for part in sys.argv[2].split("."):
        value = value[part]
except (KeyError, TypeError):
    value = json.loads(sys.argv[3])
print(json.dumps(value, separators=(",", ":")) if isinstance(value, (list, dict)) else value)
PY
}

SEED=$(cfg_value train.seed)
STEPS=$(cfg_value train.max_steps)
BS=$(cfg_value train.batch_size)
GRAD_ACCUM=$(cfg_value train.gradient_accumulation_steps)
PRECISION=$(cfg_value train.precision)
R=$(cfg_value peft.r)
ALPHA=$(cfg_value peft.lora_alpha)
DROPOUT=$(cfg_value peft.lora_dropout)
BIAS=$(cfg_value peft.bias)
# JSON-encode so a PEFT regex string is one CLI token (never character-split).
TARGET_MODULES=$(python3 - "$CONFIG" <<'PY'
import sys
from pathlib import Path
import yaml
root = Path(sys.argv[1]).resolve().parents[2]
sys.path.insert(0, str(root))
from training.smolvla_s3.peft_targets import target_modules_for_cli
cfg = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
print(target_modules_for_cli(cfg["peft"]["target_modules"]))
PY
)
FULL_TRAINING_MODULES=$(python3 - "$CONFIG" <<'PY'
import json, sys
from pathlib import Path
import yaml
root = Path(sys.argv[1]).resolve().parents[2]
sys.path.insert(0, str(root))
from training.smolvla_s3.peft_targets import normalize_full_training_modules
cfg = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
print(json.dumps(normalize_full_training_modules(cfg["peft"].get("full_training_modules"))))
PY
)
LR=$(cfg_value train.learning_rate)
WEIGHT_DECAY=$(cfg_value train.weight_decay)
MAX_GRAD_NORM=$(cfg_value train.max_grad_norm)
WARMUP_STEPS=$(cfg_value train.lr_warmup_steps)
LOG_FREQ=$(cfg_value train.logging_steps)
EVAL_FREQ=$(cfg_value train.eval_every_steps)
SAVE_FREQ=$(cfg_value train.save_every_steps)
NUM_WORKERS=$(cfg_value train.dataloader_workers)
CHUNK_SIZE=$(cfg_value train.action_chunk_size)
ACTION_STEPS=$(cfg_value_or inference.action_steps "$CHUNK_SIZE")
EMPTY_CAMERAS=$(cfg_value_or inference.empty_cameras 2)
POLICY_INPUT_FEATURES=$(python3 - "$CONFIG" <<'PY'
import json
import sys
from pathlib import Path

import yaml

root = Path(sys.argv[1]).resolve().parents[2]
sys.path.insert(0, str(root))
from training.scripts.run_smolvla_s3_control import _policy_feature_overrides

cfg = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
inputs, _ = _policy_feature_overrides(cfg)
print("" if inputs is None else json.dumps(inputs, separators=(",", ":")))
PY
)
POLICY_OUTPUT_FEATURES=$(python3 - "$CONFIG" <<'PY'
import json
import sys
from pathlib import Path

import yaml

root = Path(sys.argv[1]).resolve().parents[2]
sys.path.insert(0, str(root))
from training.scripts.run_smolvla_s3_control import _policy_feature_overrides

cfg = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
_, outputs = _policy_feature_overrides(cfg)
print("" if outputs is None else json.dumps(outputs, separators=(",", ":")))
PY
)
RENAME_MAP=$(python3 - "$CONFIG" <<'PY'
import json
import sys
from pathlib import Path

import yaml

root = Path(sys.argv[1]).resolve().parents[2]
sys.path.insert(0, str(root))
from training.smolvla_s3.policy_features import camera_rename_map

cfg = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
variant = str((cfg.get("inference") or {}).get("camera_variant") or "scene_only")
print(json.dumps(camera_rename_map(variant), separators=(",", ":")))
PY
)
MODEL_ID=$(cfg_value base_checkpoint.model_id)
BASE_REVISION="${SMOLVLA_BASE_REVISION:-$(cfg_value base_checkpoint.revision)}"
MODEL_SOURCE="${SMOLVLA_BASE_DIR:-$MODEL_ID}"

if [[ "$GRAD_ACCUM" != "1" ]]; then
  echo "[s3-train] FATAL: pinned LeRobot entry supports frozen gradient_accumulation_steps=1 only" >&2
  exit 2
fi
if [[ "$PRECISION" != "bf16" && "$PRECISION" != "fp16" ]]; then
  echo "[s3-train] FATAL: precision must be bf16 or fp16, got: $PRECISION" >&2
  exit 2
fi
if (( ACTION_STEPS < 1 || ACTION_STEPS > CHUNK_SIZE )); then
  echo "[s3-train] FATAL: inference.action_steps must be in [1, chunk_size=$CHUNK_SIZE], got: $ACTION_STEPS" >&2
  exit 2
fi
if (( EMPTY_CAMERAS < 0 )); then
  echo "[s3-train] FATAL: inference.empty_cameras must be >= 0, got: $EMPTY_CAMERAS" >&2
  exit 2
fi
LEROBOT_VERSION=$(python3 - <<'PY'
from importlib.metadata import version

print(version("lerobot"))
PY
)
if ! python3 - "$LEROBOT_VERSION" <<'PY'
import re
import sys

match = re.match(r"^(\d+)\.(\d+)", sys.argv[1])
raise SystemExit(0 if match and tuple(map(int, match.groups())) == (0, 5) else 1)
PY
then
  echo "[s3-train] FATAL: verified entry requires LeRobot 0.5.x, got: $LEROBOT_VERSION" >&2
  exit 2
fi
if [[ "$BASE_REVISION" == "main" || ! "$BASE_REVISION" =~ ^[0-9a-fA-F]{40}$ ]]; then
  echo "[s3-train] FATAL: pin exact 40-hex SMOLVLA_BASE_REVISION after download" >&2
  exit 2
fi
if [[ -n "${SMOLVLA_BASE_DIR:-}" && ! -d "$MODEL_SOURCE" ]]; then
  echo "[s3-train] FATAL: SMOLVLA_BASE_DIR does not exist: $MODEL_SOURCE" >&2
  exit 2
fi

DATASET_ROOT="${S3_DATASET_ROOT:-}"
if [[ -z "$DATASET_ROOT" ]]; then
  echo "[s3-train] FATAL: S3_DATASET_ROOT must point to a train-only LeRobot root" >&2
  echo "[s3-train] hint: ./scripts/materialize_smolvla_s3_train_root.sh" >&2
  exit 2
fi

POLICY_FEATURE_ARGS=()
if [[ -n "$POLICY_INPUT_FEATURES" ]]; then
  POLICY_FEATURE_ARGS+=(--policy.input_features="$POLICY_INPUT_FEATURES")
  POLICY_FEATURE_ARGS+=(--s3-policy-input-features="$POLICY_INPUT_FEATURES")
fi
if [[ -n "$POLICY_OUTPUT_FEATURES" ]]; then
  POLICY_FEATURE_ARGS+=(--policy.output_features="$POLICY_OUTPUT_FEATURES")
  POLICY_FEATURE_ARGS+=(--s3-policy-output-features="$POLICY_OUTPUT_FEATURES")
fi
if [[ ! -f "$DATASET_ROOT/train_root_provenance.json" ]]; then
  echo "[s3-train] FATAL: missing train_root_provenance.json under $DATASET_ROOT" >&2
  echo "[s3-train] refusing unfiltered roots (validation/benchmark leak risk)" >&2
  exit 2
fi
python3 "$ROOT/training/scripts/validate_smolvla_s3_release.py" \
  --release-dir "$RELEASE" \
  --train-root "$DATASET_ROOT" \
  --include-split "${S3_INCLUDE_SPLIT:-train}"

mkdir -p "$OUT"
LEROBOT_OUT="$OUT/lerobot_run"
CHECKPOINT_DIR="$LEROBOT_OUT/checkpoints/$(printf '%06d' "$STEPS")/pretrained_model"
{
  echo "start=$(date -Is)"
  echo "seed=$SEED steps=$STEPS batch=$BS grad_accum=$GRAD_ACCUM precision=$PRECISION"
  echo "lerobot_version=$LEROBOT_VERSION"
  echo "r=$R alpha=$ALPHA dropout=$DROPOUT bias=$BIAS targets=$TARGET_MODULES"
  echo "lr=$LR weight_decay=$WEIGHT_DECAY max_grad_norm=$MAX_GRAD_NORM warmup=$WARMUP_STEPS"
  echo "log_freq=$LOG_FREQ eval_freq=$EVAL_FREQ save_freq=$SAVE_FREQ workers=$NUM_WORKERS chunk=$CHUNK_SIZE action_steps=$ACTION_STEPS empty_cameras=$EMPTY_CAMERAS"
  echo "model_id=$MODEL_ID model_source=$MODEL_SOURCE base_revision=$BASE_REVISION"
  echo "rename_map=$RENAME_MAP"
  echo "dataset=$DATASET_ROOT"
  echo "lerobot_output=$LEROBOT_OUT"
} | tee "$OUT/train_launch.env"

# Official LeRobot PEFT fields follow the upstream PEFT training CLI contract.
# LeRobot 0.5.x PeftConfig CLI only accepts method_type/r/target_modules/init_type/
# full_training_modules. Alpha/dropout/bias are injected via the wrapper that patches
# PreTrainedPolicy._build_peft_config (PEFT defaults otherwise: alpha=8, dropout=0.0).
export ACCELERATE_MIXED_PRECISION="$PRECISION"
export S3_LORA_ALPHA="$ALPHA"
export S3_LORA_DROPOUT="$DROPOUT"
export S3_LORA_BIAS="$BIAS"
set -x
python3 "$ROOT/training/scripts/lerobot_train_with_peft_overrides.py" \
  --s3-lora-alpha="$ALPHA" \
  --s3-lora-dropout="$DROPOUT" \
  --s3-lora-bias="$BIAS" \
  --policy.path="$MODEL_SOURCE" \
  --dataset.repo_id="${S3_DATASET_REPO_ID:-local/smolvla_s3_merged}" \
  --dataset.root="$DATASET_ROOT" \
  --dataset.video_backend="${S3_VIDEO_BACKEND:-pyav}" \
  --dataset.use_imagenet_stats=false \
  --batch_size="$BS" \
  --steps="$STEPS" \
  --seed="$SEED" \
  --num_workers="$NUM_WORKERS" \
  --log_freq="$LOG_FREQ" \
  --eval_freq="$EVAL_FREQ" \
  --save_freq="$SAVE_FREQ" \
  --policy.push_to_hub=false \
  --policy.optimizer_lr="$LR" \
  --policy.optimizer_weight_decay="$WEIGHT_DECAY" \
  --policy.optimizer_grad_clip_norm="$MAX_GRAD_NORM" \
  --policy.scheduler_warmup_steps="$WARMUP_STEPS" \
  --policy.chunk_size="$CHUNK_SIZE" \
  --policy.n_action_steps="$ACTION_STEPS" \
  --rename_map="$RENAME_MAP" \
  --policy.empty_cameras="$EMPTY_CAMERAS" \
  "${POLICY_FEATURE_ARGS[@]}" \
  --peft.method_type=LORA \
  --peft.r="$R" \
  --peft.target_modules="$TARGET_MODULES" \
  --peft.full_training_modules="$FULL_TRAINING_MODULES" \
  --output_dir="$LEROBOT_OUT" \
  2>&1 | tee "$OUT/train_log.txt"
set +x

python3 "$ROOT/training/scripts/run_smolvla_s3_control.py" \
  --mode finalize-train \
  --config "$CONFIG" \
  --release-dir "$RELEASE" \
  --output-dir "$OUT" \
  --checkpoint-dir "$CHECKPOINT_DIR"

echo "[s3-train] finished and checkpoint config verified. Package evidence before stopping the instance."
