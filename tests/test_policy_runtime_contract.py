"""M0 contract tests for the policy-runtime/HOC integration boundary.

These tests intentionally stay CPU-only.  M0 freezes data semantics and does not
authorize ROS runtime wiring, simulation, policy execution, or training.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "evaluation/schemas/policy_runtime_contract.schema.json"
DESCRIPTOR_PATH = ROOT / "evaluation/examples/policy_runtime_contract_fixture.json"
GRAPH_PATH = ROOT / "configs/policy_runtime/runtime_diagnostic_graph.yaml"
LOCK_PATH = ROOT / "configs/policy_runtime/panda_policy_runtime_v1.lock.json"
FIXTURE_PATHS = (
    DESCRIPTOR_PATH,
    ROOT / "evaluation/examples/policy_command_fixture.json",
    ROOT / "evaluation/examples/policy_execution_report_fixture.json",
    ROOT / "evaluation/examples/policy_runtime_health_fixture.json",
    ROOT / "evaluation/examples/task_evaluation_status_fixture.json",
    ROOT / "evaluation/examples/hoc_runtime_frame_fixture.json",
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    value = _json(SCHEMA_PATH)
    Draft202012Validator.check_schema(value)
    return value


@pytest.fixture(scope="module")
def validator(schema: dict[str, Any]) -> Draft202012Validator:
    return Draft202012Validator(schema)


def test_all_m0_artifacts_validate(validator: Draft202012Validator) -> None:
    for path in FIXTURE_PATHS:
        validator.validate(_json(path))
    validator.validate(_yaml(GRAPH_PATH))


def test_descriptor_enums_match_schema(schema: dict[str, Any]) -> None:
    descriptor = _json(DESCRIPTOR_PATH)
    assert descriptor["validity_states"] == schema["$defs"]["validity"]["enum"]
    assert descriptor["reason_codes"] == schema["$defs"]["reasonCode"]["enum"]
    assert descriptor["supported_action_schemas"] == schema["$defs"]["actionSchema"]["enum"]
    assert descriptor["hoc_frame_kinds"] == schema["$defs"]["hocRuntimeFrame"]["properties"]["frame_kind"]["enum"]


@pytest.mark.parametrize(
    ("action_schema", "action"),
    [
        ("panda_absolute_eef_gripper_v0", [0.0] * 8),
        ("panda_ee_delta_gripper_v0", [0.0] * 7),
    ],
)
def test_action_schema_dimensions_are_frozen(
    validator: Draft202012Validator,
    action_schema: str,
    action: list[float],
) -> None:
    command = _json(ROOT / "evaluation/examples/policy_command_fixture.json")
    command["action_schema_version"] = action_schema
    command["action"] = action
    validator.validate(command)

    command["action"] = action + [0.0]
    assert not validator.is_valid(command)


def test_unknown_action_schema_is_rejected(validator: Draft202012Validator) -> None:
    command = _json(ROOT / "evaluation/examples/policy_command_fixture.json")
    command["action_schema_version"] = "unversioned_action"
    assert not validator.is_valid(command)


def test_non_finite_values_are_rejected_by_m0_semantics() -> None:
    def assert_finite(value: Any, path: str = "$") -> None:
        if isinstance(value, float):
            assert math.isfinite(value), f"non-finite numeric value at {path}"
        elif isinstance(value, dict):
            for key, child in value.items():
                assert_finite(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                assert_finite(child, f"{path}[{index}]")

    for fixture_path in FIXTURE_PATHS:
        assert_finite(_json(fixture_path))
    with pytest.raises(AssertionError, match="non-finite"):
        assert_finite({"action": [0.0, math.nan]})


def test_m0_artifacts_cannot_claim_task_success(validator: Draft202012Validator) -> None:
    for path in FIXTURE_PATHS:
        artifact = _json(path)
        artifact["claims_task_success"] = True
        assert not validator.is_valid(artifact), path.name

    graph = _yaml(GRAPH_PATH)
    graph["claims_task_success"] = True
    assert not validator.is_valid(graph)


def test_hoc_frame_kind_must_match_payload(validator: Draft202012Validator) -> None:
    frame = _json(ROOT / "evaluation/examples/hoc_runtime_frame_fixture.json")
    frame["frame_kind"] = "policy_health"
    assert not validator.is_valid(frame)


def test_active_health_requires_loaded_policy(validator: Draft202012Validator) -> None:
    health = _json(ROOT / "evaluation/examples/policy_runtime_health_fixture.json")
    health["policy_loaded"] = False
    assert not validator.is_valid(health)


def test_task_pass_requires_complete_task_gt(validator: Draft202012Validator) -> None:
    task = _json(ROOT / "evaluation/examples/task_evaluation_status_fixture.json")
    task.update(
        task_status="PASS",
        phase="DONE",
        reason_code="task_pass",
        reach=True,
        grasp=True,
        lift=True,
        place=True,
    )
    validator.validate(task)
    for field in ("reach", "grasp", "lift", "place"):
        invalid = copy.deepcopy(task)
        invalid[field] = False
        assert not validator.is_valid(invalid), field


def test_lifecycle_and_qos_guards_are_frozen() -> None:
    descriptor = _json(DESCRIPTOR_PATH)
    lifecycle = descriptor["lifecycle"]
    assert lifecycle["initial_state"] == "UNCONFIGURED"
    assert lifecycle["command_enabled_state"] == "ACTIVE"
    transitions = {(item["name"], item["from"], item["to"]) for item in lifecycle["transitions"]}
    assert {
        ("configure", "UNCONFIGURED", "INACTIVE"),
        ("activate", "INACTIVE", "ACTIVE"),
        ("deactivate", "ACTIVE", "INACTIVE"),
        ("cleanup", "INACTIVE", "UNCONFIGURED"),
        ("error", "ANY_NON_FINALIZED", "ERROR_PROCESSING"),
        ("recover", "ERROR_PROCESSING", "UNCONFIGURED"),
        ("shutdown", "ANY_NON_FINALIZED", "FINALIZED"),
    } == transitions

    command_qos = descriptor["qos_profiles"]["policy_command"]
    assert command_qos["reliability"] == "reliable"
    assert command_qos["durability"] == "volatile"
    assert command_qos["history"] == "keep_last"
    assert command_qos["depth"] == 1
    assert command_qos["deadline_period_multiplier"] > 1.0
    assert command_qos["lifespan_lte_application_ttl"] is True
    latched_qos = descriptor["qos_profiles"]["latched_state"]
    assert latched_qos["durability"] == "transient_local"
    assert latched_qos["depth"] == 1


def _assert_acyclic(nodes: dict[str, dict[str, Any]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        assert node_id not in visiting, f"cycle detected at {node_id}"
        visiting.add(node_id)
        for child in nodes[node_id]["inputs"]:
            visit(child)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in nodes:
        visit(node_id)


def _evaluate_scenario(
    graph: dict[str, Any],
    scenario: dict[str, Any],
) -> tuple[str, str, dict[str, str]]:
    nodes = {node["id"]: node for node in graph["nodes"]}
    statuses = dict(scenario["input_status"])

    def status(node_id: str) -> str:
        if node_id in statuses:
            return statuses[node_id]
        node = nodes[node_id]
        child_statuses = [status(child) for child in node["inputs"]]
        if node["type"] == "and":
            value = "ERROR" if "ERROR" in child_statuses else "STALE" if "STALE" in child_statuses else "WARN" if "WARN" in child_statuses else "OK"
            statuses[node_id] = value
            return value
        raise AssertionError(f"status unavailable for {node_id}")

    for node in graph["nodes"]:
        if node["type"] == "and":
            status(node["id"])

    for rule in sorted(graph["decision_rules"], key=lambda item: item["priority"], reverse=True):
        if status(rule["when_node"]) == rule["when_status"]:
            return rule["decision"], rule["reason_code"], statuses
    raise AssertionError("no decision rule matched")


def test_diagnostic_graph_is_connected_acyclic_and_replayable() -> None:
    graph = _yaml(GRAPH_PATH)
    descriptor = _json(DESCRIPTOR_PATH)
    nodes = {node["id"]: node for node in graph["nodes"]}
    assert len(nodes) == len(graph["nodes"])
    assert graph["root_node"] in nodes
    for node in nodes.values():
        assert set(node["inputs"]) <= set(nodes)
    _assert_acyclic(nodes)

    priorities = [rule["priority"] for rule in graph["decision_rules"]]
    assert len(priorities) == len(set(priorities))
    assert {rule["reason_code"] for rule in graph["decision_rules"]} <= set(descriptor["reason_codes"])

    # Task ground truth is observational.  It must not be an ancestor of the
    # runtime safety decision and therefore cannot mask or create a risk event.
    reachable: set[str] = set()

    def collect(node_id: str) -> None:
        if node_id in reachable:
            return
        reachable.add(node_id)
        for child in nodes[node_id]["inputs"]:
            collect(child)

    collect(graph["root_node"])
    assert "task_gt_status" not in reachable
    assert graph["risk_may_override_task_gt"] is False

    for scenario in graph["fixture_scenarios"]:
        decision, reason, _statuses = _evaluate_scenario(graph, scenario)
        assert decision == scenario["expected_decision"], scenario["id"]
        assert reason == scenario["expected_reason_code"], scenario["id"]
        path = scenario["expected_cause_path"]
        assert path[0] == graph["root_node"]
        for parent, child in zip(path, path[1:]):
            assert child in nodes[parent]["inputs"], scenario["id"]

    all_valid = next(item for item in graph["fixture_scenarios"] if item["id"] == "all_valid_run")
    assert all_valid["input_status"]["task_gt_status"] == "ERROR"
    assert all_valid["expected_decision"] == "RUN"


def test_lock_covers_every_frozen_artifact() -> None:
    lock = _json(LOCK_PATH)
    expected_paths = {
        str(SCHEMA_PATH.relative_to(ROOT)),
        str(GRAPH_PATH.relative_to(ROOT)),
        *(str(path.relative_to(ROOT)) for path in FIXTURE_PATHS),
    }
    assert set(lock["artifact_sha256"]) == expected_paths
    for relative_path, expected_sha in lock["artifact_sha256"].items():
        assert _sha256(ROOT / relative_path) == expected_sha

    aggregate = "".join(
        f"{path}:{digest}\n" for path, digest in sorted(lock["artifact_sha256"].items())
    ).encode("utf-8")
    assert hashlib.sha256(aggregate).hexdigest() == lock["content_sha256"]
    assert lock["authorized_runtime_behavior_change"] is False
    assert lock["authorized_simulation"] is False
    assert lock["authorized_training"] is False
    assert lock["authorized_task_claim"] is False
