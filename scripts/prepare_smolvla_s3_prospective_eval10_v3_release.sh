#!/usr/bin/env bash
# Build immutable prospective-eval-only release for eval_gate_v3 (seeds 70-74).
# Does not train or launch Isaac.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM="${UPSTREAM_ROOT:-/home/ina/dev/ros2-arm-teleoperation-suite}"
STAMP="${PROSPECTIVE_STAMP:-20260724b}"
RUN_DIR="${ROOT}/runs/smolvla_s3/prospective_eval10_v3_${STAMP}"
SOURCE_JSON="${RUN_DIR}/source_roots.json"
RELEASE_ID="smolvla_s3_recovery_v3_prospective_eval10_gate_v3_${STAMP}"
OUT="${ROOT}/data/releases/${RELEASE_ID}"
NORM_SRC="${ROOT}/data/releases/smolvla_s3_panda_abs_eef_scene_v3_phaseaware50"

if [[ ! -f "${SOURCE_JSON}" ]]; then
  echo "[v3-prospective-release] missing ${SOURCE_JSON}; collect first" >&2
  exit 2
fi

mapfile -t SRC_ARGS < <(
  python3 - "${SOURCE_JSON}" <<'PY'
import json, sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for root in payload["source_dataset_roots"]:
    print("--source")
    print(root)
PY
)

python3 "${ROOT}/training/scripts/prepare_smolvla_s3_release.py" \
  --output-dir "${OUT}" \
  --release-id "${RELEASE_ID}" \
  --split-policy prospective_eval_only \
  --compose-state15 \
  --cameras scene \
  --normalization-source-release "${NORM_SRC}" \
  "${SRC_ARGS[@]}"

python3 "${ROOT}/training/scripts/validate_smolvla_s3_release.py" \
  --release-dir "${OUT}"

python3 - "${OUT}" "${RUN_DIR}/prospective_eval_manifest.yaml" <<'PY'
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import yaml

release = Path(sys.argv[1])
manifest_out = Path(sys.argv[2])
splits = json.loads((release / "splits.json").read_text(encoding="utf-8"))
gate = Path("configs/smolvla_s3/eval_gate_v3.yaml")
# refs are under benchmark for prospective_eval_only
refs = list(splits.get("benchmark") or [])
payload = {
    "contract_version": "smolvla_s3_prospective_eval_manifest_v1",
    "evaluation_id": "recovery_v3_prospective_eval10_gate_v3_20260724",
    "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "human_authorized_run": False,
    "thresholds_frozen_before_evaluation": True,
    "gate_path": "configs/smolvla_s3/eval_gate_v3.yaml",
    "gate_sha256": hashlib.sha256(gate.read_bytes()).hexdigest(),
    "release_splits_sha256": hashlib.sha256((release / "splits.json").read_bytes()).hexdigest(),
    "evaluation_episode_refs": refs,
    "notes": [
        "Fresh eval-only set for eval_gate_v3 (seeds 70-74).",
        "Zero overlap with train and with v3 threshold-design refs (incl. prior v2 prospective 10).",
        "Flip human_authorized_run=true only when authorizing the GPU open-loop run; does not authorize Isaac.",
    ],
}
manifest_out.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
print(f"[v3-prospective-release] wrote {manifest_out} with {len(refs)} refs")
PY

echo "[v3-prospective-release] immutable release ready: ${OUT}"
echo "[v3-prospective-release] NO train / NO Isaac"
