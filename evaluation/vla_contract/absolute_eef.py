"""Absolute-EEF (scheme B) helpers for Gate V2 preflight fixtures.

Converts upstream/midstream Panda rows into 55-D canonical active-channel
vectors. Does not run VLA inference, Isaac, or claim task success.

Policy semantics: absolute_eef_gripper_v0
  - NOT ee_delta_gripper
  - action uses gripper command; state uses measured gripper
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

CANONICAL_DIM = 55
POLICY_ACTION_SEMANTICS = "absolute_eef_gripper_v0"
QUATERNION_ORDER = "xyzw"

# Draft offsets from evaluation/examples/vla_panda_active_channel_spec_fixture.json
ARM_OFFSET = 0
ARM_WIDTH = 14
ARM_ACTIVE = 7
EE_OFFSET = 14
EE_WIDTH = 14
EE_ACTIVE = 7
GRIP_OFFSET = 28
GRIP_WIDTH = 2
GRIP_ACTIVE = 1


class AbsoluteEefExportError(ValueError):
    """Interface/data conversion failure (never rewritten as task success)."""


def normalize_xyzw(quat: Sequence[float], *, eps: float = 1e-8) -> list[float]:
    """Normalize quaternion [x, y, z, w]; reject near-zero norms."""
    q = np.asarray(quat, dtype=np.float64).reshape(4)
    norm = float(np.linalg.norm(q))
    if norm < eps:
        raise AbsoluteEefExportError(f"quaternion norm too small: {norm}")
    q = q / norm
    # Canonical hemisphere: force w >= 0 for stability in fixtures.
    if q[3] < 0.0:
        q = -q
    return q.astype(np.float64).tolist()


def quat_angular_error_rad(q_pred: Sequence[float], q_gt: Sequence[float]) -> float:
    """Geodesic angle between two xyzw quaternions (radians)."""
    a = np.asarray(normalize_xyzw(q_pred), dtype=np.float64)
    b = np.asarray(normalize_xyzw(q_gt), dtype=np.float64)
    dot = float(np.clip(abs(np.dot(a, b)), 0.0, 1.0))
    return float(2.0 * math.acos(dot))


def active_mask() -> np.ndarray:
    """Boolean mask over 55-D: True = active for scheme-B action packing."""
    mask = np.zeros(CANONICAL_DIM, dtype=bool)
    mask[ARM_OFFSET : ARM_OFFSET + ARM_ACTIVE] = True
    mask[EE_OFFSET : EE_OFFSET + EE_ACTIVE] = True
    mask[GRIP_OFFSET : GRIP_OFFSET + GRIP_ACTIVE] = True
    return mask


def action_active_mask() -> np.ndarray:
    """Action active dims: EE target[7] + gripper_cmd[1] (joints unused in action)."""
    mask = np.zeros(CANONICAL_DIM, dtype=bool)
    mask[EE_OFFSET : EE_OFFSET + EE_ACTIVE] = True
    mask[GRIP_OFFSET : GRIP_OFFSET + GRIP_ACTIVE] = True
    return mask


def state_active_mask() -> np.ndarray:
    """State active dims: arm joints[7] + gripper_measured[1]."""
    mask = np.zeros(CANONICAL_DIM, dtype=bool)
    mask[ARM_OFFSET : ARM_OFFSET + ARM_ACTIVE] = True
    mask[GRIP_OFFSET : GRIP_OFFSET + GRIP_ACTIVE] = True
    return mask


def _as_1d(name: str, values: Sequence[float], dim: int) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    if array.shape[0] != dim:
        raise AbsoluteEefExportError(f"{name} expected dim {dim}, got {array.shape[0]}")
    if not np.all(np.isfinite(array)):
        raise AbsoluteEefExportError(f"{name} contains non-finite values")
    return array


def _resolve_state8(row: Mapping[str, Any]) -> np.ndarray:
    if "observation.state" in row:
        state = np.asarray(row["observation.state"], dtype=np.float64).reshape(-1)
        if state.shape[0] == 8:
            return state
        if state.shape[0] == 7:
            grip = _as_1d("observation.gripper", row["observation.gripper"], 1)
            return np.concatenate([state, grip])
    raise AbsoluteEefExportError(
        "need observation.state[8] or observation.state[7]+observation.gripper[1]"
    )


def _resolve_absolute_action8(row: Mapping[str, Any]) -> np.ndarray:
    """Require absolute ee_pose_gripper[8]; reject delta[7] masquerading."""
    if "action" not in row:
        raise AbsoluteEefExportError("missing action")
    action = np.asarray(row["action"], dtype=np.float64).reshape(-1)
    if action.shape[0] == 7:
        raise AbsoluteEefExportError(
            "refusing ee_delta_gripper[7] as absolute EEF action; "
            "export requires upstream ee_pose_gripper[8] (xyz+xyzw+gripper_cmd)"
        )
    if action.shape[0] != 8:
        raise AbsoluteEefExportError(f"expected action[8], got [{action.shape[0]}]")
    if not np.all(np.isfinite(action)):
        raise AbsoluteEefExportError("action contains non-finite values")
    # Quat must be normalizable (rejects pure-delta RPY packed as fake quat).
    normalize_xyzw(action[3:7])
    return action


def pack_state55(row: Mapping[str, Any]) -> list[float]:
    state8 = _resolve_state8(row)
    out = np.zeros(CANONICAL_DIM, dtype=np.float64)
    out[ARM_OFFSET : ARM_OFFSET + ARM_ACTIVE] = state8[:7]
    out[GRIP_OFFSET] = state8[7]  # measured gripper
    return out.tolist()


def pack_action55(row: Mapping[str, Any]) -> list[float]:
    action8 = _resolve_absolute_action8(row)
    xyz = action8[:3]
    quat = normalize_xyzw(action8[3:7])
    grip_cmd = float(action8[7])
    if not (0.0 <= grip_cmd <= 1.0):
        raise AbsoluteEefExportError(f"gripper_cmd out of [0,1]: {grip_cmd}")
    out = np.zeros(CANONICAL_DIM, dtype=np.float64)
    out[EE_OFFSET : EE_OFFSET + 3] = xyz
    out[EE_OFFSET + 3 : EE_OFFSET + 7] = quat
    out[GRIP_OFFSET] = grip_cmd
    return out.tolist()


def gripper_cmd_vs_measured(
    row: Mapping[str, Any],
    *,
    tol: float = 1e-3,
) -> dict[str, Any]:
    """Document cmd≠measured split required by scheme B."""
    action8 = _resolve_absolute_action8(row)
    state8 = _resolve_state8(row)
    cmd = float(action8[7])
    measured = float(state8[7])
    abs_diff = abs(cmd - measured)
    return {
        "gripper_cmd": cmd,
        "gripper_measured": measured,
        "abs_diff": abs_diff,
        "cmd_neq_measured": bool(abs_diff > tol),
    }


def export_frame(row: Mapping[str, Any]) -> dict[str, Any]:
    """Export one frame to scheme-B absolute-EEF fixture record."""
    state55 = pack_state55(row)
    action55 = pack_action55(row)
    action8 = _resolve_absolute_action8(row)
    state8 = _resolve_state8(row)
    grip_split = gripper_cmd_vs_measured(row)
    record: dict[str, Any] = {
        "contract_version": "vla_absolute_eef_frame_v0",
        "artifact_type": "vla_absolute_eef_frame",
        "policy_action_semantics": POLICY_ACTION_SEMANTICS,
        "quaternion_order": QUATERNION_ORDER,
        "canonical_dim": CANONICAL_DIM,
        "claims_task_success": False,
        "claims_official_layout_verified": False,
        "frame_index": int(row.get("frame_index", 0)),
        "episode_index": int(row.get("episode_index", 0)),
        "timestamp": float(row.get("timestamp", 0.0)),
        "language_instruction": str(
            row.get("language_instruction", row.get("task", ""))
        ),
        "state_active": {
            "arm_joints": state8[:7].tolist(),
            "gripper_measured": float(state8[7]),
        },
        "action_active": {
            "ee_target_xyz": action8[:3].tolist(),
            "ee_target_xyzw": normalize_xyzw(action8[3:7]),
            "gripper_cmd": float(action8[7]),
        },
        "gripper_split": grip_split,
        "state55": state55,
        "action55": action55,
        "state_active_mask": state_active_mask().astype(int).tolist(),
        "action_active_mask": action_active_mask().astype(int).tolist(),
        "padding_anomaly": {
            "state_pad_l2": float(
                np.linalg.norm(
                    np.asarray(state55)[~state_active_mask()]
                )
            ),
            "action_pad_l2": float(
                np.linalg.norm(
                    np.asarray(action55)[~action_active_mask()]
                )
            ),
        },
    }
    if "source_path" in row:
        record["source_path"] = str(row["source_path"])
    return record


def load_rows_from_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def load_rows_from_parquet(
    path: Path,
    *,
    max_frames: int | None = None,
    stride: int = 1,
    prefer_cmd_neq_measured: bool = False,
    cmd_tol: float = 1e-3,
) -> list[dict[str, Any]]:
    """Load upstream LeRobot parquet rows with absolute ``action[8]``.

    Does not reconstruct from midstream ``ee_delta_gripper[7]`` releases.
    """
    del cmd_tol  # ranking uses absolute |cmd-measured|; export uses gripper_cmd_vs_measured.
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover
        raise AbsoluteEefExportError(
            "pyarrow required to load parquet episodes"
        ) from exc

    if stride < 1:
        raise AbsoluteEefExportError(f"stride must be >= 1, got {stride}")

    table = pq.read_table(path)
    names = set(table.column_names)
    required = {"action", "observation.state"}
    missing = required - names
    if missing:
        raise AbsoluteEefExportError(f"parquet missing columns: {sorted(missing)}")

    n = table.num_rows
    indices = list(range(0, n, stride))
    if prefer_cmd_neq_measured:
        # Prefer close-phase rows where command lags/differs from measured.
        ranked: list[tuple[float, int]] = []
        actions = table.column("action").to_pylist()
        grips = (
            table.column("observation.gripper").to_pylist()
            if "observation.gripper" in names
            else None
        )
        states = table.column("observation.state").to_pylist()
        for i in indices:
            action = np.asarray(actions[i], dtype=np.float64).reshape(-1)
            if action.shape[0] != 8:
                continue
            if grips is not None:
                g = grips[i]
                measured = float(g[0] if isinstance(g, (list, tuple)) else g)
            else:
                st = np.asarray(states[i], dtype=np.float64).reshape(-1)
                if st.shape[0] < 8:
                    continue
                measured = float(st[7])
            ranked.append((abs(float(action[7]) - measured), i))
        ranked.sort(key=lambda item: item[0], reverse=True)
        indices = [i for _, i in ranked]

    if max_frames is not None:
        indices = indices[: max(0, int(max_frames))]

    rows: list[dict[str, Any]] = []
    for i in indices:
        row: dict[str, Any] = {"source_path": str(path)}
        for name in table.column_names:
            value = table.column(name)[i].as_py()
            row[name] = value
        rows.append(row)
    return rows


def export_frames(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [export_frame(row) for row in rows]


def write_frames_jsonl(path: Path, frames: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for frame in frames:
            handle.write(json.dumps(frame, ensure_ascii=False) + "\n")


def compute_active_norm_stats(
    vectors: Sequence[Sequence[float]],
    mask: np.ndarray,
) -> dict[str, list[float]]:
    """Mean/std on active dims only; pad dims get mean=0, std=1 sentinels."""
    if not vectors:
        raise AbsoluteEefExportError("cannot compute norm stats on empty set")
    data = np.asarray(vectors, dtype=np.float64)
    if data.ndim != 2 or data.shape[1] != CANONICAL_DIM:
        raise AbsoluteEefExportError(
            f"expected [N,{CANONICAL_DIM}], got {data.shape}"
        )
    mean = np.zeros(CANONICAL_DIM, dtype=np.float64)
    std = np.ones(CANONICAL_DIM, dtype=np.float64)
    active = np.asarray(mask, dtype=bool)
    mean[active] = data[:, active].mean(axis=0)
    std_active = data[:, active].std(axis=0)
    std_active = np.where(std_active < 1e-6, 1.0, std_active)
    std[active] = std_active
    return {"mean": mean.tolist(), "std": std.tolist()}


def apply_norm(
    vector: Sequence[float],
    mean: Sequence[float],
    std: Sequence[float],
    mask: np.ndarray,
) -> list[float]:
    x = np.asarray(vector, dtype=np.float64)
    m = np.asarray(mean, dtype=np.float64)
    s = np.asarray(std, dtype=np.float64)
    out = np.zeros_like(x)
    active = np.asarray(mask, dtype=bool)
    out[active] = (x[active] - m[active]) / s[active]
    # Padding stays zero after norm (ignored).
    return out.tolist()
