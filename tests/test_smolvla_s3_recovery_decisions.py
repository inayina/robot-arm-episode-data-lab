"""Tests for frozen Recovery state[15] contract and Phase-1 wrist smoke audit helpers."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from training.smolvla_s3.state15 import (  # noqa: E402
    compose_state15,
    compose_state15_from_row,
    pad_state15_to_max,
    state15_contract_dict,
)

AUDIT_SCRIPT = ROOT / "training" / "scripts" / "audit_smolvla_s3_policy_inputs.py"
SPEC = importlib.util.spec_from_file_location("policy_input_audit_state15", AUDIT_SCRIPT)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)

PHASE1 = ROOT / "training" / "scripts" / "audit_smolvla_s3_phase1_wrist_smoke.py"
SPEC1 = importlib.util.spec_from_file_location("phase1_wrist_audit", PHASE1)
assert SPEC1 and SPEC1.loader
P1 = importlib.util.module_from_spec(SPEC1)
sys.modules[SPEC1.name] = P1
SPEC1.loader.exec_module(P1)

DECISIONS = ROOT / "configs" / "smolvla_s3" / "recovery_decisions.yaml"
RECOVERY_CONFIG = (
    ROOT / "configs" / "smolvla_s3" / "lora_train_recovery_draft.yaml"
)


def test_compose_state15_is_joint_ee_gripper() -> None:
    state = compose_state15(
        joint_position=[0.1] * 7,
        ee_pose_xyzw=[0.4, 0.0, 0.2, 0.0, 0.0, 0.0, 1.0],
        measured_gripper=0.8,
    )
    assert state.shape == (15,)
    np.testing.assert_allclose(state[:7], [0.1] * 7, rtol=1e-6)
    np.testing.assert_allclose(
        state[7:14], [0.4, 0.0, 0.2, 0.0, 0.0, 0.0, 1.0], rtol=1e-6
    )
    assert abs(float(state[14]) - 0.8) < 1e-6
    padded = pad_state15_to_max(state, 32)
    assert padded.shape == (32,)
    assert abs(float(padded[14]) - 0.8) < 1e-6
    assert float(padded[15]) == 0.0


def test_compose_state15_from_recorder_row_fields() -> None:
    row = {
        "observation.state": list(range(7)),
        "observation.ee_pose": [1, 2, 3, 0, 0, 0, 1],
        "observation.gripper": [0.25],
    }
    state = compose_state15_from_row(row)
    assert state.tolist() == list(range(7)) + [1, 2, 3, 0, 0, 0, 1] + [0.25]
    assert state15_contract_dict()["dim"] == 15


def test_recovery_decisions_freeze_state15_and_peft_regex() -> None:
    cfg = yaml.safe_load(DECISIONS.read_text(encoding="utf-8"))
    assert cfg["state_contract"]["name"] == "observation.state[15]"
    assert cfg["authorized_to_train"] is True
    assert cfg["authorized_train_config"].endswith(
        "lora_train_recovery_v3_phaseaware50.yaml"
    )
    assert cfg["authorized_to_build_v3_release"] is True
    assert cfg["authorized_to_collect_v3_phaseaware50"] is True
    assert cfg["authorized_isaac"] is False
    assert cfg["v3_release_id"] == "smolvla_s3_panda_abs_eef_scene_v3_phaseaware50"
    assert cfg["authorized_phase1_wrist_smoke"] is True
    assert cfg["peft"]["full_training_modules"] == []
    assert "lm_expert" in cfg["peft"]["target_modules"]
    assert "state_proj" in cfg["peft"]["target_modules"]
    inference = cfg["local_inference_contract"]
    assert inference["train_action_chunk_size"] == 10
    assert inference["inference_action_steps"] == 5
    assert inference["policy_input_features"]["observation.state"] == [15]
    assert inference["empty_cameras"] == 0
    assert inference["expected_empty_cameras_appended"] == 0
    assert inference["queued_diagnostic_gate_eligible"] is False
    assert inference["async_double_buffer_runtime_implemented"] is False


def test_recovery_inference_contract_is_chunk10_k5_scene_only() -> None:
    cfg = yaml.safe_load(RECOVERY_CONFIG.read_text(encoding="utf-8"))
    assert cfg["state_contract"]["dim"] == 15
    assert cfg["train_budget_candidate"]["action_chunk_size"] == 10
    assert cfg["inference"]["action_steps"] == 5
    assert cfg["inference"]["empty_cameras"] == 0
    assert cfg["inference"]["camera_variant"] == "scene_only"
    assert cfg["inference"]["canonical_mode"] == "canonical_first_action"
    assert cfg["inference"]["diagnostic_mode"] == "queued_diagnostic"


def test_official_peft_regex_excludes_vision_and_covers_projections() -> None:
    cfg = yaml.safe_load(DECISIONS.read_text(encoding="utf-8"))
    probe = AUDIT.probe_peft_targets(
        AUDIT.build_mock_module_names(),
        configured_targets=cfg["peft"]["target_modules"],
    )
    assert probe["regex_scopes_away_from_vision_and_base_lm"] is True
    assert probe["configured_hits_vision_encoder"] is False
    assert probe["configured_hits_base_language_non_expert"] is False
    assert probe["projection_trainable_under_current_config"]["state_proj"] is True
    assert any("lm_expert" in hit for hit in probe["configured_target_hits"])


def test_phase1_audit_flags_missing_wrist(tmp_path: Path) -> None:
    source = tmp_path / "seed58_wrist_smoke"
    (source / "meta").mkdir(parents=True)
    (source / "data" / "chunk-000").mkdir(parents=True)
    scene_dir = source / "videos" / "chunk-000" / "observation.images.scene"
    scene_dir.mkdir(parents=True)
    n = 5
    table = pa.table(
        {
            "observation.state": pa.array([[0.0] * 7] * n, type=pa.list_(pa.float32())),
            "observation.ee_pose": pa.array(
                [[0.4, 0.0, 0.05, 0, 0, 0, 1]] * n, type=pa.list_(pa.float32())
            ),
            "observation.object_pose": pa.array(
                [[0.4, 0.0, 0.025, 0, 0, 0, 1]] * n, type=pa.list_(pa.float32())
            ),
            "observation.gripper": pa.array([1.0] * n, type=pa.float32()),
            "action": pa.array(
                [[0.4, 0.0, 0.05, 0, 0, 0, 1, 1.0]] * n, type=pa.list_(pa.float32())
            ),
            "timestamp": pa.array([0.1 * i for i in range(n)], type=pa.float32()),
        }
    )
    pq.write_table(table, source / "data" / "chunk-000" / "episode_000000.parquet")
    # Write a tiny valid-ish mp4 via OpenCV for scene only.
    writer = cv2_writer = None
    import cv2

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(scene_dir / "episode_000000.mp4"), fourcc, 10.0, (32, 24))
    for _ in range(n):
        writer.write(np.full((24, 32, 3), 40, dtype=np.uint8))
    writer.release()
    (source / "meta" / "info.json").write_text(
        json.dumps({"total_episodes": 1, "total_frames": n}) + "\n", encoding="utf-8"
    )
    report = P1.audit_episode(source, 0)
    assert report["passed"] is False
    assert "missing_wrist_video" in report["failures"]


def test_phase1_red_target_visibility_rejects_clear_non_target_frame() -> None:
    clear_gray = np.full((24, 32, 3), 120, dtype=np.uint8)
    assert P1._red_target_ratio(clear_gray) == 0.0

    with_red_target = clear_gray.copy()
    with_red_target[6:18, 8:24] = (0, 0, 180)
    assert P1._red_target_ratio(with_red_target) > 0.20
