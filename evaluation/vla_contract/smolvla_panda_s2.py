"""SmolVLA Gate S2 helpers: Panda absolute-EEF open-loop packaging (offline).

Does not train, does not launch Isaac, does not claim task success.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from evaluation.vla_contract.absolute_eef import (
    POLICY_ACTION_SEMANTICS,
    quat_angular_error_rad,
)

# Declared diagnostic mapping only — not a claim that SmolVLA-native == absolute EEF.
MAPPING_HYPOTHESIS = "libero6d_pred012_as_xyz_pred5_as_gripper_quat_unmapped"
S2_REPORT_VERSION = "smolvla_gate_s2_report_v0"

# H-3 semantic Go thresholds (strict; pretrained base expected to fail).
H3_EE_RMSE_M_MAX = 0.05
H3_GRIPPER_ACC_MIN = 0.70


def load_video_frame_bgr(video_path: Path, frame_index: int) -> np.ndarray:
    """Load one BGR frame via OpenCV (av not required)."""
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"cannot open video: {video_path}")
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_index < 0 or (total > 0 and frame_index >= total):
            raise IndexError(f"frame_index {frame_index} out of range (total={total})")
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
        ok, frame = cap.read()
        if not ok or frame is None:
            raise RuntimeError(f"failed to read frame {frame_index} from {video_path}")
        return frame
    finally:
        cap.release()


def bgr_to_chw_float01(frame_bgr: np.ndarray, size: int = 256) -> np.ndarray:
    """BGR uint8 HxWx3 → float32 CHW in [0,1], resized to size×size."""
    import cv2

    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_AREA)
    chw = np.transpose(resized.astype(np.float32) / 255.0, (2, 0, 1))
    return chw


def panda_state6_from_row(row: Mapping[str, Any]) -> np.ndarray:
    """Provisional 6-D proprio for SmolVLA-base (libero-shaped) input.

    Uses EE xyz[3] + first 3 joints. Documented adapter mapping, not native Panda schema.
    """
    ee = np.asarray(row["observation.ee_pose"], dtype=np.float32).reshape(-1)
    joints = np.asarray(row["observation.state"], dtype=np.float32).reshape(-1)
    if ee.shape[0] < 3 or joints.shape[0] < 3:
        raise ValueError("need observation.ee_pose>=3 and observation.state>=3")
    return np.concatenate([ee[:3], joints[:3]], axis=0)


def expert_absolute_action8(row: Mapping[str, Any]) -> np.ndarray:
    action = np.asarray(row["action"], dtype=np.float64).reshape(-1)
    if action.shape[0] == 7:
        raise ValueError("refusing ee_delta_gripper[7] as absolute EEF expert label")
    if action.shape[0] != 8:
        raise ValueError(f"expected action[8], got {action.shape[0]}")
    return action


def map_libero6_to_abs_channels(pred6: Sequence[float]) -> dict[str, Any]:
    """Map SmolVLA 6-D output under MAPPING_HYPOTHESIS."""
    p = np.asarray(pred6, dtype=np.float64).reshape(-1)
    if p.shape[0] < 6:
        raise ValueError(f"expected pred[6], got {p.shape[0]}")
    xyz = p[:3].tolist()
    grip = float(np.clip(p[5], 0.0, 1.0))
    return {
        "ee_target_xyz": xyz,
        "ee_target_xyzw": None,  # unmapped under 6-D hypothesis
        "gripper_cmd": grip,
        "raw_pred6": p[:6].tolist(),
        "mapping_hypothesis": MAPPING_HYPOTHESIS,
    }


def frame_errors(
    pred_mapped: Mapping[str, Any],
    expert8: Sequence[float],
    *,
    gripper_tol: float = 0.25,
) -> dict[str, float | None]:
    expert = np.asarray(expert8, dtype=np.float64).reshape(8)
    pred_xyz = np.asarray(pred_mapped["ee_target_xyz"], dtype=np.float64)
    ee_err = float(np.linalg.norm(pred_xyz - expert[:3]))
    grip_ok = float(abs(float(pred_mapped["gripper_cmd"]) - float(expert[7])) <= gripper_tol)
    quat_err = None
    if pred_mapped.get("ee_target_xyzw") is not None:
        quat_err = quat_angular_error_rad(pred_mapped["ee_target_xyzw"], expert[3:7])
    return {
        "ee_position_l2_m": ee_err,
        "quaternion_angular_error_rad": quat_err,
        "gripper_correct": grip_ok,
        "gripper_abs_err": abs(float(pred_mapped["gripper_cmd"]) - float(expert[7])),
    }


def aggregate_open_loop_metrics(
    per_frame: Sequence[Mapping[str, Any]],
    latencies_ms: Sequence[float],
) -> dict[str, Any]:
    if not per_frame:
        raise ValueError("empty per_frame errors")
    ee = np.asarray([f["ee_position_l2_m"] for f in per_frame], dtype=np.float64)
    grip = np.asarray([f["gripper_correct"] for f in per_frame], dtype=np.float64)
    grip_err = np.asarray([f["gripper_abs_err"] for f in per_frame], dtype=np.float64)
    # Smoothness on mapped xyz sequence if provided
    jerk = None
    xyz_seq = [f.get("pred_xyz") for f in per_frame if f.get("pred_xyz") is not None]
    if len(xyz_seq) >= 3:
        arr = np.asarray(xyz_seq, dtype=np.float64)
        accel = np.diff(arr, n=2, axis=0)
        jerk = float(np.mean(np.linalg.norm(accel, axis=1)))

    quat_vals = [
        f["quaternion_angular_error_rad"]
        for f in per_frame
        if f.get("quaternion_angular_error_rad") is not None
    ]
    quat_mean = float(np.mean(quat_vals)) if quat_vals else None

    active = ee  # only comparable active scalar under hypothesis
    return {
        "active_channel_mae": float(np.mean(ee)),
        "active_channel_rmse": float(math.sqrt(np.mean(ee**2))),
        "ee_position_rmse_m": float(math.sqrt(np.mean(ee**2))),
        "quaternion_angular_error_rad": quat_mean,
        "gripper_accuracy": float(np.mean(grip)),
        "gripper_close_timing_frames": None,
        "action_smoothness_jerk": jerk,
        "action_saturation_ratio": float(np.mean((grip_err > 0.99).astype(np.float64))),
        "padding_channel_anomaly_ratio": 0.0,
        "inference_latency_ms": float(np.mean(latencies_ms)) if latencies_ms else None,
        "home_no_close_rate": None,
        "stage_aligned_errors": None,
    }


def build_open_loop_report(metrics: Mapping[str, Any], *, notes: str) -> dict[str, Any]:
    return {
        "contract_version": "vla_open_loop_report_v0",
        "artifact_type": "vla_open_loop_report",
        "policy_action_semantics": POLICY_ACTION_SEMANTICS,
        "metric_lane": "offline_open_loop",
        "claims_task_success": False,
        "forbids_act_delta_mixed_table": True,
        "metrics": dict(metrics),
        "prohibited_fields": [
            "act_ee_delta_l1",
            "act_ee_delta_rmse",
            "task_success_rate",
            "place_success_rate",
        ],
        "notes": notes,
    }


def h3_semantic_status(metrics: Mapping[str, Any]) -> str:
    ee = metrics.get("ee_position_rmse_m")
    grip = metrics.get("gripper_accuracy")
    if ee is None or grip is None:
        return "no_go"
    if float(ee) <= H3_EE_RMSE_M_MAX and float(grip) >= H3_GRIPPER_ACC_MIN:
        return "go"
    return "no_go"


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
