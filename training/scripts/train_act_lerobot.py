#!/usr/bin/env python3
"""Train a scene-only ACT policy with LeRobot 0.5.x.

The v1 policy consumes Panda state[8] and one fixed third-person RGB frame.
Language remains release metadata and is deliberately not model input.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.device import cpu_state_dict, resolve_device
from training.io.scene_cache import SCENE_KEY, SceneFrameCache
from training.scripts.inspect_dataset import load_manifest, load_rows

DEFAULT_SCHEMA = REPO_ROOT / "configs" / "robot_schemas" / "panda.yaml"
IMAGE_SIZE = 224
IMAGE_MEAN = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
IMAGE_STD = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)
STAGE_NAMES = (
    "other",
    "grasp_context",
    "closing",
    "closed_transport",
    "release",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--chunk-size", type=int, default=50)
    parser.add_argument("--n-obs-steps", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--cache-root", type=Path, default=None)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument(
        "--stage-balanced-sampling",
        action="store_true",
        help=(
            "Weight grasp context, gripper closing, and closed-carry anchors. "
            "Validation remains uniformly sampled."
        ),
    )
    parser.add_argument("--grasp-context-frames", type=int, default=10)
    parser.add_argument("--grasp-context-weight", type=float, default=4.0)
    parser.add_argument("--closing-weight", type=float, default=2.0)
    parser.add_argument("--transport-weight", type=float, default=1.5)
    parser.add_argument("--stage-closed-threshold", type=float, default=0.12)
    parser.add_argument("--stage-open-threshold", type=float, default=0.95)
    return parser.parse_args()


def load_schema(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _episode_counts(rows: list[dict[str, Any]]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for row in rows:
        episode = int(row["episode_index"])
        counts[episode] = counts.get(episode, 0) + 1
    return counts


def split_episode_ids(
    rows: list[dict[str, Any]],
    *,
    validation_fraction: float,
    seed: int,
) -> tuple[set[int], set[int]]:
    episode_ids = sorted({int(row["episode_index"]) for row in rows})
    if len(episode_ids) < 2:
        raise ValueError("scene ACT requires at least two episodes for episode-level validation")
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction must be in (0, 1)")
    shuffled = np.random.default_rng(seed).permutation(episode_ids).tolist()
    val_count = max(1, min(len(episode_ids) - 1, round(
        len(episode_ids) * validation_fraction)))
    val_ids = set(int(value) for value in shuffled[:val_count])
    train_ids = set(episode_ids) - val_ids
    return train_ids, val_ids


def normalization_from_rows(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    states = np.asarray([row["observation.state"] for row in rows], dtype=np.float32)
    actions = np.asarray([row["action"] for row in rows], dtype=np.float32)
    state_std = np.maximum(states.std(axis=0), 1e-6)
    action_std = np.maximum(actions.std(axis=0), 1e-6)
    return {
        "state_mean": states.mean(axis=0).tolist(),
        "state_std": state_std.tolist(),
        "action_mean": actions.mean(axis=0).tolist(),
        "action_std": action_std.tolist(),
    }


def infer_stage_labels(
    rows: list[dict[str, Any]],
    *,
    closed_threshold: float = 0.12,
    open_threshold: float = 0.95,
    transition_delta: float = 0.01,
    grasp_context_frames: int = 10,
) -> list[str]:
    """Infer temporal task stages from the verified gripper command sequence.

    This is a training sampler heuristic, not a physical lift/place evaluator. It
    deliberately does not inspect ``observation.object_pose``. ``closed_transport``
    means the interval after close and before release, which covers grasp hold,
    lift, transport, and pre-release motion in the upstream ordered FSM.
    """
    if not 0.0 <= closed_threshold < open_threshold <= 1.0:
        raise ValueError("stage thresholds must satisfy 0 <= closed < open <= 1")
    if transition_delta <= 0.0:
        raise ValueError("transition_delta must be positive")
    if grasp_context_frames < 0:
        raise ValueError("grasp_context_frames must be non-negative")
    labels = ["other"] * len(rows)
    cursor = 0
    while cursor < len(rows):
        episode = int(rows[cursor]["episode_index"])
        end = cursor + 1
        while end < len(rows) and int(rows[end]["episode_index"]) == episode:
            end += 1
        gripper = [float(row["action"][-1]) for row in rows[cursor:end]]
        close_start = next((
            index for index in range(1, len(gripper))
            if gripper[index - 1] - gripper[index] >= transition_delta
            and gripper[index] < open_threshold
        ), None)
        if close_start is None:
            cursor = end
            continue
        close_end = next((
            index for index in range(close_start, len(gripper))
            if gripper[index] <= closed_threshold
        ), None)
        if close_end is None:
            cursor = end
            continue
        release_start = next((
            index for index in range(close_end + 1, len(gripper))
            if gripper[index] - gripper[index - 1] >= transition_delta
        ), len(gripper))
        release_end = next((
            index for index in range(release_start, len(gripper))
            if gripper[index] >= open_threshold
        ), len(gripper) - 1)

        context_start = max(0, close_start - grasp_context_frames)
        for local_index in range(context_start, close_start):
            labels[cursor + local_index] = "grasp_context"
        for local_index in range(close_start, close_end + 1):
            labels[cursor + local_index] = "closing"
        for local_index in range(close_end + 1, release_start):
            labels[cursor + local_index] = "closed_transport"
        for local_index in range(release_start, release_end + 1):
            labels[cursor + local_index] = "release"
        cursor = end
    return labels


def stage_sampling_profile(
    rows: list[dict[str, Any]],
    *,
    grasp_context_frames: int,
    grasp_context_weight: float,
    closing_weight: float,
    transport_weight: float,
    closed_threshold: float,
    open_threshold: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Build per-anchor weights and a serializable audit profile."""
    requested_weights = {
        "other": 1.0,
        "grasp_context": float(grasp_context_weight),
        "closing": float(closing_weight),
        "closed_transport": float(transport_weight),
        "release": 1.0,
    }
    if any(not np.isfinite(value) or value <= 0.0
           for value in requested_weights.values()):
        raise ValueError("all stage sampling weights must be finite and positive")
    labels = infer_stage_labels(
        rows,
        closed_threshold=closed_threshold,
        open_threshold=open_threshold,
        grasp_context_frames=grasp_context_frames,
    )
    counts = {stage: labels.count(stage) for stage in STAGE_NAMES}
    if counts["closing"] == 0 or counts["closed_transport"] == 0:
        raise ValueError(
            "stage-balanced sampling found no complete close/carry sequence"
        )
    weights = np.asarray(
        [requested_weights[label] for label in labels], dtype=np.float64)
    total_frames = len(labels)
    weighted_total = float(weights.sum())
    profile = {
        "strategy": "weighted_random_anchor_with_replacement",
        "phase_source": "per_episode_verified_action_gripper_sequence",
        "physical_success_rederived": False,
        "grasp_context_frames": grasp_context_frames,
        "closed_threshold": closed_threshold,
        "open_threshold": open_threshold,
        "weights": requested_weights,
        "observed_frames": counts,
        "observed_fraction": {
            stage: counts[stage] / total_frames for stage in STAGE_NAMES
        },
        "expected_sample_fraction": {
            stage: counts[stage] * requested_weights[stage] / weighted_total
            for stage in STAGE_NAMES
        },
        "samples_per_epoch": total_frames,
        "validation_sampling": "uniform_sequential_unweighted",
    }
    return weights, profile


def _load_scene_tensor(path: Path, torch):
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for scene ACT image loading") from exc
    with Image.open(path) as image:
        image = image.convert("RGB")
        width, height = image.size
        scale = max(IMAGE_SIZE / width, IMAGE_SIZE / height)
        resized = image.resize(
            (round(width * scale), round(height * scale)),
            resample=Image.Resampling.BILINEAR,
        )
        left = (resized.width - IMAGE_SIZE) // 2
        top = (resized.height - IMAGE_SIZE) // 2
        cropped = resized.crop((left, top, left + IMAGE_SIZE, top + IMAGE_SIZE))
        array = np.asarray(cropped, dtype=np.float32) / 255.0
    array = (array - IMAGE_MEAN) / IMAGE_STD
    return torch.from_numpy(np.transpose(array, (2, 0, 1)).copy())


class SceneACTDataset:
    def __init__(
        self,
        rows: list[dict[str, Any]],
        cache: SceneFrameCache,
        normalization: dict[str, list[float]],
        *,
        chunk_size: int,
    ) -> None:
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("Activate the lerobot conda environment") from exc
        if not rows:
            raise ValueError("dataset split contains no frames")
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self._torch = torch
        self.rows = sorted(
            rows, key=lambda row: (int(row["episode_index"]), int(row["frame_index"])))
        self.cache = cache
        self.chunk_size = chunk_size
        self.state_mean = torch.tensor(
            normalization["state_mean"], dtype=torch.float32)
        self.state_std = torch.tensor(
            normalization["state_std"], dtype=torch.float32)
        self.action_mean = torch.tensor(
            normalization["action_mean"], dtype=torch.float32)
        self.action_std = torch.tensor(
            normalization["action_std"], dtype=torch.float32)
        self.states = torch.tensor(
            np.asarray([row["observation.state"] for row in self.rows], dtype=np.float32))
        self.actions = torch.tensor(
            np.asarray([row["action"] for row in self.rows], dtype=np.float32))
        self.episode_ids = [int(row["episode_index"]) for row in self.rows]
        self.episode_ends = self._episode_ends(self.episode_ids)

    @staticmethod
    def _episode_ends(episode_ids: list[int]) -> list[int]:
        ends = [0] * len(episode_ids)
        cursor = 0
        while cursor < len(episode_ids):
            end = cursor + 1
            while end < len(episode_ids) and episode_ids[end] == episode_ids[cursor]:
                end += 1
            for index in range(cursor, end):
                ends[index] = end
            cursor = end
        return ends

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        image = _load_scene_tensor(
            self.cache.frame_path(
                int(row["episode_index"]), int(row["frame_index"])),
            self._torch,
        )
        state = (self.states[index] - self.state_mean) / self.state_std
        end = min(index + self.chunk_size, self.episode_ends[index])
        chunk = (self.actions[index:end] - self.action_mean) / self.action_std
        action_is_pad = self._torch.zeros(
            self.chunk_size, dtype=self._torch.bool)
        if len(chunk) < self.chunk_size:
            action_is_pad[len(chunk):] = True
            chunk = self._torch.cat([
                chunk,
                chunk[-1:].expand(self.chunk_size - len(chunk), -1),
            ])
        return {
            "observation.state": state,
            SCENE_KEY: image,
            "action": chunk,
            "action_is_pad": action_is_pad,
        }


def build_act_policy(
    state_dim: int,
    action_dim: int,
    chunk_size: int,
    n_obs_steps: int,
    device: str,
):
    try:
        from lerobot.configs import FeatureType, PolicyFeature
        from lerobot.policies.act.configuration_act import ACTConfig
        from lerobot.policies.act.modeling_act import ACTPolicy
    except ImportError as exc:
        raise RuntimeError(
            "LeRobot 0.5.x is required; activate the lerobot conda environment"
        ) from exc
    config = ACTConfig(
        input_features={
            "observation.state": PolicyFeature(
                type=FeatureType.STATE, shape=(state_dim,)),
            SCENE_KEY: PolicyFeature(
                type=FeatureType.VISUAL, shape=(3, IMAGE_SIZE, IMAGE_SIZE)),
        },
        output_features={
            "action": PolicyFeature(type=FeatureType.ACTION, shape=(action_dim,)),
        },
        device=device,
        chunk_size=chunk_size,
        n_action_steps=chunk_size,
        n_obs_steps=n_obs_steps,
        vision_backbone="resnet18",
        pretrained_backbone_weights=None,
    )
    policy = ACTPolicy(config)
    policy.to(device)
    return policy


def _validate_release_contract(
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    if manifest.get("action_type") != "ee_delta_gripper":
        raise ValueError("scene ACT requires action_type=ee_delta_gripper")
    if manifest.get("source_action_semantics") != "ee_pose_gripper_cmd_v1":
        raise ValueError("source action semantics are not verified gripper commands")
    if not bool(manifest.get("action_semantics_verified")):
        raise ValueError("action_semantics_verified must be true")
    if manifest.get("visual_keys") != [SCENE_KEY]:
        raise ValueError(f"visual_keys must be [{SCENE_KEY!r}]")
    if not bool(manifest.get("visual_required_for_training")):
        raise ValueError("scene visual stream must be required for training")
    if any(len(row["observation.state"]) != 8 for row in rows):
        raise ValueError("observation.state must have dimension 8")
    if any(len(row["action"]) != 7 for row in rows):
        raise ValueError("action must have dimension 7")


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def evaluate(policy, loader, dataset: SceneACTDataset, device: str) -> dict[str, Any]:
    import torch
    from lerobot.utils.constants import OBS_IMAGES

    predicted: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    losses: list[float] = []
    policy.eval()
    with torch.no_grad():
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            model_batch = dict(batch)
            model_batch[OBS_IMAGES] = [batch[SCENE_KEY]]
            actions_hat, _ = policy.model(model_batch)
            valid = ~batch["action_is_pad"]
            valid_values = valid.unsqueeze(-1).expand_as(actions_hat)
            normalized_l1 = (
                torch.abs(actions_hat - batch["action"])[valid_values].mean()
            )
            losses.append(float(normalized_l1))
            pred_raw = (
                actions_hat * dataset.action_std.to(device)
                + dataset.action_mean.to(device)
            )
            target_raw = (
                batch["action"] * dataset.action_std.to(device)
                + dataset.action_mean.to(device)
            )
            predicted.append(pred_raw[valid].cpu().numpy())
            targets.append(target_raw[valid].cpu().numpy())
    pred = np.concatenate(predicted)
    target = np.concatenate(targets)
    rmse = np.sqrt(np.mean(np.square(pred - target), axis=0))
    gripper_accuracy = float(np.mean((pred[:, -1] <= 0.5) == (target[:, -1] <= 0.5)))
    smoothness = (
        float(np.mean(np.linalg.norm(np.diff(pred, axis=0), axis=1)))
        if len(pred) > 1 else 0.0
    )
    return {
        "validation_l1_loss_normalized": float(np.mean(losses)),
        "validation_l1_loss": float(np.mean(np.abs(pred - target))),
        "action_rmse": rmse.tolist(),
        "gripper_open_close_accuracy": gripper_accuracy,
        "predicted_action_smoothness": smoothness,
        "task_success_equivalent": False,
    }


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
    validation_fraction: float,
    cache_root: Path | None,
    device: str,
    stage_balanced_sampling: bool = False,
    grasp_context_frames: int = 10,
    grasp_context_weight: float = 4.0,
    closing_weight: float = 2.0,
    transport_weight: float = 1.5,
    stage_closed_threshold: float = 0.12,
    stage_open_threshold: float = 0.95,
) -> dict[str, Any]:
    try:
        import torch
        from torch.utils.data import DataLoader, WeightedRandomSampler
    except ImportError as exc:
        raise RuntimeError("Activate the lerobot conda environment") from exc
    if n_obs_steps != 1:
        raise ValueError("LeRobot ACT 0.5.x requires n_obs_steps=1")
    schema = load_schema(schema_path)
    rows = load_rows(dataset)
    manifest = load_manifest(dataset)
    if not rows:
        raise ValueError("dataset contains no frames")
    _validate_release_contract(manifest, rows)
    train_ids, val_ids = split_episode_ids(
        rows, validation_fraction=validation_fraction, seed=seed)
    train_rows = [row for row in rows if int(row["episode_index"]) in train_ids]
    val_rows = [row for row in rows if int(row["episode_index"]) in val_ids]
    normalization = normalization_from_rows(train_rows)

    cache = SceneFrameCache(dataset, manifest, cache_root=cache_root)
    cache.prepare(_episode_counts(rows))
    train_dataset = SceneACTDataset(
        train_rows, cache, normalization, chunk_size=chunk_size)
    val_dataset = SceneACTDataset(
        val_rows, cache, normalization, chunk_size=chunk_size)

    resolved_device, device_info = resolve_device(device)
    device = str(resolved_device)
    torch.manual_seed(seed)
    np.random.seed(seed)
    sampling_profile: dict[str, Any] = {
        "strategy": "uniform_shuffle",
        "samples_per_epoch": len(train_dataset),
        "validation_sampling": "uniform_sequential_unweighted",
    }
    train_sampler = None
    if stage_balanced_sampling:
        sample_weights, sampling_profile = stage_sampling_profile(
            train_dataset.rows,
            grasp_context_frames=grasp_context_frames,
            grasp_context_weight=grasp_context_weight,
            closing_weight=closing_weight,
            transport_weight=transport_weight,
            closed_threshold=stage_closed_threshold,
            open_threshold=stage_open_threshold,
        )
        generator = torch.Generator()
        generator.manual_seed(seed)
        train_sampler = WeightedRandomSampler(
            torch.as_tensor(sample_weights, dtype=torch.double),
            num_samples=len(train_dataset),
            replacement=True,
            generator=generator,
        )
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=train_sampler is None,
        sampler=train_sampler,
        drop_last=False,
    )
    val_loader = DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False, drop_last=False)
    policy = build_act_policy(8, 7, chunk_size, n_obs_steps, device)
    optimizer = torch.optim.AdamW(policy.parameters(), lr=lr)
    history: list[dict[str, float]] = []
    started = time.time()
    for epoch in range(1, epochs + 1):
        policy.train()
        total = 0.0
        count = 0
        for batch in train_loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad()
            loss, _ = policy.forward(batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0)
            optimizer.step()
            total += float(loss.item())
            count += 1
        history.append({"epoch": epoch, "loss": total / max(count, 1)})

    evaluation = evaluate(policy, val_loader, val_dataset, device)
    output.mkdir(parents=True, exist_ok=True)
    metadata = {
        "policy_type": "scene_act_lerobot",
        "conditioning": "none",
        "language_instruction_retained": bool(
            manifest.get("has_language_instruction", False)),
        "visual_key": SCENE_KEY,
        "image_shape": [3, IMAGE_SIZE, IMAGE_SIZE],
        "source_image_shape": list(
            schema["observation"]["images"]["scene_rgb"]["shape"]),
        "video_fps": float(manifest["video_fps"]),
        "image_normalization": {
            "range": [0.0, 1.0],
            "mean": IMAGE_MEAN.tolist(),
            "std": IMAGE_STD.tolist(),
            "resize": "short_side_to_224_then_center_crop",
        },
        "action_type": manifest["action_type"],
        "source_action_semantics": manifest["source_action_semantics"],
        "release_id": manifest.get("release_id"),
        "git_commit": _git_commit(),
        "state_dim": 8,
        "action_dim": 7,
        "chunk_size": chunk_size,
        "n_obs_steps": n_obs_steps,
        "train_episode_ids": sorted(train_ids),
        "validation_episode_ids": sorted(val_ids),
        "normalization": normalization,
        "sampling": sampling_profile,
    }
    torch.save(
        {"state_dict": cpu_state_dict(policy), "metadata": metadata},
        output / "checkpoint.pt",
    )
    metrics = {
        **metadata,
        **evaluation,
        "num_frames": len(rows),
        "train_frames": len(train_rows),
        "validation_frames": len(val_rows),
        "epochs": epochs,
        "batch_size": batch_size,
        "lr": lr,
        "training_history": history,
        "elapsed_s": time.time() - started,
        "device": device_info,
        "offline_metrics_are_not_task_success": True,
    }
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    return metrics


def load_scene_act_checkpoint(path: Path, device: str = "cpu"):
    import torch

    payload = torch.load(path, map_location=device, weights_only=False)
    metadata = payload["metadata"]
    policy = build_act_policy(
        int(metadata["state_dim"]),
        int(metadata["action_dim"]),
        int(metadata["chunk_size"]),
        int(metadata["n_obs_steps"]),
        device,
    )
    policy.load_state_dict(payload["state_dict"])
    policy.eval()
    return policy, metadata


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
            validation_fraction=args.validation_fraction,
            cache_root=args.cache_root,
            device=args.device,
            stage_balanced_sampling=args.stage_balanced_sampling,
            grasp_context_frames=args.grasp_context_frames,
            grasp_context_weight=args.grasp_context_weight,
            closing_weight=args.closing_weight,
            transport_weight=args.transport_weight,
            stage_closed_threshold=args.stage_closed_threshold,
            stage_open_threshold=args.stage_open_threshold,
        )
    except Exception as exc:
        print(f"Training output: {args.output}")
        print("Status: FAIL")
        print(f"Error: {exc}")
        return 1
    print(f"Training output: {args.output}")
    print(f"Train/validation frames: {metrics['train_frames']}/{metrics['validation_frames']}")
    print(f"Validation L1: {metrics['validation_l1_loss']:.6f}")
    print("Status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
