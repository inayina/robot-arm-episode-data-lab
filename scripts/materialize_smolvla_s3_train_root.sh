#!/usr/bin/env bash
# Materialize a train-only LeRobot root from an immutable S3 release split.
# Does NOT train, download weights, or modify the release.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RELEASE="${S3_RELEASE_DIR:-$ROOT/data/releases/smolvla_s3_abs_eef_rgb_v2_griptiming_lateclose}"
OUT="${S3_TRAIN_ROOT_OUT:-$ROOT/data/train_roots/$(basename "$RELEASE")_train_only}"
REPO_ID="${S3_DATASET_REPO_ID:-local/smolvla_s3_train_only}"
INCLUDE_SPLIT="${S3_INCLUDE_SPLIT:-train}"
STATE_CONTRACT="${S3_STATE_CONTRACT:-source7}"
UPSTREAM_ROOT="${S3_UPSTREAM_DATA_ROOT:-/home/ina/dev/ros2-arm-teleoperation-suite/data}"

if [[ ! -f "$RELEASE/manifest.json" || ! -f "$RELEASE/splits.json" ]]; then
  echo "[s3-train-root] FATAL: release missing manifest/splits: $RELEASE" >&2
  exit 2
fi

SOURCES=()
while IFS= read -r line; do
  [[ -n "$line" ]] && SOURCES+=("$line")
done < <(
  python3 - "$RELEASE" "$UPSTREAM_ROOT" "$INCLUDE_SPLIT" <<'PY'
import json
import sys
from pathlib import Path

release = Path(sys.argv[1])
manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
upstream = Path(sys.argv[2])
include_split = sys.argv[3]
splits = json.loads((release / "splits.json").read_text(encoding="utf-8"))
if include_split not in splits:
    raise SystemExit(f"unknown include-split: {include_split}")
# Only pass sources that contribute episodes to the requested split.
# Release manifests list all trees (including benchmark-only); zero-episode
# sources after the split filter are not an error for materialization.
needed = {
    ref.split("/", 1)[0]
    for ref in splits[include_split]
    if "/" in ref
}
roots = []
for raw in manifest.get("source_dataset_roots") or []:
    path = Path(raw)
    name = path.name
    if name not in needed:
        continue
    if path.is_dir():
        roots.append(str(path))
        continue
    candidate = upstream / name
    if candidate.is_dir():
        roots.append(str(candidate))
        continue
    raise SystemExit(f"missing source root: {raw} (also tried {candidate})")
if not roots:
    raise SystemExit(f"no source roots for split={include_split} needed={sorted(needed)}")
print("\n".join(roots))
PY
)

if [[ ${#SOURCES[@]} -lt 1 ]]; then
  echo "[s3-train-root] FATAL: no source roots resolved" >&2
  exit 2
fi

ARGS=(
  --repo-id "$REPO_ID"
  --output "$OUT"
  --splits-json "$RELEASE/splits.json"
  --include-split "$INCLUDE_SPLIT"
  --state-contract "$STATE_CONTRACT"
)
if [[ "${S3_SKIP_LEROBOT_LOAD_SMOKE:-0}" == "1" ]]; then
  ARGS+=(--skip-lerobot-load-smoke)
fi
if [[ -n "${S3_VIDEO_BACKEND:-}" ]]; then
  ARGS+=(--video-backend "$S3_VIDEO_BACKEND")
fi
for src in "${SOURCES[@]}"; do
  ARGS+=(--source "$src")
done

echo "[s3-train-root] release=$RELEASE"
echo "[s3-train-root] output=$OUT"
echo "[s3-train-root] sources=${SOURCES[*]}"
echo "[s3-train-root] state_contract=$STATE_CONTRACT"

python3 "$ROOT/training/scripts/prepare_smolvla_s3_merged_v30.py" "${ARGS[@]}"
python3 "$ROOT/training/scripts/validate_smolvla_s3_release.py" \
  --release-dir "$RELEASE" \
  --train-root "$OUT" \
  --include-split "$INCLUDE_SPLIT"

echo "[s3-train-root] Pass. Export S3_DATASET_ROOT=$OUT before formal train."
