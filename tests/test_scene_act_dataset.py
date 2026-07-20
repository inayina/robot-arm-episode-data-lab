from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from training.io.scene_cache import SCENE_KEY, SceneFrameCache
from training.scripts.train_act_lerobot import (
    SceneACTDataset,
    infer_stage_labels,
    normalization_from_rows,
    split_episode_ids,
    stage_sampling_profile,
)


def _write_video(root: Path, episode: int, frames: int = 3) -> str:
    pytest.importorskip("PIL")
    from PIL import Image

    frame_dir = root / f"source_{episode}"
    frame_dir.mkdir(parents=True)
    for index in range(frames):
        array = np.full((240, 320, 3), 30 * (episode + index), dtype=np.uint8)
        Image.fromarray(array).save(frame_dir / f"{index + 1:06d}.png")
    relative = (
        Path("videos") / "observation.images.scene"
        / f"episode_{episode:06d}.mp4"
    )
    output = root / relative
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-framerate", "10",
            "-i", str(frame_dir / "%06d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output),
        ],
        check=True,
    )
    return relative.as_posix()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg unavailable")
def test_scene_cache_and_dataset_tensor_shape(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    video_files = {
        str(episode): _write_video(tmp_path, episode) for episode in (0, 1)
    }
    rows = []
    for episode in (0, 1):
        for frame in range(3):
            rows.append({
                "observation.state": [float(episode + frame)] * 8,
                "action": [0.01 * frame] * 6 + [float(frame != 1)],
                "timestamp": frame / 10.0,
                "frame_index": frame,
                "episode_index": episode,
            })
    manifest = {
        "release_id": "scene_test",
        "video_files": {SCENE_KEY: video_files},
    }
    cache = SceneFrameCache(tmp_path, manifest, cache_root=tmp_path / "cache")
    cache.prepare({0: 3, 1: 3})
    dataset = SceneACTDataset(
        rows,
        cache,
        normalization_from_rows(rows),
        chunk_size=2,
    )

    item = dataset[0]
    assert item[SCENE_KEY].shape == torch.Size([3, 224, 224])
    assert item["action"].shape == torch.Size([2, 7])
    assert item["action_is_pad"].shape == torch.Size([2])


def test_episode_split_has_no_frame_leakage() -> None:
    rows = [
        {"episode_index": episode, "frame_index": frame}
        for episode in range(5)
        for frame in range(3)
    ]
    train_ids, val_ids = split_episode_ids(
        rows, validation_fraction=0.2, seed=7)
    assert train_ids
    assert val_ids
    assert train_ids.isdisjoint(val_ids)
    assert train_ids | val_ids == set(range(5))


def _stage_rows(gripper_commands: list[float], episode: int = 0) -> list[dict]:
    return [
        {
            "episode_index": episode,
            "frame_index": frame,
            "action": [0.0] * 6 + [command],
        }
        for frame, command in enumerate(gripper_commands)
    ]


def test_stage_labels_follow_close_carry_release_sequence() -> None:
    rows = _stage_rows([1.0, 1.0, 1.0, 0.8, 0.4, 0.1, 0.1, 0.1, 0.4, 0.8, 1.0, 1.0])

    labels = infer_stage_labels(rows, grasp_context_frames=2)

    assert labels == [
        "other",
        "grasp_context",
        "grasp_context",
        "closing",
        "closing",
        "closing",
        "closed_transport",
        "closed_transport",
        "release",
        "release",
        "release",
        "other",
    ]


def test_stage_sampling_profile_increases_requested_anchor_weights() -> None:
    rows = _stage_rows([1.0, 1.0, 1.0, 0.8, 0.4, 0.1, 0.1, 0.1, 0.4, 0.8, 1.0, 1.0])

    weights, profile = stage_sampling_profile(
        rows,
        grasp_context_frames=2,
        grasp_context_weight=2.0,
        closing_weight=4.0,
        transport_weight=3.0,
        closed_threshold=0.12,
        open_threshold=0.95,
    )

    assert weights.tolist() == [1.0, 2.0, 2.0, 4.0, 4.0, 4.0, 3.0, 3.0, 1.0, 1.0, 1.0, 1.0]
    assert profile["observed_frames"] == {
        "other": 2,
        "grasp_context": 2,
        "closing": 3,
        "closed_transport": 2,
        "release": 3,
    }
    assert profile["physical_success_rederived"] is False
    assert profile["expected_sample_fraction"]["closing"] > profile["observed_fraction"]["closing"]


def test_stage_sampling_rejects_dataset_without_close_sequence() -> None:
    rows = _stage_rows([1.0, 1.0, 1.0])

    with pytest.raises(ValueError, match="no complete close/carry sequence"):
        stage_sampling_profile(
            rows,
            grasp_context_frames=2,
            grasp_context_weight=2.0,
            closing_weight=4.0,
            transport_weight=3.0,
            closed_threshold=0.12,
            open_threshold=0.95,
        )
