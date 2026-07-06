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
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Validation ratio.")
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

    # Compute normalization stats
    state_mean = states.mean(axis=0)
    state_std = states.std(axis=0)
    state_std[state_std < 1e-4] = 1.0

    action_mean = actions.mean(axis=0)
    action_std = actions.std(axis=0)
    action_std[action_std < 1e-4] = 1.0

    # Normalize inputs
    norm_states = (states - state_mean) / state_std
    norm_actions = (actions - action_mean) / action_std

    # Split dataset
    indices = np.arange(len(rows))
    np.random.shuffle(indices)
    val_count = int(round(len(rows) * args.val_ratio))
    val_idx = indices[:val_count]
    train_idx = indices[val_count:]

    class BCDataset(Dataset):
        def __init__(self, s: np.ndarray, a: np.ndarray) -> None:
            self.s = torch.from_numpy(s)
            self.a = torch.from_numpy(a)

        def __len__(self) -> int:
            return len(self.s)

        def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
            return self.s[idx], self.a[idx]

    train_loader = DataLoader(BCDataset(norm_states[train_idx], norm_actions[train_idx]), batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(BCDataset(norm_states[val_idx], norm_actions[val_idx]), batch_size=args.batch_size, shuffle=False) if val_count > 0 else None

    # Instantiate model
    model = MLPPolicy(state_dim=states.shape[1], action_dim=actions.shape[1])
    model.set_normalization(state_mean, state_std, action_mean, action_std)

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    criterion = nn.MSELoss()

    # Training loop
    print(f"Training MLP Behavioral Cloning Policy on {len(train_idx)} samples...")
    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss = 0.0
        for batch_s, batch_a in train_loader:
            optimizer.zero_grad()
            pred_a = model(batch_s)
            loss = criterion(pred_a, batch_a)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(batch_s)
        train_loss /= len(train_idx)

        # Validation
        val_loss = 0.0
        if val_loader:
            model.eval()
            with torch.no_grad():
                for batch_s, batch_a in val_loader:
                    pred_a = model(batch_s)
                    loss = criterion(pred_a, batch_a)
                    val_loss += loss.item() * len(batch_s)
            val_loss /= len(val_idx)

        if epoch % max(1, args.epochs // 5) == 0 or epoch == args.epochs:
            val_str = f" | Val Loss: {val_loss:.6f}" if val_loader else ""
            print(f"Epoch {epoch}/{args.epochs} | Train Loss: {train_loss:.6f}{val_str}")

    # Save artifacts
    args.output.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), args.output / "mlp_policy.pth")

    metrics = {
        "policy_type": "mlp_bc",
        "epochs": args.epochs,
        "lr": args.lr,
        "train_loss": float(train_loss),
        "val_loss": float(val_loss) if val_loader else None,
        "state_dim": int(states.shape[1]),
        "action_dim": int(actions.shape[1]),
    }
    (args.output / "mlp_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Artifacts saved to {args.output}")
    print("Status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
