#!/usr/bin/env python3
"""Validate a collected robot-arm episode directory."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image


REQUIRED_ARRAYS = {
    "states.npy": None,
    "actions.npy": None,
    "ee_poses.npy": 7,
    "object_poses.npy": 7,
}
REQUIRED_METADATA_KEYS = {
    "episode_id",
    "simulator",
    "task_name",
    "num_steps",
    "image_width",
    "image_height",
    "state_dim",
    "action_dim",
    "control_mode",
    "robot",
    "object",
    "camera",
}
FRAME_RE = re.compile(r"^(\d{6})\.png$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate an episode dataset.")
    parser.add_argument("episode_dir", type=Path, help="Episode directory to validate.")
    return parser.parse_args()


def collect_errors(episode_dir: Path) -> list[str]:
    errors: list[str] = []

    if not episode_dir.exists():
        return [f"episode directory does not exist: {episode_dir}"]
    if not episode_dir.is_dir():
        return [f"episode path is not a directory: {episode_dir}"]

    images_dir = episode_dir / "images"
    if not images_dir.is_dir():
        errors.append("missing images/ directory")
        image_paths: list[Path] = []
    else:
        image_paths = sorted(images_dir.glob("*.png"))
        errors.extend(validate_image_sequence(image_paths))

    arrays: dict[str, np.ndarray] = {}
    for file_name, expected_width in REQUIRED_ARRAYS.items():
        path = episode_dir / file_name
        if not path.exists():
            errors.append(f"missing {file_name}")
            continue
        try:
            array = np.load(path)
        except Exception as exc:  # noqa: BLE001 - report any corrupt npy.
            errors.append(f"could not load {file_name}: {exc}")
            continue
        arrays[file_name] = array
        if array.ndim != 2:
            errors.append(f"{file_name} must be 2D, got shape {array.shape}")
        if expected_width is not None and array.ndim == 2 and array.shape[1] != expected_width:
            errors.append(
                f"{file_name} second dimension must be {expected_width}, "
                f"got {array.shape[1]}"
            )

    metadata = load_metadata(episode_dir / "metadata.json", errors)
    frame_count = len(image_paths)

    if frame_count > 0:
        validate_first_image(image_paths[0], metadata, errors)
    for file_name, array in arrays.items():
        if array.ndim >= 1 and array.shape[0] != frame_count:
            errors.append(
                f"{file_name} has {array.shape[0]} rows but images/ has "
                f"{frame_count} frames"
            )

    if metadata:
        missing_keys = sorted(REQUIRED_METADATA_KEYS - set(metadata))
        for key in missing_keys:
            errors.append(f"metadata.json missing key: {key}")
        if metadata.get("num_steps") != frame_count:
            errors.append(
                f"metadata num_steps={metadata.get('num_steps')} but images/ has "
                f"{frame_count} frames"
            )
        compare_dim(metadata, "state_dim", arrays.get("states.npy"), errors)
        compare_dim(metadata, "action_dim", arrays.get("actions.npy"), errors)

    return errors


def validate_image_sequence(image_paths: list[Path]) -> list[str]:
    errors: list[str] = []
    if not image_paths:
        return ["images/ contains no PNG frames"]

    indices: list[int] = []
    for image_path in image_paths:
        match = FRAME_RE.match(image_path.name)
        if not match:
            errors.append(f"unexpected image frame name: {image_path.name}")
            continue
        indices.append(int(match.group(1)))

    if len(indices) != len(image_paths):
        return errors

    expected = list(range(len(indices)))
    if indices != expected:
        errors.append(
            "image frames must be continuous from 000000.png; "
            f"got indices {indices[:5]}...{indices[-5:]}"
        )
    return errors


def load_metadata(path: Path, errors: list[str]) -> dict[str, object] | None:
    if not path.exists():
        errors.append("missing metadata.json")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"metadata.json is not valid JSON: {exc}")
    return None


def validate_first_image(
    image_path: Path,
    metadata: dict[str, object] | None,
    errors: list[str],
) -> None:
    try:
        with Image.open(image_path) as image:
            width, height = image.size
            if image.mode not in {"RGB", "RGBA"}:
                errors.append(f"{image_path.name} mode should be RGB/RGBA, got {image.mode}")
            if metadata:
                if metadata.get("image_width") != width:
                    errors.append(
                        f"metadata image_width={metadata.get('image_width')} "
                        f"but first frame width={width}"
                    )
                if metadata.get("image_height") != height:
                    errors.append(
                        f"metadata image_height={metadata.get('image_height')} "
                        f"but first frame height={height}"
                    )
    except Exception as exc:  # noqa: BLE001 - report unreadable image.
        errors.append(f"could not open first image frame: {exc}")


def compare_dim(
    metadata: dict[str, object],
    key: str,
    array: np.ndarray | None,
    errors: list[str],
) -> None:
    if array is None or array.ndim != 2:
        return
    if metadata.get(key) != array.shape[1]:
        errors.append(
            f"metadata {key}={metadata.get(key)} but array dimension={array.shape[1]}"
        )


def main() -> int:
    args = parse_args()
    errors = collect_errors(args.episode_dir)
    if errors:
        print("Dataset validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Dataset validation passed: {args.episode_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
