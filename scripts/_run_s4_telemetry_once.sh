#!/usr/bin/env bash
# One-shot attribution re-run: same seeds 1-5, video + camera/state telemetry.
# Does not expand seeds. Does not claim task success.
set -uo pipefail

MIDSTREAM="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM="${UPSTREAM:-/home/ina/dev/ros2-arm-teleoperation-suite}"
OUT="${1:-${MIDSTREAM}/evidence/smolvla_s4_bounded5_telemetry_$(date -u +%Y%m%dT%H%M%SZ)}"
LOG="${MIDSTREAM}/evidence/_telemetry_rerun_$(basename "${OUT}").log"

mkdir -p "${OUT}"
echo "${OUT}" > /tmp/smolvla_s4_telemetry_suite_out.txt
echo "${LOG}" > /tmp/smolvla_s4_telemetry_log.txt

# Cleanup without matching this script's argv (use bracket patterns).
bash "${UPSTREAM}/scripts/stop_stack.sh" >/dev/null 2>&1 || true
pkill -9 -f '[i]saac_panda_backend' 2>/dev/null || true
pkill -9 -f '[s]molvla_policy_inference' 2>/dev/null || true
pkill -9 -f '[i]saac_scene_video' 2>/dev/null || true
pkill -9 -f '[i]saac_continuous_gt' 2>/dev/null || true
sleep 2

export ISAAC_FRANKA_USD="${ISAAC_FRANKA_USD:-$HOME/isaac_assets/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd}"
export ISAAC_REQUIRE_LOCAL_FRANKA="${ISAAC_REQUIRE_LOCAL_FRANKA:-1}"
export RECORD_SCENE_VIDEO=true
export DUMP_TELEMETRY=true
export CAMERA_DUMP_STRIDE="${CAMERA_DUMP_STRIDE:-1}"
export SEEDS="${SEEDS:-1 2 3 4 5}"
export MIDSTREAM

{
  echo "[telemetry-rerun] start $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "[telemetry-rerun] OUT=${OUT}"
  echo "[telemetry-rerun] SEEDS=${SEEDS} RECORD_SCENE_VIDEO=${RECORD_SCENE_VIDEO} DUMP_TELEMETRY=${DUMP_TELEMETRY}"
  bash "${MIDSTREAM}/scripts/run_smolvla_s4_bounded_isaac.sh" "${OUT}"
  status=$?
  echo "[telemetry-rerun] suite_exit=${status} $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  # Nuke on done
  bash "${UPSTREAM}/scripts/stop_stack.sh" >/dev/null 2>&1 || true
  pkill -9 -f '[i]saac_panda_backend' 2>/dev/null || true
  pkill -9 -f '[s]molvla_policy_inference' 2>/dev/null || true
  pkill -9 -f '[i]saac_scene_video' 2>/dev/null || true
  pkill -9 -f '[i]saac_continuous_gt' 2>/dev/null || true
  exit "${status}"
} 2>&1 | tee "${LOG}"
