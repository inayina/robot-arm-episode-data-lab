"""P1 unified evaluation report contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from evaluation.unified_report import (
    BACKEND_ISAAC_S4,
    BACKEND_OPEN_LOOP,
    BACKEND_POLICY_RUNNER,
    CONTRACT_VERSION,
    build_framework_bundle,
    normalize_isaac_s4,
    normalize_open_loop,
    normalize_path_auto,
    normalize_policy_runner,
    validate_unified_report,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "evaluation/schemas/unified_eval_report.schema.json"

OPEN_LOOP_SUMMARY = (
    ROOT
    / "runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z"
    / "s3_open_loop_summary.json"
)
POLICY_RUNNER = ROOT / "evidence/downstream/smolvla_v3_ep0_benchmark_summary.json"
# Authoritative bounded S4 = post-light-fix relight rerun of the same seeds 1-5.
S4_GATE = ROOT / "evidence/smolvla_s4_bounded5_relight_20260724T151711Z/s4_gate.json"
# Superseded dark-scene first round; kept so historical evidence stays contract-valid.
S4_GATE_HISTORICAL = ROOT / "evidence/smolvla_s4_bounded5_20260724T203700Z/s4_gate.json"


def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_schema_is_valid_draft_2020_12() -> None:
    _validator()


def test_open_loop_fixture_fields_and_non_claims() -> None:
    summary = json.loads(OPEN_LOOP_SUMMARY.read_text(encoding="utf-8"))
    report = normalize_open_loop(summary, primary_path=str(OPEN_LOOP_SUMMARY))
    assert validate_unified_report(report) == []
    _validator().validate(report)

    assert report["contract_version"] == CONTRACT_VERSION
    assert report["backend_id"] == BACKEND_OPEN_LOOP
    assert report["claims_task_success"] is False
    assert report["claims_sim2real"] is False
    assert report["claims_online_autonomous_grasp"] is False
    assert report["columns"]["offline"]["evaluated"] is True
    assert report["columns"]["task"]["evaluated"] is False
    assert report["columns"]["offline"]["metrics"]["lora_ee_rmse"] == summary["lora_ee_rmse"]
    assert report["failure_lane"] == "none"
    assert report["gate_decision"] == "pass"


def test_policy_runner_defaults_claims_false() -> None:
    summary = json.loads(POLICY_RUNNER.read_text(encoding="utf-8"))
    assert "claims_task_success" not in summary
    report = normalize_policy_runner(summary, primary_path=str(POLICY_RUNNER))
    assert validate_unified_report(report) == []
    _validator().validate(report)
    assert report["backend_id"] == BACKEND_POLICY_RUNNER
    assert report["claims_task_success"] is False
    assert report["claims_sim2real"] is False
    assert report["columns"]["interface"]["evaluated"] is True
    assert report["columns"]["task"]["evaluated"] is False
    assert report["columns"]["task"]["metrics"]["is_closed_loop"] is False
    assert report["failure_lane"] == "none"


@pytest.mark.parametrize("gate_path", [S4_GATE, S4_GATE_HISTORICAL])
def test_isaac_s4_maps_task_funnel_and_keeps_non_claims(gate_path: Path) -> None:
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    report = normalize_isaac_s4(gate, primary_path=str(gate_path))
    assert validate_unified_report(report) == []
    _validator().validate(report)
    assert report["backend_id"] == BACKEND_ISAAC_S4
    assert report["claims_task_success"] is False
    assert report["claims_sim2real"] is False
    assert report["columns"]["interface"]["metrics"]["policy_interface_pass"] == 5
    assert report["columns"]["task"]["metrics"]["lift"] == 0
    assert report["columns"]["task"]["metrics"]["gate_pass"] is False
    assert report["failure_lane"] == "task_gt"


def test_published_envelope_uses_authoritative_relight_gate() -> None:
    """The published bundle must envelope the post-light-fix run, not the dark one."""
    bundle_path = (
        ROOT
        / "evidence/smolvla_v3_eval_framework_relight_20260725"
        / "smolvla_v3_eval_framework_bundle.json"
    )
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    isaac = next(r for r in bundle["backends"] if r["backend_id"] == BACKEND_ISAAC_S4)
    gate = json.loads(S4_GATE.read_text(encoding="utf-8"))
    task = isaac["columns"]["task"]["metrics"]
    for key in ("reach", "grasp", "lift", "outcome_success"):
        assert task[key] == gate[key]
    assert bundle["claims_task_success"] is False


def test_schema_rejects_task_success_claim() -> None:
    report = normalize_path_auto(OPEN_LOOP_SUMMARY)
    report["claims_task_success"] = True
    with pytest.raises(ValidationError):
        _validator().validate(report)
    assert "claims_task_success must be false" in validate_unified_report(report)


def test_bundle_contains_three_backends() -> None:
    reports = [
        normalize_path_auto(OPEN_LOOP_SUMMARY),
        normalize_path_auto(POLICY_RUNNER),
        normalize_path_auto(S4_GATE),
    ]
    bundle = build_framework_bundle(
        reports, bundle_id="smolvla_v3_eval_framework_test"
    )
    assert bundle["artifact_type"] == "smolvla_v3_eval_framework_bundle"
    assert bundle["claims_task_success"] is False
    assert len(bundle["backends"]) == 3
    assert {r["backend_id"] for r in bundle["backends"]} == {
        BACKEND_OPEN_LOOP,
        BACKEND_POLICY_RUNNER,
        BACKEND_ISAAC_S4,
    }
    assert "appendix" not in bundle


def test_bundle_risk_appendix_does_not_override_failure_lane() -> None:
    reports = [
        normalize_path_auto(OPEN_LOOP_SUMMARY),
        normalize_path_auto(POLICY_RUNNER),
        normalize_path_auto(S4_GATE),
    ]
    prior_lanes = {r["backend_id"]: r["failure_lane"] for r in reports}
    appendix = {
        "artifact_type": "risk_offline_readiness",
        "risk_level": 1,
        "composite_score": 0.12,
        "primary_driver": "comm_health",
        "claims_task_success": True,  # must be forced false
        "overrides_failure_lane": True,  # must be forced false
    }
    bundle = build_framework_bundle(
        reports,
        bundle_id="smolvla_v3_eval_framework_test",
        risk_readiness_appendix=appendix,
    )
    risk = bundle["appendix"]["risk_readiness"]
    assert risk["claims_task_success"] is False
    assert risk["overrides_failure_lane"] is False
    assert risk["use_as_task_go_no_go"] is False
    for report in bundle["backends"]:
        assert report["failure_lane"] == prior_lanes[report["backend_id"]]
    isaac = next(r for r in bundle["backends"] if r["backend_id"] == BACKEND_ISAAC_S4)
    assert isaac["failure_lane"] == "task_gt"
    assert isaac["claims_task_success"] is False
