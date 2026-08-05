"""CPU-only tests for the solution policy onboarding preflight."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from evaluation.policy_onboarding import load_bundle, validate_bundle


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evaluation" / "examples" / "policy_onboarding_fixture"
BASE = FIXTURE / "base"
CASES = FIXTURE / "cases"
VALIDATOR = ROOT / "scripts" / "validate_policy_onboarding.py"
POC = ROOT / "scripts" / "run_policy_onboarding_poc.py"
REHEARSAL = ROOT / "scripts" / "run_policy_onboarding_rehearsal.py"
REHEARSAL_EVIDENCE = (
    ROOT
    / "evidence"
    / "solution_architect"
    / "policy_onboarding_rehearsal_20260730"
    / "rehearsal_summary.json"
)


@pytest.mark.parametrize(
    ("case_name", "expected_status", "expected_reason"),
    (
        ("valid_bundle", "pass", "none"),
        ("invalid_action_dim", "invalid", "action_dimension_invalid"),
        ("invalid_hash", "invalid", "contract_mismatch"),
        ("invalid_sequence", "hold", "command_sequence_regression"),
    ),
)
def test_frozen_onboarding_cases(
    case_name: str, expected_status: str, expected_reason: str
) -> None:
    report = validate_bundle(BASE, CASES / f"{case_name}.json")
    assert report["case_id"] == case_name
    assert report["template_version"] == 1
    assert report["report_version"] == "solution_policy_preflight_v1"
    assert report["source_bundle"] == str(BASE.resolve())
    assert report["status"] == expected_status
    reasons = {
        check["reason_code"]
        for check in report["checks"]
        if check["status"] != "pass"
    }
    if expected_reason == "none":
        assert not reasons
        assert report["next_allowed_stage"] == "offline_or_interface_evaluation"
    else:
        assert expected_reason in reasons
        assert report["next_allowed_stage"] == "remediation_only"
    assert report["claims_task_success"] is False
    assert report["claims_sim2real"] is False
    assert report["claims_online_autonomous_grasp"] is False
    assert report["authorized_simulation"] is False
    assert report["authorized_training"] is False
    assert report["authorized_real_robot"] is False


def test_fixture_cases_are_single_purpose_and_do_not_modify_base() -> None:
    original = load_bundle(BASE)
    mutated = load_bundle(BASE, CASES / "invalid_action_dim.json")
    assert len(original["sample_action"]["action"]) == 8
    assert len(mutated["sample_action"]["action"]) == 7
    assert load_bundle(BASE)["sample_action"] == original["sample_action"]


@pytest.mark.parametrize(
    ("case_name", "expected_exit"),
    (("valid_bundle", 0), ("invalid_sequence", 2), ("invalid_hash", 3)),
)
def test_validator_cli_exit_codes(
    tmp_path: Path, case_name: str, expected_exit: int
) -> None:
    output = tmp_path / f"{case_name}.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--bundle",
            str(BASE),
            "--case",
            str(CASES / f"{case_name}.json"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == expected_exit, completed.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["case_id"] == case_name


def test_one_command_poc_emits_four_matching_reports(tmp_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(POC), "--output-dir", str(tmp_path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads((tmp_path / "poc_summary.json").read_text(encoding="utf-8"))
    assert summary["all_cases_matched"] is True
    assert len(summary["cases"]) == 4
    assert all(case["matched"] for case in summary["cases"])
    assert summary["claims_task_success"] is False
    assert "Not task success" in completed.stdout


def test_artifact_path_cannot_escape_bundle(tmp_path: Path) -> None:
    documents = load_bundle(BASE)
    documents["artifact_manifest"]["artifacts"][0]["path"] = "../outside.ckpt"
    case = tmp_path / "escape.json"
    case.write_text(
        json.dumps(
            {
                "case_id": "escape",
                "mutations": [
                    {
                        "document": "artifact_manifest",
                        "path": ["artifacts", 0, "path"],
                        "value": "../outside.ckpt",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report = validate_bundle(BASE, case)
    integrity = next(check for check in report["checks"] if check["gate"] == "G1_integrity")
    assert integrity["status"] == "invalid"
    assert "escapes bundle" in integrity["errors"][0]


def test_two_run_rehearsal_is_normalized_and_non_claiming(tmp_path: Path) -> None:
    output = tmp_path / "rehearsal"
    completed = subprocess.run(
        [sys.executable, str(REHEARSAL), "--output-dir", str(output)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads((output / "rehearsal_summary.json").read_text(encoding="utf-8"))
    assert summary["rehearsal_runs"] == 2
    assert summary["normalized_equivalent"] is True
    assert summary["all_cases_matched"] is True
    assert summary["runs"][0]["normalized_sha256"] == summary["runs"][1]["normalized_sha256"]
    assert summary["acceptance"] == {
        "nfr_02_reproducibility": "pass",
        "poc_fixture_expectations": "pass",
        "recorded_eight_minute_demo": "not_run",
    }
    assert summary["claims_task_success"] is False
    assert summary["authorized_simulation"] is False


def test_rehearsal_refuses_to_overwrite_evidence(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    (output / "keep.txt").write_text("user evidence\n", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(REHEARSAL), "--output-dir", str(output)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 4
    assert (output / "keep.txt").read_text(encoding="utf-8") == "user evidence\n"


def test_frozen_rehearsal_evidence_matches_reported_result() -> None:
    summary = json.loads(REHEARSAL_EVIDENCE.read_text(encoding="utf-8"))
    assert summary["normalized_equivalent"] is True
    assert summary["all_cases_matched"] is True
    assert [run["batch_validation_and_write_elapsed_ms"] for run in summary["runs"]] == [
        17.923,
        16.47,
    ]
    assert {run["normalized_sha256"] for run in summary["runs"]} == {
        "b3f0e9e2a365effd97d447b1c50d7aa325d4b62bec5cd945990389bfa491a004"
    }
    assert summary["acceptance"]["nfr_02_reproducibility"] == "pass"
    assert summary["acceptance"]["recorded_eight_minute_demo"] == "not_run"
    assert summary["claims_task_success"] is False
    assert summary["claims_sim2real"] is False
    assert summary["authorized_real_robot"] is False
