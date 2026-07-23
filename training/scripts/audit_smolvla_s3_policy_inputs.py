#!/usr/bin/env python3
"""Phase 0 audit: policy inputs, PEFT targets, and empty-camera profiler.

Read-only by default. Does not train, download weights, collect data, or launch
Isaac. Live mode only runs when checkpoints / CUDA are explicitly provided.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "smolvla_s3" / "lora_train.yaml"
DEFAULT_V2_CHECKPOINT = (
    ROOT
    / "runs"
    / "smolvla_s3"
    / "train_v2_lateclose_20260723T160000Z"
    / "lerobot_run"
    / "checkpoints"
    / "001000"
    / "pretrained_model"
)

# Official SmolVLA PEFT surface from lerobot modeling_smolvla._get_default_peft_targets
OFFICIAL_PROJECTION_MODULES = (
    "state_proj",
    "action_in_proj",
    "action_out_proj",
    "action_time_mlp_in",
    "action_time_mlp_out",
)
ATTENTION_LORA_MODULES = ("q_proj", "v_proj")
RECOVERY_RECOMMENDED_TARGET_MODULES = (
    *ATTENTION_LORA_MODULES,
    *OFFICIAL_PROJECTION_MODULES,
)

# Deployable Panda state candidate (not yet authorized for a v3 release).
RECOMMENDED_STATE15 = {
    "name": "observation.state[15]",
    "layout": [
        "joint_position[7]",
        "ee_pose_xyzw[7]",
        "measured_gripper[1]",
    ],
    "exclude_from_policy_state": [
        "observation.object_pose",  # sim GT; breaks Sim2Real-readiness
        "observation.ft",  # needs real sync/calibration first
    ],
    "pads_to_max_state_dim": 32,
}


def _tensor_summary(value: Any) -> dict[str, Any]:
    try:
        import torch

        if isinstance(value, torch.Tensor):
            flat = value.detach().float().cpu().reshape(-1)
            nonzero = float((flat != 0).float().mean().item()) if flat.numel() else 0.0
            return {
                "type": "tensor",
                "shape": list(value.shape),
                "dtype": str(value.dtype).replace("torch.", ""),
                "min": float(flat.min().item()) if flat.numel() else None,
                "max": float(flat.max().item()) if flat.numel() else None,
                "nonzero_ratio": nonzero,
            }
    except Exception:  # noqa: BLE001
        pass
    if hasattr(value, "shape"):
        return {"type": type(value).__name__, "shape": list(value.shape)}
    if isinstance(value, (list, tuple)):
        return {"type": type(value).__name__, "len": len(value)}
    return {"type": type(value).__name__, "repr": repr(value)[:120]}


def summarize_batch(batch: dict[str, Any]) -> dict[str, Any]:
    return {key: _tensor_summary(value) for key, value in sorted(batch.items())}


def compare_schema_to_preprocessor(
    *,
    source_keys: dict[str, list[int] | int],
    preprocessor_features: dict[str, Any],
    rename_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    rename_map = dict(rename_map or {})
    declared = {
        key: list(meta.get("shape") or [])
        for key, meta in preprocessor_features.items()
    }
    effective_source = {
        rename_map.get(key, key): shape for key, shape in source_keys.items()
    }
    dropped = sorted(set(effective_source) - set(declared))
    # Keys renamed away from the source name are expected absences.
    renamed_away = sorted(set(rename_map) & set(source_keys))
    shape_mismatches = {}
    for key, shape in effective_source.items():
        if key not in declared:
            continue
        expected = list(shape) if isinstance(shape, (list, tuple)) else [int(shape)]
        if declared[key] != expected:
            shape_mismatches[key] = {
                "source": expected,
                "preprocessor": declared[key],
            }
    return {
        "source_keys": source_keys,
        "rename_map": rename_map,
        "effective_source_keys_after_rename": effective_source,
        "preprocessor_keys": declared,
        "dropped_by_preprocessor": dropped,
        "renamed_source_keys": renamed_away,
        "shape_mismatches": shape_mismatches,
        "state7_vs_checkpoint6": {
            "source_observation.state": source_keys.get("observation.state"),
            "checkpoint_observation.state": declared.get("observation.state"),
            "explained": False,
            "notes": (
                "v1/v2 checkpoints declare observation.state[6] while Panda "
                "release schema is observation.state[7]. Extra ee_pose / "
                "object_pose / ft / gripper keys are present in evaluator "
                "batches but absent from checkpoint preprocessor features."
            ),
        },
    }


def classify_parameter_name(name: str) -> str:
    lower = name.lower()
    if "vision" in lower or "vision_model" in lower or "vision_tower" in lower:
        return "vision_encoder"
    if any(token in lower for token in OFFICIAL_PROJECTION_MODULES):
        for token in OFFICIAL_PROJECTION_MODULES:
            if token in lower:
                return f"projection:{token}"
    if re.search(r"(^|\.)q_proj(\.|$)", lower):
        return "lora_attention:q_proj"
    if re.search(r"(^|\.)v_proj(\.|$)", lower):
        return "lora_attention:v_proj"
    if "vlm_with_expert" in lower or "language_model" in lower:
        return "base_vlm_or_expert"
    return "other"


def probe_peft_targets(
    module_names: Iterable[str],
    *,
    configured_targets: list[str] | str,
    recommended_targets: list[str] | str | None = None,
) -> dict[str, Any]:
    if recommended_targets is None:
        recommended_targets = (
            r"(model\.vlm_with_expert\.lm_expert\..*\.(q|v)_proj|"
            r"model\.(state_proj|action_in_proj|action_out_proj|"
            r"action_time_mlp_in|action_time_mlp_out))"
        )
    names = list(module_names)
    by_class: dict[str, list[str]] = {}
    for name in names:
        by_class.setdefault(classify_parameter_name(name), []).append(name)

    def matched(targets: list[str] | str) -> list[str]:
        if isinstance(targets, str):
            pattern = re.compile(targets)
            return sorted({name for name in names if pattern.search(name)})
        hits: list[str] = []
        for name in names:
            leaf = name.rsplit(".", 1)[-1]
            if leaf in targets or any(token == leaf for token in targets):
                hits.append(name)
            elif any(token in name.split(".") for token in targets):
                hits.append(name)
        return sorted(set(hits))

    configured_hits = matched(configured_targets)
    recommended_hits = matched(recommended_targets)
    projection_present = {
        token: any(token in name for name in names)
        for token in OFFICIAL_PROJECTION_MODULES
    }
    vision_hit = any("vision" in name.lower() for name in configured_hits)
    language_non_expert_hit = any(
        "language_model" in name and "lm_expert" not in name
        for name in configured_hits
    )
    return {
        "module_count": len(names),
        "classes": {key: len(value) for key, value in sorted(by_class.items())},
        "class_examples": {
            key: value[:5] for key, value in sorted(by_class.items())
        },
        "configured_target_modules": configured_targets,
        "configured_target_hits": configured_hits,
        "recommended_target_modules": recommended_targets,
        "recommended_target_hits": recommended_hits,
        "projection_modules_present": projection_present,
        "projection_trainable_under_current_config": {
            token: any(token in hit for hit in configured_hits)
            for token in OFFICIAL_PROJECTION_MODULES
        },
        "configured_hits_vision_encoder": vision_hit,
        "configured_hits_base_language_non_expert": language_non_expert_hit,
        "official_default_peft_regex": (
            r"(model\.vlm_with_expert\.lm_expert\..*\.(q|v)_proj|"
            r"model\.(state_proj|action_in_proj|action_out_proj|"
            r"action_time_mlp_in|action_time_mlp_out))"
        ),
        "recovery_recommendation": {
            "keep_attention_lora": list(ATTENTION_LORA_MODULES),
            "add_task_dependent_projections": list(OFFICIAL_PROJECTION_MODULES),
            "use_exact_official_regex": True,
            "full_training_modules": [],
            "freeze_vision_encoder": True,
            "freeze_base_vlm": True,
            "notes": (
                "Adopted Phase-0 decision: official exact PEFT regex only; "
                "reject plain suffix lists and full_training_modules for projections."
            ),
        },
        "recommended_covers_projections": all(
            any(token in hit for hit in recommended_hits)
            for token in OFFICIAL_PROJECTION_MODULES
        ),
        "current_config_covers_projections": any(
            any(token in hit for hit in configured_hits)
            for token in OFFICIAL_PROJECTION_MODULES
        ),
        "detected_current_projection_gap": all(
            any(token in hit for hit in recommended_hits)
            for token in OFFICIAL_PROJECTION_MODULES
        )
        and not any(
            any(token in hit for hit in configured_hits)
            for token in OFFICIAL_PROJECTION_MODULES
        ),
        "regex_scopes_away_from_vision_and_base_lm": (
            isinstance(configured_targets, str)
            and not vision_hit
            and not language_non_expert_hit
            and all(
                any(token in hit for hit in configured_hits)
                for token in OFFICIAL_PROJECTION_MODULES
            )
        ),
    }


def profile_camera_plan(
    *,
    scene_only: bool,
    include_wrist: bool,
    empty_cameras: int,
    resize_hw: tuple[int, int] = (512, 512),
) -> dict[str, Any]:
    """CPU-side accounting of visual tensors the runtime intends to feed."""
    real_cameras = ["observation.images.scene"]
    if include_wrist:
        real_cameras.append("observation.images.wrist")
    variants = {
        "scene_only": {
            "real_cameras": ["observation.images.scene"],
            "empty_cameras": empty_cameras,
        },
        "scene_plus_wrist": {
            "real_cameras": [
                "observation.images.scene",
                "observation.images.wrist",
            ],
            "empty_cameras": max(0, empty_cameras - 1),
        },
        "current_empty_padding": {
            "real_cameras": real_cameras if include_wrist else ["observation.images.scene"],
            "empty_cameras": empty_cameras,
        },
    }
    reports = {}
    for name, cfg in variants.items():
        n_real = len(cfg["real_cameras"])
        n_empty = int(cfg["empty_cameras"])
        reports[name] = {
            "real_cameras": cfg["real_cameras"],
            "empty_cameras": n_empty,
            "total_image_tensors": n_real + n_empty,
            "resize_hw": list(resize_hw),
            "approx_rgb_elements": (n_real + n_empty)
            * 3
            * resize_hw[0]
            * resize_hw[1],
            "gpu_latency_ms": None,
            "gpu_vram_mib": None,
            "empty_cameras_encoded": None,
            "notes": (
                "CPU accounting only. Set --live-gpu-profiler after human GPU "
                "approval to measure whether empty cameras are actually encoded."
            ),
        }
    active = "scene_plus_wrist" if include_wrist else "scene_only"
    if scene_only and not include_wrist:
        active = "current_empty_padding"
    return {
        "active_variant": active,
        "variants": reports,
        "passed_cpu_accounting": True,
        "passed_gpu_profiler": False,
    }


def audit_checkpoint_metadata(checkpoint_dir: Path) -> dict[str, Any]:
    config = json.loads((checkpoint_dir / "config.json").read_text(encoding="utf-8"))
    preprocessor = json.loads(
        (checkpoint_dir / "policy_preprocessor.json").read_text(encoding="utf-8")
    )
    features = {}
    rename_map: dict[str, str] = {}
    for step in preprocessor.get("steps", []):
        step_cfg = step.get("config") or {}
        if "rename_map" in step_cfg and not rename_map:
            rename_map = {
                str(src): str(dst) for src, dst in step_cfg["rename_map"].items()
            }
        if "features" in step_cfg:
            features = step_cfg["features"]
    input_features = config.get("input_features") or {}
    return {
        "checkpoint_dir": str(checkpoint_dir),
        "input_features": input_features,
        "preprocessor_features": features,
        "rename_map": rename_map,
        "empty_cameras": config.get("empty_cameras"),
        "max_state_dim": config.get("max_state_dim"),
        "max_action_dim": config.get("max_action_dim"),
        "resize_imgs_with_padding": config.get("resize_imgs_with_padding"),
        "chunk_size": config.get("chunk_size"),
        "train_state_proj": config.get("train_state_proj"),
        "freeze_vision_encoder": config.get("freeze_vision_encoder"),
        "train_expert_only": config.get("train_expert_only"),
    }


def build_mock_module_names() -> list[str]:
    names = [
        "model.vlm_with_expert.get_vision_tower.vision_model.encoder.layers.0.self_attn.q_proj.weight",
        "model.vlm_with_expert.get_vision_tower.vision_model.encoder.layers.0.self_attn.v_proj.weight",
        "model.vlm_with_expert.language_model.model.layers.0.self_attn.q_proj.weight",
        "model.vlm_with_expert.language_model.model.layers.0.self_attn.v_proj.weight",
        "model.vlm_with_expert.lm_expert.layers.0.self_attn.q_proj.weight",
        "model.vlm_with_expert.lm_expert.layers.0.self_attn.v_proj.weight",
        "model.state_proj.weight",
        "model.action_in_proj.weight",
        "model.action_out_proj.weight",
        "model.action_time_mlp_in.weight",
        "model.action_time_mlp_out.weight",
    ]
    return names


def run_mock_audit(cfg: dict[str, Any], checkpoint_dir: Path | None) -> dict[str, Any]:
    source_keys = {
        "observation.state": [7],
        "observation.ee_pose": [7],
        "observation.object_pose": [7],
        "observation.ft": [6],
        "observation.gripper": [1],
        "observation.images.scene": [3, 240, 320],
        "action": [8],
        "task": 1,
    }
    if checkpoint_dir and (checkpoint_dir / "config.json").is_file():
        meta = audit_checkpoint_metadata(checkpoint_dir)
        preprocessor_features = meta["preprocessor_features"] or meta["input_features"]
        empty_cameras = int(meta.get("empty_cameras") or 0)
        resize = tuple(meta.get("resize_imgs_with_padding") or (512, 512))
        rename_map = dict(meta.get("rename_map") or {})
    else:
        meta = {"checkpoint_dir": None, "note": "no checkpoint provided"}
        preprocessor_features = {
            "observation.state": {"type": "STATE", "shape": [6]},
            "observation.images.camera1": {"type": "VISUAL", "shape": [3, 256, 256]},
            "action": {"type": "ACTION", "shape": [8]},
        }
        empty_cameras = 2
        resize = (512, 512)
        rename_map = {"observation.images.scene": "observation.images.camera1"}

    schema = compare_schema_to_preprocessor(
        source_keys=source_keys,
        preprocessor_features=preprocessor_features,
        rename_map=rename_map,
    )
    from training.smolvla_s3.peft_targets import (
        normalize_full_training_modules,
        normalize_target_modules,
    )

    configured = normalize_target_modules(cfg["peft"]["target_modules"])
    peft = probe_peft_targets(
        build_mock_module_names(),
        configured_targets=configured,
    )
    peft["configured_full_training_modules"] = normalize_full_training_modules(
        cfg["peft"].get("full_training_modules")
    )
    peft["full_training_modules_empty"] = (
        peft["configured_full_training_modules"] == []
    )
    cameras = profile_camera_plan(
        scene_only=True,
        include_wrist=False,
        empty_cameras=empty_cameras,
        resize_hw=(int(resize[0]), int(resize[1])),
    )
    # Mock batch after naive preprocess assumptions.
    batch_keys = {
        "observation.state": {"shape": [1, 6], "note": "checkpoint-declared; source is 7"},
        "observation.images.camera1": {"shape": [1, 3, 512, 512]},
        "action": {"shape": [1, 8]},
        "task": {"type": "list"},
    }
    passed = (
        schema["state7_vs_checkpoint6"]["source_observation.state"] == [7]
        and schema["shape_mismatches"].get("observation.state") is not None
        and peft["projection_modules_present"]["state_proj"] is True
        and cameras["passed_cpu_accounting"] is True
    )
    return {
        "mode": "mock",
        "passed": passed,
        "gate": "phase0_audit_fixture_ok" if passed else "phase0_audit_fixture_failed",
        "claims_ready_for_v3_release": False,
        "claims_ready_to_train": False,
        "recommended_state_contract": RECOMMENDED_STATE15,
        "checkpoint_metadata": meta,
        "schema_audit": schema,
        "policy_input_batch_mock": batch_keys,
        "peft_probe": peft,
        "camera_profiler": cameras,
        "human_audit_required": [
            "Confirm whether Recovery adopts state[15] or another deployable vector",
            "Confirm resolved PEFT target_modules / full_training_modules",
            "Confirm scene-only vs scene+wrist after Phase 1 smoke",
            "Run live GPU profiler before claiming empty-camera cost",
        ],
    }


def run_live_peft_probe_from_checkpoint(
    checkpoint_dir: Path, cfg: dict[str, Any]
) -> dict[str, Any]:
    """Best-effort named-module probe without training."""
    try:
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy
    except Exception as exc:  # noqa: BLE001
        return {"passed": False, "reason": f"import_failed: {exc}"}

    policy = SmolVLAPolicy.from_pretrained(str(checkpoint_dir), local_files_only=True)
    root = policy.model if hasattr(policy, "model") else policy
    names = [name for name, _ in root.named_modules() if name]
    return probe_peft_targets(
        names,
        configured_targets=__import__(
            "training.smolvla_s3.peft_targets", fromlist=["normalize_target_modules"]
        ).normalize_target_modules(cfg["peft"]["target_modules"]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    parser.add_argument(
        "--mode",
        choices=("mock", "live-metadata", "live-peft-probe"),
        default="mock",
    )
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    checkpoint = args.checkpoint_dir
    if checkpoint is None and DEFAULT_V2_CHECKPOINT.is_dir():
        checkpoint = DEFAULT_V2_CHECKPOINT

    if args.mode == "mock":
        report = run_mock_audit(cfg, checkpoint)
    elif args.mode == "live-metadata":
        if checkpoint is None or not checkpoint.is_dir():
            raise SystemExit("live-metadata requires --checkpoint-dir")
        report = run_mock_audit(cfg, checkpoint)
        report["mode"] = "live-metadata"
    else:
        if checkpoint is None or not checkpoint.is_dir():
            raise SystemExit("live-peft-probe requires --checkpoint-dir")
        report = run_mock_audit(cfg, checkpoint)
        report["mode"] = "live-peft-probe"
        report["peft_probe_live"] = run_live_peft_probe_from_checkpoint(
            checkpoint, cfg
        )

    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report.get("passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
