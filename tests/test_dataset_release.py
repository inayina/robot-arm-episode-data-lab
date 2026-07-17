from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
import numpy as np
import shutil
import subprocess

from training.scripts.make_mock_panda_dataset import make_rows, write_dataset
from training.scripts.prepare_dataset_release import prepare_release


SCHEMA_PATH = Path("configs/robot_schemas/panda.yaml")
MULTI_TASK_SCHEMA_PATH = Path("configs/robot_schemas/panda_multi_task.yaml")


def load_schema() -> dict:
    return yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_multi_task_schema() -> dict:
    return yaml.safe_load(MULTI_TASK_SCHEMA_PATH.read_text(encoding="utf-8"))


def write_source_dataset(path: Path) -> Path:
    schema = load_schema()
    rows = make_rows(
        schema,
        episodes=2,
        frames_per_episode=4,
        seed=7,
        action_type=schema["action"]["default_type"],
    )
    write_dataset(
        path,
        schema,
        rows,
        action_type=schema["action"]["default_type"],
        seed=7,
    )
    return path


def test_prepare_release_writes_manifest_and_inspection_report(tmp_path: Path) -> None:
    source = write_source_dataset(tmp_path / "source")
    output = tmp_path / "release"
    manifest = prepare_release(
        source,
        output,
        load_schema(),
        release_id="panda_mock_v0",
        description="mock release",
    )

    assert manifest["dataset_format"] == "panda_release_v0"
    assert manifest["release_id"] == "panda_mock_v0"
    assert manifest["robot"] == "panda"
    assert manifest["action_type"] == "ee_delta_gripper"
    assert manifest["num_episodes"] == 2
    assert manifest["num_frames"] == 8
    assert manifest["training_contract"]["state_dim"] == 8
    assert manifest["training_contract"]["action_dim"] == 7
    assert manifest["filter_rules"]["require_success_true"] is True
    assert (output / "frames.jsonl").exists()
    assert (output / "inspection_report.json").exists()

    persisted = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert persisted["release_id"] == "panda_mock_v0"
    assert persisted["inspection"]["status"] == "PASS"


def test_prepare_release_refuses_failed_inspection(tmp_path: Path) -> None:
    source = write_source_dataset(tmp_path / "bad_source")
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["robot"] = "kuka_iiwa"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="inspection failed"):
        prepare_release(
            source,
            tmp_path / "release",
            load_schema(),
            release_id="bad_release",
        )


def test_prepare_release_refuses_nonempty_output(tmp_path: Path) -> None:
    source = write_source_dataset(tmp_path / "source")
    output = tmp_path / "release"
    output.mkdir()
    (output / "existing.txt").write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(FileExistsError, match="not empty"):
        prepare_release(
            source,
            output,
            load_schema(),
            release_id="panda_mock_v0",
        )


def test_prepare_release_preserves_language_instruction_contract(tmp_path: Path) -> None:
    schema = load_multi_task_schema()
    source = tmp_path / "multi_source"
    rows = make_rows(
        schema,
        episodes=2,
        frames_per_episode=4,
        seed=7,
        action_type=schema["action"]["default_type"],
    )
    write_dataset(
        source,
        schema,
        rows,
        action_type=schema["action"]["default_type"],
        seed=7,
    )

    manifest = prepare_release(
        source,
        tmp_path / "multi_release",
        schema,
        release_id="panda_multi_mock_v0",
    )

    assert manifest["has_language_instruction"] is True
    assert (
        manifest["training_contract"]["language_instruction_key"]
        == "language_instruction"
    )


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg unavailable")
def test_prepare_scene_only_visual_release_copies_mp4(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    source = write_source_dataset(tmp_path / "scene_source")
    frames_path = source / "frames.jsonl"
    rows = [
        json.loads(line)
        for line in frames_path.read_text(encoding="utf-8").splitlines()
    ]
    video_map = {}
    for episode in (0, 1):
        episode_rows = [row for row in rows if row["episode_index"] == episode]
        for frame, row in enumerate(episode_rows):
            row["timestamp"] = frame / 10.0
        png_dir = tmp_path / f"png_{episode}"
        png_dir.mkdir()
        for frame in range(len(episode_rows)):
            Image.fromarray(np.full(
                (240, 320, 3), 20 * (episode + frame), dtype=np.uint8
            )).save(png_dir / f"{frame + 1:06d}.png")
        relative = (
            Path("videos") / "observation.images.scene"
            / f"episode_{episode:06d}.mp4"
        )
        video = source / relative
        video.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "ffmpeg", "-v", "error", "-framerate", "10",
            "-i", str(png_dir / "%06d.png"), "-c:v", "libx264",
            "-pix_fmt", "yuv420p", str(video),
        ], check=True)
        video_map[str(episode)] = relative.as_posix()
    frames_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    manifest_path = source / "manifest.json"
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_manifest.update({
        "visual_keys": ["observation.images.scene"],
        "visual_required_for_training": True,
        "video_fps": 10.0,
        "video_files": {"observation.images.scene": video_map},
        "source_action_semantics": "ee_pose_gripper_cmd_v1",
        "action_semantics_verified": True,
    })
    manifest_path.write_text(
        json.dumps(source_manifest), encoding="utf-8")

    output = tmp_path / "scene_release"
    manifest = prepare_release(
        source, output, load_schema(), release_id="scene_v1")

    assert manifest["visual_keys"] == ["observation.images.scene"]
    assert manifest["video_fps"] == 10.0
    assert manifest["action_semantics_verified"] is True
    assert (
        output / manifest["video_files"]["observation.images.scene"]["0"]
    ).is_file()
