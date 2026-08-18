#!/usr/bin/env bash
# Configure wrist-ablation v1 B (scene+wrist) train-only root.
# Does NOT train, download weights, start AutoDL, or launch Isaac.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RELEASE="${S3_RELEASE_DIR:-$ROOT/data/releases/smolvla_wrist_ablation_v1_panda_abs_eef_scene_wrist_phaseaware50}"
OUT="${S3_TRAIN_ROOT_OUT:-$ROOT/data/train_roots/smolvla_wrist_ablation_v1_B_train_only}"
REPO_ID="${S3_DATASET_REPO_ID:-local/smolvla_wrist_ablation_v1_B}"
PYTHON="${PYTHON:-/home/ina/miniforge3/envs/lerobot/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

export S3_RELEASE_DIR="$RELEASE"
export S3_TRAIN_ROOT_OUT="$OUT"
export S3_DATASET_REPO_ID="$REPO_ID"
export S3_INCLUDE_SPLIT=train
export S3_STATE_CONTRACT=recovery15
export S3_UPSTREAM_DATA_ROOT="${S3_UPSTREAM_DATA_ROOT:-/home/ina/dev/ros2-arm-teleoperation-suite/data}"

echo "[wrist-B-prep] python=$PYTHON"
echo "[wrist-B-prep] release=$RELEASE"
echo "[wrist-B-prep] train_root=$OUT"
"$PYTHON" "$ROOT/scripts/materialize_smolvla_s3_train_root.sh" 2>/dev/null || true

# materialize script is bash, not python.
bash "$ROOT/scripts/materialize_smolvla_s3_train_root.sh"

PREP_DIR="$ROOT/runs/smolvla_wrist_ablation_v1/B_train_prep"
mkdir -p "$PREP_DIR"
cat >"$PREP_DIR/autodl_env.example.sh" <<EOF
# Wrist ablation v1 B — AutoDL execute template. Do NOT run on the 6 GB laptop.
# 1) REAL preflight Pass on pinned LeRobot 0.5.1 (>=16 GB GPU)
# 2) Then, and only then:
export S3_CONFIG=$ROOT/configs/smolvla_s3/lora_train_wrist_ablation_v1_B.yaml
export S3_RELEASE_DIR=$RELEASE
export S3_DATASET_ROOT=$OUT
export S3_DATASET_REPO_ID=$REPO_ID
export S3_INCLUDE_SPLIT=train
export S3_PREFLIGHT_REPORT=/path/to/real_preflight_report.json
export S3_I_UNDERSTAND_BILLING=1
export SMOLVLA_S3_EXECUTE_TRAIN=1
export SMOLVLA_BASE_DIR=/path/to/smolvla_base
export SMOLVLA_BASE_REVISION=<40-hex>
# Flip authorized_to_train: true in the YAML only after REAL preflight Pass.
# ./scripts/run_smolvla_s3_train.sh
EOF

python3 - <<PY
import json
from pathlib import Path
from datetime import datetime, timezone
prep = Path("$PREP_DIR")
payload = {
    "experiment_id": "smolvla_wrist_ablation_v1_B",
    "configured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "trained": False,
    "ran_isaac": False,
    "authorized_to_train": False,
    "release_id": "smolvla_wrist_ablation_v1_panda_abs_eef_scene_wrist_phaseaware50",
    "train_root": "$OUT",
    "config": "configs/smolvla_s3/lora_train_wrist_ablation_v1_B.yaml",
    "max_steps": 5460,
    "train_frames": 8731,
    "camera_variant": "scene_plus_wrist",
    "number_of_policy_cameras": 2,
    "notes": "Configure-only. Formal LoRA needs AutoDL REAL preflight then explicit execute.",
}
(prep / "prep_manifest.json").write_text(json.dumps(payload, indent=2) + "\\n", encoding="utf-8")
print("wrote", prep / "prep_manifest.json")
PY

echo "[wrist-B-prep] configure-only done. NO train / NO Isaac / NO AutoDL execute."
echo "[wrist-B-prep] env template: $PREP_DIR/autodl_env.example.sh"
