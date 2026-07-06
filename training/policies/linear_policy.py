"""Small NumPy linear policy used for CPU-only smoke training."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


EPS = 1e-6


@dataclass
class LinearPolicyCheckpoint:
    weights: np.ndarray
    bias: np.ndarray
    state_mean: np.ndarray
    state_std: np.ndarray
    action_mean: np.ndarray
    action_std: np.ndarray
    input_key: str
    action_key: str
    action_type: str
    schema_id: str


def fit_linear_policy(states: np.ndarray, actions: np.ndarray, *, ridge: float = 1e-6) -> LinearPolicyCheckpoint:
    if states.ndim != 2:
        raise ValueError(f"states must be 2D, got shape {states.shape}")
    if actions.ndim != 2:
        raise ValueError(f"actions must be 2D, got shape {actions.shape}")
    if states.shape[0] != actions.shape[0]:
        raise ValueError("states and actions must have the same frame count")
    if states.shape[0] < 2:
        raise ValueError("at least two frames are required for smoke training")

    state_mean = states.mean(axis=0)
    state_std = np.maximum(states.std(axis=0), EPS)
    action_mean = actions.mean(axis=0)
    action_std = np.maximum(actions.std(axis=0), EPS)

    norm_states = (states - state_mean) / state_std
    norm_actions = (actions - action_mean) / action_std
    design = np.concatenate([norm_states, np.ones((norm_states.shape[0], 1))], axis=1)
    regularizer = ridge * np.eye(design.shape[1], dtype=np.float64)
    regularizer[-1, -1] = 0.0
    solution = np.linalg.solve(design.T @ design + regularizer, design.T @ norm_actions)
    weights = solution[:-1, :]
    bias = solution[-1, :]
    return LinearPolicyCheckpoint(
        weights=weights,
        bias=bias,
        state_mean=state_mean,
        state_std=state_std,
        action_mean=action_mean,
        action_std=action_std,
        input_key="observation.state",
        action_key="action",
        action_type="",
        schema_id="",
    )


def predict(checkpoint: LinearPolicyCheckpoint, states: np.ndarray) -> np.ndarray:
    norm_states = (states - checkpoint.state_mean) / checkpoint.state_std
    norm_actions = norm_states @ checkpoint.weights + checkpoint.bias
    return norm_actions * checkpoint.action_std + checkpoint.action_mean


def mean_squared_error(predicted: np.ndarray, target: np.ndarray) -> float:
    return float(np.mean((predicted - target) ** 2))


def mean_absolute_error(predicted: np.ndarray, target: np.ndarray) -> float:
    return float(np.mean(np.abs(predicted - target)))


def save_checkpoint(path: Path, checkpoint: LinearPolicyCheckpoint) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        weights=checkpoint.weights.astype(np.float32),
        bias=checkpoint.bias.astype(np.float32),
        state_mean=checkpoint.state_mean.astype(np.float32),
        state_std=checkpoint.state_std.astype(np.float32),
        action_mean=checkpoint.action_mean.astype(np.float32),
        action_std=checkpoint.action_std.astype(np.float32),
        input_key=np.asarray(checkpoint.input_key),
        action_key=np.asarray(checkpoint.action_key),
        action_type=np.asarray(checkpoint.action_type),
        schema_id=np.asarray(checkpoint.schema_id),
    )


def load_checkpoint(path: Path) -> LinearPolicyCheckpoint:
    payload = np.load(path, allow_pickle=False)
    return LinearPolicyCheckpoint(
        weights=payload["weights"].astype(np.float64),
        bias=payload["bias"].astype(np.float64),
        state_mean=payload["state_mean"].astype(np.float64),
        state_std=payload["state_std"].astype(np.float64),
        action_mean=payload["action_mean"].astype(np.float64),
        action_std=payload["action_std"].astype(np.float64),
        input_key=str(payload["input_key"].item()),
        action_key=str(payload["action_key"].item()),
        action_type=str(payload["action_type"].item()),
        schema_id=str(payload["schema_id"].item()),
    )


def checkpoint_metadata(checkpoint: LinearPolicyCheckpoint) -> dict[str, Any]:
    return {
        "policy_type": "linear_smoke",
        "input_key": checkpoint.input_key,
        "action_key": checkpoint.action_key,
        "action_type": checkpoint.action_type,
        "schema_id": checkpoint.schema_id,
        "state_dim": int(checkpoint.state_mean.shape[0]),
        "action_dim": int(checkpoint.action_mean.shape[0]),
    }
