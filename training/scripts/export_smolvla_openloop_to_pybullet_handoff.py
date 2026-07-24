#!/usr/bin/env python3
"""Export one SmolVLA open-loop episode to a PyBullet ee_delta handoff (diagnostic).

Converts consecutive absolute_eef_gripper[8] predictions into ee_delta_gripper[7]
by finite differencing. This is a lightweight downstream interface smoke only:
it is NOT Isaac S4 closed-loop and does NOT claim task success.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def _quat_to_rot(q: np.ndarray) -> np.ndarray:
    x, y, z, w = (float(v) for v in q)
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n < 1e-8:
        raise ValueError("quaternion norm too small")
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def _rot_to_rpy(R: np.ndarray) -> np.ndarray:
    sy = math.sqrt(float(R[0, 0]) ** 2 + float(R[1, 0]) ** 2)
    if sy > 1e-8:
        roll = math.atan2(float(R[2, 1]), float(R[2, 2]))
        pitch = math.atan2(-float(R[2, 0]), sy)
        yaw = math.atan2(float(R[1, 0]), float(R[0, 0]))
    else:
        roll = math.atan2(-float(R[1, 2]), float(R[1, 1]))
        pitch = math.atan2(-float(R[2, 0]), sy)
        yaw = 0.0
    return np.array([roll, pitch, yaw], dtype=np.float64)


def _quat_delta_rpy(q0: np.ndarray, q1: np.ndarray) -> np.ndarray:
    r0 = _quat_to_rot(q0)
    r1 = _quat_to_rot(q1)
    return _rot_to_rpy(r1 @ r0.T)


def abs_sequence_to_ee_delta(
    raw_preds: np.ndarray,
    *,
    max_delta_xyz: float,
    max_delta_rpy: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    if raw_preds.ndim != 2 or raw_preds.shape[1] != 8:
        raise ValueError(f"expected raw_pred [N,8], got {raw_preds.shape}")
    xyz = raw_preds[:, :3]
    quat = raw_preds[:, 3:7]
    grip = np.clip(raw_preds[:, 7], 0.0, 1.0)
    deltas = np.zeros((len(raw_preds), 7), dtype=np.float64)
    clipped_xyz = 0
    clipped_rpy = 0
    for index in range(len(raw_preds)):
        if index == 0:
            delta = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, float(grip[0])])
        else:
            dxyz = xyz[index] - xyz[index - 1]
            drpy = _quat_delta_rpy(quat[index - 1], quat[index])
            delta = np.concatenate([dxyz, drpy, [float(grip[index])]])
        before = delta.copy()
        delta[:3] = np.clip(delta[:3], -max_delta_xyz, max_delta_xyz)
        delta[3:6] = np.clip(delta[3:6], -max_delta_rpy, max_delta_rpy)
        if not np.allclose(before[:3], delta[:3]):
            clipped_xyz += 1
        if not np.allclose(before[3:6], delta[3:6]):
            clipped_rpy += 1
        deltas[index] = delta
    stats = {
        "frames": int(len(deltas)),
        "xyz_step_l2_p50": float(np.percentile(np.linalg.norm(deltas[:, :3], axis=1), 50)),
        "xyz_step_l2_p90": float(np.percentile(np.linalg.norm(deltas[:, :3], axis=1), 90)),
        "xyz_step_l2_max": float(np.max(np.linalg.norm(deltas[:, :3], axis=1))),
        "rpy_abs_max": float(np.max(np.abs(deltas[:, 3:6]))),
        "frames_clipped_xyz": clipped_xyz,
        "frames_clipped_rpy": clipped_rpy,
        "max_delta_xyz": max_delta_xyz,
        "max_delta_rpy": max_delta_rpy,
        "conversion": "consecutive_abs_eef_finite_difference",
    }
    return deltas, stats


def export_handoff(
    *,
    report_path: Path,
    output_dir: Path,
    episode_index: int,
    max_delta_xyz: float,
    max_delta_rpy: float,
) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    episodes = report["per_episode_raw_results"]["lora"]
    if episode_index < 0 or episode_index >= len(episodes):
        raise IndexError(f"episode_index {episode_index} out of range [0,{len(episodes)})")
    episode = episodes[episode_index]
    logs = episode["frame_logs"]
    raw = np.asarray([frame["raw_pred"] for frame in logs], dtype=np.float64)
    deltas, stats = abs_sequence_to_ee_delta(
        raw, max_delta_xyz=max_delta_xyz, max_delta_rpy=max_delta_rpy
    )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    release_id = str(report.get("release_id") or "smolvla_s3_recovery_v3_openloop_diagnostic")
    handoff_id = f"smolvla_v3_pybullet_smoke_ep{episode_index}_v0"
    rows: list[dict[str, Any]] = []
    base_ts = 1_700_000_000.0
    for frame_index, action in enumerate(deltas):
        ts = logs[frame_index].get("timestamp")
        try:
            timestamp = float(ts)
        except (TypeError, ValueError):
            timestamp = base_ts + 0.1 * frame_index
        rows.append(
            {
                "action": [float(v) for v in action.tolist()],
                "action_type": "ee_delta_gripper",
                "episode_index": 0,
                "frame_index": frame_index,
                "release_id": release_id,
                "robot": "panda",
                "schema_id": "panda_ee_delta_gripper_v0",
                "task": "smolvla_openloop_to_delta_diagnostic",
                "timestamp": timestamp,
                "source_episode_ref": episode.get("episode_ref"),
            }
        )
    replay_path = output_dir / "predicted_actions.jsonl"
    with replay_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    replay_check = {
        "status": "PASS",
        "frames": len(rows),
        "episodes": 1,
        "action_type": "ee_delta_gripper",
        "action_dim": 7,
        "warnings": [
            "Converted from SmolVLA absolute_eef open-loop predictions; not expert labels.",
            "Deltas clipped to PandaActionAdapter defaults for interface smoke.",
        ],
        "conversion_stats": stats,
        "claims_task_success": False,
        "ran_isaac": False,
        "is_closed_loop": False,
    }
    (output_dir / "replay_check.json").write_text(
        json.dumps(replay_check, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = {
        "handoff_format": "panda_bridge_handoff_v0",
        "handoff_id": handoff_id,
        "producer_repo": "robot-arm-episode-data-lab",
        "consumer_repo": "ros2-moveit-pybullet-bridge",
        "robot": "panda",
        "schema_id": "panda_ee_delta_gripper_v0",
        "action_type": "ee_delta_gripper",
        "action_dim": 7,
        "release_id": release_id,
        "episodes": 1,
        "frames": len(rows),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "files": {
            "replay": "predicted_actions.jsonl",
            "replay_check": "replay_check.json",
            "smoke_report": "pybullet_ik_smoke.json",
        },
        "source_open_loop_report": str(report_path),
        "source_episode_ref": episode.get("episode_ref"),
        "diagnostic_only": True,
        "claims_task_success": False,
        "ran_isaac": False,
        "is_closed_loop": False,
        "notes": [
            "Lightweight PyBullet interface smoke from open-loop abs-EEF finite differences.",
            "Not a substitute for Isaac S4 closed-loop.",
        ],
    }
    (output_dir / "handoff_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "handoff_dir": str(output_dir),
        "handoff_id": handoff_id,
        "episode_ref": episode.get("episode_ref"),
        "conversion_stats": stats,
    }


def run_pybullet_ik_smoke(handoff_dir: Path) -> dict[str, Any]:
    import sys

    downstream = Path("/home/ina/ros2_ws/src/ros2-moveit-pybullet-bridge")
    sys.path.insert(0, str(downstream / "pybullet_bridge"))
    from pybullet_bridge.learning.panda_action_adapter import (  # type: ignore
        PandaActionAdapter,
        PandaActionAdapterConfig,
    )
    from pybullet_bridge.learning.panda_handoff import load_handoff_bundle  # type: ignore

    bundle = load_handoff_bundle(handoff_dir)
    adapter = PandaActionAdapter(PandaActionAdapterConfig(command_mode="pybullet_ik"))
    # Neutral-ish Panda seed; absolute accuracy is not the smoke goal.
    joints = np.array([0.0, -0.4, 0.0, -2.0, 0.0, 1.5, 0.0], dtype=np.float64)
    joint_names = [f"panda_joint{i}" for i in range(1, 8)]
    ok = 0
    fail = 0
    fail_reasons: dict[str, int] = {}
    actions = np.asarray(bundle.actions, dtype=np.float64)
    for action in actions:
        try:
            command = adapter.to_joint_command(
                action, {"joint_positions": joints}, joint_names
            )
            joints = np.asarray(command.joint_targets, dtype=np.float64).reshape(7)
            ok += 1
        except Exception as exc:  # noqa: BLE001 - smoke aggregates failures
            fail += 1
            key = type(exc).__name__ + ":" + str(exc).split(":")[0][:80]
            fail_reasons[key] = fail_reasons.get(key, 0) + 1
    report = {
        "artifact_type": "smolvla_pybullet_ik_smoke_v0",
        "handoff_id": bundle.manifest.get("handoff_id"),
        "frames": int(actions.shape[0]),
        "ik_ok": ok,
        "ik_fail": fail,
        "ik_ok_ratio": float(ok / max(int(actions.shape[0]), 1)),
        "fail_reasons": fail_reasons,
        "claims_task_success": False,
        "ran_isaac": False,
        "is_closed_loop": False,
        "interpretation": (
            "interface_smoke_pass"
            if fail == 0
            else "interface_smoke_partial_or_fail"
        ),
    }
    out = handoff_dir / "pybullet_ik_smoke.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--open-loop-report",
        type=Path,
        default=ROOT
        / "runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/s3_open_loop_report.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "runs/smolvla_s3/pybullet_smoke_v3_ep0",
    )
    parser.add_argument("--episode-index", type=int, default=0)
    parser.add_argument("--max-delta-xyz", type=float, default=0.05)
    parser.add_argument("--max-delta-rpy", type=float, default=0.25)
    args = parser.parse_args()

    meta = export_handoff(
        report_path=args.open_loop_report,
        output_dir=args.output_dir,
        episode_index=args.episode_index,
        max_delta_xyz=args.max_delta_xyz,
        max_delta_rpy=args.max_delta_rpy,
    )
    smoke = run_pybullet_ik_smoke(args.output_dir)
    summary = {**meta, "pybullet_ik_smoke": smoke}
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if smoke["ik_fail"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
