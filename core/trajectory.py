"""笛卡尔轨迹生成工具。"""

from __future__ import annotations

import numpy as np


def interpolate_cartesian_line(
    start_position: np.ndarray,
    end_position: np.ndarray,
    num_waypoints: int,
    start_orientation: np.ndarray | None = None,
    end_orientation: np.ndarray | None = None,
) -> list[tuple[np.ndarray, np.ndarray | None]]:
    """Linearly interpolate position between two Cartesian points.

    Phase 1 keeps orientation fixed at ``start_orientation`` when provided.
    """
    if num_waypoints < 2:
        raise ValueError("num_waypoints must be >= 2.")

    start = np.asarray(start_position, dtype=np.float64).reshape(3)
    end = np.asarray(end_position, dtype=np.float64).reshape(3)

    orientation: np.ndarray | None = None
    if start_orientation is not None:
        orientation = np.asarray(start_orientation, dtype=np.float32).reshape(4)
    if end_orientation is not None and start_orientation is None:
        orientation = np.asarray(end_orientation, dtype=np.float32).reshape(4)

    alphas = np.linspace(0.0, 1.0, num_waypoints, dtype=np.float64)
    waypoints: list[tuple[np.ndarray, np.ndarray | None]] = []
    for alpha in alphas:
        position = ((1.0 - alpha) * start + alpha * end).astype(np.float32)
        waypoints.append((position, orientation))
    return waypoints
