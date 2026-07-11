"""Adapter for ros2-arm-teleoperation-suite M6 Panda recorder datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


UPSTREAM_ACTION_TYPE = "ee_pose_gripper"
DERIVED_ACTION_TYPE = "ee_delta_gripper"
PHYSICAL_VALIDATION_GATES = frozenset({"batch_generator"})
TRAINING_FILTER_ONLY_GATES = PHYSICAL_VALIDATION_GATES


def adapt_rows(
    rows: list[dict[str, Any]],
    schema: dict[str, Any],
    *,
    derive_ee_delta_action: bool = False,
) -> tuple[list[dict[str, Any]], str]:
    """Adapt upstream M6 rows into this repository's Panda schema."""
    if not rows:
        raise ValueError("cannot adapt an empty dataset")

    output_action_type = DERIVED_ACTION_TYPE if derive_ee_delta_action else UPSTREAM_ACTION_TYPE
    adapted: list[dict[str, Any]] = []
    for row in rows:
        # Resolve language instruction: prefer dedicated key, fall back to task field.
        lang_instr = str(row.get("language_instruction", row.get("task", "")))
        adapted_row = {
            "observation.state": adapt_state(row, schema),
            "observation.ee_pose": vector(row, "observation.ee_pose", 7),
            "action": adapt_action(
                row,
                schema,
                derive_ee_delta_action=derive_ee_delta_action,
            ),
            "timestamp": float(row["timestamp"]),
            "frame_index": int(row["frame_index"]),
            "episode_index": int(row["episode_index"]),
            # task: backward-compatible free-text label
            "task": str(row.get("task", lang_instr)),
            # language_instruction: independent key for language-conditioned training
            "language_instruction": lang_instr,
        }
        copy_optional(row, adapted_row, "observation.object_pose")
        copy_optional(row, adapted_row, "observation.ft")
        copy_optional(row, adapted_row, "observation.images.scene")
        copy_optional(row, adapted_row, "observation.images.wrist")
        copy_optional(row, adapted_row, "observation.images.tactile_left")
        copy_optional(row, adapted_row, "observation.images.tactile_right")
        copy_optional(row, adapted_row, "observation.depth.scene")
        copy_optional(row, adapted_row, "success")
        copy_optional(row, adapted_row, "safety_estop")
        copy_optional(row, adapted_row, "drive_fault")
        adapted.append(adapted_row)
    return adapted, output_action_type


def adapt_state(row: dict[str, Any], schema: dict[str, Any]) -> list[float]:
    state = vector(row, "observation.state", None)
    expected_dim = int(schema["observation"]["state"]["dim"])
    if len(state) == expected_dim:
        return state
    if len(state) == expected_dim - 1:
        gripper = vector(row, "observation.gripper", 1)
        return [*state, gripper[0]]
    raise ValueError(
        "observation.state must be either canonical [8] or upstream [7] "
        f"with observation.gripper[1], got [{len(state)}]"
    )


def adapt_action(
    row: dict[str, Any],
    schema: dict[str, Any],
    *,
    derive_ee_delta_action: bool,
) -> list[float]:
    action = vector(row, "action", None)
    if not derive_ee_delta_action:
        expected = int(schema["action"][UPSTREAM_ACTION_TYPE]["dim"])
        if len(action) != expected:
            raise ValueError(f"expected upstream action[{expected}], got action[{len(action)}]")
        return action

    expected = int(schema["action"][DERIVED_ACTION_TYPE]["dim"])
    if len(action) == expected:
        return action
    if len(action) != int(schema["action"][UPSTREAM_ACTION_TYPE]["dim"]):
        raise ValueError("cannot derive ee_delta_gripper from action with unexpected dimension")

    ee_pose = vector(row, "observation.ee_pose", 7)
    target_pose = action[:7]
    delta_xyz = (np.asarray(target_pose[:3], dtype=np.float64) - np.asarray(ee_pose[:3], dtype=np.float64))
    delta_rpy = quat_delta_to_rpy(ee_pose[3:7], target_pose[3:7])
    gripper = float(action[7])
    derived = [*delta_xyz.astype(np.float32).tolist(), *delta_rpy.astype(np.float32).tolist(), gripper]
    if len(derived) != expected:
        raise AssertionError("derived action dimension mismatch")
    return derived


def vector(row: dict[str, Any], key: str, expected_dim: int | None) -> list[float]:
    if key not in row:
        raise ValueError(f"missing required key: {key}")
    array = np.asarray(row[key], dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{key} must be 1D, got shape {array.shape}")
    if expected_dim is not None and array.shape[0] != expected_dim:
        raise ValueError(f"{key} must have dim {expected_dim}, got {array.shape[0]}")
    return array.astype(np.float32).tolist()


def copy_optional(source: dict[str, Any], target: dict[str, Any], key: str) -> None:
    if key in source:
        value = source[key]
        if hasattr(value, "tolist"):
            value = value.tolist()
        target[key] = value


def resolve_upstream_gate(source: Path) -> str | None:
    """Read episode-level upstream_gate markers from HuggingFace episode meta.json files."""
    meta_paths = _collect_meta_json_paths(source)
    gates: set[str] = set()
    for meta_path in meta_paths:
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        gate = payload.get("upstream_gate")
        if not gate and isinstance(payload.get("metadata"), dict):
            gate = payload["metadata"].get("upstream_gate")
        if gate:
            gates.add(str(gate))
    if not gates:
        return None
    if len(gates) == 1:
        return next(iter(gates))
    return "mixed"


def physical_validation_applied(upstream_gate: str | None) -> bool:
    return upstream_gate in PHYSICAL_VALIDATION_GATES


def _collect_meta_json_paths(source: Path) -> list[Path]:
    if not source.is_dir():
        return []
    if (source / "meta" / "info.json").is_file():
        return sorted(source.glob("episode_*/meta.json"))
    if source.name == "train" and (source.parent / "meta.json").is_file():
        return [source.parent / "meta.json"]
    if (source / "meta.json").is_file():
        return [source / "meta.json"]
    return sorted(source.glob("episode_*/meta.json"))


def filter_scope_for_gate(upstream_gate: str | None) -> str:
    if upstream_gate in TRAINING_FILTER_ONLY_GATES:
        return "training_split_only"
    return "schema_and_training"


def write_adapted_dataset(
    output: Path,
    rows: list[dict[str, Any]],
    schema: dict[str, Any],
    *,
    action_type: str,
    source: Path,
    derive_ee_delta_action: bool,
    upstream_gate: str | None = None,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with (output / "frames.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    has_lang = any("language_instruction" in row for row in rows)
    has_success = any("success" in row for row in rows)
    resolved_gate = upstream_gate if upstream_gate is not None else resolve_upstream_gate(source)
    manifest = {
        "dataset_format": "panda_jsonl_v0",
        "schema_id": schema["schema_id"],
        "robot": schema["robot"],
        "action_type": action_type,
        "num_episodes": len({row["episode_index"] for row in rows}),
        "num_frames": len(rows),
        "source": "ros2-arm-teleoperation-suite",
        "source_path": str(source),
        "source_action_type": UPSTREAM_ACTION_TYPE,
        "derive_ee_delta_action": bool(derive_ee_delta_action),
        "has_language_instruction": has_lang,
        "has_success_labels": has_success,
        "upstream_gate": resolved_gate,
        "physical_validation_applied": physical_validation_applied(resolved_gate),
        "filter_scope": filter_scope_for_gate(resolved_gate),
        "frames": "frames.jsonl",
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def quat_delta_to_rpy(current_xyzw: list[float], target_xyzw: list[float]) -> np.ndarray:
    current = normalize_quat(np.asarray(current_xyzw, dtype=np.float64))
    target = normalize_quat(np.asarray(target_xyzw, dtype=np.float64))
    delta = quat_multiply(target, quat_inverse(current))
    return quat_to_rpy(normalize_quat(delta))


def normalize_quat(quat: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(quat)
    if norm <= 0.0:
        raise ValueError("quaternion norm must be positive")
    return quat / norm


def quat_inverse(quat: np.ndarray) -> np.ndarray:
    return np.asarray([-quat[0], -quat[1], -quat[2], quat[3]], dtype=np.float64)


def quat_multiply(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return np.asarray(
        [
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
            lw * rw - lx * rx - ly * ry - lz * rz,
        ],
        dtype=np.float64,
    )


def quat_to_rpy(quat: np.ndarray) -> np.ndarray:
    x, y, z, w = quat
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = np.arctan2(sinr_cosp, cosr_cosp)

    sinp = 2.0 * (w * y - z * x)
    pitch = np.sign(sinp) * (np.pi / 2.0) if abs(sinp) >= 1.0 else np.arcsin(sinp)

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = np.arctan2(siny_cosp, cosy_cosp)
    return np.asarray([roll, pitch, yaw], dtype=np.float64)
