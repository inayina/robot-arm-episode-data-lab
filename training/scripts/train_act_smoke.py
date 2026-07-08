#!/usr/bin/env python3
"""[线性回归基准 Baseline] 用于接口冒烟测试的轻量 CPU-only 线性策略。

注意：本脚本名称含 "act" 仅为历史原因，实际使用的是岭回归线性策略，
并非真正的 ACT（Action Chunking Transformer）。

如需训练真实语言条件 ACT 模型，请使用（需要 lerobot conda 环境）：
    conda run -n lerobot python training/scripts/train_act_lerobot.py \\
        --dataset <数据集目录> \\
        --schema configs/robot_schemas/panda_multi_task.yaml \\
        --output /tmp/act_run \\
        --epochs 50

本脚本的用途：
    - CI 快速冒烟测试（无需 GPU / torch）
    - 验证数据集读取、schema 校验、checkpoint 格式等接口是否正确
    - 提供 val_loss 基准线供对比
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.policies.linear_policy import (
    checkpoint_metadata,
    fit_linear_policy,
    mean_absolute_error,
    mean_squared_error,
    predict,
    save_checkpoint,
)
from training.scripts.inspect_dataset import inspect_dataset, load_manifest, load_rows

DEFAULT_SCHEMA = REPO_ROOT / "configs" / "robot_schemas" / "panda.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True, help="Panda dataset release directory.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Panda schema YAML.")
    parser.add_argument("--output", type=Path, required=True, help="Training report directory.")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic split seed.")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Validation ratio.")
    parser.add_argument("--ridge", type=float, default=1e-6, help="Ridge regularization.")
    return parser.parse_args()


def load_schema(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def rows_to_arrays(rows: list[dict[str, Any]], *, state_key: str, action_key: str) -> tuple[np.ndarray, np.ndarray]:
    states = np.asarray([row[state_key] for row in rows], dtype=np.float64)
    actions = np.asarray([row[action_key] for row in rows], dtype=np.float64)
    if states.ndim != 2 or actions.ndim != 2:
        raise ValueError("state/action arrays must be 2D")
    return states, actions


def split_indices(frame_count: int, *, val_ratio: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    if not 0.0 <= val_ratio < 1.0:
        raise ValueError("val-ratio must be in [0.0, 1.0)")
    if frame_count < 2:
        raise ValueError("at least two frames are required")
    rng = np.random.default_rng(seed)
    indices = np.arange(frame_count)
    rng.shuffle(indices)
    val_count = int(round(frame_count * val_ratio))
    if val_ratio > 0.0:
        val_count = max(1, val_count)
    val_count = min(val_count, frame_count - 1)
    val_idx = np.sort(indices[:val_count])
    train_idx = np.sort(indices[val_count:])
    return train_idx, val_idx


def train_smoke_policy(
    dataset: Path,
    schema: dict[str, Any],
    output: Path,
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    seed: int,
    val_ratio: float,
    ridge: float,
) -> dict[str, Any]:
    report = inspect_dataset(dataset, schema)
    if not report.passed:
        raise ValueError("dataset inspection failed; refusing to train")
    manifest = load_manifest(dataset)
    contract = manifest.get("training_contract", {})
    state_key = str(contract.get("state_key", "observation.state"))
    action_key = str(contract.get("action_key", "action"))
    action_type = str(manifest.get("action_type", report.action_type))
    if action_type != schema["action"]["default_type"]:
        raise ValueError(
            f"smoke training requires action_type={schema['action']['default_type']!r}, "
            f"got {action_type!r}; adapt with --derive-ee-delta-action first"
        )

    rows = load_rows(dataset)
    states, actions = rows_to_arrays(rows, state_key=state_key, action_key=action_key)
    train_idx, val_idx = split_indices(len(rows), val_ratio=val_ratio, seed=seed)

    checkpoint = fit_linear_policy(states[train_idx], actions[train_idx], ridge=ridge)
    checkpoint.input_key = state_key
    checkpoint.action_key = action_key
    checkpoint.action_type = action_type
    checkpoint.schema_id = schema["schema_id"]

    train_pred = predict(checkpoint, states[train_idx])
    val_pred = predict(checkpoint, states[val_idx]) if len(val_idx) else np.empty((0, actions.shape[1]))
    metrics = {
        "policy_type": "linear_smoke",
        "schema_id": schema["schema_id"],
        "dataset": str(dataset),
        "release_id": manifest.get("release_id"),
        "action_type": action_type,
        "num_episodes": int(report.episodes),
        "num_frames": int(report.frames),
        "train_frames": int(len(train_idx)),
        "val_frames": int(len(val_idx)),
        "state_dim": int(states.shape[1]),
        "action_dim": int(actions.shape[1]),
        "train_loss": mean_squared_error(train_pred, actions[train_idx]),
        "train_mae": mean_absolute_error(train_pred, actions[train_idx]),
        "val_loss": mean_squared_error(val_pred, actions[val_idx]) if len(val_idx) else None,
        "val_mae": mean_absolute_error(val_pred, actions[val_idx]) if len(val_idx) else None,
    }

    output.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output / "checkpoint.npz"
    save_checkpoint(checkpoint_path, checkpoint)
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output / "normalization.json").write_text(
        json.dumps(normalization_payload(checkpoint), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output / "config_resolved.yaml").write_text(
        yaml.safe_dump(
            {
                "dataset": str(dataset),
                "schema": str(schema_path),
                "output": str(output),
                "seed": seed,
                "val_ratio": val_ratio,
                "ridge": ridge,
                "policy": checkpoint_metadata(checkpoint),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return metrics


def normalization_payload(checkpoint) -> dict[str, Any]:
    return {
        "state_mean": checkpoint.state_mean.astype(float).tolist(),
        "state_std": checkpoint.state_std.astype(float).tolist(),
        "action_mean": checkpoint.action_mean.astype(float).tolist(),
        "action_std": checkpoint.action_std.astype(float).tolist(),
    }


def main() -> int:
    args = parse_args()
    schema = load_schema(args.schema)
    try:
        metrics = train_smoke_policy(
            args.dataset,
            schema,
            args.output,
            schema_path=args.schema,
            seed=args.seed,
            val_ratio=args.val_ratio,
            ridge=args.ridge,
        )
    except Exception as exc:  # noqa: BLE001 - CLI should report training failures cleanly.
        print(f"Training output: {args.output}")
        print("Status: FAIL")
        print(f"Error: {exc}")
        return 1

    print(f"Training output: {args.output}")
    print(f"Frames: {metrics['num_frames']}")
    print(f"Train loss: {metrics['train_loss']:.6f}")
    if metrics["val_loss"] is not None:
        print(f"Val loss: {metrics['val_loss']:.6f}")
    print("Status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
