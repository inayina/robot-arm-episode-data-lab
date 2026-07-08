#!/usr/bin/env python3
"""Train a language-conditioned ACT policy using the lerobot conda environment.

必须在 lerobot conda 环境中运行：
    conda run -n lerobot python training/scripts/train_act_lerobot.py \\
        --dataset <panda_multi_task 数据集目录> \\
        --schema configs/robot_schemas/panda_multi_task.yaml \\
        --output /tmp/act_run \\
        --epochs 50 \\
        --chunk-size 50

数据流：
    frames.jsonl
      ↓ load_rows()
    list[dict]
      ↓ language_instruction → TextEncoder(clip) → float32[512]
      ↓ 拼接到 observation.state → state[8+512=520]
    PandaMultiTaskDataset (torch.utils.data.Dataset)
      ↓ DataLoader
    ACTPolicy.forward() / compute_loss()
      ↓ checkpoint
    output/checkpoint.pt  +  metrics.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.encoders.text_encoder import build_encoder
from training.scripts.inspect_dataset import load_manifest, load_rows

DEFAULT_SCHEMA = REPO_ROOT / "configs" / "robot_schemas" / "panda_multi_task.yaml"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--chunk-size", type=int, default=50,
                   help="ACT action chunk size (num_steps per prediction)")
    p.add_argument("--n-obs-steps", type=int, default=1)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--text-encoder", choices=["clip", "mean_hash"], default="clip")
    p.add_argument("--device", default="cpu")
    return p.parse_args()


def load_schema(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ─────────────────────────────── Dataset ──────────────────────────────────────

class PandaMultiTaskDataset:
    """将 JSONL 数据集转为 ACT 训练张量。

    LeRobot ACT 0.5.x 要求 Transformer 主输入包含 image 或
    ``observation.environment_state``。这里保留原始 ``observation.state`` 作为
    robot state，并把 ``state + language_embedding`` 作为 environment state。
    """

    def __init__(
        self,
        rows: list[dict[str, Any]],
        text_encoder,
        *,
        chunk_size: int = 50,
        n_obs_steps: int = 1,
        device: str = "cpu",
    ) -> None:
        try:
            import torch  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(
                "train_act_lerobot.py requires torch. "
                "Please activate the lerobot conda environment."
            ) from exc

        self._torch = torch
        self._device = device
        self._chunk_size = chunk_size
        self._n_obs_steps = n_obs_steps
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if n_obs_steps != 1:
            raise ValueError("LeRobot ACT 0.5.x currently requires n_obs_steps=1")

        # 对每条唯一指令预先编码，避免重复调用编码器
        _instr_cache: dict[str, np.ndarray] = {}

        robot_states, env_states, actions, episode_ids = [], [], [], []
        for row in rows:
            state = np.asarray(row["observation.state"], dtype=np.float32)
            action = np.asarray(row["action"], dtype=np.float32)
            instr = str(row.get("language_instruction", row.get("task", "")))
            if instr not in _instr_cache:
                _instr_cache[instr] = text_encoder.encode(instr)
            lang_vec = _instr_cache[instr]
            robot_states.append(state)
            env_states.append(np.concatenate([state, lang_vec], axis=0))
            actions.append(action)
            episode_ids.append(int(row["episode_index"]))

        self._robot_states = torch.tensor(np.stack(robot_states), dtype=torch.float32)
        self._env_states = torch.tensor(np.stack(env_states), dtype=torch.float32)
        self._actions = torch.tensor(np.stack(actions), dtype=torch.float32)
        self._episode_ids = episode_ids
        self._episode_start, self._episode_end = self._episode_bounds(episode_ids)
        print(
            f"[Dataset] frames={len(rows)}, "
            f"robot_state_dim={self._robot_states.shape[1]}, "
            f"env_state_dim={self._env_states.shape[1]} (state+lang_embed), "
            f"action_dim={self._actions.shape[1]}, "
            f"chunk_size={chunk_size}, n_obs_steps={n_obs_steps}"
        )

    def __len__(self) -> int:
        return len(self._robot_states)

    def __getitem__(self, idx: int):
        episode_end = self._episode_end[idx]

        end = min(idx + self._chunk_size, episode_end)
        chunk = self._actions[idx:end]
        action_is_pad = self._torch.zeros(self._chunk_size, dtype=self._torch.bool)
        if len(chunk) < self._chunk_size:
            action_is_pad[len(chunk):] = True
            pad = chunk[-1:].expand(self._chunk_size - len(chunk), -1)
            chunk = self._torch.cat([chunk, pad], dim=0)
        return self._robot_states[idx], self._env_states[idx], chunk, action_is_pad

    @staticmethod
    def _episode_bounds(episode_ids: list[int]) -> tuple[list[int], list[int]]:
        starts = [0] * len(episode_ids)
        ends = [0] * len(episode_ids)
        cursor = 0
        while cursor < len(episode_ids):
            episode_id = episode_ids[cursor]
            end = cursor + 1
            while end < len(episode_ids) and episode_ids[end] == episode_id:
                end += 1
            for index in range(cursor, end):
                starts[index] = cursor
                ends[index] = end
            cursor = end
        return starts, ends


# ─────────────────────────────── Training ─────────────────────────────────────

def build_act_policy(
    robot_state_dim: int,
    env_state_dim: int,
    action_dim: int,
    chunk_size: int,
    n_obs_steps: int,
    device: str,
):
    """构建 lerobot ACTPolicy 实例。"""
    try:
        from lerobot.policies.act.configuration_act import ACTConfig  # noqa: PLC0415
        from lerobot.policies.act.modeling_act import ACTPolicy       # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "lerobot is not installed. Activate: conda activate lerobot"
        ) from exc

    from lerobot.configs import FeatureType, PolicyFeature  # noqa: PLC0415

    config = ACTConfig(
        input_features={
            "observation.state": PolicyFeature(type=FeatureType.STATE, shape=(robot_state_dim,)),
            "observation.environment_state": PolicyFeature(
                type=FeatureType.ENV,
                shape=(env_state_dim,),
            ),
        },
        output_features={
            "action": PolicyFeature(type=FeatureType.ACTION, shape=(action_dim,)),
        },
        device=device,
        chunk_size=chunk_size,
        n_action_steps=chunk_size,
        n_obs_steps=n_obs_steps,
    )
    policy = ACTPolicy(config)
    policy.to(device)
    return policy


def train(
    dataset: Path,
    schema_path: Path,
    output: Path,
    *,
    epochs: int,
    chunk_size: int,
    n_obs_steps: int,
    batch_size: int,
    lr: float,
    seed: int,
    text_encoder_backend: str,
    device: str,
) -> dict[str, Any]:
    try:
        import torch  # noqa: PLC0415
        from torch.utils.data import DataLoader  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError("Activate the lerobot conda environment.") from exc

    torch.manual_seed(seed)
    np.random.seed(seed)

    schema = load_schema(schema_path)
    rows = load_rows(dataset)
    manifest = load_manifest(dataset)
    if not rows:
        raise ValueError("Dataset contains no frames.")

    print(f"[Train] Loaded {len(rows)} frames from {dataset}")
    encoder_kwargs = {"device": device} if text_encoder_backend == "clip" else {}
    text_enc = build_encoder(text_encoder_backend, **encoder_kwargs)
    print(f"[Train] Text encoder: {text_encoder_backend} (dim={text_enc.output_dim})")

    ds = PandaMultiTaskDataset(
        rows,
        text_enc,
        chunk_size=chunk_size,
        n_obs_steps=n_obs_steps,
        device=device,
    )
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=False)

    robot_state_dim = ds._robot_states.shape[1]
    env_state_dim = ds._env_states.shape[1]
    action_dim = ds._actions.shape[1]
    policy = build_act_policy(
        robot_state_dim,
        env_state_dim,
        action_dim,
        chunk_size,
        n_obs_steps,
        device,
    )
    optimizer = torch.optim.AdamW(policy.parameters(), lr=lr)

    output.mkdir(parents=True, exist_ok=True)
    history = []
    t0 = time.time()

    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0
        batches = 0
        policy.train()
        for robot_states_b, env_states_b, actions_b, action_is_pad_b in loader:
            robot_states_b = robot_states_b.to(device)
            env_states_b = env_states_b.to(device)
            actions_b = actions_b.to(device)
            action_is_pad_b = action_is_pad_b.to(device)
            optimizer.zero_grad()
            # ACT forward: 构建 batch dict
            batch = {
                "observation.state": robot_states_b,
                "observation.environment_state": env_states_b,
                "action": actions_b,
                "action_is_pad": action_is_pad_b,
            }
            forward_output = policy.forward(batch)
            if isinstance(forward_output, tuple):
                loss, _loss_dict = forward_output
            elif isinstance(forward_output, dict):
                loss = forward_output["loss"]
            else:
                loss = forward_output
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0)
            optimizer.step()
            epoch_loss += float(loss.item())
            batches += 1

        avg_loss = epoch_loss / max(batches, 1)
        history.append({"epoch": epoch, "loss": avg_loss})
        if epoch % max(1, epochs // 10) == 0 or epoch == epochs:
            elapsed = time.time() - t0
            print(f"  Epoch {epoch:4d}/{epochs}  loss={avg_loss:.6f}  ({elapsed:.1f}s)")

    # 保存 checkpoint
    checkpoint_path = output / "checkpoint.pt"
    torch.save(policy.state_dict(), checkpoint_path)
    print(f"[Train] Saved checkpoint → {checkpoint_path}")

    metrics = {
        "policy_type": "act_lerobot",
        "schema_id": schema.get("schema_id"),
        "dataset": str(dataset),
        "release_id": manifest.get("release_id"),
        "has_language_instruction": manifest.get("has_language_instruction", False),
        "text_encoder_backend": text_encoder_backend,
        "text_encoder_dim": text_enc.output_dim,
        "num_frames": len(rows),
        "robot_state_dim": robot_state_dim,
        "env_state_dim": env_state_dim,
        "action_dim": action_dim,
        "chunk_size": chunk_size,
        "n_obs_steps": n_obs_steps,
        "epochs": epochs,
        "batch_size": batch_size,
        "lr": lr,
        "final_loss": history[-1]["loss"] if history else None,
        "training_history": history,
    }
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8"
    )
    return metrics


def main() -> int:
    args = parse_args()
    try:
        metrics = train(
            args.dataset,
            args.schema,
            args.output,
            epochs=args.epochs,
            chunk_size=args.chunk_size,
            n_obs_steps=args.n_obs_steps,
            batch_size=args.batch_size,
            lr=args.lr,
            seed=args.seed,
            text_encoder_backend=args.text_encoder,
            device=args.device,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Training output: {args.output}")
        print("Status: FAIL")
        print(f"Error: {exc}")
        return 1

    print(f"\nTraining output: {args.output}")
    print(f"Frames: {metrics['num_frames']}")
    print(f"Robot state dim: {metrics['robot_state_dim']}")
    print(f"Env state dim (with lang embed): {metrics['env_state_dim']}")
    print(f"Final loss: {metrics['final_loss']:.6f}")
    print("Status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
