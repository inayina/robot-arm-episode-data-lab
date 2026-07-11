#!/usr/bin/env bash
# Run the midstream + optional downstream stages of the three-repo closed loop.
#
# Gate G1 (always): adapt -> inspect -> release -> smoke train -> replay -> handoff
# Gate G2 (optional): downstream panda_jsonl_replay benchmark when bridge repo is built
#
# Usage:
#   # Default: use upstream persistent archive data/episodes/ when present
#   ./scripts/run_three_repo_closed_loop.sh
#
#   # Explicit upstream raw dataset (episode_*/train layout or archive root):
#   UPSTREAM_RAW=/path/to/data/episodes ./scripts/run_three_repo_closed_loop.sh
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
ARCHIVE_EVIDENCE="${CLOSED_LOOP_ARCHIVE_EVIDENCE:-1}"
REPO_EVIDENCE="${REPO_ROOT}/evidence"
DEFAULT_UPSTREAM_ARCHIVE="${UPSTREAM_REPO}/data/episodes"

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

if [[ "${USE_MOCK}" != "1" && -z "${RAW_INPUT}" && -d "${DEFAULT_UPSTREAM_ARCHIVE}" ]]; then
  if compgen -G "${DEFAULT_UPSTREAM_ARCHIVE}/episode_*/train" > /dev/null; then
    RAW_INPUT="${DEFAULT_UPSTREAM_ARCHIVE}"
    log "using default upstream archive: ${RAW_INPUT}"
  fi
fi

if [[ -z "${RAW_INPUT}" ]]; then
  echo "Set UPSTREAM_RAW to an upstream episode root, or CLOSED_LOOP_USE_MOCK=1" >&2
  exit 2
fi

if [[ ! -d "${RAW_INPUT}" ]]; then
  echo "UPSTREAM_RAW not found: ${RAW_INPUT}" >&2
  exit 2
fi

log "G0 validate upstream raw: ${RAW_INPUT}"
G0_VALIDATE="${EVIDENCE}/_g0_validate_dataset.json"
mkdir -p "${EVIDENCE}/upstream"
if [[ "${USE_MOCK}" == "1" ]]; then
  log "G0 skipped (mock upstream uses midstream layout, not upstream episode_*/train)"
elif [[ -f "${UPSTREAM_REPO}/scripts/validate_dataset.py" ]]; then
  set +e
  python3 "${UPSTREAM_REPO}/scripts/validate_dataset.py" \
    "${RAW_INPUT}" --min-frames 5 --json > "${G0_VALIDATE}"
  G0_RC=$?
  set -e
  cp "${G0_VALIDATE}" "${EVIDENCE}/upstream/validate_dataset.json"
  if [[ "${G0_RC}" -ne 0 ]]; then
    log "WARN: G0 validate_dataset returned ${G0_RC} (see upstream/validate_dataset.json)"
  fi
else
  log "WARN: upstream validate_dataset.py not found; skipping G0"
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

# Evidence bundle (G3) — template layout under ${EVIDENCE}/
G3_META="${EVIDENCE}/meta"
G3_MIDDLE="${EVIDENCE}/middle"
G3_DOWNSTREAM="${EVIDENCE}/downstream"
mkdir -p "${G3_META}" "${G3_MIDDLE}" "${G3_DOWNSTREAM}"

{
  echo "created_at=${STAMP}"
  echo "upstream_raw=${RAW_INPUT}"
  echo "release_id=${RELEASE_ID}"
  echo "handoff_id=${HANDOFF_ID}"
  echo "adapted=${ADAPTED}"
  echo "release=${RELEASE}"
  echo "train=${TRAIN}"
  echo "handoff=${HANDOFF}"
  echo "closed_loop_output=${OUT_ROOT}"
  echo "with_downstream=${WITH_DOWNSTREAM}"
  echo "use_mock=${USE_MOCK}"
} > "${G3_META}/paths.env"

UPSTREAM_COMMIT=""
MIDDLE_COMMIT=""
DOWNSTREAM_COMMIT=""
if [[ -d "${UPSTREAM_REPO}/.git" ]]; then
  UPSTREAM_COMMIT="$(git -C "${UPSTREAM_REPO}" rev-parse HEAD 2>/dev/null || true)"
fi
MIDDLE_COMMIT="$(git -C "${REPO_ROOT}" rev-parse HEAD 2>/dev/null || true)"
if [[ -d "${BRIDGE_REPO}/.git" ]]; then
  DOWNSTREAM_COMMIT="$(git -C "${BRIDGE_REPO}" rev-parse HEAD 2>/dev/null || true)"
fi
{
  echo "upstream=${UPSTREAM_REPO}"
  echo "upstream_commit=${UPSTREAM_COMMIT}"
  echo "middle=${REPO_ROOT}"
  echo "middle_commit=${MIDDLE_COMMIT}"
  echo "downstream=${BRIDGE_REPO}"
  echo "downstream_commit=${DOWNSTREAM_COMMIT}"
} > "${G3_META}/three_repo_commits.txt"

cp "${ADAPTED}/manifest.json" "${G3_MIDDLE}/adapted_manifest.json" 2>/dev/null || true
cp "${RELEASE}/manifest.json" "${G3_MIDDLE}/release_manifest.json" 2>/dev/null || true
cp "${HANDOFF}/handoff_manifest.json" "${G3_MIDDLE}/handoff_manifest.json" 2>/dev/null || true
cp "${TRAIN}/metrics.json" "${G3_MIDDLE}/metrics.json" 2>/dev/null || true
cp "${ADAPTED}/inspection_report.json" "${G3_MIDDLE}/inspection_report.json" 2>/dev/null || true

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
  cp "${BENCH_OUT}/benchmark_summary.json" "${G3_DOWNSTREAM}/benchmark_summary.json" 2>/dev/null || true
fi

python3 - <<PY
import json
from pathlib import Path

evidence = Path("${EVIDENCE}")
summary = {
    "created_at": "${STAMP}",
    "release_id": "${RELEASE_ID}",
    "handoff_id": "${HANDOFF_ID}",
    "upstream_raw": "${RAW_INPUT}",
    "closed_loop_output": "${OUT_ROOT}",
    "with_downstream": "${WITH_DOWNSTREAM}" == "1",
    "use_mock": "${USE_MOCK}" == "1",
    "commits": {
        "upstream": "${UPSTREAM_COMMIT}",
        "middle": "${MIDDLE_COMMIT}",
        "downstream": "${DOWNSTREAM_COMMIT}",
    },
    "gates": {},
}
g0 = evidence / "upstream" / "validate_dataset.json"
if g0.is_file() and g0.read_text(encoding="utf-8").strip():
    payload = json.loads(g0.read_text(encoding="utf-8"))
    summary["gates"]["g0_validate_dataset"] = {
        "valid": bool(payload.get("valid")),
        "episodes": payload.get("episodes"),
        "upstream_gates": payload.get("upstream_gates"),
    }
for name, path in (
    ("g1_release_manifest", evidence / "middle" / "release_manifest.json"),
    ("g1_handoff_manifest", evidence / "middle" / "handoff_manifest.json"),
    ("g1_metrics", evidence / "middle" / "metrics.json"),
):
    summary["gates"][name] = path.is_file()
bench = evidence / "downstream" / "benchmark_summary.json"
if bench.is_file():
    payload = json.loads(bench.read_text(encoding="utf-8"))
    summary["gates"]["g2_benchmark"] = {
        "present": True,
        "mean_latency_ms": payload.get("mean_latency_ms"),
        "max_latency_ms": payload.get("max_latency_ms"),
        "completed_episodes": payload.get("completed_episodes"),
    }
else:
    summary["gates"]["g2_benchmark"] = {"present": False}
(evidence / "meta" / "run_summary.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

if [[ "${ARCHIVE_EVIDENCE}" == "1" ]]; then
  log "G3 archive evidence bundle to ${REPO_EVIDENCE}"
  rm -rf "${REPO_EVIDENCE}"
  mkdir -p "${REPO_EVIDENCE}"
  cp -a "${EVIDENCE}/upstream" "${EVIDENCE}/middle" "${EVIDENCE}/downstream" "${EVIDENCE}/meta" "${REPO_EVIDENCE}/"
  cp "${REPO_ROOT}/docs/templates/closed_loop_evidence/README.md" "${REPO_EVIDENCE}/README.md"
fi

log "PASS: closed loop artifacts at ${OUT_ROOT}"
log "  release: ${RELEASE}"
log "  handoff: ${HANDOFF}"
log "  evidence: ${EVIDENCE}"
if [[ "${ARCHIVE_EVIDENCE}" == "1" ]]; then
  log "  archived: ${REPO_EVIDENCE}"
fi
