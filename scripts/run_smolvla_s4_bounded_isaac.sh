#!/usr/bin/env bash
# Thin midstream launcher for bounded SmolVLA → Isaac S4.
# Delegates to upstream scripts/run_isaac_smolvla_s4.sh.
set -euo pipefail
MIDSTREAM="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM="${UPSTREAM:-/home/ina/dev/ros2-arm-teleoperation-suite}"
export MIDSTREAM
export ISAAC_FRANKA_USD="${ISAAC_FRANKA_USD:-$HOME/isaac_assets/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd}"
export ISAAC_REQUIRE_LOCAL_FRANKA="${ISAAC_REQUIRE_LOCAL_FRANKA:-1}"
export RECORD_SCENE_VIDEO="${RECORD_SCENE_VIDEO:-false}"
exec bash "${UPSTREAM}/scripts/run_isaac_smolvla_s4.sh" "$@"
