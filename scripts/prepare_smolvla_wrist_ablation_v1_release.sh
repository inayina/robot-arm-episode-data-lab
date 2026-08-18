#!/usr/bin/env bash
# Build immutable wrist-ablation v1 parent release (scene + wrist, state[15]).
# Does not train or launch Isaac. Does not overwrite the historical v3 release.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM="${UPSTREAM_ROOT:-/home/ina/dev/ros2-arm-teleoperation-suite}"
STAMP="${WRIST_ABLATION_STAMP:-$(date +%Y%m%d)}"
RELEASE_ID="smolvla_wrist_ablation_v1_panda_abs_eef_scene_wrist_phaseaware50"
OUT="${ROOT}/data/releases/${RELEASE_ID}"
MAP_JSON="${POSITION_MAP_JSON:-${UPSTREAM}/evidence/wrist_ablation_v1_phaseaware50_${STAMP}_position_map.json}"

if [[ ! -f "${MAP_JSON}" ]]; then
  echo "[wrist-ablation-release] missing position map: ${MAP_JSON}" >&2
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
  --cameras scene,wrist \
  "${SRC_ARGS[@]}"

python3 "${ROOT}/training/scripts/validate_smolvla_s3_release.py" \
  --release-dir "${OUT}"

echo "[wrist-ablation-release] immutable parent release ready: ${OUT}"
echo "[wrist-ablation-release] NO train / NO Isaac"
