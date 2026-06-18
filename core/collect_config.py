"""采集脚本共享配置类型与 YAML 加载。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "configs" / "default.yaml"


@dataclass(frozen=True)
class CameraConfig:
    width: int = 640
    height: int = 480
    eye: tuple[float, float, float] = (1.15, -1.05, 0.85)
    target: tuple[float, float, float] = (0.45, 0.0, 0.25)
    up: tuple[float, float, float] = (0.0, 0.0, 1.0)
    fov: float = 55.0
    type: str = "fixed_rgb"


@dataclass(frozen=True)
class CollectSettings:
    mode: str
    output: Path
    num_steps: int
    width: int
    height: int
    gui: bool
    seed: int
    simulator: str
    task_name: str
    robot: str
    object_name: str
    control_mode: str
    camera: CameraConfig
    config_path: Path | None
    planner: str = "cartesian"
    grasp_mode: str = "constraint"


def resolve_config_path(config_path: Path) -> Path:
    if config_path.is_absolute():
        return config_path
    cwd_candidate = Path.cwd() / config_path
    if cwd_candidate.exists():
        return cwd_candidate
    repo_candidate = REPO_ROOT / config_path
    if repo_candidate.exists():
        return repo_candidate
    return cwd_candidate


def _as_float_triplet(value: Any, field_name: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{field_name} must be a list of three numbers.")
    return (float(value[0]), float(value[1]), float(value[2]))


def load_yaml_config(config_path: Path) -> dict[str, Any]:
    resolved = resolve_config_path(config_path)
    if not resolved.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with resolved.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config root must be a mapping: {resolved}")
    return raw


def camera_from_mapping(
    image_width: int,
    image_height: int,
    camera_mapping: dict[str, Any] | None,
) -> CameraConfig:
    camera_mapping = camera_mapping or {}
    return CameraConfig(
        width=image_width,
        height=image_height,
        eye=_as_float_triplet(
            camera_mapping.get("eye", [1.15, -1.05, 0.85]),
            "camera.eye",
        ),
        target=_as_float_triplet(
            camera_mapping.get("target", [0.45, 0.0, 0.25]),
            "camera.target",
        ),
        up=_as_float_triplet(
            camera_mapping.get("up", [0.0, 0.0, 1.0]),
            "camera.up",
        ),
        fov=float(camera_mapping.get("fov", 55.0)),
        type=str(camera_mapping.get("type", "fixed_rgb")),
    )


def settings_from_config(config_path: Path) -> CollectSettings:
    config = load_yaml_config(config_path)
    camera_mapping = config.get("camera")
    if camera_mapping is not None and not isinstance(camera_mapping, dict):
        raise ValueError("camera must be a mapping in the config file.")

    width = int(config.get("image_width", 640))
    height = int(config.get("image_height", 480))
    output_raw = config.get("output_dir", "dataset_sample/episode_000001")

    return CollectSettings(
        mode="episode",
        output=Path(str(output_raw)),
        num_steps=int(config.get("num_steps", 100)),
        width=width,
        height=height,
        gui=False,
        seed=int(config.get("seed", 7)),
        simulator=str(config.get("simulator", "pybullet")),
        task_name=str(config.get("task_name", "reach_cube")),
        robot=str(config.get("robot", "kuka_iiwa")),
        object_name=str(config.get("object", "cube")),
        control_mode=str(config.get("control_mode", "joint_position")),
        camera=camera_from_mapping(width, height, camera_mapping),
        config_path=resolve_config_path(config_path),
        planner=str(config.get("planner", "cartesian")),
        grasp_mode=str(config.get("grasp_mode", "constraint")),
    )


def resolve_settings(args: argparse.Namespace) -> CollectSettings:
    config_arg = getattr(args, "config", None)
    if config_arg is None:
        base = settings_from_config(DEFAULT_CONFIG_PATH)
        config_path: Path | None = None
    else:
        config_path = resolve_config_path(Path(config_arg))
        base = settings_from_config(config_path)

    output = Path(getattr(args, "output", None) or base.output)
    mode = getattr(args, "mode", None) or base.mode
    num_steps = getattr(args, "num_steps", None) or base.num_steps
    width = getattr(args, "width", None) or base.width
    height = getattr(args, "height", None) or base.height
    seed = getattr(args, "seed", None) or base.seed
    gui = bool(getattr(args, "gui", False))

    camera = camera_from_mapping(
        width,
        height,
        {
            "type": base.camera.type,
            "eye": list(base.camera.eye),
            "target": list(base.camera.target),
            "up": list(base.camera.up),
            "fov": base.camera.fov,
        },
    )

    control_mode = getattr(args, "control_mode", None) or base.control_mode
    task_name = getattr(args, "task", None) or base.task_name
    planner = getattr(args, "planner", None) or base.planner
    grasp_mode = getattr(args, "grasp_mode", None) or base.grasp_mode

    return CollectSettings(
        mode=mode,
        output=output,
        num_steps=num_steps,
        width=width,
        height=height,
        gui=gui,
        seed=seed,
        simulator=base.simulator,
        task_name=task_name,
        robot=base.robot,
        object_name=base.object_name,
        control_mode=control_mode,
        camera=camera,
        config_path=config_path if config_arg is not None else None,
        planner=planner,
        grasp_mode=grasp_mode,
    )
