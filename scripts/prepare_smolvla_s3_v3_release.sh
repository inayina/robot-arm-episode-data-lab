#!/usr/bin/env bash
# Build immutable SmolVLA S3 v3 scene-only phaseaware50 release (state[15]).
# Does not train or launch Isaac.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM="${UPSTREAM_ROOT:-/home/ina/dev/ros2-arm-teleoperation-suite}"
STAMP="${V3_STAMP:-$(date +%Y%m%d)}"
RELEASE_ID="smolvla_s3_panda_abs_eef_scene_v3_phaseaware50"
OUT="${ROOT}/data/releases/${RELEASE_ID}"
MAP_JSON="${POSITION_MAP_JSON:-${UPSTREAM}/evidence/v3_phaseaware50_${STAMP}_position_map.json}"

if [[ ! -f "${MAP_JSON}" ]]; then
  echo "[v3-release] missing position map: ${MAP_JSON}" >&2
  exit 2
fi

SRC_ARGS=()
while IFS= read -r name; do
  SRC_ARGS+=(--source "${UPSTREAM}/data/${name}")
done < <(python3 - "${MAP_JSON}" <<'PY'
import json, sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for source_name in sorted(payload):
    print(source_name)
PY
)

python3 "${ROOT}/training/scripts/prepare_smolvla_s3_release.py" \
  --output-dir "${OUT}" \
  --release-id "${RELEASE_ID}" \
  --split-policy phaseaware50 \
  --compose-state15 \
  --position-map-json "${MAP_JSON}" \
  --cameras scene \
  "${SRC_ARGS[@]}"

python3 "${ROOT}/training/scripts/validate_smolvla_s3_release.py" \
  --release-dir "${OUT}"

echo "[v3-release] immutable release ready: ${OUT}"
echo "[v3-release] NO train / NO Isaac"
