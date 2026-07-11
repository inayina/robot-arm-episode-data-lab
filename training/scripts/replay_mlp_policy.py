#!/usr/bin/env python3
"""Export predicted Panda actions from PyTorch MLP policy as neutral replay JSONL."""

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
from training.scripts.replay_policy import build_replay_row

DEFAULT_SCHEMA = REPO_ROOT / "configs" / "robot_schemas" / "panda.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True, help="Panda dataset release directory.")
    parser.add_argument("--checkpoint-dir", type=Path, required=True, help="Directory containing mlp_policy.pth and scalers.npz.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Panda schema YAML.")
    parser.add_argument("--output", type=Path, required=True, help="Replay JSONL output path.")
    return parser.parse_args()


def load_schema(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()

    if not HAS_TORCH:
        print("PyTorch is required to run MLP policy replay.")
        return 1

    import torch

    schema = load_schema(args.schema)
    manifest = load_manifest(args.dataset)
    action_type = str(manifest.get("action_type", schema["action"]["default_type"]))

    report = inspect_dataset(args.dataset, schema)
    if not report.passed:
        print("Dataset inspection failed; refusing to replay.")
        return 1

    # Load scalers
    scalers_path = args.checkpoint_dir / "scalers.npz"
    if not scalers_path.exists():
        print(f"Scalers not found at {scalers_path}")
        return 1
    scalers = np.load(scalers_path)
    state_mean = scalers["state_mean"]
    state_std = scalers["state_std"]
    action_mean = scalers["action_mean"]
    action_std = scalers["action_std"]

    # Load model
    pth_path = args.checkpoint_dir / "mlp_policy.pth"
    if not pth_path.exists():
        print(f"Model checkpoint not found at {pth_path}")
        return 1

    rows = load_rows(args.dataset)
    contract = manifest.get("training_contract", {})
    state_key = str(contract.get("state_key", "observation.state"))
    states = np.asarray([row[state_key] for row in rows], dtype=np.float32)

    model = MLPPolicy(state_dim=states.shape[1], action_dim=action_mean.shape[0])
    model.load_state_dict(torch.load(pth_path, map_location="cpu"))
    model.eval()

    # Normalization
    norm_states = (states - state_mean) / state_std
    norm_states_t = torch.from_numpy(norm_states)

    with torch.no_grad():
        norm_actions_t = model(norm_states_t)
        norm_actions = norm_actions_t.numpy()

    # De-normalization
    predicted = norm_actions * action_std + action_mean

    expected_action_dim = int(schema["action"][action_type]["dim"])
    if predicted.ndim != 2 or predicted.shape[1] != expected_action_dim:
        print(f"Predicted action dim {predicted.shape[1]} != schema expected dim {expected_action_dim}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row, action in zip(rows, predicted, strict=True):
            handle.write(
                json.dumps(
                    build_replay_row(
                        row=row,
                        action=action,
                        schema=schema,
                        manifest=manifest,
                        action_type=action_type,
                    ),
                    sort_keys=True,
                )
                + "\n"
            )

    print(f"Replay output: {args.output}")
    print(f"Frames: {len(rows)}")
    print(f"Action type: {action_type}")
    print("Status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
