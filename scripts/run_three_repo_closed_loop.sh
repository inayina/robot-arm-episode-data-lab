#!/usr/bin/env bash
# Run the midstream + optional downstream stages of the three-repo closed loop.
#
# Gate G1 (always): adapt -> inspect -> release -> smoke train -> replay -> handoff
# Gate G2 (optional): downstream panda_jsonl_replay benchmark when bridge repo is built
#
# Usage:
#   # Real upstream raw dataset (episode_*/train layout):
#   UPSTREAM_RAW=/tmp/batch_out ./scripts/run_three_repo_closed_loop.sh
#
#   # Mock upstream (CI / no ROS):
#   CLOSED_LOOP_USE_MOCK=1 ./scripts/run_three_repo_closed_loop.sh
#
#   # Include downstream benchmark (requires ros2_ws + bridge built):
#   WITH_DOWNSTREAM=1 ./scripts/run_three_repo_closed_loop.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM_REPO="${UPSTREAM_REPO:-/home/ina/dev/ros2-arm-teleoperation-suite}"
BRIDGE_REPO="${BRIDGE_REPO:-/home/ina/ros2_ws/src/ros2-moveit-pybullet-bridge}"
ROS2_WS="${ROS2_WS:-/home/ina/ros2_ws}"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_ROOT="${CLOSED_LOOP_OUTPUT_ROOT:-/tmp/three_repo_closed_loop_${STAMP}_$$}"
RELEASE_ID="${CLOSED_LOOP_RELEASE_ID:-panda_closed_loop_${STAMP}}"
HANDOFF_ID="${CLOSED_LOOP_HANDOFF_ID:-${RELEASE_ID}_bridge}"
SCHEMA="${CLOSED_LOOP_SCHEMA:-${REPO_ROOT}/configs/robot_schemas/panda.yaml}"
WITH_DOWNSTREAM="${WITH_DOWNSTREAM:-0}"
USE_MOCK="${CLOSED_LOOP_USE_MOCK:-0}"

RAW_INPUT="${UPSTREAM_RAW:-}"
ADAPTED="${OUT_ROOT}/adapted"
RELEASE="${OUT_ROOT}/release"
TRAIN="${OUT_ROOT}/train"
HANDOFF="${TRAIN}/bridge_handoff"
EVIDENCE="${OUT_ROOT}/evidence"

log() { echo "[closed-loop] $*"; }

mkdir -p "${OUT_ROOT}" "${EVIDENCE}"

if [[ "${USE_MOCK}" == "1" ]]; then
  log "G1: generating mock upstream raw at ${OUT_ROOT}/mock_raw"
  python3 "${REPO_ROOT}/training/scripts/make_mock_panda_dataset.py" \
    --output "${OUT_ROOT}/mock_raw"
  RAW_INPUT="${OUT_ROOT}/mock_raw"
fi

if [[ -z "${RAW_INPUT}" ]]; then
  echo "Set UPSTREAM_RAW to an upstream episode root, or CLOSED_LOOP_USE_MOCK=1" >&2
  exit 2
fi

if [[ ! -d "${RAW_INPUT}" ]]; then
  echo "UPSTREAM_RAW not found: ${RAW_INPUT}" >&2
  exit 2
fi

log "G1-1 adapt upstream raw: ${RAW_INPUT}"
python3 "${REPO_ROOT}/training/scripts/adapt_upstream_panda_dataset.py" \
  --input "${RAW_INPUT}" \
  --output "${ADAPTED}" \
  --schema "${SCHEMA}" \
  --derive-ee-delta-action

log "G1-2 inspect adapted dataset"
python3 "${REPO_ROOT}/training/scripts/inspect_dataset.py" \
  --dataset "${ADAPTED}" \
  --schema "${SCHEMA}" \
  --json-output "${ADAPTED}/inspection_report.json"

log "G1-3 prepare release ${RELEASE_ID}"
python3 "${REPO_ROOT}/training/scripts/prepare_dataset_release.py" \
  --input "${ADAPTED}" \
  --output "${RELEASE}" \
  --schema "${SCHEMA}" \
  --release-id "${RELEASE_ID}" \
  --description "three-repo closed loop ${STAMP}"

log "G1-4 smoke train"
python3 "${REPO_ROOT}/training/scripts/train_act_smoke.py" \
  --dataset "${RELEASE}" \
  --schema "${SCHEMA}" \
  --output "${TRAIN}"

log "G1-5 replay export"
python3 "${REPO_ROOT}/training/scripts/replay_policy.py" \
  --dataset "${RELEASE}" \
  --checkpoint "${TRAIN}/checkpoint.npz" \
  --schema "${SCHEMA}" \
  --output "${TRAIN}/predicted_actions.jsonl"

log "G1-6 bridge handoff"
python3 "${REPO_ROOT}/training/scripts/prepare_bridge_handoff.py" \
  --dataset "${RELEASE}" \
  --replay "${TRAIN}/predicted_actions.jsonl" \
  --schema "${SCHEMA}" \
  --output "${HANDOFF}" \
  --handoff-id "${HANDOFF_ID}"

# Evidence bundle (G3)
{
  echo "created_at=${STAMP}"
  echo "upstream_raw=${RAW_INPUT}"
  echo "release_id=${RELEASE_ID}"
  echo "handoff_id=${HANDOFF_ID}"
  echo "adapted=${ADAPTED}"
  echo "release=${RELEASE}"
  echo "train=${TRAIN}"
  echo "handoff=${HANDOFF}"
} > "${EVIDENCE}/paths.env"

if [[ -d "${UPSTREAM_REPO}/.git" ]]; then
  git -C "${UPSTREAM_REPO}" rev-parse HEAD > "${EVIDENCE}/upstream_commit.txt" 2>/dev/null || true
fi
git -C "${REPO_ROOT}" rev-parse HEAD > "${EVIDENCE}/middle_commit.txt" 2>/dev/null || true
if [[ -d "${BRIDGE_REPO}/.git" ]]; then
  git -C "${BRIDGE_REPO}" rev-parse HEAD > "${EVIDENCE}/downstream_commit.txt" 2>/dev/null || true
fi

cp "${ADAPTED}/manifest.json" "${EVIDENCE}/adapted_manifest.json" 2>/dev/null || true
cp "${RELEASE}/manifest.json" "${EVIDENCE}/release_manifest.json" 2>/dev/null || true
cp "${HANDOFF}/handoff_manifest.json" "${EVIDENCE}/handoff_manifest.json" 2>/dev/null || true
cp "${TRAIN}/metrics.json" "${EVIDENCE}/metrics.json" 2>/dev/null || true

python3 - <<PY
import json
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

registry = Path("${REPO_ROOT}") / "data" / "registry" / "releases.yaml"
entry = {
    "release_id": "${RELEASE_ID}",
    "handoff_id": "${HANDOFF_ID}",
    "upstream_raw": "${RAW_INPUT}",
    "release_path": "${RELEASE}",
    "handoff_path": "${HANDOFF}",
    "created_at": "${STAMP}",
    "closed_loop_output": "${OUT_ROOT}",
}
registry.parent.mkdir(parents=True, exist_ok=True)
if yaml is not None and registry.exists():
    data = yaml.safe_load(registry.read_text(encoding="utf-8")) or {}
    releases = list(data.get("releases") or [])
    releases.append(entry)
    data["releases"] = releases
    registry.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
else:
    lines = registry.read_text(encoding="utf-8").splitlines() if registry.exists() else [
        "# Auto-appended by run_three_repo_closed_loop.sh",
        "releases:",
    ]
    if not registry.exists():
        registry.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with registry.open("a", encoding="utf-8") as handle:
        handle.write(f"  - release_id: {entry['release_id']}\n")
        handle.write(f"    handoff_id: {entry['handoff_id']}\n")
        handle.write(f"    upstream_raw: {entry['upstream_raw']}\n")
        handle.write(f"    release_path: {entry['release_path']}\n")
        handle.write(f"    handoff_path: {entry['handoff_path']}\n")
        handle.write(f"    created_at: {entry['created_at']}\n")
print("appended registry entry:", registry)
PY

if [[ "${WITH_DOWNSTREAM}" == "1" ]]; then
  log "G2: downstream panda_jsonl_replay benchmark"
  if [[ ! -f "${ROS2_WS}/install/setup.bash" ]]; then
    echo "ROS2 workspace not built at ${ROS2_WS}; skip downstream (set WITH_DOWNSTREAM=0)" >&2
    exit 1
  fi
  # shellcheck disable=SC1091
  set +u
  source /opt/ros/jazzy/setup.bash
  source "${ROS2_WS}/install/setup.bash"
  set -u
  BENCH_OUT="${OUT_ROOT}/downstream_benchmark"
  mkdir -p "${BENCH_OUT}"
  python3 "${BRIDGE_REPO}/scripts/benchmark_system.py" \
    --strategy panda_jsonl_replay \
    --panda-handoff-path "${HANDOFF}" \
    --episodes 1 \
    --duration-sec 5.0 \
    --output-dir "${BENCH_OUT}" \
    --launch-stack
  cp "${BENCH_OUT}/benchmark_summary.json" "${EVIDENCE}/benchmark_summary.json" 2>/dev/null || true
fi

log "PASS: closed loop artifacts at ${OUT_ROOT}"
log "  release: ${RELEASE}"
log "  handoff: ${HANDOFF}"
log "  evidence: ${EVIDENCE}"
