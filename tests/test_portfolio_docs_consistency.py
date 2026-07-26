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
BADCASE = PORTFOLIO / "BADCASE_ATTRIBUTION_SUMMARY.md"
ROADMAP = DOCS / "FUTURE_WORK_ROADMAP.md"
PERTURBATION_DESIGN = DOCS / "SMOLVLA_OPENLOOP_PERTURBATION_DESIGN.md"
RESUME = PORTFOLIO / "resume_description.md"
CANONICAL_FACTS = PORTFOLIO / "THREE_REPO_CANONICAL_FACTS.md"
EVIDENCE_INDEX = PORTFOLIO / "EVIDENCE_INDEX.md"
UNIFIED_DOC = PORTFOLIO / "UNIFIED_EVAL_REPORT.md"
V3_PORTFOLIO = PORTFOLIO / "SMOLVLA_RECOVERY_V3_PORTFOLIO.md"
V3_SOP = DOCS / "SMOLVLA_V3_EVAL_SOP.md"
S3_READY = DOCS / "SMOLVLA_GATE_S3_READY.md"
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

REQUIRED_DOCS = (FINAL_SUMMARY, BADCASE, ROADMAP, RESUME)

# Docs that describe the *current* project state; stale wording here misleads readers.
CURRENT_STATE_DOCS = (
    README,
    AGENTS,
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
    assert "面向机器人模仿学习与 VLA 策略的数据质量、动作契约" in text


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
    # Positioning: test/verification engineer, not VLA algorithm researcher.
    assert re.search(r"不是\**\s*VLA 算法研究员", text)


@pytest.mark.parametrize(
    "path", (FINAL_SUMMARY, BADCASE, RESUME, V3_PORTFOLIO, UNIFIED_DOC), ids=lambda p: p.name
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
    (FINAL_SUMMARY, BADCASE, ROADMAP, RESUME, V3_PORTFOLIO, UNIFIED_DOC, EVIDENCE_INDEX, V3_SOP),
    ids=lambda p: p.name,
)
def test_relative_markdown_links_resolve(path: Path) -> None:
    missing = []
    for target in MD_LINK.findall(_read(path)):
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            missing.append(target)
    assert not missing, f"{path.name} has broken relative links: {missing}"
