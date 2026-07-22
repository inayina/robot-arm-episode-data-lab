"""SmolVLA S3 Ready local tests (no full training; mock vs real preflight distinguished)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "data" / "releases" / "smolvla_s3_abs_eef_rgb_v0"
CONFIG = ROOT / "configs" / "smolvla_s3" / "lora_train.yaml"
EVAL_GATE = ROOT / "configs" / "smolvla_s3" / "eval_gate.yaml"


def test_release_manifest_and_hashes() -> None:
    manifest = json.loads((RELEASE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["release_id"] == "smolvla_s3_abs_eef_rgb_v0"
    assert manifest["policy_action_semantics"] == "absolute_eef_gripper_v0"
    assert manifest["quaternion_order"] == "xyzw"
    assert manifest["scene_rgb_complete_rate"] == 1.0
    assert manifest["num_episodes"] == 10
    assert manifest["num_frames"] == 2052
    assert manifest["go_no_go"] == "go"
    assert manifest["trained"] is False
    assert manifest["ran_isaac"] is False
    for name, expected in manifest["file_sha256"].items():
        if name == "manifest.json":
            continue
        data = (RELEASE / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected


def test_split_no_leakage() -> None:
    splits = json.loads((RELEASE / "splits.json").read_text(encoding="utf-8"))
    train, val, bench = map(set, (splits["train"], splits["validation"], splits["benchmark"]))
    assert not (train & val)
    assert not (train & bench)
    assert not (val & bench)
    assert len(train) == 6 and len(val) == 2 and len(bench) == 2


def test_validate_script_pass() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "training/scripts/validate_smolvla_s3_release.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["passed"] is True


def test_gripper_and_quat_fields_in_index() -> None:
    rows = [
        json.loads(line)
        for line in (RELEASE / "episode_index.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    for row in rows:
        assert row["action_dim"] == 8
        assert row["quat_order"] == "xyzw"
        assert 0.0 <= row["gripper_cmd_min"] <= row["gripper_cmd_max"] <= 1.0
        assert row["rgb_complete"] is True
        assert row["valid_mask_all_true"] is True
        assert "action_delta_indices" in row


def test_norm_stats_train_only_and_expert_scale() -> None:
    norms = json.loads((RELEASE / "norm_stats.json").read_text(encoding="utf-8"))
    assert norms["computed_on_split"] == "train"
    assert len(norms["action8"]["mean"]) == 8
    assert norms["expert_scale"]["ee_step_l2_p90"] > 0
    assert norms["expert_scale"]["gripper_cmd_range"] == [0.0, 1.0]


def test_lora_config_frozen_fields() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert cfg["release_id"] == "smolvla_s3_abs_eef_rgb_v0"
    assert cfg["peft"]["r"] == 64
    assert cfg["peft"]["lora_alpha"] == 64
    assert cfg["train"]["seed"] == 42
    assert cfg["train"]["no_auto_hparam_search"] is True
    assert cfg["train"]["no_architecture_change"] is True
    assert cfg["gates"]["forbid_auto_start_train_from_preflight"] is True
    assert cfg["gates"]["forbid_isaac_until_open_loop_pass"] is True


def test_eval_gate_thresholds_derived_from_s2() -> None:
    gate = yaml.safe_load(EVAL_GATE.read_text(encoding="utf-8"))
    s2 = gate["baselines"]["s2_ee_rmse_m"]
    assert abs(s2 - 0.2734163848429447) < 1e-9
    assert gate["thresholds"]["pass"]["ee_position_rmse_m_max"] == 0.100
    assert gate["thresholds"]["hold"]["ee_position_rmse_m_max"] == 0.205
    assert gate["thresholds"]["no_go"]["ee_position_rmse_m_min"] == 0.246
    assert gate["thresholds"]["pass"]["gripper_accuracy_min"] == 0.70
    assert "home_no_close_detected" in gate["metrics_required"]
    assert "ood_position_slice" in gate["metrics_required"]


def test_mock_preflight_distinguished_from_real() -> None:
    out = ROOT / "runs" / "smolvla_s3" / "test_mock_preflight"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "training/scripts/run_smolvla_s3_control.py"),
            "--mode",
            "mock-preflight",
            "--config",
            str(CONFIG),
            "--release-dir",
            str(RELEASE),
            "--output-dir",
            str(out),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads((out / "preflight_report.json").read_text(encoding="utf-8"))
    assert report["mode"] == "mock-preflight"
    assert report["distinction"].startswith("MOCK_ONLY")
    assert report["real_gpu_preflight_required"] is True
    assert report["passed"] is True


def test_train_rejects_mock_preflight_authorization() -> None:
    mock_out = ROOT / "runs" / "smolvla_s3" / "test_mock_preflight"
    pref = mock_out / "preflight_report.json"
    assert pref.is_file()
    train_out = ROOT / "runs" / "smolvla_s3" / "test_train_reject_mock"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "training/scripts/run_smolvla_s3_control.py"),
            "--mode",
            "train",
            "--config",
            str(CONFIG),
            "--release-dir",
            str(RELEASE),
            "--output-dir",
            str(train_out),
            "--preflight-report",
            str(pref),
            "--i-understand-billing",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    report = json.loads(proc.stdout)
    assert report["passed"] is False
    assert "mock" in report["reason"].lower()


def test_docs_exist_and_link_release() -> None:
    ready = (ROOT / "docs/SMOLVLA_GATE_S3_READY.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs/SMOLVLA_S3_AUTODL_RUNBOOK.md").read_text(encoding="utf-8")
    assert "smolvla_s3_abs_eef_rgb_v0" in ready
    assert "MOCK_ONLY" in ready or "mock-preflight" in ready
    assert "不得" in runbook or "禁止" in runbook
    assert "open-loop" in runbook.lower() or "open-loop" in ready.lower()
    assert (ROOT / "scripts/run_smolvla_s3_preflight.sh").is_file()
    assert (ROOT / "scripts/run_smolvla_s3_train.sh").is_file()
    assert (ROOT / "scripts/autodl_setup_smolvla_s3.sh").is_file()


def test_s2_baseline_unchanged() -> None:
    """Do not rewrite historical S2 evidence."""
    s2 = json.loads(
        (ROOT / "evaluation/examples/smolvla_gate_s2_report.json").read_text(encoding="utf-8")
    )
    assert s2["h3_pretrained_vs_absolute_eef"] == "no_go"
    assert s2["claims_task_success"] is False
