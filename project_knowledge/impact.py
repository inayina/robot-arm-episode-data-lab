"""Read-only Git change impact analysis."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .core import DEFAULT_REGISTRY, classify_path, load_registry, resolve_repositories


COMPONENT_GUIDANCE: dict[str, dict[str, list[str]]] = {
    "data_schema": {
        "tests": ["tests/test_panda_schema.py", "tests/test_panda_dataset_inspection.py"],
        "docs": ["docs/DATA_FLOW.md", "docs/INTER_REPO_CONTRACTS.md", "docs/portfolio/THREE_REPO_CANONICAL_FACTS.md"],
        "risks": ["Schema/action dimension compatibility may change across all three repositories."],
    },
    "dataset_adapter": {
        "tests": ["tests/test_upstream_m6_adapter.py", "tests/test_panda_dataset_inspection.py"],
        "docs": ["docs/DATA_FLOW.md", "docs/INTER_REPO_CONTRACTS.md"],
        "risks": ["Gate ownership or action semantics may drift from the upstream contract."],
    },
    "training": {
        "tests": ["tests/test_train_mlp_policy.py", "tests/test_train_act_smoke.py", "tests/test_evaluate_policy.py"],
        "docs": ["docs/TRAINING_METHODS.md", "docs/TRAINING_PIPELINE.md", "docs/portfolio/THREE_REPO_CANONICAL_FACTS.md"],
        "risks": ["Offline metrics or model status claims may become stale."],
    },
    "handoff": {
        "tests": [
            "tests/test_prepare_bridge_handoff.py",
            "ros2-moveit-pybullet-bridge:pybullet_bridge/test/test_panda_handoff.py",
            "ros2-moveit-pybullet-bridge:pybullet_bridge/test/test_jsonl_action_replay_policy.py",
        ],
        "docs": ["docs/INTER_REPO_CONTRACTS.md", "docs/CLOSED_LOOP_RUNBOOK.md", "docs/portfolio/THREE_REPO_CANONICAL_FACTS.md"],
        "risks": ["Handoff manifest, action type, dimensions, finite checks, or downstream compatibility may change."],
    },
    "downstream_replay": {
        "tests": [
            "ros2-moveit-pybullet-bridge:pybullet_bridge/test/test_panda_handoff.py",
            "ros2-moveit-pybullet-bridge:pybullet_bridge/test/test_panda_action_adapter.py",
            "ros2-moveit-pybullet-bridge:pybullet_bridge/test/test_policy_runner_node.py",
        ],
        "docs": ["docs/CLOSED_LOOP_RUNBOOK.md", "docs/portfolio/THREE_REPO_CANONICAL_FACTS.md"],
        "risks": ["Replay compatibility and benchmark comparability require revalidation."],
    },
    "risk_monitoring": {
        "tests": [
            "ros2-moveit-pybullet-bridge:dist_monitor/test/test_metrics_core.py",
            "ros2-moveit-pybullet-bridge:risk_engine/test/test_aggregator.py",
        ],
        "docs": [
            "ros2-moveit-pybullet-bridge:docs/FMEA.md",
            "ros2-moveit-pybullet-bridge:docs/SAFETY_ACCEPTANCE_PLAN.md",
            "docs/portfolio/THREE_REPO_CANONICAL_FACTS.md",
        ],
        "risks": ["Fault thresholds, Hold/E-stop behavior, or canonical risk claims may change."],
    },
    "canonical_evidence": {
        "tests": ["tests/test_project_knowledge.py", "tests/test_rag_assistant.py"],
        "docs": ["README.md", "docs/README.md", "docs/portfolio/THREE_REPO_CANONICAL_FACTS.md", "docs/portfolio/CANONICAL_EXPERIMENT.md"],
        "risks": ["A verified headline, run ID, or evidence dependency may be stale or conflicting."],
    },
}


def changed_paths(repository_root: Path, base: str, head: str) -> tuple[str, str, list[dict[str, str]]]:
    base_hash = subprocess.run(
        ["git", "-C", str(repository_root), "rev-parse", base],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    head_hash = subprocess.run(
        ["git", "-C", str(repository_root), "rev-parse", head],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    output = subprocess.run(
        ["git", "-C", str(repository_root), "diff", "--name-status", "--find-renames", base_hash, head_hash, "--"],
        check=True, capture_output=True, text=True,
    ).stdout
    changes: list[dict[str, str]] = []
    for line in output.splitlines():
        fields = line.split("\t")
        if not fields:
            continue
        status = fields[0]
        if status.startswith("R") and len(fields) >= 3:
            changes.append({"status": status, "old_path": fields[1], "path": fields[2]})
        elif len(fields) >= 2:
            changes.append({"status": status, "path": fields[1]})
    return base_hash, head_hash, changes


def _fallback_components(path: str) -> set[str]:
    mappings = [
        (("configs/robot_schemas/", "training/io/"), "data_schema"),
        (("training/adapters/", "adapt_upstream_panda_dataset.py"), "dataset_adapter"),
        (("training/policies/", "training/encoders/", "training/scripts/train_", "training/scripts/evaluate_", "training/scripts/replay_"), "training"),
        (("prepare_bridge_handoff.py", "handoff_manifest"), "handoff"),
        (("panda_handoff.py", "panda_action_adapter.py", "jsonl_action_replay_policy.py", "policy_runner.py", "benchmark_system.py"), "downstream_replay"),
        (("dist_monitor/", "risk_engine/", "sensor_fusion"), "risk_monitoring"),
        (("evidence/", "CANONICAL", "THREE_REPO_CANONICAL_FACTS", "README.md", "knowledge_registry"), "canonical_evidence"),
    ]
    return {component for patterns, component in mappings if any(pattern in path for pattern in patterns)}


def analyze_changed_paths(
    repository_name: str,
    changes: list[dict[str, str]],
    registry: dict[str, Any],
) -> dict[str, Any]:
    components: set[str] = set()
    changed = [item["path"] for item in changes]
    for path in changed:
        metadata = classify_path(registry, repository_name, path)
        if metadata:
            components.update(metadata.components)
        components.update(_fallback_components(path))
    components &= set(COMPONENT_GUIDANCE)
    tests = sorted({value for component in components for value in COMPONENT_GUIDANCE[component]["tests"]})
    docs = sorted({value for component in components for value in COMPONENT_GUIDANCE[component]["docs"]})
    risks = sorted({value for component in components for value in COMPONENT_GUIDANCE[component]["risks"]})

    # Exact depends_on reverse edges add documents that may now be stale.
    for item in registry.get("overrides", []):
        if item["repository"] != repository_name:
            continue
        if any(dependency in changed for dependency in item.get("depends_on", [])):
            docs.append(item["path"])
    docs = sorted(set(docs))
    canonical = sorted({doc for doc in docs if "CANONICAL" in doc or "README" in doc})
    if changes and not tests:
        risks.append("No mapped tests were found for the changed paths.")
    return {
        "changed_files": changes,
        "components": sorted(components),
        "related_tests": tests,
        "possibly_stale_docs": docs,
        "canonical_facts": canonical,
        "risks": sorted(set(risks)),
    }


def analyze_impact(
    *, registry_path: Path = DEFAULT_REGISTRY, repository_name: str = "robot-arm-episode-data-lab",
    base: str = "HEAD~1", head: str = "HEAD",
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    repositories, _ = resolve_repositories(registry)
    repository = next((item for item in repositories if item.name == repository_name), None)
    if repository is None:
        raise ValueError(f"repository is not configured or available: {repository_name}")
    base_hash, head_hash, changes = changed_paths(repository.root, base, head)
    result = analyze_changed_paths(repository_name, changes, registry)
    return {
        "schema_version": 1,
        "repository": repository_name,
        "base": base,
        "base_hash": base_hash,
        "head": head,
        "head_hash": head_hash,
        **result,
    }


def render_impact_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Project Knowledge Impact Analysis", "",
        f"Repository: `{report['repository']}`", f"Base: `{report['base_hash']}`",
        f"Head: `{report['head_hash']}`", "", "## Components", "",
    ]
    if report["components"]:
        lines.extend(f"- `{item}`" for item in report["components"])
    else:
        lines.append("- None")
    lines.extend(["", "## Related tests", ""])
    if report["related_tests"]:
        lines.extend(f"- `{item}`" for item in report["related_tests"])
    else:
        lines.append("- None")
    lines.extend(["", "## Possibly stale documentation", ""])
    if report["possibly_stale_docs"]:
        lines.extend(f"- `{item}`" for item in report["possibly_stale_docs"])
    else:
        lines.append("- None")
    lines.extend(["", "## Risks", ""])
    if report["risks"]:
        lines.extend(f"- {item}" for item in report["risks"])
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"
