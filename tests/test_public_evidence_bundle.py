"""Public evidence bundle invariants: machine-readable, portable, and honest."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "docs" / "portfolio" / "public_evidence" / "canonical_v3"
JSON_FILES = (
    "open_loop_gate_summary.json",
    "release_checkpoint_summary.json",
    "s4_gate.json",
    "s4_per_seed_summary.json",
    "unified_eval_summary.json",
    "provenance.json",
)


def test_public_evidence_bundle_is_complete_and_portable() -> None:
    assert (BUNDLE / "README.md").is_file()
    for name in JSON_FILES:
        path = BUNDLE / name
        assert path.is_file(), f"missing public evidence: {name}"
        text = path.read_text(encoding="utf-8")
        assert "/home/" not in text
        payload = json.loads(text)
        assert payload.get("claims_task_success") is False
        assert payload.get("claims_sim2real") is False


def test_public_evidence_provenance_has_source_hashes() -> None:
    provenance = json.loads((BUNDLE / "provenance.json").read_text(encoding="utf-8"))
    assert len(provenance["sources"]) == 6
    for source in provenance["sources"]:
        assert re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
        assert source["public_derivative"] in JSON_FILES


def test_local_source_hashes_match_provenance_when_available() -> None:
    provenance = json.loads((BUNDLE / "provenance.json").read_text(encoding="utf-8"))
    checked = 0
    for source in provenance["sources"]:
        path = ROOT / source["path"]
        if not path.is_file():
            continue
        checked += 1
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
    # Public CI intentionally has no generated runs; the canonical development
    # workspace has all sources and therefore verifies all six hashes.
    assert checked in (0, len(provenance["sources"]))


def test_public_derivatives_match_local_sources_when_available() -> None:
    open_loop_path = ROOT / (
        "runs/smolvla_s3/"
        "openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/"
        "s3_open_loop_report.json"
    )
    release_path = ROOT / (
        "data/releases/smolvla_s3_panda_abs_eef_scene_v3_phaseaware50/manifest.json"
    )
    checkpoint_path = ROOT / (
        "runs/smolvla_s3/recovery_v3_lora_20260723T125632Z/"
        "checkpoint_config_audit.json"
    )
    s4_path = ROOT / (
        "evidence/smolvla_s4_bounded5_relight_20260724T151711Z/s4_gate.json"
    )
    if not all(path.is_file() for path in (open_loop_path, release_path, checkpoint_path, s4_path)):
        return

    public_open = json.loads((BUNDLE / "open_loop_gate_summary.json").read_text())
    raw_open = json.loads(open_loop_path.read_text())
    assert public_open["gate_decision"] == raw_open["gate_decision"]
    assert public_open["metrics"]["ee_position_rmse_m"] == raw_open["lora"]["metrics"][
        "ee_position_rmse_m"
    ]
    assert public_open["metrics"]["gripper_balanced_accuracy"] == raw_open["lora"][
        "metrics"
    ]["gripper_balanced_accuracy"]
    assert public_open["prospective_evaluation"]["evaluation_episode_count"] == raw_open[
        "prospective_evaluation"
    ]["evaluation_episode_count"]

    public_release = json.loads((BUNDLE / "release_checkpoint_summary.json").read_text())
    raw_release = json.loads(release_path.read_text())
    raw_checkpoint = json.loads(checkpoint_path.read_text())
    assert public_release["release"]["release_content_sha256"] == raw_release[
        "release_content_sha256"
    ]
    assert public_release["release"]["split_counts"] == {
        name: len(rows) for name, rows in raw_release["splits"].items()
    }
    assert public_release["checkpoint_audit"]["adapter_model_sha256"] == raw_checkpoint[
        "adapter_model_sha256"
    ]
    assert public_release["checkpoint_audit"]["all_contract_checks_passed"] is all(
        raw_checkpoint["checks"].values()
    )

    assert json.loads((BUNDLE / "s4_gate.json").read_text()) == json.loads(
        s4_path.read_text()
    )


def test_public_s4_gate_matches_per_seed_funnel() -> None:
    gate = json.loads((BUNDLE / "s4_gate.json").read_text(encoding="utf-8"))
    episodes = json.loads(
        (BUNDLE / "s4_per_seed_summary.json").read_text(encoding="utf-8")
    )["episodes"]
    assert len(episodes) == gate["episodes_recorded"] == 5
    assert sum(row["reach"] for row in episodes) == gate["reach"] == 1
    assert sum(row["grasp"] for row in episodes) == gate["grasp"] == 0
    assert sum(row["lift"] for row in episodes) == gate["lift"] == 0
    assert gate["gate_pass"] is False
