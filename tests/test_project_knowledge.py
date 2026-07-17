from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from project_knowledge import core
from project_knowledge.audit import _known_claim_conflicts, audit_project, render_audit_markdown
from project_knowledge.cli import main as cli_main
from project_knowledge.impact import analyze_changed_paths


ROOT = Path(__file__).resolve().parents[1]
QUERY_CASES = ROOT / "tests" / "fixtures" / "project_knowledge" / "query_cases.yaml"


@pytest.fixture(scope="session")
def registry():
    return core.load_registry()


@pytest.fixture(scope="session")
def catalog(registry):
    return core.build_catalog(registry)[0]


def metadata(kind: str, *, status: str = "current", modes=("fact",), priority: int = 50):
    return core.EvidenceMetadata(kind, status, tuple(modes), priority, last_verified="2026-07-14")


def entry(tmp_path: Path, relative: str, text: str, meta: core.EvidenceMetadata) -> core.CatalogEntry:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    repository = core.Repository("fixture", "midstream", tmp_path)
    return core.CatalogEntry(repository, path, relative, meta, True)


def write_registry(tmp_path: Path, rules: list[dict], overrides: list[dict] | None = None) -> Path:
    payload = {
        "schema_version": 1,
        "repositories": [{"name": "fixture", "role": "midstream", "path": str(tmp_path), "required": True}],
        "exclude_dirs": [".git"],
        "rules": rules,
        "overrides": overrides or [],
    }
    path = tmp_path / "knowledge_registry.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def rule(globs, kind, status, modes, priority, **extra):
    return {
        "repository": "fixture", "globs": globs, "kind": kind, "status": status,
        "enabled_modes": modes, "evidence_priority": priority,
        "authoritative_for": extra.get("authoritative_for", []),
        "component": extra.get("component", []), "tags": extra.get("tags", []),
        "last_verified": "2026-07-14",
    }


def test_registry_loads_three_real_repositories(registry):
    repositories, warnings = core.resolve_repositories(registry)
    assert not warnings
    assert {item.name for item in repositories} == {
        "ros2-arm-teleoperation-suite", "robot-arm-episode-data-lab", "ros2-moveit-pybullet-bridge"
    }


def test_registry_rejects_path_escape(tmp_path):
    path = write_registry(tmp_path, [rule(["README.md"], "current_doc", "current", ["fact"], 65)], [{
        "repository": "fixture", "path": "../escape.md", "kind": "current_doc", "status": "current",
        "enabled_modes": ["fact"], "evidence_priority": 65,
    }])
    with pytest.raises(ValueError, match="safe and relative"):
        core.load_registry(path)


def test_registry_rejects_unknown_metadata_field(tmp_path):
    bad_rule = rule(["README.md"], "current_doc", "current", ["fact"], 65)
    bad_rule["mystery"] = True
    path = write_registry(tmp_path, [bad_rule])
    with pytest.raises(ValueError, match="unknown registry metadata fields"):
        core.load_registry(path)


@pytest.mark.parametrize(("repository", "path"), [
    ("robot-arm-episode-data-lab", "tests/test_panda_schema.py"),
    ("ros2-arm-teleoperation-suite", "src/grasp_monitor/test/test_grasp_monitor_state_machine.py"),
    ("ros2-moveit-pybullet-bridge", "pybullet_bridge/test/test_panda_handoff.py"),
])
def test_real_test_layouts_are_classified_as_test(registry, repository, path):
    assert core.classify_path(registry, repository, path).kind == "test"


@pytest.mark.parametrize(("repository", "path"), [
    ("ros2-arm-teleoperation-suite", "bin/project-evidence"),
    ("robot-arm-episode-data-lab", "project_knowledge/cli.py"),
    ("ros2-moveit-pybullet-bridge", "bin/project-evidence"),
])
def test_three_repo_agent_entrypoints_are_classified_as_code(registry, repository, path):
    assert core.classify_path(registry, repository, path).kind == "code"


def test_fact_excludes_legacy_and_archive(tmp_path):
    entries = [
        entry(tmp_path, "src/current.py", "unique gate token", metadata("code", priority=90)),
        entry(tmp_path, "legacy/old.md", "unique gate token", metadata("legacy", status="legacy", modes=("legacy",), priority=30)),
        entry(tmp_path, "archive/old.md", "unique gate token", metadata("archive", status="archive", modes=(), priority=5)),
        entry(tmp_path, "reference/learn.md", "unique gate token", metadata("reference", modes=("learning",), priority=25)),
        entry(tmp_path, "conflict.md", "unique gate token", metadata("portfolio", status="needs_reconciliation", modes=("portfolio",), priority=20)),
    ]
    results = core.retrieve_evidence("unique gate token", entries, "fact", 10)
    assert {item.chunk.entry.metadata.kind for item in results} == {"code"}


def test_learning_allows_reference_with_label(tmp_path):
    entries = [entry(tmp_path, "reference/learn.md", "robot concept token",
                     metadata("reference", modes=("learning",), priority=25))]
    result = core.retrieve_evidence("robot concept token", entries, "learning", 5)[0].to_dict()
    assert result["kind"] == "reference"
    assert result["authoritative"] is False


def test_evidence_priority_ranks_test_above_document(tmp_path):
    entries = [
        entry(tmp_path, "tests/test_gate.py", "same evidence token", metadata("test", priority=100)),
        entry(tmp_path, "docs/gate.md", "same evidence token", metadata("current_doc", priority=65)),
    ]
    results = core.retrieve_evidence("same evidence token", entries, "fact", 2)
    assert results[0].chunk.entry.metadata.kind == "test"


def test_auto_routing_is_deterministic():
    assert core.route_mode("KUKA legacy 实现") == "legacy"
    assert core.route_mode("这个数字能否写入简历") == "portfolio"
    assert core.route_mode("handoff 报错怎么排查") == "debug"
    assert core.route_mode("如何运行闭环命令") == "runbook"
    assert core.route_mode("为什么需要数据契约") == "learning"
    assert core.route_mode("三仓职责") == "fact"


def test_act_query_cannot_claim_completed_canonical_training():
    result = core.query_project("ACT是否已经完成canonical训练？", mode="fact", no_llm=True)
    paths = {item.chunk.relative_path for item in result.evidence}
    assert {
        "training/scripts/train_act_lerobot.py",
        "training/scripts/train_act_smoke.py",
        "docs/portfolio/THREE_REPO_CANONICAL_FACTS.md",
    } <= paths
    assert result.claims[0]["status"] == "insufficient_verified_run"
    assert result.claims[0]["verified"] is False
    assert result.claims[0]["code_present"] is True
    assert all(item.chunk.entry.metadata.kind not in {"archive", "legacy", "reference", "portfolio"}
               for item in result.evidence)


def test_94399_cannot_be_verified_headline():
    result = core.query_project("94.399 ms能否作为已验证数字写入简历？", mode="portfolio", no_llm=True)
    paths = {item.chunk.relative_path for item in result.evidence}
    assert {
        "docs/portfolio/CANONICAL_EXPERIMENT.md",
        "docs/portfolio/THREE_REPO_CANONICAL_FACTS.md",
        "evidence/downstream/benchmark_summary.json",
    } <= paths
    assert result.claims[0]["status"] == "needs_reconciliation"
    assert result.claims[0]["verified_headline"] is False


def test_no_llm_json_contains_complete_evidence():
    result = core.query_project("三仓当前职责", mode="fact", no_llm=True)
    payload = result.to_dict()
    assert payload["coverage"]["complete"] is True
    assert payload["llm_summary"] is None
    assert payload["evidence"]
    for field in ("repository", "path", "line_start", "symbol", "kind", "status", "last_verified"):
        assert field in payload["evidence"][0]


def test_query_evidence_order_is_deterministic(catalog):
    first = core.retrieve_evidence("三仓当前职责", catalog, "fact", 8)
    second = core.retrieve_evidence("三仓当前职责", catalog, "fact", 8)
    assert [item.chunk.evidence_id() for item in first] == [item.chunk.evidence_id() for item in second]


def test_query_eval_cases():
    cases = yaml.safe_load(QUERY_CASES.read_text(encoding="utf-8"))
    for case in cases:
        result = core.query_project(case["query"], mode=case["mode"], top_k=8, no_llm=True)
        paths = {item.chunk.relative_path for item in result.evidence}
        kinds = {item.chunk.entry.metadata.kind for item in result.evidence}
        assert set(case.get("required_paths", [])) <= paths, case["id"]
        assert set(case.get("required_kinds", [])) <= kinds, case["id"]
        assert not (set(case.get("forbidden_kinds", [])) & kinds), case["id"]
        if case.get("claim_status"):
            assert result.claims and result.claims[0]["status"] == case["claim_status"]


def test_audit_detects_registry_and_markdown_problems(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "registered.md").write_text(
        "# First\n[missing](missing.md)\n![missing image](missing.png)\n"
        "[duplicate](same.md) [duplicate again](same.md)\n"
        "[absolute](file:///tmp/private.md)\n# Second\n```text\n```bash\n", encoding="utf-8"
    )
    (docs / "same.md").write_text("# Same\n", encoding="utf-8")
    (docs / "orphan.md").write_text("# Orphan\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "docs/registered.md", "docs/orphan.md", "docs/same.md"], check=True)
    registered_rule = rule(["docs/registered.md"], "current_doc", "current", ["fact"], 65)
    registered_rule.pop("last_verified")
    registry_path = write_registry(tmp_path, [registered_rule], [{
        "repository": "fixture", "path": "docs/missing_override.md", "kind": "current_doc",
        "status": "current", "enabled_modes": ["fact"], "evidence_priority": 65,
        "authoritative_for": [], "component": [], "tags": [], "last_verified": "2026-07-14",
    }])
    report = audit_project(registry_path)
    rules = {item["rule_id"] for item in report["findings"]}
    assert {"UNREGISTERED_MARKDOWN", "MISSING_REGISTERED_PATH", "BROKEN_LOCAL_LINK",
            "DOC_INDEX_ERROR", "DUPLICATE_H1", "MISSING_LAST_VERIFIED",
            "NONPORTABLE_LOCAL_LINK", "UNCLOSED_CODE_FENCE"} <= rules
    assert "# Project Evidence Audit" in render_audit_markdown(report)


def test_actual_audit_has_no_known_claim_conflict_after_reconciliation():
    report = audit_project()
    conflicts = [item for item in report["findings"] if item["rule_id"] == "KNOWN_CLAIM_CONFLICT"]
    assert not conflicts


def test_audit_detects_known_claim_conflict_fixture(tmp_path):
    canonical = tmp_path / "docs" / "portfolio" / "CANONICAL_EXPERIMENT.md"
    artifact = tmp_path / "evidence" / "downstream" / "benchmark_summary.json"
    canonical.parent.mkdir(parents=True)
    artifact.parent.mkdir(parents=True)
    canonical.write_text("# Canonical\nFault alarm: 94.399 ms\n", encoding="utf-8")
    artifact.write_text(json.dumps({"fault_injection": False, "health_alarm_latency_ms": None}), encoding="utf-8")
    findings = []
    repository = SimpleNamespace(name="robot-arm-episode-data-lab", root=tmp_path)
    _known_claim_conflicts({repository.name: repository}, findings)
    assert findings and findings[0].rule_id == "KNOWN_CLAIM_CONFLICT"


def test_audit_detects_hardware_pass_conflict_fixture(tmp_path):
    readiness = tmp_path / "docs" / "REAL_MACHINE_READINESS.md"
    status = tmp_path / "docs" / "CURRENT_STATUS.md"
    readiness.parent.mkdir(parents=True)
    readiness.write_text("# Readiness\n| Check | Status |\n|---|---|\n| Hardware | `Pass` |\n", encoding="utf-8")
    status.write_text("# Status\n## Partial Or Future Work\n- Real Panda hardware source.\n", encoding="utf-8")
    findings = []
    repository = SimpleNamespace(name="ros2-moveit-pybullet-bridge", root=tmp_path)
    _known_claim_conflicts({repository.name: repository}, findings)
    assert findings and "Hardware readiness row" in findings[0].message


def test_audit_cli_writes_json_and_markdown(tmp_path):
    json_out = tmp_path / "audit.json"
    markdown_out = tmp_path / "audit.md"
    assert cli_main(["audit", "--json-out", str(json_out), "--markdown-out", str(markdown_out), "--no-fail"]) == 0
    assert json.loads(json_out.read_text(encoding="utf-8"))["schema_version"] == 1
    assert markdown_out.read_text(encoding="utf-8").startswith("# Project Evidence Audit")


def test_handoff_impact_maps_tests_docs_and_risk(registry):
    report = analyze_changed_paths("robot-arm-episode-data-lab", [{
        "status": "M", "path": "training/scripts/prepare_bridge_handoff.py"
    }], registry)
    assert "handoff" in report["components"]
    assert "tests/test_prepare_bridge_handoff.py" in report["related_tests"]
    assert "ros2-moveit-pybullet-bridge:pybullet_bridge/test/test_panda_handoff.py" in report["related_tests"]
    assert "docs/INTER_REPO_CONTRACTS.md" in report["possibly_stale_docs"]
    assert report["risks"]


@pytest.mark.parametrize("component,path", [
    ("data_schema", "configs/robot_schemas/panda.yaml"),
    ("dataset_adapter", "training/adapters/upstream_m6.py"),
    ("training", "training/policies/mlp_policy.py"),
    ("handoff", "training/scripts/prepare_bridge_handoff.py"),
    ("downstream_replay", "pybullet_bridge/pybullet_bridge/learning/panda_handoff.py"),
    ("risk_monitoring", "risk_engine/risk_engine/aggregator.py"),
    ("canonical_evidence", "docs/portfolio/THREE_REPO_CANONICAL_FACTS.md"),
])
def test_all_required_impact_components_have_mapping(registry, component, path):
    repository = "ros2-moveit-pybullet-bridge" if component in {"downstream_replay", "risk_monitoring"} else "robot-arm-episode-data-lab"
    report = analyze_changed_paths(repository, [{"status": "M", "path": path}], registry)
    assert component in report["components"]
    assert report["related_tests"]
    assert report["possibly_stale_docs"]


def test_legacy_cli_and_shell_wrapper_subprocesses():
    env = {**os.environ, "OLLAMA_HOST": "http://127.0.0.1:9", "PYTHONDONTWRITEBYTECODE": "1"}
    script = subprocess.run(
        [sys.executable, "scripts/rag_assistant.py", "--query", "ACT是否已经完成canonical训练？", "--top-k", "3"],
        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )
    assert script.returncode == 0, script.stderr
    assert "证据类型:" in script.stdout
    assert "无法确认 canonical 完整训练产物" in script.stdout
    wrapper = subprocess.run(
        [str(ROOT / "bin" / "ask-project"), "三仓当前职责是什么？"],
        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )
    assert wrapper.returncode == 0, wrapper.stderr
    assert "检索证据" in wrapper.stdout
