"""Portfolio finalization invariants: docs consistency, honest claims, evidence traceability.

CPU-only. These tests guard the 2026-07-25 portfolio freeze:

* the mandated summary docs exist and keep their honest-boundary disclaimers;
* headline numbers quoted in prose match the raw frozen JSON;
* the authoritative bounded-S4 run is the relight rerun and the dark-scene first
  run stays labelled Superseded;
* no "current status" doc reverts to stale claims (S3 untrained / Isaac not run);
* relative markdown links in the portfolio entry docs resolve on disk.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PORTFOLIO = DOCS / "portfolio"

FINAL_SUMMARY = PORTFOLIO / "FINAL_PROJECT_SUMMARY.md"
PORTFOLIO_MASTER = PORTFOLIO / "PORTFOLIO_REFERENCE.md"
BADCASE = PORTFOLIO / "BADCASE_ATTRIBUTION_SUMMARY.md"
ROADMAP = DOCS / "FUTURE_WORK_ROADMAP.md"
PERTURBATION_DESIGN = DOCS / "SMOLVLA_OPENLOOP_PERTURBATION_DESIGN.md"
RESUME = PORTFOLIO / "resume_description.md"
CANONICAL_FACTS = PORTFOLIO / "THREE_REPO_CANONICAL_FACTS.md"
EVIDENCE_INDEX = PORTFOLIO / "EVIDENCE_INDEX.md"
PORTFOLIO_NAV = PORTFOLIO / "README.md"
UNIFIED_DOC = PORTFOLIO / "UNIFIED_EVAL_REPORT.md"
V3_PORTFOLIO = PORTFOLIO / "SMOLVLA_RECOVERY_V3_PORTFOLIO.md"
V3_SOP = DOCS / "SMOLVLA_V3_EVAL_SOP.md"
S3_READY = DOCS / "SMOLVLA_GATE_S3_READY.md"
TRACKS = PORTFOLIO / "tracks"
TRACKS_NAV = TRACKS / "README.md"
TECHNICAL_INTERVIEW_TRACK = TRACKS / "technical_interview" / "README.md"
SOLUTION_ARCHITECT_TRACK = TRACKS / "solution_architect" / "README.md"
RESEARCH_ASSISTANT_TRACK = TRACKS / "research_assistant" / "README.md"
RESEARCH_ASSISTANT_DIR = TRACKS / "research_assistant"
RESEARCH_ASSISTANT_DOCS = tuple(
    RESEARCH_ASSISTANT_DIR / name
    for name in (
        "RESEARCH_BRIEF.md",
        "HYPOTHESIS_EVIDENCE_MATRIX.md",
        "EXPERIMENT_PREREGISTRATION.md",
        "CLOSED_LOOP_SHIFT_RESULTS.md",
        "RELATED_WORK_MATRIX.md",
        "NEGATIVE_RESULTS_AND_THREATS.md",
        "REPRODUCIBILITY_GUIDE.md",
        "RA_APPLICATION_BRIEF.md",
        "RA_RESEARCH_SLIDES.md",
    )
)
RESEARCH_IDENTITY = RESEARCH_ASSISTANT_DIR / "research_identity.yaml"
SOLUTION_TRACK_DIR = TRACKS / "solution_architect"
SOLUTION_TRACK_DOCS = tuple(
    SOLUTION_TRACK_DIR / name
    for name in (
        "SOLUTION_BRIEF.md",
        "CUSTOMER_DISCOVERY_QUESTIONNAIRE.md",
        "REFERENCE_ARCHITECTURE.md",
        "POLICY_ONBOARDING_GUIDE.md",
        "CUSTOMER_ACCEPTANCE_MATRIX.md",
        "DEPLOYMENT_AND_OPERATIONS_RUNBOOK.md",
        "POC_DEMO_SCRIPT.md",
        "SECURITY_COST_CHECKLIST.md",
        "SOLUTION_ARCHITECT_EXECUTIVE_DECK.md",
    )
)
SOLUTION_TEMPLATE_DIR = SOLUTION_TRACK_DIR / "templates"
SOLUTION_YAML_TEMPLATES = tuple(
    SOLUTION_TEMPLATE_DIR / name
    for name in (
        "solution_scope.template.yaml",
        "policy_identity.template.yaml",
        "observation_schema.template.yaml",
        "action_schema.template.yaml",
        "runtime_contract.template.yaml",
        "adapter_mapping.template.yaml",
        "acceptance_report.template.yaml",
        "cost_estimate.template.yaml",
    )
)
SOLUTION_JSON_TEMPLATES = tuple(
    SOLUTION_TEMPLATE_DIR / name
    for name in (
        "artifact_manifest.template.json",
        "preflight_report.template.json",
    )
)
RA_STRENGTHENING_SPEC = PORTFOLIO / "RA_RESEARCH_ASSISTANT_STRENGTHENING_SPEC.md"
SOLUTION_ARCHITECT_STRENGTHENING_SPEC = (
    PORTFOLIO / "PRODUCT_SOLUTION_ARCHITECT_STRENGTHENING_SPEC.md"
)
README = ROOT / "README.md"
AGENTS = ROOT / "AGENTS.md"

S4_AUTHORITATIVE = ROOT / "evidence" / "smolvla_s4_bounded5_relight_20260724T151711Z" / "s4_gate.json"
S4_SUPERSEDED = ROOT / "evidence" / "smolvla_s4_bounded5_20260724T203700Z" / "s4_gate.json"
OPEN_LOOP_REPORT = (
    ROOT
    / "runs"
    / "smolvla_s3"
    / "openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z"
    / "s3_open_loop_report.json"
)
RECOVERY_DECISIONS = ROOT / "configs" / "smolvla_s3" / "recovery_decisions.yaml"
FIGURE_SCRIPT = ROOT / "scripts" / "generate_smolvla_v3_portfolio_figures.py"

REQUIRED_DOCS = (PORTFOLIO_MASTER, FINAL_SUMMARY, BADCASE, ROADMAP, RESUME)

# Docs that describe the *current* project state; stale wording here misleads readers.
CURRENT_STATE_DOCS = (
    README,
    AGENTS,
    PORTFOLIO_MASTER,
    FINAL_SUMMARY,
    BADCASE,
    ROADMAP,
    RESUME,
    CANONICAL_FACTS,
    EVIDENCE_INDEX,
    UNIFIED_DOC,
    V3_PORTFOLIO,
)

MD_LINK = re.compile(r"\[[^\]]*\]\((?!https?://|mailto:|file://|#)([^)#\s]+)")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", REQUIRED_DOCS, ids=lambda p: p.name)
def test_mandated_portfolio_docs_exist_and_are_substantive(path: Path) -> None:
    assert path.exists(), f"missing mandated portfolio doc: {path}"
    assert len(_read(path)) > 2000


def test_final_summary_covers_required_sections() -> None:
    text = _read(FINAL_SUMMARY)
    for heading in (
        "项目一句话定位",
        "系统架构与三仓边界",
        "评测框架",
        "当前结论",
        "Badcase 归因",
        "诚实边界",
    ):
        assert heading in text, f"FINAL_PROJECT_SUMMARY missing section: {heading}"
    assert "具身策略数据治理与分层验证框架" in text


def test_portfolio_master_supports_five_and_thirty_minute_readers() -> None:
    text = _read(PORTFOLIO_MASTER)
    for marker in (
        "我把一个机器人学习 demo，做成了可排查、可验证的软硬件系统",
        "30 秒看懂这个项目",
        "我做了什么",
        "系统如何工作",
        "一次跨软硬件链条的排查",
        "技术面试可以从哪里继续",
        "可以聊半小时的问题",
        "portfolio_fault_localization_chain.svg",
        "portfolio_system_overview.svg",
        "portfolio_control_safety_stack.svg",
        "portfolio_realtime_priority_gantt.svg",
        "portfolio_data_evidence_flow.svg",
        "smolvla_recovery_v3_openloop_ee_vs_s2.png",
        "smolvla_s4_bounded5_funnel.png",
        "内核层",
        "内存层",
        "FIFO 50",
        "priority=0",
        "EMCY",
        "奈奎斯特",
        "Hardware Pending",
        "Not task success",
    ):
        assert marker in text, f"portfolio master missing: {marker}"


def test_portfolio_navigation_promotes_master_and_human_architecture() -> None:
    text = _read(PORTFOLIO_NAV)
    assert "PORTFOLIO_REFERENCE.md" in text
    assert "portfolio_fault_localization_chain.svg" in text
    assert "portfolio_system_overview.svg" in text
    assert "portfolio_control_safety_stack.svg" in text
    assert "portfolio_realtime_priority_gantt.svg" in text
    assert "5 分钟" in text and "30 分钟" in text


@pytest.mark.parametrize("path", SOLUTION_TRACK_DOCS, ids=lambda p: p.name)
def test_solution_architect_docs_exist_and_are_substantive(path: Path) -> None:
    assert path.is_file(), f"missing solution architect deliverable: {path}"
    text = _read(path)
    assert len(text) > 1200
    assert "task success" in text.lower() or "任务成功" in text


@pytest.mark.parametrize("path", SOLUTION_YAML_TEMPLATES, ids=lambda p: p.name)
def test_solution_yaml_templates_are_parseable_and_non_claiming(path: Path) -> None:
    payload = yaml.safe_load(_read(path))
    assert isinstance(payload, dict)
    assert payload.get("template_version") == 1
    text = _read(path).lower()
    if "claims" in payload:
        assert payload["claims"].get("task_success") is False
    assert "real_robot: true" not in text
    assert "sim2real: true" not in text


@pytest.mark.parametrize("path", SOLUTION_JSON_TEMPLATES, ids=lambda p: p.name)
def test_solution_json_templates_are_parseable_and_non_claiming(path: Path) -> None:
    payload = json.loads(_read(path))
    assert payload["template_version"] == 1
    assert payload.get("claims_task_success") is False
    assert payload.get("claims_sim2real") is False


@pytest.mark.parametrize("path", RESEARCH_ASSISTANT_DOCS, ids=lambda p: p.name)
def test_research_assistant_docs_exist_and_are_substantive(path: Path) -> None:
    assert path.is_file(), f"missing RA deliverable: {path}"
    text = _read(path)
    assert len(text) > 1800
    assert "task success" in text.lower() or "任务成功" in text


def test_research_identity_is_frozen_and_non_claiming() -> None:
    identity = yaml.safe_load(_read(RESEARCH_IDENTITY))
    assert identity["identity_version"] == "ra_evaluation_study_v1"
    assert identity["evaluation"]["gate_sha256"] == (
        "37325a1fee3cce2e14361071d39f2a0a5b767044e25472114fcb8684c495d46f"
    )
    shift = identity["planned_analysis"]["closed_loop_shift_quantification"]
    assert shift["status"] == "completed_diagnostic"
    assert shift["report"] == "evidence/closed_loop_shift_v1/report.json"
    assert shift["conditioning"] == "normalized_progress_proxy_phase_unavailable"
    assert shift["h2_assessment"] == "directional_support_not_causal_proof"
    assert shift["gate_eligible"] is False
    assert all(value is False for value in identity["claims"].values())


def test_badcase_summary_is_layered_and_stays_hypothesis_scoped() -> None:
    text = _read(BADCASE)
    for layer in ("Data", "Interface", "Behavior", "Task", "System"):
        assert layer in text
    # Covariate shift must remain a leading hypothesis, never a proven sole root cause.
    assert "尚未被完全证明" in text or "不是被完整实验证明的唯一根因" in text
    assert "唯一根因已证明" not in text


def test_roadmap_registers_p1_p2_without_executing() -> None:
    text = _read(ROADMAP)
    for marker in ("P0", "P1", "P2"):
        assert marker in text
    assert re.search(r"P1\s*/\s*P2\s*\**\s*只登记", text.replace("**", "")) or "只登记，不执行" in text
    assert "人工批准" in text
    # Weekend eval matrix: clean full-episode stays; perturbation is anchored, not H=5/H=10.
    assert "P1-0A" in text and "阶段锚点" in text
    assert "H=5" in text and "禁止" in text


def test_openloop_perturbation_design_preserves_canonical_and_forbids_horizon() -> None:
    assert PERTURBATION_DESIGN.is_file()
    text = _read(PERTURBATION_DESIGN)
    for marker in (
        "canonical_first_action",
        "stride=1",
        "queued_diagnostic",
        "6",
        "240",
        "21",
        "210",
        "H=5",
        "H=10",
        "禁止",
        "gate_eligible=false",
    ):
        assert marker in text, f"perturbation design missing: {marker}"
    assert "只评 1 步" in text or "H=1" in text
    assert "所有帧" in text or "全帧" in text
    # Must not authorize shrinking clean canonical to 5/10 steps.
    assert "禁止" in text and ("只跑 5" in text or "5/10 步" in text)


def test_resume_description_has_three_variants_and_talk_tracks() -> None:
    text = _read(RESUME)
    for marker in ("系统验证", "具身数据评测", "仿真评测", "30 秒", "2 分钟", "失败归因"):
        assert marker in text, f"resume_description missing: {marker}"
    # Positioning: test/verification engineer, not algorithm tuning.
    assert "具身策略数据治理与分层验证" in text
    assert "不是算法调参" in text


@pytest.mark.parametrize(
    "path", (PORTFOLIO_MASTER, FINAL_SUMMARY, BADCASE, RESUME, V3_PORTFOLIO, UNIFIED_DOC), ids=lambda p: p.name
)
def test_portfolio_docs_carry_honest_boundaries(path: Path) -> None:
    text = _read(path)
    honest = (
        "Not task success",
        "not_task_success",
        "claims_task_success=false",
        "claims_task_success` 恒为 false",
    )
    denial = re.search(r"不是[^\n]{0,12}(任务成功|Sim2Real)", text)
    assert denial or any(marker in text for marker in honest), (
        f"{path.name} lacks an honest-boundary marker"
    )


@pytest.mark.parametrize("path", CURRENT_STATE_DOCS, ids=lambda p: p.name)
def test_no_stale_current_state_claims(path: Path) -> None:
    text = _read(path)
    forbidden = (
        "尚未 LoRA",
        "未完成 LoRA",
        "S4 未运行",
        "尚未运行 Isaac",
        "ran_isaac=false",
        "ran_isaac = false",
    )
    for phrase in forbidden:
        assert phrase not in text, f"{path.name} still contains stale claim: {phrase}"


def test_open_loop_pass_numbers_match_frozen_report() -> None:
    report = json.loads(_read(OPEN_LOOP_REPORT))
    assert report["gate_decision"] == "pass"
    assert report["stride"] == 1
    assert report["sampling_contract"]["inference_mode"] == "canonical_first_action"
    assert report["sampling_contract"]["canonical_pass_requires_full_episode"] is True
    assert report["sampling_contract"]["executes_action_chunk_queue"] is False
    assert report["claims_task_success"] is False
    assert report["prospective_evaluation"]["train_overlap"] == []
    assert report["prospective_evaluation"]["threshold_design_overlap"] == []

    metrics = report["lora"]["metrics"]
    ee = metrics["ee_position_rmse_m"]
    grip_ba = metrics["gripper_balanced_accuracy"]
    text = _read(FINAL_SUMMARY)
    assert f"{ee:.4f}" in text, f"FINAL summary must quote EE RMSE {ee:.4f}"
    assert f"{grip_ba:.4f}" in text, f"FINAL summary must quote grip BA {grip_ba:.4f}"
    assert report["eval_gate_sha256"] in text


def test_s4_authoritative_gate_numbers_match_docs() -> None:
    gate = json.loads(_read(S4_AUTHORITATIVE))
    assert gate["ran_isaac"] is True
    assert gate["gate_pass"] is False
    assert gate["claims_task_success"] is False
    assert gate["claims_sim2real"] is False
    assert gate["policy_interface_pass"] == 5
    assert (gate["reach"], gate["grasp"], gate["lift"]) == (1, 0, 0)

    for path in (FINAL_SUMMARY, V3_PORTFOLIO, CANONICAL_FACTS, UNIFIED_DOC):
        text = _read(path)
        assert S4_AUTHORITATIVE.parent.name in text, (
            f"{path.name} must reference the authoritative relight S4 run"
        )


def test_superseded_dark_scene_s4_is_labelled_not_deleted() -> None:
    assert S4_SUPERSEDED.exists(), "historical dark-scene S4 evidence must be preserved"
    superseded = json.loads(_read(S4_SUPERSEDED))
    assert (superseded["reach"], superseded["grasp"], superseded["lift"]) == (3, 1, 0)
    for path in (FINAL_SUMMARY, V3_PORTFOLIO, CANONICAL_FACTS, EVIDENCE_INDEX):
        text = _read(path)
        assert S4_SUPERSEDED.parent.name in text, f"{path.name} must still cite the historical run"
        window_ok = any(
            marker in text for marker in ("Superseded", "superseded", "Historical", "历史")
        )
        assert window_ok, f"{path.name} must label the dark-scene run as Superseded/historical"


def test_queued_diagnostic_never_claims_canonical_pass() -> None:
    cfg = yaml.safe_load(_read(RECOVERY_DECISIONS))
    contract = cfg["local_inference_contract"]
    assert contract["queued_diagnostic_gate_eligible"] is False
    assert contract["canonical_mode"] == "canonical_first_action"
    assert contract["diagnostic_mode"] == "queued_diagnostic"
    text = _read(FINAL_SUMMARY)
    assert "queued_diagnostic" in text
    assert "canonical Gate Pass 资格" in text or "永不具备 canonical Gate Pass" in text


def test_recovery_decisions_bounded_s4_record_is_consistent() -> None:
    cfg = yaml.safe_load(_read(RECOVERY_DECISIONS))
    assert cfg["ran_isaac"] is True
    record = cfg["bounded_s4_executed"]
    assert S4_AUTHORITATIVE.parent.name in record["authoritative_run"]
    assert record["gate_pass"] is False
    assert record["claims_task_success"] is False
    assert record["claims_sim2real"] is False


def test_gate_s3_ready_doc_is_marked_historical() -> None:
    head = _read(S3_READY)[:1500]
    assert "HISTORICAL" in head or "Historical" in head
    assert "SUPERSEDED" in head or "Superseded" in head
    assert "Recovery v3" in head


def test_figure_script_defaults_to_authoritative_evidence() -> None:
    text = _read(FIGURE_SCRIPT)
    assert S4_AUTHORITATIVE.parent.name in text
    assert "smolvla_v3_eval_framework_relight_20260725" in text
    # Subgoal counts must be derived from the gate JSON, never hardcoded in captions.
    assert "reach 3/5 · grasp 1/5" not in text


@pytest.mark.parametrize(
    "path",
    (
        PORTFOLIO_MASTER,
        FINAL_SUMMARY,
        BADCASE,
        ROADMAP,
        RESUME,
        V3_PORTFOLIO,
        UNIFIED_DOC,
        EVIDENCE_INDEX,
        V3_SOP,
        TRACKS_NAV,
        TECHNICAL_INTERVIEW_TRACK,
        SOLUTION_ARCHITECT_TRACK,
        RESEARCH_ASSISTANT_TRACK,
        RA_STRENGTHENING_SPEC,
        SOLUTION_ARCHITECT_STRENGTHENING_SPEC,
        *SOLUTION_TRACK_DOCS,
        *RESEARCH_ASSISTANT_DOCS,
    ),
    ids=lambda p: p.name,
)
def test_relative_markdown_links_resolve(path: Path) -> None:
    missing = []
    for target in MD_LINK.findall(_read(path)):
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            missing.append(target)
    assert not missing, f"{path.name} has broken relative links: {missing}"
