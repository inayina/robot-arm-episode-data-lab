"""Deterministic stage-anchor and close-window selection for open-loop diagnostics.

CPU-only helpers. Close detection matches open-loop evaluator:
Panda gripper 0=closed / 1=open, sustained debounce.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

STAGE_NAMES = (
    "hover_approach",
    "descend_mid",
    "pre_close",
    "close_transition",
    "early_lift",
    "late_lift",
)

GRIPPER_THRESHOLD = 0.5
DEFAULT_CLOSE_DEBOUNCE = 3


def first_close_frame(
    cmds: Sequence[float],
    thr: float = GRIPPER_THRESHOLD,
    *,
    debounce: int = DEFAULT_CLOSE_DEBOUNCE,
) -> int | None:
    if debounce < 1:
        raise ValueError("debounce must be >= 1")
    closed = [float(c) <= thr for c in cmds]
    for i in range(0, len(closed) - debounce + 1):
        if all(closed[i : i + debounce]):
            return i
    return None


def close_window_indices(
    n_frames: int,
    close_idx: int,
    *,
    before: int = 10,
    after: int = 10,
) -> list[int]:
    if n_frames <= 0:
        return []
    start = max(0, int(close_idx) - int(before))
    end = min(n_frames - 1, int(close_idx) + int(after))
    return list(range(start, end + 1))


def select_stage_anchors(
    *,
    ee_z: Sequence[float],
    gripper_cmds: Sequence[float],
    close_debounce: int = DEFAULT_CLOSE_DEBOUNCE,
    gripper_threshold: float = GRIPPER_THRESHOLD,
) -> dict[str, Any]:
    """Pick one frame index per stage for a single episode.

    Heuristics are deterministic functions of (ee_z, gripper_cmd) only.
    """
    z = np.asarray(ee_z, dtype=np.float64).reshape(-1)
    g = np.asarray(gripper_cmds, dtype=np.float64).reshape(-1)
    if z.shape[0] == 0 or z.shape[0] != g.shape[0]:
        raise ValueError("ee_z and gripper_cmds must be non-empty and same length")
    n = int(z.shape[0])
    close_idx = first_close_frame(g.tolist(), gripper_threshold, debounce=close_debounce)
    if close_idx is None:
        # Fall back to last open→closed crossing or mid episode.
        closed = g <= gripper_threshold
        if np.any(closed):
            close_idx = int(np.argmax(closed))
        else:
            close_idx = max(0, n // 2)

    z_min_idx = int(np.argmin(z[: close_idx + 1])) if close_idx > 0 else int(np.argmin(z))
    # Hover / approach: early open frame while still high above table.
    hover = min(15, max(0, close_idx // 8))
    while hover < close_idx and g[hover] <= gripper_threshold:
        hover += 1
    hover = min(hover, max(0, close_idx - 1))

    descend_mid = int((hover + z_min_idx) // 2)
    descend_mid = int(np.clip(descend_mid, 0, max(0, close_idx - 1)))

    pre_close = max(0, close_idx - 5)
    while pre_close > 0 and g[pre_close] <= gripper_threshold:
        pre_close -= 1

    early_lift = min(n - 1, close_idx + 15)
    z_close = float(z[close_idx])
    for i in range(close_idx + 1, min(n, close_idx + 80)):
        if float(z[i]) >= z_close + 0.02:
            early_lift = i
            break

    late_lift = min(n - 1, close_idx + 60)
    late_lift = max(late_lift, early_lift)

    anchors = {
        "hover_approach": int(hover),
        "descend_mid": int(descend_mid),
        "pre_close": int(pre_close),
        "close_transition": int(close_idx),
        "early_lift": int(early_lift),
        "late_lift": int(late_lift),
    }
    return {
        "close_idx": int(close_idx),
        "z_min_idx": int(z_min_idx),
        "anchors": anchors,
        "n_frames": n,
    }


def build_episode_plan(
    episode_meta: Mapping[str, Any],
    *,
    ee_z: Sequence[float],
    gripper_cmds: Sequence[float],
    close_debounce: int = DEFAULT_CLOSE_DEBOUNCE,
    gripper_threshold: float = GRIPPER_THRESHOLD,
    window_before: int = 10,
    window_after: int = 10,
) -> dict[str, Any]:
    selected = select_stage_anchors(
        ee_z=ee_z,
        gripper_cmds=gripper_cmds,
        close_debounce=close_debounce,
        gripper_threshold=gripper_threshold,
    )
    window = close_window_indices(
        selected["n_frames"],
        selected["close_idx"],
        before=window_before,
        after=window_after,
    )
    return {
        "ref": episode_meta.get("ref"),
        "slice": episode_meta.get("slice"),
        "parquet": episode_meta.get("parquet"),
        "video": episode_meta.get("video"),
        "close_idx": selected["close_idx"],
        "z_min_idx": selected["z_min_idx"],
        "n_frames": selected["n_frames"],
        "stage_anchors": selected["anchors"],
        "close_window_indices": window,
        "close_window_len": len(window),
    }
