"""Fail-closed visual input allowlist for SmolVLA wrist ablation v1.

Experiment visual variable is strictly:

  A_scene_only:  state[15] + scene RGB
  B_scene_wrist: state[15] + scene RGB + H_knuckle_z05 wrist RGB

No third camera. Tactile / GelSight / depth / segmentation / extra MuJoCo
cameras are forbidden at collection, release, training, and inference.

Gripper/fingers appearing *inside* the wrist RGB frame are expected
eye-in-hand content, not a separate policy camera.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

EXPERIMENT_ID = "smolvla_wrist_ablation_v1"

VARIANT_A = "A_scene_only"
VARIANT_B = "B_scene_wrist"

DATASET_SCENE = "observation.images.scene"
DATASET_WRIST = "observation.images.wrist"
POLICY_CAMERA1 = "observation.images.camera1"
POLICY_CAMERA2 = "observation.images.camera2"

ALLOWED_DATASET_KEYS: dict[str, tuple[str, ...]] = {
    VARIANT_A: (DATASET_SCENE,),
    VARIANT_B: (DATASET_SCENE, DATASET_WRIST),
}
ALLOWED_POLICY_KEYS: dict[str, tuple[str, ...]] = {
    VARIANT_A: (POLICY_CAMERA1,),
    VARIANT_B: (POLICY_CAMERA1, POLICY_CAMERA2),
}
REQUIRED_CAMERA_COUNT: dict[str, int] = {
    VARIANT_A: 1,
    VARIANT_B: 2,
}

# Dataset → LeRobot/SmolVLA input_features rename. Order is part of the contract.
DEFAULT_RENAME_MAP: dict[str, dict[str, str]] = {
    VARIANT_A: {DATASET_SCENE: POLICY_CAMERA1},
    VARIANT_B: {DATASET_SCENE: POLICY_CAMERA1, DATASET_WRIST: POLICY_CAMERA2},
}

FORBIDDEN_VISUAL_KEYS = (
    "observation.images.tactile_left",
    "observation.images.tactile_right",
    "observation.images.camera3",
    "observation.images.empty_camera_0",
    "observation.images.empty_camera_1",
    "observation.images.empty_camera_2",
    "observation.depth.scene",
    "observation.depth.wrist",
)

FORBIDDEN_KEY_SUBSTRINGS = (
    "tactile",
    "gelsight",
    "empty_camera",
    "segmentation",
    "object_pose",
    "gripper_camera",
    "fingertip",
)


def _is_visual_key(key: str) -> bool:
    return str(key).startswith("observation.images.") or str(key).startswith(
        "observation.depth."
    )


def extract_visual_keys(source: Mapping[str, Any] | Iterable[str] | None) -> list[str]:
    if source is None:
        return []
    if isinstance(source, Mapping):
        keys = [str(key) for key in source]
    else:
        keys = [str(key) for key in source]
    return sorted({key for key in keys if _is_visual_key(key)})


def _forbidden_reason(key: str) -> str | None:
    lower = key.lower()
    if key in FORBIDDEN_VISUAL_KEYS:
        return "forbidden_visual_key"
    if any(token in lower for token in FORBIDDEN_KEY_SUBSTRINGS):
        return "forbidden_visual_substring"
    return None


def apply_rename(keys: Sequence[str], rename_map: Mapping[str, str]) -> list[str]:
    mapped = [str(rename_map.get(key, key)) for key in keys]
    return sorted(set(mapped))


def audit_visual_keys(
    *,
    variant: str,
    stage: str,
    observed_keys: Sequence[str],
    rename_map: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Fail-closed allowlist. Never silently drop or auto-include extras."""
    if variant not in ALLOWED_DATASET_KEYS:
        raise ValueError(f"unknown visual variant: {variant}")
    allowed_dataset = list(ALLOWED_DATASET_KEYS[variant])
    allowed_policy = list(ALLOWED_POLICY_KEYS[variant])
    expected_count = REQUIRED_CAMERA_COUNT[variant]
    rename = dict(rename_map or DEFAULT_RENAME_MAP[variant])

    observed = extract_visual_keys(observed_keys)
    unexpected: list[str] = []
    reasons: dict[str, str] = {}
    allowed_union = set(allowed_dataset) | set(allowed_policy)
    for key in observed:
        forbidden = _forbidden_reason(key)
        if forbidden:
            unexpected.append(key)
            reasons[key] = forbidden
            continue
        if key not in allowed_union:
            unexpected.append(key)
            reasons[key] = "not_on_allowlist"

    mapped = apply_rename(
        [key for key in observed if key not in unexpected],
        rename,
    )
    mapped_policy = [key for key in mapped if str(key).startswith("observation.images.")]
    missing = [key for key in allowed_policy if key not in mapped_policy]
    extra_after_rename = [key for key in mapped_policy if key not in set(allowed_policy)]
    camera_count = len(mapped_policy)
    failures: list[str] = []
    if unexpected:
        failures.append("unexpected_visual_keys")
    if missing:
        failures.append("missing_required_visual_keys")
    if extra_after_rename:
        failures.append("extra_keys_after_rename")
    if camera_count != expected_count:
        failures.append(
            f"number_of_policy_cameras={camera_count}_expected={expected_count}"
        )
    if camera_count >= 3:
        failures.append("third_camera_forbidden")

    passed = not failures
    return {
        "experiment_id": EXPERIMENT_ID,
        "variant": variant,
        "stage": stage,
        "allowed_dataset_visual_keys": allowed_dataset,
        "allowed_policy_visual_keys": allowed_policy,
        "rename_map": dict(rename),
        "observed_visual_keys": observed,
        "mapped_policy_visual_keys": mapped_policy,
        "number_of_policy_cameras": camera_count,
        "expected_number_of_policy_cameras": expected_count,
        "unexpected_visual_keys": unexpected,
        "unexpected_reasons": reasons,
        "missing_required_visual_keys": missing,
        "extra_keys_after_rename": extra_after_rename,
        "failures": failures,
        "passed": passed,
        "claims_third_camera_ok": False,
        "notes": (
            "Gripper/fingers inside wrist RGB are expected eye-in-hand content, "
            "not a separate policy camera. Tactile/depth/segmentation/camera3 "
            "are forbidden."
        ),
    }


def merge_stage_audits(
    *,
    variant: str,
    stages: Mapping[str, Sequence[str] | Mapping[str, Any] | None],
    rename_map: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Audit collection/release/training/checkpoint/runtime in one report."""
    stage_reports: dict[str, Any] = {}
    unexpected: list[str] = []
    for stage, source in stages.items():
        keys = extract_visual_keys(source)
        report = audit_visual_keys(
            variant=variant,
            stage=stage,
            observed_keys=keys,
            rename_map=rename_map,
        )
        stage_reports[stage] = report
        unexpected.extend(report["unexpected_visual_keys"])
    unique_unexpected = sorted(set(unexpected))
    passed = all(item["passed"] for item in stage_reports.values())
    camera_counts = {
        stage: item["number_of_policy_cameras"] for stage, item in stage_reports.items()
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "variant": variant,
        "dataset_visual_keys": list(
            (stage_reports.get("dataset") or {}).get("observed_visual_keys") or []
        ),
        "release_visual_keys": list(
            (stage_reports.get("release") or {}).get("observed_visual_keys") or []
        ),
        "training_input_features": list(
            (stage_reports.get("training") or {}).get("mapped_policy_visual_keys")
            or []
        ),
        "checkpoint_input_features": list(
            (stage_reports.get("checkpoint") or {}).get("mapped_policy_visual_keys")
            or []
        ),
        "runtime_visual_keys": list(
            (stage_reports.get("runtime") or {}).get("mapped_policy_visual_keys") or []
        ),
        "number_of_policy_cameras": REQUIRED_CAMERA_COUNT[variant],
        "stage_camera_counts": camera_counts,
        "unexpected_visual_keys": unique_unexpected,
        "stages": stage_reports,
        "passed": passed,
        "authorized_to_train": False,
        "stop_on_third_camera": True,
    }


def dataset_visual_keys_from_info(info: Mapping[str, Any]) -> list[str]:
    features = info.get("features") or {}
    return extract_visual_keys(features)


def dataset_visual_keys_from_video_tree(root: Any) -> list[str]:
    from pathlib import Path

    videos = Path(root) / "videos"
    if not videos.is_dir():
        return []
    keys: set[str] = set()
    for path in videos.rglob("*"):
        if path.is_dir() and path.name.startswith("observation.images."):
            keys.add(path.name)
        if path.is_dir() and path.name.startswith("observation.depth."):
            keys.add(path.name)
    return sorted(keys)
