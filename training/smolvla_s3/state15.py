#!/usr/bin/env python3
"""Compose / validate the frozen Recovery observation.state[15] contract.

state[15] = joint_position[7] + ee_pose_xyzw[7] + measured_gripper[1]

Does not write a v3 release, train, or call Isaac.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

STATE15_DIM = 15
STATE15_LAYOUT = (
    "joint_position[7]",
    "ee_pose_xyzw[7]",
    "measured_gripper[1]",
)
EXCLUDE_FROM_POLICY_STATE = (
    "observation.object_pose",
    "observation.ft",
)


def compose_state15(
    *,
    joint_position: Sequence[float] | np.ndarray,
    ee_pose_xyzw: Sequence[float] | np.ndarray,
    measured_gripper: float | Sequence[float] | np.ndarray,
) -> np.ndarray:
    joints = np.asarray(joint_position, dtype=np.float32).reshape(-1)
    ee = np.asarray(ee_pose_xyzw, dtype=np.float32).reshape(-1)
    grip = np.asarray(measured_gripper, dtype=np.float32).reshape(-1)
    if joints.shape[0] != 7:
        raise ValueError(f"joint_position must be [7], got {joints.shape}")
    if ee.shape[0] != 7:
        raise ValueError(f"ee_pose_xyzw must be [7], got {ee.shape}")
    if grip.shape[0] < 1:
        raise ValueError("measured_gripper missing")
    return np.concatenate([joints, ee, grip[:1]], axis=0).astype(np.float32)


def compose_state15_from_row(row: Mapping[str, Any]) -> np.ndarray:
    return compose_state15(
        joint_position=row["observation.state"],
        ee_pose_xyzw=row["observation.ee_pose"],
        measured_gripper=row["observation.gripper"],
    )


def pad_state15_to_max(state15: np.ndarray, max_state_dim: int = 32) -> np.ndarray:
    arr = np.asarray(state15, dtype=np.float32).reshape(-1)
    if arr.shape[0] != STATE15_DIM:
        raise ValueError(f"expected state[15], got {arr.shape}")
    if max_state_dim < STATE15_DIM:
        raise ValueError("max_state_dim < 15")
    out = np.zeros((max_state_dim,), dtype=np.float32)
    out[:STATE15_DIM] = arr
    return out


def state15_contract_dict() -> dict[str, Any]:
    return {
        "name": f"observation.state[{STATE15_DIM}]",
        "dim": STATE15_DIM,
        "layout": list(STATE15_LAYOUT),
        "exclude_from_policy_state": list(EXCLUDE_FROM_POLICY_STATE),
        "pads_to_max_state_dim": 32,
        "status": "adopted_for_v3_recovery",
    }


def observation_state_for_policy(row: Mapping[str, Any]) -> np.ndarray:
    """Return state[15] from a composed column or from joint+ee+gripper fields."""
    raw = np.asarray(row["observation.state"], dtype=np.float32).reshape(-1)
    if raw.shape[0] == STATE15_DIM:
        return raw
    if raw.shape[0] == 7:
        return compose_state15_from_row(row)
    raise ValueError(f"observation.state dim {raw.shape[0]} not in {{7, 15}}")


def rewrite_parquet_observation_state15(src: Path, dst: Path) -> dict[str, Any]:
    """Copy parquet and replace observation.state with composed state[15]."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pq.read_table(src)
    names = set(table.column_names)
    required = {"observation.state", "observation.ee_pose", "observation.gripper"}
    missing = sorted(required - names)
    if missing:
        raise ValueError(f"{src}: missing {missing}")

    composed: list[list[float]] = []
    for i in range(table.num_rows):
        row = {
            "observation.state": table.column("observation.state")[i].as_py(),
            "observation.ee_pose": table.column("observation.ee_pose")[i].as_py(),
            "observation.gripper": table.column("observation.gripper")[i].as_py(),
        }
        composed.append(compose_state15_from_row(row).tolist())

    arrays: dict[str, pa.Array] = {}
    for name in table.column_names:
        if name == "observation.state":
            arrays[name] = pa.array(composed, type=pa.list_(pa.float32(), STATE15_DIM))
        else:
            arrays[name] = table.column(name)
    dst.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(arrays), dst)
    return {
        "src": str(src),
        "dst": str(dst),
        "num_rows": table.num_rows,
        "state_dim": STATE15_DIM,
    }
