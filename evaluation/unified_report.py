"""Unified evaluation report v0 — minimal cross-backend envelope.

Maps existing SmolVLA open-loop, downstream PolicyRunner benchmark, and Isaac S4
gate JSON into one contract with interface / behavior / task / offline columns.

Does not invent metrics, retrain, expand seeds, or claim task success / Sim2Real.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

CONTRACT_VERSION = "unified_eval_report_v0"
ARTIFACT_TYPE = "unified_eval_report"
BUNDLE_ARTIFACT_TYPE = "smolvla_v3_eval_framework_bundle"

BACKEND_OPEN_LOOP = "smolvla_open_loop"
BACKEND_POLICY_RUNNER = "downstream_policy_runner"
BACKEND_ISAAC_S4 = "isaac_s4_bounded"

FAILURE_LANES = (
    "none",
    "data_fail",
    "interface_fail",
    "behavior_tag",
    "task_gt",
    "system_fail",
)

DEFAULT_NON_CLAIMS = (
    "Does not claim task success.",
    "Does not claim Sim2Real.",
    "Does not claim online autonomous grasp.",
    "Open-loop / interface Pass is not runtime GT success.",
)

REQUIRED_KEYS = (
    "contract_version",
    "artifact_type",
    "evaluation_run_id",
    "backend_id",
    "claims_task_success",
    "claims_sim2real",
    "claims_online_autonomous_grasp",
    "failure_lane",
    "columns",
    "source",
    "non_claims",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _column(*, evaluated: bool, metrics: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"evaluated": bool(evaluated), "metrics": dict(metrics or {})}


def _base_envelope(
    *,
    evaluation_run_id: str,
    backend_id: str,
    failure_lane: str,
    columns: Mapping[str, Any],
    source: Mapping[str, Any],
    gate_decision: str | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    if failure_lane not in FAILURE_LANES:
        raise ValueError(f"invalid failure_lane: {failure_lane}")
    payload = {
        "contract_version": CONTRACT_VERSION,
        "artifact_type": ARTIFACT_TYPE,
        "evaluation_run_id": evaluation_run_id,
        "backend_id": backend_id,
        "gate_decision": gate_decision,
        "claims_task_success": False,
        "claims_sim2real": False,
        "claims_online_autonomous_grasp": False,
        "failure_lane": failure_lane,
        "columns": {
            "interface": columns["interface"],
            "behavior": columns["behavior"],
            "task": columns["task"],
            "offline": columns["offline"],
        },
        "source": dict(source),
        "non_claims": list(DEFAULT_NON_CLAIMS),
    }
    if notes:
        payload["notes"] = list(notes)
    return payload


def validate_unified_report(payload: Mapping[str, Any]) -> list[str]:
    """Return human-readable errors; empty list means structurally OK for P1."""
    errors: list[str] = []
    for key in REQUIRED_KEYS:
        if key not in payload:
            errors.append(f"missing required key: {key}")
    if payload.get("contract_version") != CONTRACT_VERSION:
        errors.append("contract_version must be unified_eval_report_v0")
    if payload.get("artifact_type") != ARTIFACT_TYPE:
        errors.append("artifact_type must be unified_eval_report")
    for claim in (
        "claims_task_success",
        "claims_sim2real",
        "claims_online_autonomous_grasp",
    ):
        if payload.get(claim) is not False:
            errors.append(f"{claim} must be false")
    if payload.get("failure_lane") not in FAILURE_LANES:
        errors.append(f"failure_lane invalid: {payload.get('failure_lane')}")
    columns = payload.get("columns")
    if not isinstance(columns, dict):
        errors.append("columns must be an object")
    else:
        for name in ("interface", "behavior", "task", "offline"):
            col = columns.get(name)
            if not isinstance(col, dict):
                errors.append(f"columns.{name} missing")
                continue
            if "evaluated" not in col or "metrics" not in col:
                errors.append(f"columns.{name} needs evaluated+metrics")
            elif not isinstance(col["metrics"], dict):
                errors.append(f"columns.{name}.metrics must be object")
    return errors


def normalize_open_loop(
    summary: Mapping[str, Any],
    *,
    primary_path: str,
    evaluation_run_id: str | None = None,
    report: Mapping[str, Any] | None = None,
    companion_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Map s3_open_loop_summary.json (+ optional report) → unified report."""
    run_id = evaluation_run_id or Path(primary_path).parent.name
    gate = summary.get("gate_decision")
    if gate is None and report is not None:
        gate = report.get("gate_decision")
    gate_s = str(gate).lower() if gate is not None else None

    checkpoint_ok = bool(summary.get("checkpoint_config_verified"))
    if report is not None:
        lora = report.get("lora") if isinstance(report.get("lora"), dict) else {}
        interface_ok = bool(lora.get("interface_ok", checkpoint_ok))
        latency_p50 = lora.get("latency_ms_p50", summary.get("lora_latency_ms_p50"))
        latency_p95 = lora.get("latency_ms_p95", summary.get("lora_latency_ms_p95"))
    else:
        interface_ok = checkpoint_ok
        latency_p50 = summary.get("lora_latency_ms_p50")
        latency_p95 = summary.get("lora_latency_ms_p95")

    if gate_s == "pass":
        failure_lane = "none"
    elif not interface_ok or not checkpoint_ok:
        failure_lane = "interface_fail"
    else:
        failure_lane = "behavior_tag"

    columns = {
        "interface": _column(
            evaluated=True,
            metrics={
                "checkpoint_config_verified": checkpoint_ok,
                "interface_ok": interface_ok,
                "latency_ms_p50": latency_p50,
                "latency_ms_p95": latency_p95,
            },
        ),
        "behavior": _column(
            evaluated=True,
            metrics={
                "lora_close_offset_frames_signed": summary.get(
                    "lora_close_offset_frames_signed"
                ),
                "lora_close_offset_seconds_signed": summary.get(
                    "lora_close_offset_seconds_signed"
                ),
                "lora_raw_gripper_oob_beyond_epsilon_ratio": summary.get(
                    "lora_raw_gripper_oob_beyond_epsilon_ratio"
                ),
            },
        ),
        "task": _column(
            evaluated=False,
            metrics={
                "reach": None,
                "grasp": None,
                "lift": None,
                "outcome_success": None,
                "note": "open_loop_has_no_runtime_gt",
            },
        ),
        "offline": _column(
            evaluated=True,
            metrics={
                "gate_decision": gate_s,
                "lora_ee_rmse": summary.get("lora_ee_rmse"),
                "lora_grip_balanced_acc": summary.get("lora_grip_balanced_acc"),
                "lora_gripper_clip_adjustment_mae": summary.get(
                    "lora_gripper_clip_adjustment_mae"
                ),
                "relative_ee_improvement_vs_s2": summary.get(
                    "relative_ee_improvement_vs_s2"
                ),
                "prospective_eval_eligible": summary.get("prospective_eval_eligible"),
                "full_episode_coverage": summary.get("full_episode_coverage"),
            },
        ),
    }
    mapped = [
        "gate_decision",
        "lora_ee_rmse",
        "lora_grip_balanced_acc",
        "lora_close_offset_frames_signed",
        "lora_latency_ms_p50",
        "checkpoint_config_verified",
        "claims_task_success:=false",
    ]
    return _base_envelope(
        evaluation_run_id=run_id,
        backend_id=BACKEND_OPEN_LOOP,
        failure_lane=failure_lane,
        columns=columns,
        gate_decision=gate_s,
        source={
            "backend_id": BACKEND_OPEN_LOOP,
            "primary_path": primary_path,
            "companion_paths": list(companion_paths or []),
            "mapped_from": mapped,
        },
        notes=[
            "Offline open-loop / gate_v3 only; not Isaac task success.",
            "Task column intentionally unevaluated.",
        ],
    )


def normalize_policy_runner(
    summary: Mapping[str, Any],
    *,
    primary_path: str,
    evaluation_run_id: str | None = None,
) -> dict[str, Any]:
    """Map PolicyRunner benchmark_summary.json → unified report."""
    run_id = (
        evaluation_run_id
        or str(summary.get("handoff_id") or "")
        or Path(primary_path).stem
    )
    episodes = int(summary.get("episodes") or 0)
    completed = int(summary.get("completed_episodes") or 0)
    if episodes > 0 and completed < episodes:
        failure_lane = "system_fail"
        gate = "incomplete"
    else:
        failure_lane = "none"
        gate = "smoke_complete"

    columns = {
        "interface": _column(
            evaluated=True,
            metrics={
                "strategy": summary.get("strategy"),
                "panda_command_mode": summary.get("panda_command_mode"),
                "completed_episodes": completed,
                "episodes": episodes,
                "mean_latency_ms": summary.get("mean_latency_ms"),
                "max_latency_ms": summary.get("max_latency_ms"),
                "health_alarm_detected_within_1s": summary.get(
                    "health_alarm_detected_within_1s"
                ),
                "timeseries_rows": summary.get("timeseries_rows"),
            },
        ),
        "behavior": _column(
            evaluated=False,
            metrics={"note": "policy_runner_smoke_has_no_behavior_tags"},
        ),
        "task": _column(
            evaluated=False,
            metrics={
                "reach": None,
                "grasp": None,
                "lift": None,
                "outcome_success": None,
                "is_closed_loop": False,
                "note": "open_loop_jsonl_replay_not_runtime_gt",
            },
        ),
        "offline": _column(
            evaluated=False,
            metrics={"note": "not_an_open_loop_metric_source"},
        ),
    }
    return _base_envelope(
        evaluation_run_id=run_id,
        backend_id=BACKEND_POLICY_RUNNER,
        failure_lane=failure_lane,
        columns=columns,
        gate_decision=gate,
        source={
            "backend_id": BACKEND_POLICY_RUNNER,
            "primary_path": primary_path,
            "companion_paths": [],
            "mapped_from": [
                "strategy",
                "panda_command_mode",
                "completed_episodes",
                "mean_latency_ms",
                "handoff_id",
                "claims_task_success:=false",
            ],
        },
        notes=[
            "Downstream PolicyRunner / pybullet_ik smoke only.",
            "is_closed_loop=false; not grasp success.",
        ],
    )


def normalize_isaac_s4(
    gate: Mapping[str, Any],
    *,
    primary_path: str,
    evaluation_run_id: str | None = None,
    summary: Mapping[str, Any] | None = None,
    companion_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Map s4_gate.json (+ optional contract summary) → unified report."""
    run_id = evaluation_run_id
    if not run_id and summary is not None:
        run_id = summary.get("evaluation_run_id")
    if not run_id:
        run_id = Path(primary_path).parent.name

    interface_pass = int(gate.get("policy_interface_pass") or 0)
    episodes = int(gate.get("episodes_recorded") or gate.get("seeds_planned") or 0)
    lift = int(gate.get("lift") or 0)
    outcome = int(gate.get("outcome_success") or 0)
    gate_pass = bool(gate.get("gate_pass")) if "gate_pass" in gate else None

    if episodes > 0 and interface_pass < episodes:
        failure_lane = "interface_fail"
    elif not gate_pass and (lift == 0 or outcome == 0):
        failure_lane = "task_gt"
    elif gate_pass:
        failure_lane = "none"
    else:
        failure_lane = "task_gt"

    if gate_pass is True:
        gate_decision = "pass"
    elif gate_pass is False:
        gate_decision = str(gate.get("interpretation") or "hold")
    else:
        gate_decision = None

    # Source may already carry false claims; still force false in envelope.
    columns = {
        "interface": _column(
            evaluated=True,
            metrics={
                "policy_interface_pass": interface_pass,
                "policy_reports": gate.get("policy_reports"),
                "episodes_recorded": gate.get("episodes_recorded"),
                "seeds_planned": gate.get("seeds_planned"),
                "ran_isaac": gate.get("ran_isaac"),
            },
        ),
        "behavior": _column(
            evaluated=False,
            metrics={"note": "s4_gate_exposes_subgoals_under_task_column"},
        ),
        "task": _column(
            evaluated=True,
            metrics={
                "reach": gate.get("reach"),
                "grasp": gate.get("grasp"),
                "lift": gate.get("lift"),
                "outcome_success": gate.get("outcome_success"),
                "pass_threshold": gate.get("pass_threshold"),
                "gate_pass": gate_pass,
            },
        ),
        "offline": _column(
            evaluated=False,
            metrics={"note": "isaac_s4_is_runtime_not_open_loop"},
        ),
    }
    return _base_envelope(
        evaluation_run_id=str(run_id),
        backend_id=BACKEND_ISAAC_S4,
        failure_lane=failure_lane,
        columns=columns,
        gate_decision=gate_decision,
        source={
            "backend_id": BACKEND_ISAAC_S4,
            "primary_path": primary_path,
            "companion_paths": list(companion_paths or []),
            "mapped_from": [
                "policy_interface_pass",
                "reach",
                "grasp",
                "lift",
                "outcome_success",
                "gate_pass",
                "ran_isaac",
                "claims_task_success",
                "claims_sim2real",
            ],
        },
        notes=[
            "Bounded Isaac S4 GT funnel only.",
            "lift/outcome counts are diagnostic; claims_* remain false.",
        ],
    )


def build_framework_bundle(
    reports: list[Mapping[str, Any]],
    *,
    bundle_id: str,
    risk_readiness_appendix: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    for report in reports:
        errs = validate_unified_report(report)
        if errs:
            raise ValueError(f"invalid unified report in bundle: {errs}")
    payload: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "artifact_type": BUNDLE_ARTIFACT_TYPE,
        "evaluation_run_id": bundle_id,
        "claims_task_success": False,
        "claims_sim2real": False,
        "claims_online_autonomous_grasp": False,
        "backends": [dict(r) for r in reports],
        "non_claims": list(DEFAULT_NON_CLAIMS),
        "notes": [
            "One framework envelope, three backends (open-loop / PolicyRunner / Isaac S4).",
            "Metrics are remapped from existing evidence only.",
        ],
    }
    if risk_readiness_appendix is not None:
        # Appendix only — must not rewrite backend failure_lane or task GT.
        appendix = dict(risk_readiness_appendix)
        appendix["claims_task_success"] = False
        appendix["overrides_failure_lane"] = False
        appendix["use_as_task_go_no_go"] = False
        payload["appendix"] = {"risk_readiness": appendix}
        payload["notes"].append(
            "appendix.risk_readiness is offline RiskAggregator对照; "
            "not task go/no-go and does not override failure_lane."
        )
    return payload


def normalize_path_auto(path: Path) -> dict[str, Any]:
    """Dispatch by filename conventions used in SmolVLA v3 evidence."""
    path = path.resolve()
    name = path.name
    if name == "s3_open_loop_summary.json" or name.endswith("open_loop_summary.json"):
        report_path = path.with_name("s3_open_loop_report.json")
        report = load_json(report_path) if report_path.is_file() else None
        companions = [str(report_path)] if report is not None else []
        return normalize_open_loop(
            load_json(path),
            primary_path=str(path),
            report=report,
            companion_paths=companions,
        )
    if name.endswith("benchmark_summary.json"):
        return normalize_policy_runner(load_json(path), primary_path=str(path))
    if name == "s4_gate.json":
        summary_path = path.with_name("summary.json")
        summary = load_json(summary_path) if summary_path.is_file() else None
        companions = [str(summary_path)] if summary is not None else []
        return normalize_isaac_s4(
            load_json(path),
            primary_path=str(path),
            summary=summary,
            companion_paths=companions,
        )
    raise ValueError(f"cannot auto-detect backend for {path}")
