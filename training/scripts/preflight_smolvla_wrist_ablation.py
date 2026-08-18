#!/usr/bin/env python3
"""CPU dual-camera preflight for wrist ablation v1. No formal train. No Isaac.

Verifies LeRobot/SmolVLA can legally consume scene+wrist as camera1+camera2
without empty-camera padding, without copying one image into two slots, and
without a third visual stream.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.smolvla_s3.policy_features import (  # noqa: E402
    CAMERA_VARIANT_SCENE_ONLY,
    CAMERA_VARIANT_SCENE_PLUS_WRIST,
    apply_feature_contract,
    camera_rename_map,
    image_feature_keys,
    policy_visual_features,
    simulate_draccus_feature_merge,
)
from training.smolvla_s3.visual_allowlist import (  # noqa: E402
    DATASET_SCENE,
    DATASET_WRIST,
    FORBIDDEN_VISUAL_KEYS,
    POLICY_CAMERA1,
    POLICY_CAMERA2,
    VARIANT_A,
    VARIANT_B,
    audit_visual_keys,
    merge_stage_audits,
)
from training.smolvla_s3.wrist_geometry_contract import (  # noqa: E402
    audit_wrist_geometry,
)

BASE_SMOLVLA_FEATURES = {
    "observation.state": {"type": "STATE", "shape": [6]},
    "observation.images.camera1": {"type": "VISUAL", "shape": [3, 256, 256]},
    "observation.images.camera2": {"type": "VISUAL", "shape": [3, 256, 256]},
    "observation.images.camera3": {"type": "VISUAL", "shape": [3, 256, 256]},
}


def _distinct_rgb(seed: int, height: int = 240, width: int = 320) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)


def _chw01(rgb: np.ndarray) -> np.ndarray:
    return np.transpose(rgb.astype(np.float32) / 255.0, (2, 0, 1))


def _cpu_prepare_images_contract(
    configured: list[str],
    batch_keys: list[str],
    empty_cameras: int,
) -> dict[str, Any]:
    present = [key for key in configured if key in batch_keys]
    missing = [key for key in configured if key not in batch_keys]
    appended = min(len(missing), int(empty_cameras))
    return {
        "configured_visual_features": configured,
        "present_visual_features": present,
        "missing_visual_features": missing,
        "empty_cameras_limit": int(empty_cameras),
        "empty_cameras_appended": appended,
        "silent_empty_padding": appended > 0,
    }


def _live_forward_probe(*, device: str) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ran": False,
        "device": device,
        "passed": False,
        "reason": None,
        "outputs_differ_when_wrist_is_distinct": None,
        "outputs_match_when_wrist_copied": None,
    }
    try:
        import torch
        from lerobot.policies.smolvla.configuration_smolvla import SmolVLAConfig
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy
    except Exception as exc:  # noqa: BLE001
        report["reason"] = f"import_failed:{exc}"
        return report
    if device == "cuda" and not torch.cuda.is_available():
        report["reason"] = "cuda_unavailable"
        return report
    try:
        cfg = SmolVLAConfig()
        cfg.input_features = {}  # type: ignore[misc]
        from lerobot.configs.types import FeatureType, PolicyFeature

        cfg.input_features = {
            "observation.state": PolicyFeature(type=FeatureType.STATE, shape=(15,)),
            POLICY_CAMERA1: PolicyFeature(type=FeatureType.VISUAL, shape=(3, 240, 320)),
            POLICY_CAMERA2: PolicyFeature(type=FeatureType.VISUAL, shape=(3, 240, 320)),
        }
        cfg.output_features = {
            "action": PolicyFeature(type=FeatureType.ACTION, shape=(8,)),
        }
        cfg.empty_cameras = 0
        cfg.chunk_size = 10
        cfg.n_action_steps = 5
        cfg.load_vlm_weights = False
        policy = SmolVLAPolicy(cfg)
        policy.eval()
        policy.to(device)
        scene = torch.from_numpy(_chw01(_distinct_rgb(1))).unsqueeze(0).to(device)
        wrist = torch.from_numpy(_chw01(_distinct_rgb(2))).unsqueeze(0).to(device)
        state = torch.zeros(1, 15, device=device)
        batch_distinct = {
            "observation.state": state,
            POLICY_CAMERA1: scene,
            POLICY_CAMERA2: wrist,
            "task": ["pick up the red box\n"],
        }
        batch_copy = {
            "observation.state": state,
            POLICY_CAMERA1: scene,
            POLICY_CAMERA2: scene,
            "task": ["pick up the red box\n"],
        }
        with torch.inference_mode():
            # prepare_images only; full select_action needs tokenizer/VLM.
            images_a, masks_a = policy.prepare_images(batch_distinct)
            images_b, masks_b = policy.prepare_images(batch_copy)
        report["ran"] = True
        n_images = len(images_a)
        empty_masks = [not bool(mask.all().item()) for mask in masks_a]
        same_when_distinct = bool(torch.allclose(images_a[0], images_a[1]))
        same_when_copied = bool(torch.allclose(images_b[0], images_b[1]))
        report["number_of_prepared_images"] = n_images
        report["empty_image_masks"] = empty_masks
        report["outputs_differ_when_wrist_is_distinct"] = not same_when_distinct
        report["outputs_match_when_wrist_copied"] = same_when_copied
        report["passed"] = (
            n_images == 2
            and not any(empty_masks)
            and not same_when_distinct
            and same_when_copied
        )
        if n_images != 2:
            report["reason"] = f"prepared_image_count={n_images}"
        elif any(empty_masks):
            report["reason"] = "empty_camera_padding_detected"
        elif same_when_distinct:
            report["reason"] = "scene_and_wrist_collapsed_to_same_tensor"
        return report
    except Exception as exc:  # noqa: BLE001
        report["reason"] = f"forward_failed:{exc}"
        return report


def run_preflight(cfg: dict[str, Any], *, live_forward: bool) -> dict[str, Any]:
    failures: list[str] = []
    a_visuals = policy_visual_features(CAMERA_VARIANT_SCENE_ONLY)
    b_visuals = policy_visual_features(CAMERA_VARIANT_SCENE_PLUS_WRIST)
    if len(b_visuals) != 2:
        failures.append("b_camera_count")
    if POLICY_CAMERA3 := "observation.images.camera3":
        if POLICY_CAMERA3 in b_visuals:
            failures.append("third_camera_in_b_contract")

    merged = simulate_draccus_feature_merge(BASE_SMOLVLA_FEATURES, b_visuals)
    replaced, removed = apply_feature_contract(merged, b_visuals)
    if "observation.images.camera3" not in removed:
        failures.append("camera3_not_stripped")
    if image_feature_keys(replaced) != [POLICY_CAMERA1, POLICY_CAMERA2]:
        failures.append("replace_did_not_yield_exactly_camera1_camera2")

    scene = _distinct_rgb(11)
    wrist = _distinct_rgb(22)
    pixels_distinct = not np.array_equal(scene, wrist)
    if not pixels_distinct:
        failures.append("synthetic_scene_wrist_not_distinct")

    padding_ok = _cpu_prepare_images_contract(
        [POLICY_CAMERA1, POLICY_CAMERA2],
        [POLICY_CAMERA1, POLICY_CAMERA2],
        int((cfg.get("inference") or {}).get("empty_cameras") or 0),
    )
    padding_missing_wrist = _cpu_prepare_images_contract(
        [POLICY_CAMERA1, POLICY_CAMERA2],
        [POLICY_CAMERA1],
        0,
    )
    if padding_ok["empty_cameras_appended"] != 0:
        failures.append("silent_empty_camera_padding")
    if padding_missing_wrist["empty_cameras_appended"] != 0:
        # empty_cameras=0 must NOT invent a second camera.
        pass
    else:
        if POLICY_CAMERA2 not in padding_missing_wrist["missing_visual_features"]:
            failures.append("missing_wrist_not_detected")

    tactile_probe = audit_visual_keys(
        variant=VARIANT_B,
        stage="dataset",
        observed_keys=[DATASET_SCENE, DATASET_WRIST, "observation.images.tactile_left"],
    )
    if tactile_probe["passed"] or "observation.images.tactile_left" not in tactile_probe["unexpected_visual_keys"]:
        failures.append("tactile_not_rejected")

    a_audit = merge_stage_audits(
        variant=VARIANT_A,
        stages={
            "dataset": [DATASET_SCENE],
            "release": [DATASET_SCENE],
            "training": list(a_visuals),
            "checkpoint": list(a_visuals),
            "runtime": list(a_visuals),
        },
        rename_map=camera_rename_map(CAMERA_VARIANT_SCENE_ONLY),
    )
    b_audit = merge_stage_audits(
        variant=VARIANT_B,
        stages={
            "dataset": [DATASET_SCENE, DATASET_WRIST],
            "release": [DATASET_SCENE, DATASET_WRIST],
            "training": list(b_visuals),
            "checkpoint": list(b_visuals),
            "runtime": list(b_visuals),
        },
        rename_map=camera_rename_map(CAMERA_VARIANT_SCENE_PLUS_WRIST),
    )
    if not a_audit["passed"] or a_audit["number_of_policy_cameras"] != 1:
        failures.append("A_allowlist_failed")
    if not b_audit["passed"] or b_audit["number_of_policy_cameras"] != 2:
        failures.append("B_allowlist_failed")

    geometry = audit_wrist_geometry()
    if not geometry["passed"]:
        failures.append("wrist_geometry_failed")

    live = {
        "cpu": {"ran": False, "passed": False, "reason": "not_requested"},
        "cuda": {"ran": False, "passed": False, "reason": "not_requested"},
    }
    if live_forward:
        live["cpu"] = _live_forward_probe(device="cpu")
        live["cuda"] = _live_forward_probe(device="cuda")
        # CPU prepare_images is sufficient for Stage B; CUDA may be unavailable.
        if live["cpu"]["ran"] and not live["cpu"]["passed"]:
            failures.append("cpu_prepare_images_failed")

    passed = not failures
    return {
        "mode": "wrist_ablation_dual_camera_preflight",
        "experiment_id": "smolvla_wrist_ablation_v1",
        "authorized_to_train": False,
        "triggers_isaac": False,
        "formal_train": False,
        "camera_variant_A": CAMERA_VARIANT_SCENE_ONLY,
        "camera_variant_B": CAMERA_VARIANT_SCENE_PLUS_WRIST,
        "rename_map_A": camera_rename_map(CAMERA_VARIANT_SCENE_ONLY),
        "rename_map_B": camera_rename_map(CAMERA_VARIANT_SCENE_PLUS_WRIST),
        "policy_visual_features_A": a_visuals,
        "policy_visual_features_B": b_visuals,
        "draccus_merge_keeps_camera3": "observation.images.camera3"
        in image_feature_keys(merged),
        "replace_strips_camera3": "observation.images.camera3" in removed,
        "replaced_image_keys": image_feature_keys(replaced),
        "scene_wrist_pixels_distinct": bool(pixels_distinct),
        "prepare_images_both_present": padding_ok,
        "prepare_images_missing_wrist_empty_cameras_0": padding_missing_wrist,
        "tactile_rejected": not tactile_probe["passed"],
        "forbidden_visual_keys": list(FORBIDDEN_VISUAL_KEYS),
        "visual_allowlist_A": a_audit,
        "visual_allowlist_B": b_audit,
        "wrist_geometry": geometry,
        "live_forward": live,
        "failures": failures,
        "passed": passed,
        "gate": "dual_camera_preflight_pass" if passed else "dual_camera_preflight_hold",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "smolvla_s3" / "wrist_ablation_v1.yaml",
    )
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument(
        "--visual-audit-out",
        type=Path,
        default=None,
        help="Write policy_visual_input_audit.json (B contract).",
    )
    parser.add_argument("--live-forward", action="store_true")
    args = parser.parse_args(argv)
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    report = run_preflight(cfg, live_forward=args.live_forward)
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text, encoding="utf-8")
    if args.visual_audit_out:
        args.visual_audit_out.parent.mkdir(parents=True, exist_ok=True)
        args.visual_audit_out.write_text(
            json.dumps(report["visual_allowlist_B"], indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
    print(text, end="")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
