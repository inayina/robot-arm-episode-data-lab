"""Tests for SmolVLA S3 Phase 0 policy-input / PEFT / camera audits."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "training" / "scripts" / "audit_smolvla_s3_policy_inputs.py"
SPEC = importlib.util.spec_from_file_location("smolvla_s3_policy_input_audit_test", SCRIPT)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)

CONFIG = ROOT / "configs" / "smolvla_s3" / "lora_train.yaml"
V2_CKPT = (
    ROOT
    / "runs"
    / "smolvla_s3"
    / "train_v2_lateclose_20260723T160000Z"
    / "lerobot_run"
    / "checkpoints"
    / "001000"
    / "pretrained_model"
)


def test_schema_audit_flags_state7_vs_checkpoint6_and_dropped_extras() -> None:
    source_keys = {
        "observation.state": [7],
        "observation.ee_pose": [7],
        "observation.object_pose": [7],
        "observation.ft": [6],
        "observation.gripper": [1],
        "observation.images.scene": [3, 240, 320],
        "action": [8],
    }
    preprocessor = {
        "observation.state": {"type": "STATE", "shape": [6]},
        "observation.images.camera1": {"type": "VISUAL", "shape": [3, 256, 256]},
        "action": {"type": "ACTION", "shape": [8]},
    }
    report = AUDIT.compare_schema_to_preprocessor(
        source_keys=source_keys,
        preprocessor_features=preprocessor,
        rename_map={"observation.images.scene": "observation.images.camera1"},
    )
    assert report["shape_mismatches"]["observation.state"]["source"] == [7]
    assert report["shape_mismatches"]["observation.state"]["preprocessor"] == [6]
    assert "observation.ee_pose" in report["dropped_by_preprocessor"]
    assert "observation.object_pose" in report["dropped_by_preprocessor"]
    assert "observation.ft" in report["dropped_by_preprocessor"]
    assert "observation.gripper" in report["dropped_by_preprocessor"]
    assert "observation.images.scene" not in report["dropped_by_preprocessor"]
    assert "observation.images.camera1" in report["effective_source_keys_after_rename"]


def test_peft_probe_shows_current_yaml_misses_projections() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    probe = AUDIT.probe_peft_targets(
        AUDIT.build_mock_module_names(),
        configured_targets=list(cfg["peft"]["target_modules"]),
    )
    assert cfg["peft"]["target_modules"] == ["q_proj", "v_proj"]
    assert probe["projection_modules_present"]["state_proj"] is True
    assert probe["projection_trainable_under_current_config"]["state_proj"] is False
    assert probe["projection_trainable_under_current_config"]["action_in_proj"] is False
    assert "state_proj" in probe["recommended_target_modules"]
    assert "action_out_proj" in probe["recommended_target_modules"]
    assert probe["recommended_covers_projections"] is True
    assert probe["current_config_covers_projections"] is False
    assert probe["detected_current_projection_gap"] is True


def test_camera_profiler_accounts_empty_padding_without_claiming_gpu() -> None:
    report = AUDIT.profile_camera_plan(
        scene_only=True,
        include_wrist=False,
        empty_cameras=2,
        resize_hw=(512, 512),
    )
    current = report["variants"]["current_empty_padding"]
    assert current["real_cameras"] == ["observation.images.scene"]
    assert current["empty_cameras"] == 2
    assert current["total_image_tensors"] == 3
    assert report["passed_cpu_accounting"] is True
    assert report["passed_gpu_profiler"] is False
    assert current["gpu_latency_ms"] is None


def test_mock_audit_report_is_fail_closed_for_train_and_v3() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    checkpoint = V2_CKPT if V2_CKPT.is_dir() else None
    report = AUDIT.run_mock_audit(cfg, checkpoint)
    assert report["passed"] is True
    assert report["claims_ready_to_train"] is False
    assert report["claims_ready_for_v3_release"] is False
    assert report["recommended_state_contract"]["name"] == "observation.state[15]"
    assert report["schema_audit"]["state7_vs_checkpoint6"]["source_observation.state"] == [7]
    if checkpoint is not None:
        assert report["checkpoint_metadata"]["empty_cameras"] == 2
        state_shape = report["checkpoint_metadata"]["input_features"][
            "observation.state"
        ]["shape"]
        assert state_shape == [6]


def test_cli_mock_writes_json(tmp_path: Path) -> None:
    out = tmp_path / "phase0_audit.json"
    rc = AUDIT.main(
        [
            "--mode",
            "mock",
            "--config",
            str(CONFIG),
            "--json-out",
            str(out),
        ]
    )
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["mode"] == "mock"
    assert payload["peft_probe"]["configured_target_modules"] == ["q_proj", "v_proj"]
