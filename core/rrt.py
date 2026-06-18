"""纯 Python 双向 RRT-Connect 关节空间规划。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from core.joint_limits import JointLimits


@dataclass
class RRTConfig:
    step_size: float = 0.15
    goal_bias: float = 0.15
    max_iterations: int = 2000
    goal_tolerance: float = 0.08


@dataclass
class RRTResult:
    success: bool
    path: list[np.ndarray] = field(default_factory=list)
    failure_reason: str | None = None


@dataclass
class _RRTNode:
    config: np.ndarray
    parent: int | None


def _distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def _nearest_index(nodes: list[_RRTNode], target: np.ndarray) -> int:
    best_index = 0
    best_distance = _distance(nodes[0].config, target)
    for index in range(1, len(nodes)):
        distance = _distance(nodes[index].config, target)
        if distance < best_distance:
            best_distance = distance
            best_index = index
    return best_index


def _steer(from_config: np.ndarray, to_config: np.ndarray, step_size: float) -> np.ndarray:
    delta = to_config - from_config
    distance = float(np.linalg.norm(delta))
    if distance <= step_size or distance < 1e-9:
        return to_config.copy()
    return (from_config + (delta / distance) * step_size).astype(np.float32)


def _edge_is_free(
    start: np.ndarray,
    end: np.ndarray,
    is_free: Callable[[np.ndarray], bool],
    step_size: float,
) -> bool:
    if not is_free(end):
        return False

    delta = end - start
    distance = float(np.linalg.norm(delta))
    if distance < 1e-9:
        return is_free(start)

    num_checks = max(2, int(np.ceil(distance / (step_size * 0.5))) + 1)
    for alpha in np.linspace(0.0, 1.0, num_checks):
        config = (start + alpha * delta).astype(np.float32)
        if not is_free(config):
            return False
    return True


def _extend_tree(
    nodes: list[_RRTNode],
    target: np.ndarray,
    is_free: Callable[[np.ndarray], bool],
    step_size: float,
) -> int | None:
    nearest_index = _nearest_index(nodes, target)
    nearest_config = nodes[nearest_index].config
    new_config = _steer(nearest_config, target, step_size)

    if _distance(nearest_config, new_config) < 1e-6:
        return None
    if not _edge_is_free(nearest_config, new_config, is_free, step_size):
        return None

    nodes.append(_RRTNode(config=new_config, parent=nearest_index))
    return len(nodes) - 1


def _connect_tree(
    nodes: list[_RRTNode],
    target: np.ndarray,
    is_free: Callable[[np.ndarray], bool],
    step_size: float,
    goal_tolerance: float,
) -> int | None:
    nearest_index = _nearest_index(nodes, target)
    if _distance(nodes[nearest_index].config, target) <= goal_tolerance:
        return nearest_index

    while True:
        new_index = _extend_tree(nodes, target, is_free, step_size)
        if new_index is None:
            return None
        if _distance(nodes[new_index].config, target) <= goal_tolerance:
            return new_index


def _extract_path(
    tree_a: list[_RRTNode],
    index_a: int,
    tree_b: list[_RRTNode],
    index_b: int,
) -> list[np.ndarray]:
    path_a: list[np.ndarray] = []
    cursor: int | None = index_a
    while cursor is not None:
        path_a.append(tree_a[cursor].config.copy())
        cursor = tree_a[cursor].parent
    path_a.reverse()

    path_b: list[np.ndarray] = []
    cursor = index_b
    while cursor is not None:
        path_b.append(tree_b[cursor].config.copy())
        cursor = tree_b[cursor].parent

    return path_a + path_b


def bidirectional_rrt_connect(
    start: np.ndarray,
    goal: np.ndarray,
    is_free: Callable[[np.ndarray], bool],
    joint_limits: JointLimits,
    config: RRTConfig | None = None,
    rng: np.random.Generator | None = None,
) -> RRTResult:
    """Plan a collision-free joint-space path with bidirectional RRT-Connect."""
    cfg = config or RRTConfig()
    random_generator = rng or np.random.default_rng()

    start_q = joint_limits.clamp(np.asarray(start, dtype=np.float32))
    goal_q = joint_limits.clamp(np.asarray(goal, dtype=np.float32))

    if not is_free(start_q):
        return RRTResult(success=False, failure_reason="start_in_collision")
    if not is_free(goal_q):
        return RRTResult(success=False, failure_reason="goal_in_collision")

    tree_start = [_RRTNode(config=start_q.copy(), parent=None)]
    tree_goal = [_RRTNode(config=goal_q.copy(), parent=None)]

    for _ in range(cfg.max_iterations):
        if random_generator.random() < cfg.goal_bias:
            sample = goal_q.copy()
        else:
            sample = joint_limits.sample_uniform(random_generator)

        if _extend_tree(tree_start, sample, is_free, cfg.step_size) is None:
            tree_start, tree_goal = tree_goal, tree_start
            continue

        new_index = len(tree_start) - 1
        new_config = tree_start[new_index].config
        connect_index = _connect_tree(
            tree_goal,
            new_config,
            is_free,
            cfg.step_size,
            cfg.goal_tolerance,
        )
        if connect_index is not None:
            path = _extract_path(tree_start, new_index, tree_goal, connect_index)
            return RRTResult(success=True, path=path)

        tree_start, tree_goal = tree_goal, tree_start

    return RRTResult(success=False, failure_reason="timeout")


def resample_joint_path(path: list[np.ndarray], num_steps: int) -> list[np.ndarray]:
    """Resample a joint-space path to a fixed number of control steps."""
    if num_steps <= 0:
        raise ValueError("num_steps must be positive.")
    if not path:
        raise ValueError("path must not be empty.")
    if len(path) == 1:
        return [path[0].copy() for _ in range(num_steps)]

    segments = [path[index + 1] - path[index] for index in range(len(path) - 1)]
    lengths = [float(np.linalg.norm(segment)) for segment in segments]
    total_length = sum(lengths)
    if total_length < 1e-9:
        return [path[0].copy() for _ in range(num_steps)]

    cumulative = np.linspace(0.0, total_length, num_steps, dtype=np.float64)
    edge_starts = np.cumsum([0.0, *lengths[:-1]])

    resampled: list[np.ndarray] = []
    for target_distance in cumulative:
        segment_index = int(np.searchsorted(edge_starts, target_distance, side="right") - 1)
        segment_index = min(segment_index, len(segments) - 1)
        segment_length = lengths[segment_index]
        local_alpha = 0.0 if segment_length < 1e-9 else (
            (target_distance - edge_starts[segment_index]) / segment_length
        )
        config = path[segment_index] + local_alpha * segments[segment_index]
        resampled.append(config.astype(np.float32))
    return resampled
