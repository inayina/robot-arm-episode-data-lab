"""Regression tests for the formal SmolVLA S3 train and open-loop entrypoints."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "smolvla_s3" / "lora_train.yaml"
RELEASE = ROOT / "data" / "releases" / "smolvla_s3_abs_eef_rgb_v0"


def _load_module(name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTROL = _load_module(
    "run_smolvla_s3_control_test", "training/smolvla_s3/control_plane.py"
)
OPEN_LOOP = _load_module(
    "run_smolvla_s3_open_loop_test", "training/smolvla_s3/open_loop_eval.py"
)
RECOMPUTE = _load_module(
    "recompute_smolvla_s3_saved_open_loop_test",
    "training/scripts/recompute_smolvla_s3_saved_open_loop.py",
)


def _config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _write_checkpoint_fixture(root: Path, cfg: dict) -> Path:
    checkpoint = root / "pretrained_model"
    checkpoint.mkdir(parents=True)
    expected = CONTROL._checkpoint_contract(cfg)
    (checkpoint / "adapter_model.safetensors").write_bytes(b"adapter-fixture")
    (checkpoint / "adapter_config.json").write_text(
        json.dumps(
            {
                "peft_type": expected["peft_type"],
                "r": expected["r"],
                "lora_alpha": expected["lora_alpha"],
                "lora_dropout": expected["lora_dropout"],
                "bias": expected["bias"],
                "target_modules": expected["target_modules"],
                "modules_to_save": expected["full_training_modules"],
            }
        ),
        encoding="utf-8",
    )
    policy_config = {
        "optimizer_lr": expected["optimizer_lr"],
        "optimizer_weight_decay": expected["optimizer_weight_decay"],
        "optimizer_grad_clip_norm": expected["optimizer_grad_clip_norm"],
        "scheduler_warmup_steps": expected["scheduler_warmup_steps"],
        "chunk_size": expected["chunk_size"],
        "n_action_steps": expected["n_action_steps"],
        "empty_cameras": expected["empty_cameras"],
    }
    if expected["observation_state_dim"] is not None:
        policy_config["input_features"] = {
            "observation.state": {
                "type": "STATE",
                "shape": [expected["observation_state_dim"]],
            },
            **{
                key: {"type": "VISUAL", "shape": [3, 240, 320]}
                for key in expected["nonempty_camera_keys"]
            },
        }
        policy_config["output_features"] = {
            "action": {"type": "ACTION", "shape": [expected["action_dim"]]}
        }
    (checkpoint / "config.json").write_text(
        json.dumps(policy_config), encoding="utf-8"
    )
    (checkpoint / "train_config.json").write_text(
        json.dumps(
            {
                "peft": {
                    "method_type": expected["peft_type"],
                    "r": expected["r"],
                    "target_modules": expected["target_modules"],
                },
                "policy": {
                    "chunk_size": expected["chunk_size"],
                    "n_action_steps": expected["n_action_steps"],
                    "empty_cameras": expected["empty_cameras"],
                },
                "optimizer": {
                    "lr": expected["optimizer_lr"],
                    "weight_decay": expected["optimizer_weight_decay"],
                    "grad_clip_norm": expected["optimizer_grad_clip_norm"],
                },
                "scheduler": {
                    "type": "cosine_decay_with_warmup",
                    "num_warmup_steps": expected["scheduler_warmup_steps"],
                },
                "steps": expected["steps"],
                "batch_size": expected["batch_size"],
                "seed": expected["seed"],
                "log_freq": expected["log_freq"],
                "eval_freq": expected["eval_freq"],
                "save_freq": expected["save_freq"],
                "num_workers": expected["num_workers"],
            }
        ),
        encoding="utf-8",
    )
    preprocessor_features = {}
    if expected["observation_state_dim"] is not None:
        preprocessor_features = {
            "observation.state": {
                "type": "STATE",
                "shape": [expected["observation_state_dim"]],
            },
            **{
                key: {"type": "VISUAL", "shape": [3, 240, 320]}
                for key in expected["nonempty_camera_keys"]
            },
            "action": {
                "type": "ACTION",
                "shape": [expected["action_dim"]],
            },
        }
    (checkpoint / "policy_preprocessor.json").write_text(
        json.dumps(
            {
                "steps": [
                    {
                        "registry_name": "rename_observations_processor",
                        "config": {
                            "rename_map": {
                                "observation.images.scene": "observation.images.camera1"
                            }
                        },
                    },
                    {
                        "registry_name": "normalizer_processor",
                        "config": {"features": preprocessor_features},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return checkpoint


def test_zero_is_closed_for_timing_and_home_no_close() -> None:
    assert OPEN_LOOP._first_close_frame([1.0, 0.8, 0.5, 0.0]) == 2
    assert OPEN_LOOP._first_close_frame([1.0, 0.8, 0.6]) is None

    logs = [
        {
            "expert_gripper_cmd": expert,
            "pred_gripper_cmd": pred,
            "pred_xyz": [float(i), 0.0, 0.0],
            "raw_pred": [0.0] * 7 + [pred],
        }
        for i, (expert, pred) in enumerate(((1.0, 1.0), (0.0, 1.0)))
    ]
    metrics = OPEN_LOOP._episode_extra_metrics(logs, grip_idx=7, close_debounce=1)
    assert metrics["gripper_close_timing_error_frames"] == 999
    assert metrics["home_no_close_detected"] is True


def test_gripper_metrics_are_signed_debounced_and_class_balanced() -> None:
    expert = [1.0, 1.0, 1.0, 0.0, 0.0, 0.0]
    pred = [1.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    logs = [
        {
            "frame_index": i * 10,
            "timestamp": float(i),
            "expert_gripper_cmd": e,
            "pred_gripper_cmd": p,
            "expert_xyz": [float(i), 0.0, 0.0],
            "pred_xyz": [float(i), 0.0, 0.0],
            "raw_pred": [0.0] * 7 + [p],
        }
        for i, (e, p) in enumerate(zip(expert, pred, strict=True))
    ]
    metrics = OPEN_LOOP._episode_extra_metrics(
        logs, grip_idx=7, close_debounce=2
    )
    # The one-frame false close at sample 1 is ignored; sustained close aligns at sample 3.
    assert metrics["gripper_close_timing_offset_frames_signed"] == 0
    assert metrics["gripper_close_timing_offset_seconds_signed"] == 0.0
    assert metrics["gripper_binary_transition_count"] == 3
    assert metrics["gripper_balanced_accuracy"] == (2 / 3 + 1.0) / 2
    assert metrics["gripper_tolerance_accuracy"] == 5 / 6


def test_checkpoint_audit_accepts_exact_frozen_config(tmp_path: Path) -> None:
    cfg = _config()
    checkpoint = _write_checkpoint_fixture(tmp_path, cfg)
    report = CONTROL.audit_trained_checkpoint(cfg, checkpoint)
    assert report["passed"] is True
    assert report["failures"] == []
    assert len(report["adapter_model_sha256"]) == 64


def test_checkpoint_audit_rejects_lora_and_optimizer_drift(tmp_path: Path) -> None:
    cfg = _config()
    checkpoint = _write_checkpoint_fixture(tmp_path, cfg)
    adapter_path = checkpoint / "adapter_config.json"
    adapter = json.loads(adapter_path.read_text(encoding="utf-8"))
    adapter["lora_alpha"] = 8
    adapter_path.write_text(json.dumps(adapter), encoding="utf-8")
    policy_path = checkpoint / "config.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["optimizer_lr"] = 1e-4
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    report = CONTROL.audit_trained_checkpoint(cfg, checkpoint)
    assert report["passed"] is False
    assert "lora_alpha" in report["failures"]
    assert "optimizer_lr" in report["failures"]
    assert report["reason"] == "checkpoint_config_drift"


def test_recovery_runtime_separates_chunk_from_action_steps() -> None:
    cfg = _config()
    cfg["train"]["action_chunk_size"] = 10
    cfg["inference"] = {
        "action_steps": 5,
        "empty_cameras": 2,
        "camera_variant": "scene_only",
    }
    cfg["state_contract"] = {"name": "observation.state[15]", "dim": 15}
    runtime = CONTROL._runtime_contract(cfg)
    contract = CONTROL._checkpoint_contract(cfg)
    assert runtime == {"chunk_size": 10, "action_steps": 5, "empty_cameras": 2}
    assert contract["chunk_size"] == 10
    assert contract["n_action_steps"] == 5
    assert contract["observation_state_dim"] == 15


def test_recovery_draft_is_preflight_complete_but_train_fail_closed(
    tmp_path: Path,
) -> None:
    recovery_path = (
        ROOT / "configs" / "smolvla_s3" / "lora_train_recovery_draft.yaml"
    )
    cfg = yaml.safe_load(recovery_path.read_text(encoding="utf-8"))
    assert CONTROL._runtime_contract(cfg) == {
        "chunk_size": 10,
        "action_steps": 5,
        "empty_cameras": 0,
    }
    report = CONTROL.run_train_guarded(
        cfg,
        ROOT
        / "data"
        / "releases"
        / "smolvla_s3_abs_eef_rgb_v2_griptiming_lateclose",
        tmp_path / "run",
        tmp_path / "not-needed.json",
        True,
        recovery_path,
    )
    assert report["passed"] is False
    assert report["reason"] == "config_not_authorized_to_train"


def test_recovery_has_zero_missing_camera_padding_when_camera1_present() -> None:
    recovery_path = (
        ROOT / "configs" / "smolvla_s3" / "lora_train_recovery_draft.yaml"
    )
    cfg = yaml.safe_load(recovery_path.read_text(encoding="utf-8"))
    report = CONTROL._empty_camera_padding_contract(
        cfg, {"observation.state", "observation.images.camera1"}
    )
    assert report["configured_visual_features"] == [
        "observation.images.camera1"
    ]
    assert report["missing_visual_features"] == []
    assert report["empty_cameras_limit"] == 0
    assert report["empty_cameras_appended"] == 0


def test_recovery_dependency_audit_accepts_only_qualified_autodl_stack() -> None:
    recovery_path = (
        ROOT / "configs" / "smolvla_s3" / "lora_train_recovery_draft.yaml"
    )
    cfg = yaml.safe_load(recovery_path.read_text(encoding="utf-8"))
    observed = {
        "python": "3.12.13",
        "lerobot": "0.5.1",
        "torch": "2.6.0+cu124",
        "torchvision": "0.21.0+cu124",
        "transformers": "4.57.6",
        "peft": "0.19.1",
        "accelerate": "1.14.0",
        "safetensors": "0.8.0",
    }
    passed = CONTROL._audit_dependency_versions(cfg, observed)
    assert passed["passed"] is True
    assert passed["source_field"] == "dependency_versions_preflight_qualified"

    observed["peft"] = "0.15.2"
    rejected = CONTROL._audit_dependency_versions(cfg, observed)
    assert rejected["passed"] is False
    assert rejected["checks"]["peft"] is False
    assert "does not satisfy" in rejected["errors"]["peft"]


def test_recovery_train_requires_live_full_model_peft_resolve(
    tmp_path: Path,
) -> None:
    recovery_path = (
        ROOT / "configs" / "smolvla_s3" / "lora_train_recovery_draft.yaml"
    )
    cfg = yaml.safe_load(recovery_path.read_text(encoding="utf-8"))
    cfg["authorized_to_train"] = True
    cfg["train"]["max_steps"] = 1
    preflight = tmp_path / "preflight.json"
    preflight.write_text(
        json.dumps(
            {
                "mode": "preflight",
                "passed": True,
                "live_peft_resolve_probe_passed": False,
            }
        ),
        encoding="utf-8",
    )
    report = CONTROL.run_train_guarded(
        cfg,
        ROOT
        / "data"
        / "releases"
        / "smolvla_s3_abs_eef_rgb_v2_griptiming_lateclose",
        tmp_path / "run",
        preflight,
        True,
        recovery_path,
    )
    assert report["passed"] is False
    assert report["reason"] == "live_peft_resolve_probe_not_passed"


def test_recovery_train_requires_dependency_audit_from_same_preflight(
    tmp_path: Path,
) -> None:
    recovery_path = (
        ROOT / "configs" / "smolvla_s3" / "lora_train_recovery_draft.yaml"
    )
    cfg = yaml.safe_load(recovery_path.read_text(encoding="utf-8"))
    cfg["authorized_to_train"] = True
    cfg["train"]["max_steps"] = 1
    preflight = tmp_path / "preflight.json"
    preflight.write_text(
        json.dumps(
            {
                "mode": "preflight",
                "passed": True,
                "live_peft_resolve_probe_passed": True,
            }
        ),
        encoding="utf-8",
    )
    report = CONTROL.run_train_guarded(
        cfg,
        ROOT
        / "data"
        / "releases"
        / "smolvla_s3_abs_eef_rgb_v2_griptiming_lateclose",
        tmp_path / "run",
        preflight,
        True,
        recovery_path,
    )
    assert report["passed"] is False
    assert report["reason"] == "preflight_dependency_version_audit_not_passed"


def test_recovery_train_rejects_preflight_from_older_config(
    tmp_path: Path,
) -> None:
    recovery_path = (
        ROOT / "configs" / "smolvla_s3" / "lora_train_recovery_draft.yaml"
    )
    cfg = yaml.safe_load(recovery_path.read_text(encoding="utf-8"))
    cfg["authorized_to_train"] = True
    cfg["train"]["max_steps"] = 1
    preflight = tmp_path / "preflight.json"
    preflight.write_text(
        json.dumps(
            {
                "mode": "preflight",
                "passed": True,
                "live_peft_resolve_probe_passed": True,
                "dependency_version_audit": {"passed": True},
                "config_sha256": "old-config",
            }
        ),
        encoding="utf-8",
    )
    report = CONTROL.run_train_guarded(
        cfg,
        ROOT
        / "data"
        / "releases"
        / "smolvla_s3_abs_eef_rgb_v2_griptiming_lateclose",
        tmp_path / "run",
        preflight,
        True,
        recovery_path,
    )
    assert report["passed"] is False
    assert report["reason"] == "preflight_config_sha256_mismatch"


def test_checkpoint_audit_rejects_action_step_drift(tmp_path: Path) -> None:
    cfg = _config()
    cfg["train"]["action_chunk_size"] = 10
    cfg["inference"] = {
        "action_steps": 5,
        "empty_cameras": 2,
        "camera_variant": "scene_only",
    }
    checkpoint = _write_checkpoint_fixture(tmp_path, cfg)
    policy_path = checkpoint / "config.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["n_action_steps"] = 10
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    report = CONTROL.audit_trained_checkpoint(cfg, checkpoint)
    assert report["passed"] is False
    assert "n_action_steps" in report["failures"]


def test_checkpoint_audit_accepts_recovery_state15_and_k5(tmp_path: Path) -> None:
    cfg = _config()
    cfg["train"]["action_chunk_size"] = 10
    cfg["inference"] = {
        "action_steps": 5,
        "empty_cameras": 2,
        "camera_variant": "scene_only",
    }
    cfg["state_contract"] = {"name": "observation.state[15]", "dim": 15}
    checkpoint = _write_checkpoint_fixture(tmp_path, cfg)
    report = CONTROL.audit_trained_checkpoint(cfg, checkpoint)
    assert report["passed"] is True
    assert report["actual"]["observation_state_dim"] == 15
    assert report["actual"]["n_action_steps"] == 5
    assert report["actual"]["nonempty_camera_keys"] == [
        "observation.images.camera1"
    ]
    assert report["actual"]["action_dim"] == 8


def test_finalize_train_records_real_completion(tmp_path: Path) -> None:
    cfg = _config()
    checkpoint = _write_checkpoint_fixture(tmp_path, cfg)
    out = tmp_path / "run"
    out.mkdir()
    (out / "run_metadata.json").write_text(
        json.dumps({"mode": "train", "executed": False, "gate": "launch_authorized"}),
        encoding="utf-8",
    )
    report = CONTROL.finalize_train_run(cfg, out, checkpoint, CONFIG)
    assert report["executed"] is True
    assert report["completed"] is True
    assert report["ready_to_execute"] is False
    assert report["gate"] == "checkpoint_config_verified"
    assert report["checkpoint_audit"]["passed"] is True


def test_execute_flag_authorizes_shell_launch(tmp_path: Path, monkeypatch) -> None:
    preflight = tmp_path / "preflight_report.json"
    preflight.write_text(
        json.dumps({"mode": "preflight", "passed": True}), encoding="utf-8"
    )
    monkeypatch.setenv("SMOLVLA_S3_EXECUTE_TRAIN", "1")
    report = CONTROL.run_train_guarded(
        _config(), RELEASE, tmp_path / "run", preflight, True, CONFIG
    )
    assert report["passed"] is True
    assert report["executed"] is False
    assert report["execution_requested"] is True
    assert report["gate"] == "launch_authorized"


def test_train_shell_passes_and_audits_frozen_fields() -> None:
    shell = (ROOT / "scripts" / "run_smolvla_s3_train.sh").read_text(encoding="utf-8")
    for flag in (
        "--policy.optimizer_lr",
        "--policy.optimizer_weight_decay",
        "--policy.optimizer_grad_clip_norm",
        "--policy.scheduler_warmup_steps",
        "--s3-lora-alpha",
        "--s3-lora-dropout",
        "--s3-lora-bias",
        "--peft.target_modules",
        "--peft.full_training_modules",
        "--policy.n_action_steps",
        "--policy.empty_cameras",
        "--policy.input_features",
        "--policy.output_features",
        "--s3-policy-input-features",
        "--s3-policy-output-features",
        "lerobot_train_with_peft_overrides.py",
        "S3_LORA_ALPHA",
        "--mode finalize-train",
        "--checkpoint-dir",
        'export ACCELERATE_MIXED_PRECISION="$PRECISION"',
        "verified entry requires LeRobot 0.5.x",
    ):
        assert flag in shell
    assert "checkpoint config verified" in shell
    assert '--policy.n_action_steps="$CHUNK_SIZE"' not in shell
    assert "--policy.empty_cameras=2" not in shell
    assert "--peft.lora_alpha" not in shell.split("lerobot_train_with_peft_overrides.py", 1)[-1]
    assert "--s3-policy-input-features=" in shell
    assert "--s3-policy-output-features=" in shell


def test_peft_override_wrapper_resolves_frozen_alpha() -> None:
    wrapper = _load_module(
        "lerobot_train_with_peft_overrides_test",
        "training/scripts/lerobot_train_with_peft_overrides.py",
    )
    alpha, dropout, bias, input_features, output_features, rest = (
        wrapper._resolve_overrides(
            [
                "--s3-lora-alpha",
                "64",
                "--s3-lora-dropout",
                "0.05",
                "--s3-lora-bias",
                "none",
                "--s3-policy-input-features",
                '{"observation.state":{"type":"STATE","shape":[15]}}',
                "--peft.r",
                "64",
            ]
        )
    )
    assert alpha == 64
    assert dropout == 0.05
    assert bias == "none"
    assert input_features == {
        "observation.state": {"type": "STATE", "shape": [15]}
    }
    assert output_features is None
    assert rest == ["--peft.r", "64"]


def test_draccus_merge_leaves_base_cameras_but_replace_strips_them() -> None:
    from training.smolvla_s3.policy_features import (
        apply_feature_contract,
        image_feature_keys,
        simulate_draccus_feature_merge,
    )

    base = {
        "observation.state": {"type": "STATE", "shape": [6]},
        "observation.images.camera1": {"type": "VISUAL", "shape": [3, 256, 256]},
        "observation.images.camera2": {"type": "VISUAL", "shape": [3, 256, 256]},
        "observation.images.camera3": {"type": "VISUAL", "shape": [3, 256, 256]},
    }
    override = {
        "observation.state": {"type": "STATE", "shape": [15]},
        "observation.images.camera1": {"type": "VISUAL", "shape": [3, 240, 320]},
    }
    merged = simulate_draccus_feature_merge(base, override)
    assert image_feature_keys(merged) == [
        "observation.images.camera1",
        "observation.images.camera2",
        "observation.images.camera3",
    ]
    assert merged["observation.images.camera1"]["shape"] == [3, 240, 320]
    assert merged["observation.images.camera2"]["shape"] == [3, 256, 256]

    replaced, removed = apply_feature_contract(merged, override)
    assert removed == [
        "observation.images.camera2",
        "observation.images.camera3",
    ]
    assert image_feature_keys(replaced) == ["observation.images.camera1"]
    assert replaced["observation.state"]["shape"] == [15]


def test_checkpoint_audit_rejects_base_camera_merge_and_repair_passes(
    tmp_path: Path,
) -> None:
    cfg = yaml.safe_load(
        (
            ROOT
            / "configs"
            / "smolvla_s3"
            / "lora_train_recovery_v3_phaseaware50.yaml"
        ).read_text(encoding="utf-8")
    )
    checkpoint = _write_checkpoint_fixture(tmp_path, cfg)
    policy_path = checkpoint / "config.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["input_features"]["observation.images.camera2"] = {
        "type": "VISUAL",
        "shape": [3, 256, 256],
    }
    policy["input_features"]["observation.images.camera3"] = {
        "type": "VISUAL",
        "shape": [3, 256, 256],
    }
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    pre_path = checkpoint / "policy_preprocessor.json"
    pre = json.loads(pre_path.read_text(encoding="utf-8"))
    for step in pre["steps"]:
        if step.get("registry_name") == "normalizer_processor":
            feats = step["config"]["features"]
            feats["observation.images.camera2"] = {
                "type": "VISUAL",
                "shape": [3, 256, 256],
            }
            feats["observation.images.camera3"] = {
                "type": "VISUAL",
                "shape": [3, 256, 256],
            }
    pre_path.write_text(json.dumps(pre), encoding="utf-8")

    failed = CONTROL.audit_trained_checkpoint(cfg, checkpoint)
    assert failed["passed"] is False
    assert "nonempty_camera_keys" in failed["failures"]
    assert "preprocessor_nonempty_camera_keys" in failed["failures"]

    repair = CONTROL.repair_checkpoint_camera_contract(cfg, checkpoint, write=True)
    assert repair["passed"] is True
    assert repair["wrote"] is True
    assert repair["removed_image_keys"]["config.json"] == [
        "observation.images.camera2",
        "observation.images.camera3",
    ]
    assert (
        repair["adapter_model_sha256_before"] == repair["adapter_model_sha256_after"]
    )

    passed = CONTROL.audit_trained_checkpoint(cfg, checkpoint)
    assert passed["passed"] is True
    assert passed["actual"]["nonempty_camera_keys"] == [
        "observation.images.camera1"
    ]
    assert passed["actual"]["preprocessor_nonempty_camera_keys"] == [
        "observation.images.camera1"
    ]


def test_native_policy_state_uses_recovery_state15() -> None:
    row = {
        "observation.state": list(range(7)),
        "observation.ee_pose": [1, 2, 3, 0, 0, 0, 1],
        "observation.gripper": 0.25,
    }
    state = OPEN_LOOP._native_policy_state(
        row, {"name": "observation.state[15]", "dim": 15}
    )
    assert state.shape == (15,)
    assert state.tolist() == list(range(7)) + [1, 2, 3, 0, 0, 0, 1, 0.25]


def test_open_loop_exposes_separate_canonical_and_queued_modes() -> None:
    source = (
        ROOT / "training" / "smolvla_s3" / "open_loop_eval.py"
    ).read_text(encoding="utf-8")
    assert "--inference-mode" in source
    assert "canonical_first_action" in source
    assert "queued_diagnostic" in source


def test_queued_diagnostic_cannot_pass_canonical_gate() -> None:
    gate = yaml.safe_load(
        (ROOT / "configs" / "smolvla_s3" / "eval_gate.yaml").read_text(
            encoding="utf-8"
        )
    )
    metrics = {
        "ee_position_rmse_m": 0.01,
        "gripper_balanced_accuracy": 1.0,
        "quaternion_angular_error_rad": 0.01,
        "gripper_close_timing_error_frames": 0,
        "action_smoothness_ee_step_l2_p90": 0.01,
        "raw_gripper_oob_ratio": 0.0,
        "home_no_close_detected_rate": 0.0,
        "temporal_metrics_gate_eligible": False,
    }
    decision = OPEN_LOOP.decide_gate(gate, metrics, s2_ee=0.27)
    assert decision["gate_decision"] != "pass"
    assert "temporal_coverage" in decision["pass_failures"]


def test_open_loop_fails_before_cuda_on_checkpoint_drift(tmp_path: Path) -> None:
    cfg = _config()
    checkpoint = _write_checkpoint_fixture(tmp_path, cfg)
    adapter_path = checkpoint / "adapter_config.json"
    adapter = json.loads(adapter_path.read_text(encoding="utf-8"))
    adapter["lora_alpha"] = 8
    adapter_path.write_text(json.dumps(adapter), encoding="utf-8")
    out = tmp_path / "openloop"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "training/scripts/run_smolvla_s3_open_loop.py"),
            "--base-dir",
            str(tmp_path / "unused-base"),
            "--vlm-dir",
            str(tmp_path / "unused-vlm"),
            "--lora-dir",
            str(checkpoint),
            "--train-config",
            str(CONFIG),
            "--output-dir",
            str(out),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    summary = json.loads((out / "s3_open_loop_summary.json").read_text(encoding="utf-8"))
    assert summary["gate_decision"] == "no_go"
    assert summary["checkpoint_config_verified"] is False
    assert "lora_alpha" in summary["failures"]


def test_open_loop_shell_uses_selected_train_config_and_gate_is_fail_closed() -> None:
    shell = (ROOT / "scripts" / "run_smolvla_s3_open_loop.sh").read_text(
        encoding="utf-8"
    )
    source = (ROOT / "training/smolvla_s3/open_loop_eval.py").read_text(
        encoding="utf-8"
    )
    assert 'CONFIG="${S3_CONFIG:-' in shell
    assert '--train-config "$CONFIG"' in shell
    assert 'STRIDE="${S3_OPENLOOP_STRIDE:-1}"' in shell
    assert 'MAX_FRAMES="${S3_OPENLOOP_MAX_FRAMES:-0}"' in shell
    assert (
        'INFERENCE_MODE="${S3_OPENLOOP_INFERENCE_MODE:-canonical_first_action}"'
        in shell
    )
    assert '--inference-mode "$INFERENCE_MODE"' in shell
    assert "configs/smolvla_s3/eval_gate_v2.yaml" in shell
    assert "S3_PROSPECTIVE_EVAL_MANIFEST" in shell
    assert "--prospective-eval-manifest" in shell
    assert "--prospective-eval-manifest" in source
    assert "smolvla_s3_abs_eef_rgb_v1_griptiming" in shell
    assert "smolvla_s3_abs_eef_rgb_v1_griptiming" in source
    assert 'return 0 if report["gate_decision"] == "pass" else 2' in source


def test_gate_requires_complete_stride_one_temporal_coverage() -> None:
    gate = yaml.safe_load(
        (ROOT / "configs" / "smolvla_s3" / "eval_gate.yaml").read_text(
            encoding="utf-8"
        )
    )
    metrics = {
        "ee_position_rmse_m": 0.05,
        "gripper_balanced_accuracy": 0.8,
        "quaternion_angular_error_rad": 0.1,
        "gripper_close_timing_error_frames": 2,
        "action_smoothness_ee_step_l2_p90": 0.02,
        "raw_gripper_oob_ratio": 0.02,
        "home_no_close_detected_rate": 0.0,
        "temporal_metrics_gate_eligible": False,
    }
    hold = OPEN_LOOP.decide_gate(
        gate, metrics, s2_ee=gate["baselines"]["s2_ee_rmse_m"]
    )
    assert hold["gate_decision"] == "hold"
    assert "temporal_coverage" in hold["pass_failures"]

    metrics["temporal_metrics_gate_eligible"] = True
    passed = OPEN_LOOP.decide_gate(
        gate, metrics, s2_ee=gate["baselines"]["s2_ee_rmse_m"]
    )
    assert passed["gate_decision"] == "pass"


def test_gate_cannot_pass_with_missing_rotation_or_timing_metrics() -> None:
    gate = yaml.safe_load(
        (ROOT / "configs" / "smolvla_s3" / "eval_gate.yaml").read_text(
            encoding="utf-8"
        )
    )
    metrics = {
        "ee_position_rmse_m": 0.05,
        "gripper_balanced_accuracy": 0.8,
        "quaternion_angular_error_rad": None,
        "gripper_close_timing_error_frames": None,
        "action_smoothness_ee_step_l2_p90": 0.02,
        "raw_gripper_oob_ratio": 0.02,
        "home_no_close_detected_rate": 0.0,
        "temporal_metrics_gate_eligible": True,
    }
    result = OPEN_LOOP.decide_gate(
        gate, metrics, s2_ee=gate["baselines"]["s2_ee_rmse_m"]
    )
    assert result["gate_decision"] == "hold"
    assert {"quat", "timing"} <= set(result["pass_failures"])


def test_saved_report_recompute_is_cpu_only_and_cannot_promote_partial_sampling() -> None:
    logs = [
        {
            "frame_index": i * 10,
            "expert_xyz": [float(i), 0.0, 0.0],
            "pred_xyz": [float(i), 0.0, 0.0],
            "expert_gripper_cmd": e,
            "pred_gripper_cmd": p,
            "raw_pred": [0.0] * 7 + [p],
        }
        for i, (e, p) in enumerate(
            zip(
                [1.0, 1.0, 1.0, 0.0, 0.0, 0.0],
                [1.0, 1.0, 1.0, 0.0, 0.0, 0.0],
                strict=True,
            )
        )
    ]
    episode = {
        "episode_ref": "fixture/episode_000000",
        "slice": "validation",
        "protocol": "native_abs_eef",
        "frame_logs": logs,
    }
    lane = {
        "protocol": "native_abs_eef",
        "metrics": {
            "ee_position_rmse_m": 0.05,
            "quaternion_angular_error_rad": 0.1,
        },
    }
    result = RECOMPUTE.recompute_lane(
        lane, [episode], stride=10, max_frames_per_episode=6
    )
    assert result["metrics"]["gripper_balanced_accuracy"] == 1.0
    assert result["metrics"]["temporal_metrics_gate_eligible"] is False
    assert result["metrics"]["gripper_close_timing_offset_frames_signed"] == 0.0
