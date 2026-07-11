#!/usr/bin/env python3
"""Train a PyTorch MLP policy for state-based Behavioral Cloning (BC)."""

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

from training.policies.mlp_policy import MLPPolicy, HAS_TORCH
from training.device import cpu_state_dict, resolve_device
from training.scripts.inspect_dataset import inspect_dataset, load_manifest, load_rows

DEFAULT_SCHEMA = REPO_ROOT / "configs" / "robot_schemas" / "panda.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True, help="Panda dataset release directory.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Panda schema YAML.")
    parser.add_argument("--output", type=Path, required=True, help="Training report directory.")
    parser.add_argument("--epochs", type=int, default=50, help="Number of training epochs.")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size.")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate.")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic seed.")
    parser.add_argument("--test-ratio", type=float, default=0.2, help="Held-out final test ratio.")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not HAS_TORCH:
        print("=" * 60)
        print(" PyTorch is not installed in the current environment.")
        print(" To run advanced neural network policy training, please run:")
        print("   pip install torch")
        print("=" * 60)
        return 1

    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset

    # Set random seeds for reproducibility
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device, device_info = resolve_device(args.device)
    print(f"Device: {device_info['selected']} (requested={device_info['requested']})")
    if device_info["gpu_name"]:
        print(f"GPU: {device_info['gpu_name']} ({device_info['gpu_memory_bytes']} bytes)")

    schema = yaml.safe_load(args.schema.read_text(encoding="utf-8"))
    report = inspect_dataset(args.dataset, schema)
    if not report.passed:
        print("Dataset inspection failed; refusing to train.")
        return 1

    manifest = load_manifest(args.dataset)
    contract = manifest.get("training_contract", {})
    state_key = str(contract.get("state_key", "observation.state"))
    action_key = str(contract.get("action_key", "action"))

    rows = load_rows(args.dataset)
    states = np.asarray([row[state_key] for row in rows], dtype=np.float32)
    actions = np.asarray([row[action_key] for row in rows], dtype=np.float32)

    episode_ids = np.asarray([int(row["episode_index"]) for row in rows], dtype=np.int64)
    train_idx, test_idx, split_episodes = split_by_episode(
        episode_ids, test_ratio=args.test_ratio, seed=args.seed
    )

    # Compute normalization from train episodes only to avoid validation/test leakage.
    state_mean = states[train_idx].mean(axis=0)
    state_std = states[train_idx].std(axis=0)
    state_std[state_std < 1e-4] = 1.0

    action_mean = actions[train_idx].mean(axis=0)
    action_std = actions[train_idx].std(axis=0)
    action_std[action_std < 1e-4] = 1.0

    # Normalize inputs
    norm_states = (states - state_mean) / state_std
    norm_actions = (actions - action_mean) / action_std

    class BCDataset(Dataset):
        def __init__(self, s: np.ndarray, a: np.ndarray) -> None:
            self.s = torch.from_numpy(s)
            self.a = torch.from_numpy(a)

        def __len__(self) -> int:
            return len(self.s)

        def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
            return self.s[idx], self.a[idx]

    train_loader = DataLoader(BCDataset(norm_states[train_idx], norm_actions[train_idx]), batch_size=args.batch_size, shuffle=True)
    test_loader = DataLoader(BCDataset(norm_states[test_idx], norm_actions[test_idx]), batch_size=args.batch_size, shuffle=False) if len(test_idx) else None

    # Instantiate model
    model = MLPPolicy(state_dim=states.shape[1], action_dim=actions.shape[1])
    model.to(device)
    model.set_normalization(state_mean, state_std, action_mean, action_std)

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    criterion = nn.MSELoss()

    # Training loop
    print(f"Training MLP Behavioral Cloning Policy on {len(train_idx)} samples...")
    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss = 0.0
        for batch_s, batch_a in train_loader:
            batch_s = batch_s.to(device)
            batch_a = batch_a.to(device)
            optimizer.zero_grad()
            pred_a = model(batch_s)
            loss = criterion(pred_a, batch_a)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(batch_s)
        train_loss /= len(train_idx)

        if epoch % max(1, args.epochs // 5) == 0 or epoch == args.epochs:
            print(f"Epoch {epoch}/{args.epochs} | Train Loss: {train_loss:.6f}")

    test_loss = evaluate_loss(model, test_loader, criterion) if test_loader else None

    # Save artifacts
    args.output.mkdir(parents=True, exist_ok=True)
    torch.save(cpu_state_dict(model), args.output / "mlp_policy.pth")

    metrics = {
        "policy_type": "mlp_bc",
        "epochs": args.epochs,
        "lr": args.lr,
        "train_loss": float(train_loss),
        "test_loss": float(test_loss) if test_loss is not None else None,
        "num_episodes": int(len(np.unique(episode_ids))),
        "train_frames": int(len(train_idx)),
        "test_frames": int(len(test_idx)),
        "split_episodes": split_episodes,
        "device": device_info,
        "state_dim": int(states.shape[1]),
        "action_dim": int(actions.shape[1]),
    }
    (args.output / "mlp_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    np.savez(
        args.output / "scalers.npz",
        state_mean=state_mean, state_std=state_std,
        action_mean=action_mean, action_std=action_std,
    )
    (args.output / "split_manifest.json").write_text(
        json.dumps({"seed": args.seed, "test_ratio": args.test_ratio,
                    "episodes": split_episodes}, indent=2, sort_keys=True), encoding="utf-8")
    (args.output / "feature_contract.yaml").write_text(yaml.safe_dump({
        "observation_features": [{"name": "joint_positions", "shape": [7], "unit": "rad"},
                                 {"name": "gripper_opening", "shape": [1], "unit": "normalized_0_1"}],
        "excluded_features": ["observation.images.scene", "observation.images.wrist",
                              "observation.depth.scene", "observation.images.tactile_left",
                              "observation.images.tactile_right"],
        "action_type": manifest.get("action_type"),
        "action_features": [{"name": "ee_delta_xyz", "shape": [3], "unit": "m"},
                            {"name": "ee_delta_rpy", "shape": [3], "unit": "rad"},
                            {"name": "gripper_cmd", "shape": [1], "unit": "normalized_0_1"}],
    }, sort_keys=False), encoding="utf-8")
    print(f"Artifacts saved to {args.output}")
    print("Status: PASS")
    return 0


def split_by_episode(
    episode_ids: np.ndarray, *, test_ratio: float, seed: int
) -> tuple[np.ndarray, np.ndarray, dict[str, list[int]]]:
    if not 0.0 < test_ratio < 1.0:
        raise ValueError("test_ratio must be in (0, 1)")
    episodes = np.unique(episode_ids)
    if len(episodes) < 2:
        raise ValueError("at least 2 episodes are required for train/test splitting")
    rng = np.random.default_rng(seed)
    episodes = episodes.copy()
    rng.shuffle(episodes)
    test_count = max(1, int(round(len(episodes) * test_ratio))) if test_ratio else 0
    if test_count >= len(episodes):
        raise ValueError("not enough episodes for the requested train/test ratio")
    test_eps = episodes[:test_count]
    train_eps = episodes[test_count:]
    split = {
        "train": sorted(train_eps.astype(int).tolist()),
        "test": sorted(test_eps.astype(int).tolist()),
    }
    return (
        np.flatnonzero(np.isin(episode_ids, train_eps)),
        np.flatnonzero(np.isin(episode_ids, test_eps)),
        split,
    )


def evaluate_loss(model, loader, criterion) -> float:
    import torch
    model.eval()
    total = 0.0
    count = 0
    with torch.no_grad():
        for batch_s, batch_a in loader:
            device = next(model.parameters()).device
            batch_s = batch_s.to(device)
            batch_a = batch_a.to(device)
            total += float(criterion(model(batch_s), batch_a).item()) * len(batch_s)
            count += len(batch_s)
    return total / count


if __name__ == "__main__":
    raise SystemExit(main())
