#!/usr/bin/env bash
# SmolVLA S3 preflight only (20–50 steps). NEVER starts full train.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${S3_PREFLIGHT_MODE:-mock-preflight}"
STEPS="${S3_PREFLIGHT_STEPS:-32}"
CONFIG="${S3_CONFIG:-$ROOT/configs/smolvla_s3/lora_train.yaml}"
RELEASE="${S3_RELEASE_DIR:-$ROOT/data/releases/smolvla_s3_abs_eef_rgb_v0}"
OUT="${S3_PREFLIGHT_OUT:-$ROOT/runs/smolvla_s3/preflight_$(date -u +%Y%m%dT%H%M%SZ)}"

echo "[s3-preflight] mode=$MODE steps=$STEPS"
echo "[s3-preflight] config=$CONFIG"
echo "[s3-preflight] release=$RELEASE"
echo "[s3-preflight] out=$OUT"

python3 "$ROOT/training/scripts/validate_smolvla_s3_release.py" --release-dir "$RELEASE"

if [[ "$MODE" == "mock-preflight" ]]; then
  python3 "$ROOT/training/scripts/run_smolvla_s3_control.py" \
    --mode mock-preflight \
    --config "$CONFIG" \
    --release-dir "$RELEASE" \
    --output-dir "$OUT"
  echo "[s3-preflight] MOCK_ONLY passed control-flow. Real GPU preflight still required on AutoDL."
  echo "[s3-preflight] Refusing to start full train (by design)."
  exit 0
fi

if [[ "$MODE" != "preflight" ]]; then
  echo "[s3-preflight] FATAL: S3_PREFLIGHT_MODE must be mock-preflight or preflight" >&2
  exit 2
fi

if (( STEPS < 20 || STEPS > 50 )); then
  echo "[s3-preflight] FATAL: steps must be in [20,50], got $STEPS" >&2
  exit 2
fi

python3 "$ROOT/training/scripts/run_smolvla_s3_control.py" \
  --mode preflight \
  --config "$CONFIG" \
  --release-dir "$RELEASE" \
  --output-dir "$OUT" \
  --steps "$STEPS"

echo "[s3-preflight] done. Inspect $OUT/preflight_report.json"
echo "[s3-preflight] Refusing to start full train (by design)."
