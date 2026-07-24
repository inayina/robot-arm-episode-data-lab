#!/usr/bin/env bash
# Collect the frozen SmolVLA S3 prospective eval-only set.
# Raw MuJoCo/ROS episodes stay upstream; this script never trains or launches Isaac.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM="${UPSTREAM_ROOT:-/home/ina/dev/ros2-arm-teleoperation-suite}"
CFG="${PROSPECTIVE_CFG:-${ROOT}/configs/smolvla_s3/prospective_eval10.yaml}"
STAMP="${PROSPECTIVE_STAMP:-20260724}"
RUN_TAG="${PROSPECTIVE_RUN_TAG:-prospective_eval10}"
RUN_DIR="${ROOT}/runs/smolvla_s3/${RUN_TAG}_${STAMP}"

cleanup() {
  pkill -9 -f "teleop_bringup" || true
  pkill -9 -f "mujoco_sim" || true
  pkill -9 -f "lerobot_recorder" || true
  pkill -9 -f "servo_node" || true
  pkill -9 -f "ros2_control" || true
  bash "${UPSTREAM}/scripts/stop_stack.sh" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [[ ! -x "${UPSTREAM}/scripts/run_batch_preflight_smoke.sh" ]]; then
  echo "[prospective-collect] missing upstream batch runner: ${UPSTREAM}" >&2
  exit 2
fi

mkdir -p "${RUN_DIR}"
mapfile -t POSITION_ROWS < <(
  python3 - "${CFG}" <<'PY'
import sys
from pathlib import Path

import yaml

cfg = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
per_position = int(cfg["collection"]["accepted_episodes_per_position"])
max_attempts = int(cfg["collection"]["max_attempts_per_position"])
for position, row in cfg["positions"].items():
    print(position, row["seed"], per_position, max_attempts, sep="\t")
PY
)

SOURCE_ARGS=()
for row in "${POSITION_ROWS[@]}"; do
  IFS=$'\t' read -r position seed episodes max_attempts <<<"${row}"
  source_name="e2_red_500hz_seed${seed}_v3_prospective_${position}_eval${episodes}_${STAMP}"
  output_root="${UPSTREAM}/data/${source_name}"
  log_root="${UPSTREAM}/evidence/${source_name}"
  randomization="${ROOT}/configs/smolvla_s3/prospective_eval_randomization/${position}.yaml"

  if [[ -e "${output_root}" ]]; then
    echo "[prospective-collect] refuse overwrite: ${output_root}" >&2
    exit 2
  fi

  echo "[prospective-collect] ${position} seed=${seed} accepted=${episodes}"
  (
    cd "${UPSTREAM}"
    export BATCH_PREFLIGHT_OUTPUT_ROOT="${output_root}"
    export BATCH_PREFLIGHT_LOG_DIR="${log_root}"
    export BATCH_PREFLIGHT_SEED="${seed}"
    export BATCH_PREFLIGHT_OBJECTS=object_red_box
    export BATCH_PREFLIGHT_EPISODES="${episodes}"
    export BATCH_PREFLIGHT_MAX_ATTEMPTS="${max_attempts}"
    export BATCH_PREFLIGHT_RANDOMIZE=true
    export BATCH_PREFLIGHT_HEADLESS=true
    export BATCH_PREFLIGHT_CAPTURE_MODE=portfolio
    export BATCH_PREFLIGHT_SCENE_USE_MUJOCO_RENDERER=true
    export BATCH_PREFLIGHT_ENABLE_WRIST_CAMERA=false
    export BATCH_PREFLIGHT_RANDOMIZATION_PATH="${randomization}"
    export BATCH_PREFLIGHT_GRASP_ASSIST=false
    export BATCH_PREFLIGHT_ENABLE_GRASP_MONITOR=false
    export BATCH_PREFLIGHT_VALIDATION_MODE=lift
    export BATCH_PREFLIGHT_CAMERA_WIDTH=320
    export BATCH_PREFLIGHT_CAMERA_HEIGHT=240
    export BATCH_PREFLIGHT_CAMERA_RATE=10.0
    export BATCH_PREFLIGHT_PRE_CLOSE_HOLD=0.4
    export BATCH_PREFLIGHT_CLOSE_DURATION=0.8
    export BATCH_PREFLIGHT_GRASP_PAUSE=0.5
    export BATCH_PREFLIGHT_HOVER_DURATION=3.0
    export BATCH_PREFLIGHT_HOVER_HEIGHT=0.20
    export BATCH_PREFLIGHT_DESCEND_DURATION=6.0
    export BATCH_PREFLIGHT_APPROACH_XY_DURATION=0.0
    export BATCH_PREFLIGHT_POSE_STEP_M=0.001
    export BATCH_PREFLIGHT_POSE_CMD_RATE_HZ=100.0
    export BATCH_PREFLIGHT_POSE_MAX_ACCELERATION_MPS2=0.5
    export BATCH_PREFLIGHT_LIFT_DURATION=8.0
    export BATCH_PREFLIGHT_POST_LIFT_HOLD=4.0
    export BATCH_PREFLIGHT_BATCH_TIMEOUT_S=3600
    export BATCH_PREFLIGHT_DATASET_WAIT_S=120
    export MUJOCO_GL="${MUJOCO_GL:-egl}"
    export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-95}"
    timeout 3900s bash "${UPSTREAM}/scripts/run_batch_preflight_smoke.sh"
  )
  cleanup
  SOURCE_ARGS+=(--source "${output_root}")
done

python3 "${ROOT}/training/scripts/audit_smolvla_s3_phaseaware_dataset.py" \
  "${SOURCE_ARGS[@]}" \
  --config "${CFG}" \
  --json-out "${RUN_DIR}/phaseaware_qa.json"

python3 - "${RUN_DIR}/source_roots.json" "${SOURCE_ARGS[@]}" <<'PY'
import json
import sys
from pathlib import Path

args = sys.argv[2:]
roots = [args[i + 1] for i in range(0, len(args), 2)]
path = Path(sys.argv[1])
path.write_text(json.dumps({"source_dataset_roots": roots}, indent=2) + "\n")
print(f"[prospective-collect] wrote {path}")
PY

echo "[prospective-collect] 10 eval-only episodes collected and QA passed"
echo "[prospective-collect] NO train / NO GPU evaluation / NO Isaac"
