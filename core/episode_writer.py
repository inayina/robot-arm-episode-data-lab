"""Episode 目录准备、数组落盘与 metadata 构建。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from agents.evaluator import EvaluationResult
from agents.task_fsm import PickLiftTaskFSM
from core.collect_config import (
    DEFAULT_CONFIG_PATH,
    REPO_ROOT,
    CameraConfig,
    CollectSettings,
)

FRAME_NAME_RE = re.compile(r"^\d{6}\.png$")


def prepare_episode_dir(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    for frame_path in images_dir.glob("*.png"):
        if FRAME_NAME_RE.match(frame_path.name):
            frame_path.unlink()
    return images_dir


def save_png(path: Path, rgb: np.ndarray) -> None:
    Image.fromarray(rgb, mode="RGB").save(path)


def save_episode_arrays(
    output_dir: Path,
    states: np.ndarray,
    actions: np.ndarray,
    ee_poses: np.ndarray,
    object_poses: np.ndarray,
) -> None:
    np.save(output_dir / "states.npy", states)
    np.save(output_dir / "actions.npy", actions)
    np.save(output_dir / "ee_poses.npy", ee_poses)
    np.save(output_dir / "object_poses.npy", object_poses)


def write_metadata(
    output_dir: Path,
    metadata: dict[str, object],
) -> None:
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )


def build_metadata(
    output_dir: Path,
    mode: str,
    num_steps: int,
    state_dim: int,
    action_dim: int,
    camera: CameraConfig,
    settings: CollectSettings,
    evaluation: EvaluationResult | None = None,
    gripper_states: list[int] | None = None,
    phase_labels: list[str] | None = None,
    planning_success: bool | None = None,
    planning_failure_reason: str | None = None,
    grasp_mode: str | None = None,
    grasp_established: bool | None = None,
    grasp_established_at_step: int | None = None,
) -> dict[str, object]:
    notes = (
        "Minimal PyBullet image-state-action episode for portfolio "
        "data collection demonstration."
    )
    config_path = settings.config_path or DEFAULT_CONFIG_PATH
    try:
        config_label = config_path.relative_to(REPO_ROOT)
    except ValueError:
        config_label = config_path
    notes += f" Loaded config: {config_label}."

    metadata: dict[str, object] = {
        "episode_id": output_dir.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "simulator": settings.simulator,
        "mode": mode,
        "task_name": settings.task_name,
        "num_steps": num_steps,
        "image_width": camera.width,
        "image_height": camera.height,
        "state_dim": state_dim,
        "action_dim": action_dim,
        "control_mode": settings.control_mode,
        "robot": settings.robot,
        "object": settings.object_name,
        "camera": {
            "type": camera.type,
            "width": camera.width,
            "height": camera.height,
            "eye": list(camera.eye),
            "target": list(camera.target),
            "up": list(camera.up),
            "fov": camera.fov,
        },
        "seed": settings.seed,
        "notes": notes,
        "planning_mode": settings.planner,
    }
    if planning_success is not None:
        metadata["planning_success"] = planning_success
    if planning_failure_reason is not None:
        metadata["planning_failure_reason"] = planning_failure_reason
    if settings.task_name == "pick_and_lift":
        metadata["language_instruction"] = PickLiftTaskFSM.LANGUAGE_INSTRUCTION
    if evaluation is not None:
        metadata["success"] = evaluation.success
        metadata["failure_reason"] = evaluation.failure_reason
        metadata["object_z_lift"] = round(evaluation.object_z_lift, 6)
        metadata["aborted"] = evaluation.aborted
    if gripper_states is not None:
        metadata["gripper_states"] = gripper_states
    if phase_labels is not None:
        metadata["task_phases"] = phase_labels
    if grasp_mode is not None:
        metadata["grasp_mode"] = grasp_mode
    if grasp_established is not None:
        metadata["grasp_established"] = grasp_established
    if grasp_established_at_step is not None:
        metadata["grasp_established_at_step"] = grasp_established_at_step
    return metadata
