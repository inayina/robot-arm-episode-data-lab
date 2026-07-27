"""SmolVLA S3 preflight / train control-plane library.

Thin CLI: ``training/scripts/run_smolvla_s3_control.py``.

Modes:
  --mode mock-preflight   local CI: no model weights, validates config/release/control flow
  --mode preflight        real GPU: short LoRA steps (20–50); NEVER starts full train
  --mode train            real GPU full LoRA; requires --i-understand-billing and preflight pass JSON
  --mode finalize-train   audit a finished checkpoint and write run_metadata gate
  --mode repair-checkpoint-cameras
                          strip base SmolVLA camera2/3 metadata leftovers, re-audit

Does not run Isaac. Does not overwrite S2 evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_CONFIG = ROOT / "configs" / "smolvla_s3" / "lora_train.yaml"
DEFAULT_RELEASE = ROOT / "data" / "releases" / "smolvla_s3_abs_eef_rgb_v0"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _same_float(actual: Any, expected: Any, *, atol: float = 1e-12) -> bool:
    try:
        return math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=atol)
    except (TypeError, ValueError):
        return False


def _normalize_peft_targets(raw: Any) -> list[str]:
    """Fingerprint PEFT targets without iterating a regex string as characters."""
    import sys
    from pathlib import Path

    from training.smolvla_s3.peft_targets import target_modules_fingerprint

    return target_modules_fingerprint(raw)


def _normalize_full_training_modules(raw: Any) -> list[str]:
    from training.smolvla_s3.peft_targets import normalize_full_training_modules

    return normalize_full_training_modules(raw)


def _runtime_contract(cfg: dict[str, Any]) -> dict[str, int]:
    """Resolve train chunking separately from deployed queue consumption."""
    train = cfg["train"]
    inference = cfg.get("inference") or {}
    chunk_size = int(train["action_chunk_size"])
    action_steps = int(inference.get("action_steps", chunk_size))
    empty_cameras = int(inference.get("empty_cameras", 2))
    if chunk_size < 1:
        raise ValueError("train.action_chunk_size must be >= 1")
    if not 1 <= action_steps <= chunk_size:
        raise ValueError(
            "inference.action_steps must satisfy "
            f"1 <= action_steps <= action_chunk_size ({chunk_size}), got {action_steps}"
        )
    if empty_cameras < 0:
        raise ValueError("inference.empty_cameras must be >= 0")
    return {
        "chunk_size": chunk_size,
        "action_steps": action_steps,
        "empty_cameras": empty_cameras,
    }


def _empty_camera_padding_contract(
    cfg: dict[str, Any], present_batch_features: set[str]
) -> dict[str, Any]:
    """Mirror LeRobot 0.5.1 SmolVLA missing-image padding semantics.

    ``empty_cameras`` is an upper bound on missing *configured* visual features;
    it does not append cameras when every configured visual feature is present.
    """
    input_features, _ = _policy_feature_overrides(cfg)
    configured = sorted(
        key
        for key in (input_features or {})
        if key.startswith("observation.images.")
    )
    present = sorted(key for key in configured if key in present_batch_features)
    missing = sorted(key for key in configured if key not in present_batch_features)
    limit = _runtime_contract(cfg)["empty_cameras"]
    return {
        "configured_visual_features": configured,
        "present_visual_features": present,
        "missing_visual_features": missing,
        "empty_cameras_limit": limit,
        "empty_cameras_appended": min(len(missing), limit),
    }


def _runtime_dependency_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {"python": platform.python_version()}
    for package in (
        "lerobot",
        "torch",
        "torchvision",
        "transformers",
        "peft",
        "accelerate",
        "safetensors",
    ):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def _audit_dependency_versions(
    cfg: dict[str, Any],
    observed: Mapping[str, str | None] | None = None,
) -> dict[str, Any]:
    """Fail-closed comparison against the Recovery preflight-qualified stack."""
    expected = cfg.get("dependency_versions_preflight_qualified")
    source_field = "dependency_versions_preflight_qualified"
    if not expected:
        expected = cfg.get("dependency_versions_expected") or {}
        source_field = "dependency_versions_expected"
    actual = dict(observed) if observed is not None else _runtime_dependency_versions()
    checks: dict[str, bool] = {}
    errors: dict[str, str] = {}
    try:
        from packaging.specifiers import InvalidSpecifier, SpecifierSet
        from packaging.version import InvalidVersion, Version
    except Exception as exc:  # noqa: BLE001
        return {
            "passed": False,
            "source_field": source_field,
            "expected": dict(expected),
            "observed": actual,
            "checks": checks,
            "errors": {"packaging": f"import_failed: {exc}"},
        }

    for package, specifier in expected.items():
        version = actual.get(package)
        if version is None:
            checks[package] = False
            errors[package] = "not_installed_or_not_observed"
            continue
        try:
            checks[package] = Version(str(version)) in SpecifierSet(str(specifier))
        except (InvalidSpecifier, InvalidVersion) as exc:
            checks[package] = False
            errors[package] = str(exc)
        if not checks[package] and package not in errors:
            errors[package] = f"{version!s} does not satisfy {specifier!s}"
    return {
        "passed": bool(checks) and all(checks.values()),
        "source_field": source_field,
        "expected": dict(expected),
        "observed": actual,
        "checks": checks,
        "errors": errors,
    }


def _configured_state_dim(cfg: dict[str, Any]) -> int | None:
    state = cfg.get("state_contract") or {}
    if "dim" in state:
        return int(state["dim"])
    name = str(state.get("name") or "")
    if name.startswith("observation.state[") and name.endswith("]"):
        return int(name.removeprefix("observation.state[").removesuffix("]"))
    return None


def _feature_dim(policy: Mapping[str, Any], key: str) -> int | None:
    feature = (policy.get("input_features") or {}).get(key) or {}
    shape = feature.get("shape") or []
    return int(shape[0]) if shape else None


def _preprocessor_contract(preprocessor: Mapping[str, Any]) -> dict[str, Any]:
    features: Mapping[str, Any] = {}
    rename_map: Mapping[str, Any] = {}
    for step in preprocessor.get("steps") or []:
        config = step.get("config") or {}
        if step.get("registry_name") == "normalizer_processor":
            features = config.get("features") or {}
        elif step.get("registry_name") == "rename_observations_processor":
            rename_map = config.get("rename_map") or {}
    state_shape = (features.get("observation.state") or {}).get("shape") or []
    action_shape = (features.get("action") or {}).get("shape") or []
    return {
        "state_dim": int(state_shape[0]) if state_shape else None,
        "nonempty_camera_keys": sorted(
            key
            for key in features
            if key.startswith("observation.images.") and "empty_camera_" not in key
        ),
        "action_dim": int(action_shape[0]) if action_shape else None,
        "rename_map": dict(rename_map),
    }


def _policy_feature_overrides(
    cfg: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    state_dim = _configured_state_dim(cfg)
    if state_dim is None:
        return None, None
    camera_variant = str((cfg.get("inference") or {}).get("camera_variant") or "")
    if camera_variant != "scene_only":
        raise ValueError(
            "Recovery policy feature override currently supports scene_only only"
        )
    return (
        {
            "observation.state": {"type": "STATE", "shape": [state_dim]},
            "observation.images.camera1": {
                "type": "VISUAL",
                "shape": [3, 240, 320],
            },
        },
        {"action": {"type": "ACTION", "shape": [8]}},
    )


def _checkpoint_contract(cfg: dict[str, Any]) -> dict[str, Any]:
    """Frozen fields that must survive LeRobot CLI parsing and checkpoint save."""
    peft = cfg["peft"]
    train = cfg["train"]
    runtime = _runtime_contract(cfg)
    input_override, output_override = _policy_feature_overrides(cfg)
    return {
        "peft_type": str(peft["method_type"]).upper(),
        "r": int(peft["r"]),
        "lora_alpha": int(peft["lora_alpha"]),
        "lora_dropout": float(peft["lora_dropout"]),
        "bias": str(peft.get("bias", "none")),
        "target_modules": _normalize_peft_targets(peft["target_modules"]),
        "full_training_modules": _normalize_full_training_modules(
            peft.get("full_training_modules")
        ),
        "optimizer_lr": float(train["learning_rate"]),
        "optimizer_weight_decay": float(train["weight_decay"]),
        "optimizer_grad_clip_norm": float(train["max_grad_norm"]),
        "scheduler_warmup_steps": int(train["lr_warmup_steps"]),
        "scheduler_type": str(train["lr_scheduler"]),
        "steps": int(train["max_steps"]),
        "batch_size": int(train["batch_size"]),
        "seed": int(train["seed"]),
        "log_freq": int(train["logging_steps"]),
        "eval_freq": int(train["eval_every_steps"]),
        "save_freq": int(train["save_every_steps"]),
        "num_workers": int(train["dataloader_workers"]),
        "chunk_size": runtime["chunk_size"],
        "n_action_steps": runtime["action_steps"],
        "empty_cameras": runtime["empty_cameras"],
        "observation_state_dim": _configured_state_dim(cfg),
        "nonempty_camera_keys": (
            sorted(
                key
                for key in (input_override or {})
                if key.startswith("observation.images.")
            )
            if input_override is not None
            else None
        ),
        "action_dim": (
            int(output_override["action"]["shape"][0])
            if output_override is not None
            else None
        ),
    }


def audit_trained_checkpoint(
    cfg: dict[str, Any], checkpoint_dir: Path
) -> dict[str, Any]:
    """Fail closed when a saved LeRobot checkpoint drifted from frozen S3 config."""
    required = {
        "adapter_config": checkpoint_dir / "adapter_config.json",
        "policy_config": checkpoint_dir / "config.json",
        "train_config": checkpoint_dir / "train_config.json",
        "adapter_weights": checkpoint_dir / "adapter_model.safetensors",
        "policy_preprocessor": checkpoint_dir / "policy_preprocessor.json",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        return {
            "passed": False,
            "checkpoint_dir": str(checkpoint_dir),
            "missing": missing,
            "checks": {},
            "reason": "missing_checkpoint_artifacts",
        }

    expected = _checkpoint_contract(cfg)
    adapter = _json_file(required["adapter_config"])
    policy = _json_file(required["policy_config"])
    train = _json_file(required["train_config"])
    preprocessor = _preprocessor_contract(
        _json_file(required["policy_preprocessor"])
    )
    train_peft = train.get("peft") or {}
    train_policy = train.get("policy") or {}
    optimizer = train.get("optimizer") or {}
    scheduler = train.get("scheduler") or {}

    actual = {
        "peft_type": str(adapter.get("peft_type") or train_peft.get("method_type", "")).upper(),
        "r": adapter.get("r"),
        "lora_alpha": adapter.get("lora_alpha"),
        "lora_dropout": adapter.get("lora_dropout"),
        "bias": adapter.get("bias"),
        "target_modules": _normalize_peft_targets(adapter.get("target_modules") or []),
        "full_training_modules": _normalize_full_training_modules(
            adapter.get("modules_to_save")
            or train_peft.get("full_training_modules")
            or []
        ),
        "optimizer_lr": policy.get("optimizer_lr", optimizer.get("lr")),
        "optimizer_weight_decay": policy.get(
            "optimizer_weight_decay", optimizer.get("weight_decay")
        ),
        "optimizer_grad_clip_norm": policy.get(
            "optimizer_grad_clip_norm", optimizer.get("grad_clip_norm")
        ),
        "scheduler_warmup_steps": policy.get(
            "scheduler_warmup_steps", scheduler.get("num_warmup_steps")
        ),
        "scheduler_type": scheduler.get("type"),
        "steps": train.get("steps"),
        "batch_size": train.get("batch_size"),
        "seed": train.get("seed"),
        "log_freq": train.get("log_freq"),
        "eval_freq": train.get("eval_freq"),
        "save_freq": train.get("save_freq"),
        "num_workers": train.get("num_workers"),
        "chunk_size": policy.get("chunk_size", train_policy.get("chunk_size")),
        "n_action_steps": policy.get(
            "n_action_steps", train_policy.get("n_action_steps")
        ),
        "empty_cameras": policy.get(
            "empty_cameras", train_policy.get("empty_cameras")
        ),
        "observation_state_dim": _feature_dim(policy, "observation.state"),
        "nonempty_camera_keys": sorted(
            key
            for key in (policy.get("input_features") or {})
            if key.startswith("observation.images.") and "empty_camera_" not in key
        ),
        "action_dim": _feature_dim(policy, "action")
        or _feature_dim({"input_features": policy.get("output_features")}, "action"),
        "preprocessor_observation_state_dim": preprocessor["state_dim"],
        "preprocessor_nonempty_camera_keys": preprocessor[
            "nonempty_camera_keys"
        ],
        "preprocessor_action_dim": preprocessor["action_dim"],
        "preprocessor_rename_map": preprocessor["rename_map"],
    }
    checks = {
        "peft_type": actual["peft_type"] == expected["peft_type"],
        "r": actual["r"] == expected["r"],
        "lora_alpha": actual["lora_alpha"] == expected["lora_alpha"],
        "lora_dropout": _same_float(actual["lora_dropout"], expected["lora_dropout"]),
        "bias": actual["bias"] == expected["bias"],
        "target_modules": actual["target_modules"] == expected["target_modules"],
        "full_training_modules": actual["full_training_modules"]
        == expected["full_training_modules"],
        "optimizer_lr": _same_float(actual["optimizer_lr"], expected["optimizer_lr"]),
        "optimizer_weight_decay": _same_float(
            actual["optimizer_weight_decay"], expected["optimizer_weight_decay"]
        ),
        "optimizer_grad_clip_norm": _same_float(
            actual["optimizer_grad_clip_norm"], expected["optimizer_grad_clip_norm"]
        ),
        "scheduler_warmup_steps": (
            actual["scheduler_warmup_steps"] == expected["scheduler_warmup_steps"]
        ),
        "scheduler_type": str(actual["scheduler_type"] or "").startswith(
            expected["scheduler_type"]
        ),
        "steps": actual["steps"] == expected["steps"],
        "batch_size": actual["batch_size"] == expected["batch_size"],
        "seed": actual["seed"] == expected["seed"],
        "log_freq": actual["log_freq"] == expected["log_freq"],
        "eval_freq": actual["eval_freq"] == expected["eval_freq"],
        "save_freq": actual["save_freq"] == expected["save_freq"],
        "num_workers": actual["num_workers"] == expected["num_workers"],
        "chunk_size": actual["chunk_size"] == expected["chunk_size"],
        "n_action_steps": actual["n_action_steps"] == expected["n_action_steps"],
        "empty_cameras": actual["empty_cameras"] == expected["empty_cameras"],
    }
    if expected["observation_state_dim"] is not None:
        checks["observation_state_dim"] = (
            actual["observation_state_dim"] == expected["observation_state_dim"]
        )
        checks["nonempty_camera_keys"] = (
            actual["nonempty_camera_keys"] == expected["nonempty_camera_keys"]
        )
        checks["action_dim"] = actual["action_dim"] == expected["action_dim"]
        checks["preprocessor_observation_state_dim"] = (
            actual["preprocessor_observation_state_dim"]
            == expected["observation_state_dim"]
        )
        checks["preprocessor_nonempty_camera_keys"] = (
            actual["preprocessor_nonempty_camera_keys"]
            == expected["nonempty_camera_keys"]
        )
        checks["preprocessor_action_dim"] = (
            actual["preprocessor_action_dim"] == expected["action_dim"]
        )
        checks["preprocessor_rename_map"] = (
            actual["preprocessor_rename_map"].get("observation.images.scene")
            == "observation.images.camera1"
        )
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not failures,
        "checkpoint_dir": str(checkpoint_dir),
        "adapter_model_sha256": _sha256_file(required["adapter_weights"]),
        "expected": expected,
        "actual": actual,
        "checks": checks,
        "failures": failures,
        "reason": None if not failures else "checkpoint_config_drift",
    }


def repair_checkpoint_camera_contract(
    cfg: dict[str, Any], checkpoint_dir: Path, *, write: bool = True
) -> dict[str, Any]:
    """Strip base-SmolVLA camera2/3 leftovers from saved JSON (metadata only).

    Safe when adapter weights and preprocessor safetensors never consumed those
    cameras (Recovery ``empty_cameras=0`` + scene-only batch). Does not modify
    ``adapter_model.safetensors``.
    """
    from training.smolvla_s3.policy_features import (
        apply_feature_contract,
        image_feature_keys,
    )

    input_contract, output_contract = _policy_feature_overrides(cfg)
    if input_contract is None or output_contract is None:
        raise ValueError(
            "repair_checkpoint_camera_contract requires Recovery feature overrides"
        )
    feature_contract = {**input_contract, **output_contract}
    required = {
        "policy_config": checkpoint_dir / "config.json",
        "train_config": checkpoint_dir / "train_config.json",
        "policy_preprocessor": checkpoint_dir / "policy_preprocessor.json",
        "adapter_weights": checkpoint_dir / "adapter_model.safetensors",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        return {
            "passed": False,
            "reason": "missing_checkpoint_artifacts",
            "missing": missing,
            "checkpoint_dir": str(checkpoint_dir),
        }

    adapter_sha_before = _sha256_file(required["adapter_weights"])
    removed: dict[str, list[str]] = {}
    rewritten: dict[str, Any] = {}

    policy = _json_file(required["policy_config"])
    new_input, removed_policy = apply_feature_contract(
        policy.get("input_features") or {}, input_contract
    )
    policy["input_features"] = new_input
    if output_contract:
        policy["output_features"] = dict(output_contract)
    removed["config.json"] = removed_policy
    rewritten["config.json"] = policy

    train = _json_file(required["train_config"])
    train_policy = dict(train.get("policy") or {})
    new_train_input, removed_train = apply_feature_contract(
        train_policy.get("input_features") or {}, input_contract
    )
    train_policy["input_features"] = new_train_input
    if output_contract:
        train_policy["output_features"] = dict(output_contract)
    train["policy"] = train_policy
    removed["train_config.json"] = removed_train
    rewritten["train_config.json"] = train

    preprocessor = _json_file(required["policy_preprocessor"])
    removed_pre: list[str] = []
    for step in preprocessor.get("steps") or []:
        if step.get("registry_name") != "normalizer_processor":
            continue
        config = step.setdefault("config", {})
        new_feats, step_removed = apply_feature_contract(
            config.get("features") or {}, feature_contract
        )
        config["features"] = new_feats
        removed_pre.extend(step_removed)
    removed["policy_preprocessor.json"] = sorted(set(removed_pre))
    rewritten["policy_preprocessor.json"] = preprocessor

    expected_cams = image_feature_keys(input_contract)
    actual_after = {
        "config.json": image_feature_keys(policy.get("input_features")),
        "train_config.json": image_feature_keys(train_policy.get("input_features")),
        "policy_preprocessor.json": image_feature_keys(
            next(
                (
                    (step.get("config") or {}).get("features")
                    for step in (preprocessor.get("steps") or [])
                    if step.get("registry_name") == "normalizer_processor"
                ),
                {},
            )
        ),
    }
    cameras_ok = all(cams == expected_cams for cams in actual_after.values())
    report: dict[str, Any] = {
        "passed": cameras_ok,
        "checkpoint_dir": str(checkpoint_dir),
        "adapter_model_sha256_before": adapter_sha_before,
        "expected_nonempty_camera_keys": expected_cams,
        "removed_image_keys": removed,
        "actual_nonempty_camera_keys_after": actual_after,
        "wrote": False,
        "reason": None if cameras_ok else "camera_contract_not_met_after_repair",
        "repair_kind": "metadata_strip_base_smolvla_cameras",
        "safe_rationale": (
            "Adapter tensors are LoRA-only (no per-camera weights). "
            "Preprocessor safetensors retain scene stats only. "
            "LeRobot prepare_images with empty_cameras=0 never padded missing "
            "camera2/3 during Recovery train; leftover keys are base-config "
            "draccus merge artifacts."
        ),
    }
    if not cameras_ok:
        return report
    if write:
        for name, payload in rewritten.items():
            path = checkpoint_dir / name
            backup = path.with_suffix(path.suffix + ".bak_camera_repair")
            if not backup.is_file():
                backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        report["wrote"] = True
        report["adapter_model_sha256_after"] = _sha256_file(required["adapter_weights"])
        if report["adapter_model_sha256_after"] != adapter_sha_before:
            report["passed"] = False
            report["reason"] = "adapter_sha_changed_unexpectedly"
    return report


def finalize_train_run(
    cfg: dict[str, Any], out_dir: Path, checkpoint_dir: Path, config_path: Path
) -> dict[str, Any]:
    """Record process completion and checkpoint-contract verification."""
    metadata_path = out_dir / "run_metadata.json"
    meta = _json_file(metadata_path) if metadata_path.is_file() else {"mode": "train"}
    audit = audit_trained_checkpoint(cfg, checkpoint_dir)
    meta.update(
        {
            "executed": True,
            "completed": True,
            "ready_to_execute": False,
            "execution_requested": True,
            "passed": bool(audit["passed"]),
            "gate": "checkpoint_config_verified" if audit["passed"] else "no_go",
            "config_sha256": _sha256_file(config_path),
            "checkpoint_dir": str(checkpoint_dir),
            "checkpoint_audit": audit,
            "base_checkpoint_revision": os.environ.get(
                "SMOLVLA_BASE_REVISION", cfg["base_checkpoint"].get("revision")
            ),
            "completed_at": _utc_stamp(),
        }
    )
    if not audit["passed"]:
        meta["reason"] = audit["reason"]
    else:
        meta.pop("reason", None)
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return meta


def _validate_release(release_dir: Path) -> dict[str, Any]:
    mod_path = ROOT / "training" / "scripts" / "validate_smolvla_s3_release.py"
    spec = importlib.util.spec_from_file_location("validate_smolvla_s3_release", mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {mod_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.validate_release(release_dir)


def run_mock_preflight(cfg: dict[str, Any], release_dir: Path, out_dir: Path) -> dict[str, Any]:
    rel = _validate_release(release_dir)
    if not rel["passed"]:
        return {
            "mode": "mock-preflight",
            "passed": False,
            "gate": "no_go",
            "reason": "release_validation_failed",
            "release_report": rel,
            "distinction": "MOCK_ONLY — not a real GPU preflight",
        }

    peft = cfg["peft"]
    train = cfg["train"]
    checks = {
        "config_parsed": True,
        "release_ok": True,
        "lora_r": peft["r"] == 64,
        "lora_alpha": peft["lora_alpha"] == 64,
        "no_arch_change": bool(train["no_architecture_change"]),
        "no_new_loss": bool(train["no_new_loss"]),
        "no_auto_hparam_search": bool(train["no_auto_hparam_search"]),
        "seed_fixed": train["seed"] == 42,
        "forbid_auto_train": bool(cfg["gates"]["forbid_auto_start_train_from_preflight"]),
        "human_confirm_required": bool(cfg["gates"]["require_human_confirm_for_full_train"]),
        "preflight_subset_present": (release_dir / "preflight_subset.json").is_file(),
    }
    # Simulated LoRA update bookkeeping (no tensors)
    fake_lora_before = {"adapter.weight": 0.0}
    fake_lora_after = {"adapter.weight": 1.0e-3}
    lora_updated = fake_lora_after != fake_lora_before

    report = {
        "mode": "mock-preflight",
        "passed": all(checks.values()) and lora_updated,
        "gate": "mock_pass" if all(checks.values()) else "no_go",
        "distinction": "MOCK_ONLY — control-flow validated; real GPU preflight still required on AutoDL",
        "checks": checks,
        "simulated": {
            "forward_backward": "mocked_ok",
            "loss_finite": True,
            "oom": False,
            "lora_params_updated": lora_updated,
            "checkpoint_save_reload": "mocked_ok",
            "peak_vram_mib": None,
            "step_time_ms": None,
        },
        "config_sha256": _sha256_file(Path(os.environ.get("S3_CONFIG", str(DEFAULT_CONFIG)))),
        "release_id": rel.get("release_id"),
        "release_report": rel,
        "created_at": _utc_stamp(),
        "real_gpu_preflight_required": True,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "preflight_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def run_real_preflight(
    cfg: dict[str, Any],
    release_dir: Path,
    out_dir: Path,
    steps: int,
    config_path: Path,
) -> dict[str, Any]:
    """Real short LoRA loop. Fail closed if imports/GPU/data unavailable."""
    rel = _validate_release(release_dir)
    if not rel["passed"]:
        return {
            "mode": "preflight",
            "passed": False,
            "gate": "no_go",
            "reason": "release_validation_failed",
            "release_report": rel,
        }

    dependency_audit = _audit_dependency_versions(cfg)
    if bool(cfg.get("gates", {}).get("require_dependency_version_match")) and not bool(
        dependency_audit["passed"]
    ):
        return {
            "mode": "preflight",
            "passed": False,
            "gate": "no_go",
            "reason": "dependency_version_mismatch",
            "dependency_version_audit": dependency_audit,
            "distinction": "REAL_GPU_PREFLIGHT_NOT_STARTED",
        }

    try:
        import torch
        from peft import LoraConfig, get_peft_model
    except Exception as exc:  # noqa: BLE001
        return {
            "mode": "preflight",
            "passed": False,
            "gate": "no_go",
            "reason": f"import_failed: {exc}",
            "distinction": "REAL_GPU_PREFLIGHT_ATTEMPTED",
        }

    if not torch.cuda.is_available():
        return {
            "mode": "preflight",
            "passed": False,
            "gate": "no_go",
            "reason": "cuda_unavailable",
            "distinction": "REAL_GPU_PREFLIGHT_ATTEMPTED",
        }

    # Resolve PEFT against the complete policy when weights are present. The official
    # SmolVLA regex starts with ``model.`` and therefore must not be applied to
    # ``policy.model`` with that prefix stripped.
    base_dir = Path(os.environ.get("SMOLVLA_BASE_DIR", ROOT / "checkpoints" / "smolvla_base_s3"))
    used_full_model = False
    peak_before = torch.cuda.max_memory_allocated() / (1024**2)
    torch.cuda.reset_peak_memory_stats()
    device = torch.device("cuda")

    try:
        if base_dir.is_dir() and any(base_dir.iterdir()):
            from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

            policy = SmolVLAPolicy.from_pretrained(str(base_dir))
            used_full_model = True
            model = policy
        else:
            # Stand-in mirrors the official target paths. It proves only the GPU/PEFT
            # stack; a Recovery live-resolve gate still requires full weights.
            class TinyExpertLayer(torch.nn.Module):
                def __init__(self):
                    super().__init__()
                    self.q_proj = torch.nn.Linear(32, 32)
                    self.v_proj = torch.nn.Linear(32, 32)

            class TinyExpert(torch.nn.Module):
                def __init__(self):
                    super().__init__()
                    self.layers = torch.nn.ModuleList([TinyExpertLayer()])

            class TinyVlmWithExpert(torch.nn.Module):
                def __init__(self):
                    super().__init__()
                    self.lm_expert = TinyExpert()

            class TinyModel(torch.nn.Module):
                def __init__(self):
                    super().__init__()
                    self.vlm_with_expert = TinyVlmWithExpert()
                    self.state_proj = torch.nn.Linear(32, 32)
                    self.action_in_proj = torch.nn.Linear(32, 32)
                    self.action_out_proj = torch.nn.Linear(32, 8)
                    self.action_time_mlp_in = torch.nn.Linear(32, 32)
                    self.action_time_mlp_out = torch.nn.Linear(32, 32)

            class Tiny(torch.nn.Module):
                def __init__(self):
                    super().__init__()
                    self.model = TinyModel()

            model = Tiny()

        target_modules = _normalize_peft_targets(cfg["peft"]["target_modules"])
        if len(target_modules) == 1 and "(" in target_modules[0]:
            lora_targets: Any = target_modules[0]
        else:
            lora_targets = target_modules
        lora_cfg = LoraConfig(
            r=int(cfg["peft"]["r"]),
            lora_alpha=int(cfg["peft"]["lora_alpha"]),
            lora_dropout=float(cfg["peft"]["lora_dropout"]),
            target_modules=lora_targets,
            bias=cfg["peft"].get("bias", "none"),
            modules_to_save=(
                _normalize_full_training_modules(
                    cfg["peft"].get("full_training_modules")
                )
                or None
            ),
        )
        model = get_peft_model(model, lora_cfg).to(device)
        trainable_names = [
            name for name, parameter in model.named_parameters() if parameter.requires_grad
        ]
        if not trainable_names:
            raise RuntimeError("PEFT resolved zero trainable parameters")
        before = {
            n: p.detach().float().cpu().clone()
            for n, p in model.named_parameters()
            if p.requires_grad
        }
        opt = torch.optim.AdamW(
            [p for p in model.parameters() if p.requires_grad],
            lr=float(cfg["train"]["learning_rate"]),
        )
        losses = []
        t0 = time.perf_counter()
        for step in range(steps):
            # This probe intentionally avoids inventing a fake SmolVLA observation.
            # It validates target resolution, CUDA backward/optimizer, and adapter
            # serialization. Policy forward/latency has a separate inference probe.
            loss = sum(
                parameter.float().mean()
                for parameter in model.parameters()
                if parameter.requires_grad
            )
            if not torch.isfinite(loss):
                raise RuntimeError("non-finite loss")
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))
        step_ms = (time.perf_counter() - t0) * 1000.0 / max(steps, 1)
        after = {
            n: p.detach().float().cpu()
            for n, p in model.named_parameters()
            if p.requires_grad
        }
        updated = any(
            not torch.allclose(before[n], after[n]) for n in before
        )
        ckpt = out_dir / "preflight_adapter"
        out_dir.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(ckpt)
        reload_ok = (ckpt / "adapter_config.json").is_file() and any(
            (ckpt / name).is_file()
            for name in ("adapter_model.safetensors", "adapter_model.bin")
        )
        peak = torch.cuda.max_memory_allocated() / (1024**2)
        live_resolve_passed = bool(used_full_model and trainable_names)
        input_features, _ = _policy_feature_overrides(cfg)
        declared_present_visuals = {
            key
            for key in (input_features or {})
            if key.startswith("observation.images.")
        }
        report = {
            "mode": "preflight",
            "passed": bool(updated and reload_ok and all(math_isfinite(l) for l in losses)),
            "gate": "pass" if updated and reload_ok else "no_go",
            "distinction": "REAL_GPU_PREFLIGHT",
            "used_full_smolvla_weights": used_full_model,
            "probe_kind": "peft_target_resolve_parameter_update_and_adapter_save",
            "policy_forward_executed": False,
            "inference_latency_measured": False,
            "live_peft_resolve_probe_passed": live_resolve_passed,
            "resolved_trainable_parameter_names": trainable_names,
            "resolved_trainable_parameter_count": len(trainable_names),
            "steps": steps,
            "loss_last": losses[-1] if losses else None,
            "loss_finite": all(math_isfinite(l) for l in losses),
            "oom": False,
            "lora_params_updated": updated,
            "checkpoint_path": str(ckpt),
            "adapter_save_ok": reload_ok,
            "peak_vram_mib": peak,
            "step_time_ms_mean": step_ms,
            "gpu_name": torch.cuda.get_device_name(0),
            "torch_version": torch.__version__,
            "dependency_version_audit": dependency_audit,
            "empty_camera_padding_contract": _empty_camera_padding_contract(
                cfg, declared_present_visuals
            ),
            "config_sha256": _sha256_file(config_path),
            "release_id": rel.get("release_id"),
            "release_report": rel,
            "created_at": _utc_stamp(),
            "must_not_auto_start_full_train": True,
            "note": (
                "This preflight validates PEFT target resolution, CUDA parameter "
                "updates, and adapter save. It does not execute policy forward or "
                "measure inference latency. Recovery requires full SmolVLA weights "
                "for live_peft_resolve_probe_passed=true."
            ),
        }
        (out_dir / "preflight_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return report
    except torch.cuda.OutOfMemoryError:
        return {
            "mode": "preflight",
            "passed": False,
            "gate": "no_go",
            "reason": "oom",
            "distinction": "REAL_GPU_PREFLIGHT",
            "oom": True,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "mode": "preflight",
            "passed": False,
            "gate": "no_go",
            "reason": str(exc),
            "distinction": "REAL_GPU_PREFLIGHT",
        }


def math_isfinite(x: float) -> bool:
    return x == x and abs(x) != float("inf")


def run_train_guarded(
    cfg: dict[str, Any],
    release_dir: Path,
    out_dir: Path,
    preflight_report: Path,
    confirm: bool,
    config_path: Path,
) -> dict[str, Any]:
    if cfg.get("authorized_to_train") is False:
        return {
            "mode": "train",
            "passed": False,
            "gate": "no_go",
            "reason": "config_not_authorized_to_train",
            "executed": False,
        }
    if int(cfg["train"]["max_steps"]) < 1:
        return {
            "mode": "train",
            "passed": False,
            "gate": "no_go",
            "reason": "train.max_steps_not_resolved",
            "executed": False,
        }
    if not confirm:
        return {
            "mode": "train",
            "passed": False,
            "gate": "no_go",
            "reason": "missing --i-understand-billing human confirm",
        }
    if not preflight_report.is_file():
        return {
            "mode": "train",
            "passed": False,
            "gate": "no_go",
            "reason": "missing preflight_report.json",
        }
    pref = json.loads(preflight_report.read_text(encoding="utf-8"))
    if pref.get("mode") == "mock-preflight":
        return {
            "mode": "train",
            "passed": False,
            "gate": "no_go",
            "reason": "mock preflight cannot authorize real train",
        }
    if not pref.get("passed"):
        return {
            "mode": "train",
            "passed": False,
            "gate": "no_go",
            "reason": "preflight did not pass",
        }
    if bool(cfg.get("gates", {}).get("require_live_peft_resolve_probe")) and not bool(
        pref.get("live_peft_resolve_probe_passed")
    ):
        return {
            "mode": "train",
            "passed": False,
            "gate": "no_go",
            "reason": "live_peft_resolve_probe_not_passed",
        }
    if bool(cfg.get("gates", {}).get("require_dependency_version_match")) and not bool(
        (pref.get("dependency_version_audit") or {}).get("passed")
    ):
        return {
            "mode": "train",
            "passed": False,
            "gate": "no_go",
            "reason": "preflight_dependency_version_audit_not_passed",
        }
    if bool(
        cfg.get("gates", {}).get("require_preflight_config_sha256_match")
    ) and pref.get("config_sha256") != _sha256_file(config_path):
        return {
            "mode": "train",
            "passed": False,
            "gate": "no_go",
            "reason": "preflight_config_sha256_mismatch",
        }
    rel = _validate_release(release_dir)
    if not rel["passed"]:
        return {
            "mode": "train",
            "passed": False,
            "gate": "no_go",
            "reason": "release_validation_failed",
            "release_report": rel,
        }

    # Emit a frozen run metadata + exact command template; do not start long training
    # from this local S3 Ready pass unless SMOLVLA_S3_EXECUTE_TRAIN=1.
    out_dir.mkdir(parents=True, exist_ok=True)
    train_root = os.environ.get("S3_DATASET_ROOT")
    train_root_meta: dict[str, Any] = {
        "S3_DATASET_ROOT": train_root,
        "train_root_validated": False,
    }
    if train_root:
        merge_path = Path(__file__).resolve().parent / "prepare_smolvla_s3_merged_v30.py"
        spec = importlib.util.spec_from_file_location(
            "prepare_smolvla_s3_merged_v30", merge_path
        )
        assert spec and spec.loader
        merge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(merge)
        train_report = merge.validate_train_root_against_splits(
            Path(train_root).resolve(),
            (release_dir / "splits.json").resolve(),
            include_split=os.environ.get("S3_INCLUDE_SPLIT", "train"),
        )
        train_root_meta = {
            "S3_DATASET_ROOT": train_root,
            "train_root_validated": bool(train_report.get("passed")),
            "splits_sha256": train_report.get("splits_sha256"),
            "episode_refs": train_report.get("episode_refs"),
            "num_episodes": train_report.get("actual_num_episodes"),
            "validation_benchmark_intersection": train_report.get(
                "validation_benchmark_intersection"
            ),
            "train_root_report": train_report,
        }
        if not train_report.get("passed"):
            return {
                "mode": "train",
                "passed": False,
                "gate": "no_go",
                "reason": "train_root_split_validation_failed",
                "train_root": train_root_meta,
            }

    from training.smolvla_s3.peft_targets import (
        normalize_full_training_modules,
        normalize_target_modules,
        target_modules_for_cli,
    )

    peft_targets_cli = target_modules_for_cli(cfg["peft"]["target_modules"])
    peft_full_cli = json.dumps(
        normalize_full_training_modules(cfg["peft"].get("full_training_modules"))
    )
    runtime = _runtime_contract(cfg)
    policy_input_override, policy_output_override = _policy_feature_overrides(cfg)
    policy_feature_cli = ""
    if policy_input_override is not None and policy_output_override is not None:
        in_json = json.dumps(policy_input_override, separators=(",", ":"))
        out_json = json.dumps(policy_output_override, separators=(",", ":"))
        policy_feature_cli = (
            f"--s3-policy-input-features={in_json} "
            f"--s3-policy-output-features={out_json} "
            f"--policy.input_features={in_json} "
            f"--policy.output_features={out_json} "
        )
    # Sanity: regex must remain one string for LeRobot, not character list.
    _normalized_targets = normalize_target_modules(cfg["peft"]["target_modules"])
    if isinstance(_normalized_targets, str) and len(_normalized_targets) < 8:
        raise ValueError("peft.target_modules regex looks truncated")

    meta = {
        "mode": "train",
        "executed": False,
        "ready_to_execute": True,
        "gate": "awaiting_autodl_execute",
        "release_id": rel.get("release_id"),
        "config_sha256": _sha256_file(config_path),
        "seed": cfg["train"]["seed"],
        "max_steps": cfg["train"]["max_steps"],
        "output_dir": str(out_dir),
        "preflight_report": str(preflight_report),
        "train_root": train_root_meta,
        "base_checkpoint_revision": os.environ.get(
            "SMOLVLA_BASE_REVISION", cfg["base_checkpoint"].get("revision")
        ),
        "command_template": (
            f"ACCELERATE_MIXED_PRECISION={cfg['train']['precision']} "
            f"S3_LORA_ALPHA={cfg['peft']['lora_alpha']} "
            f"S3_LORA_DROPOUT={cfg['peft']['lora_dropout']} "
            f"S3_LORA_BIAS={cfg['peft']['bias']} "
            f"python3 training/scripts/lerobot_train_with_peft_overrides.py "
            f"--s3-lora-alpha={cfg['peft']['lora_alpha']} "
            f"--s3-lora-dropout={cfg['peft']['lora_dropout']} "
            f"--s3-lora-bias={cfg['peft']['bias']} "
            f"--policy.path={cfg['base_checkpoint']['model_id']} "
            f"--dataset.root=$S3_DATASET_ROOT "
            f"--batch_size={cfg['train']['batch_size']} "
            f"--steps={cfg['train']['max_steps']} "
            f"--seed={cfg['train']['seed']} "
            f"--num_workers={cfg['train']['dataloader_workers']} "
            f"--log_freq={cfg['train']['logging_steps']} "
            f"--eval_freq={cfg['train']['eval_every_steps']} "
            f"--save_freq={cfg['train']['save_every_steps']} "
            f"--policy.optimizer_lr={cfg['train']['learning_rate']} "
            f"--policy.optimizer_weight_decay={cfg['train']['weight_decay']} "
            f"--policy.optimizer_grad_clip_norm={cfg['train']['max_grad_norm']} "
            f"--policy.scheduler_warmup_steps={cfg['train']['lr_warmup_steps']} "
            f"--policy.chunk_size={runtime['chunk_size']} "
            f"--policy.n_action_steps={runtime['action_steps']} "
            f"--policy.empty_cameras={runtime['empty_cameras']} "
            f"{policy_feature_cli}"
            f"--peft.method_type={cfg['peft']['method_type']} "
            f"--peft.r={cfg['peft']['r']} "
            f"--peft.target_modules={peft_targets_cli} "
            f"--peft.full_training_modules={peft_full_cli} "
            f"--output_dir={out_dir}/lerobot_run"
        ),
        "note": (
            "Local S3 Ready does not start billing train. "
            "On AutoDL set SMOLVLA_S3_EXECUTE_TRAIN=1 after human approval. "
            "S3_DATASET_ROOT must be a train-only root with train_root_provenance.json."
        ),
        "created_at": _utc_stamp(),
    }
    if os.environ.get("SMOLVLA_S3_EXECUTE_TRAIN") == "1":
        meta["execution_requested"] = True
        meta["gate"] = "launch_authorized"
        meta["passed"] = True
        meta["reason"] = (
            "Control-plane authorization only; scripts/run_smolvla_s3_train.sh "
            "must finalize metadata after checkpoint audit."
        )
    else:
        meta["execution_requested"] = False
        meta["passed"] = True  # control-plane ready
    (out_dir / "run_metadata.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=[
            "mock-preflight",
            "preflight",
            "train",
            "finalize-train",
            "repair-checkpoint-cameras",
        ],
        required=True,
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--steps", type=int, default=32)
    parser.add_argument(
        "--i-understand-billing",
        action="store_true",
        help="Required for --mode train (human confirm).",
    )
    parser.add_argument(
        "--preflight-report",
        type=Path,
        default=None,
        help="Path to successful REAL preflight_report.json for train mode.",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=None,
        help="Saved pretrained_model directory for --mode finalize-train / repair-checkpoint-cameras.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="For repair-checkpoint-cameras: compute strip plan without writing.",
    )
    args = parser.parse_args()
    os.environ["S3_CONFIG"] = str(args.config)
    cfg = _load_config(args.config)
    stamp = _utc_stamp()
    if args.output_dir is None:
        if args.mode in {"train", "finalize-train", "repair-checkpoint-cameras"}:
            args.output_dir = ROOT / "runs" / "smolvla_s3" / f"train_{stamp}"
        else:
            args.output_dir = ROOT / "runs" / "smolvla_s3" / f"preflight_{stamp}"

    if args.mode == "mock-preflight":
        report = run_mock_preflight(cfg, args.release_dir, args.output_dir)
    elif args.mode == "preflight":
        if args.steps < 20 or args.steps > 50:
            raise SystemExit("--steps for preflight must be in [20, 50]")
        report = run_real_preflight(
            cfg, args.release_dir, args.output_dir, args.steps, args.config
        )
    elif args.mode == "train":
        pref = args.preflight_report or (args.output_dir / "preflight_report.json")
        report = run_train_guarded(
            cfg,
            args.release_dir,
            args.output_dir,
            pref,
            args.i_understand_billing,
            args.config,
        )
    elif args.mode == "repair-checkpoint-cameras":
        if args.checkpoint_dir is None:
            raise SystemExit(
                "--checkpoint-dir is required for --mode repair-checkpoint-cameras"
            )
        repair = repair_checkpoint_camera_contract(
            cfg, args.checkpoint_dir, write=not args.dry_run
        )
        audit = None
        if repair.get("passed") and repair.get("wrote"):
            audit = audit_trained_checkpoint(cfg, args.checkpoint_dir)
            (args.output_dir).mkdir(parents=True, exist_ok=True)
            (args.output_dir / "checkpoint_camera_repair.json").write_text(
                json.dumps(
                    {"repair": repair, "checkpoint_audit": audit},
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            if audit.get("passed"):
                finalize_train_run(
                    cfg, args.output_dir, args.checkpoint_dir, args.config
                )
        report = {
            "mode": "repair-checkpoint-cameras",
            "passed": bool(repair.get("passed"))
            and (audit is None or bool(audit.get("passed"))),
            "gate": (
                "checkpoint_config_verified"
                if audit and audit.get("passed")
                else ("repair_planned" if args.dry_run and repair.get("passed") else "no_go")
            ),
            "repair": repair,
            "checkpoint_audit": audit,
        }
    else:
        if args.checkpoint_dir is None:
            raise SystemExit("--checkpoint-dir is required for --mode finalize-train")
        report = finalize_train_run(
            cfg, args.output_dir, args.checkpoint_dir, args.config
        )

    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.mode == "mock-preflight":
        return 0 if report.get("passed") else 2
    if args.mode == "preflight":
        return 0 if report.get("passed") else 2
    if args.mode == "repair-checkpoint-cameras":
        return 0 if report.get("passed") else 2
    # Train authorization/finalization must both fail closed.
    return 0 if report.get("passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
