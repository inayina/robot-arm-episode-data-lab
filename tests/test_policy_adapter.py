from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from evaluation.policies import (
    ACTION_DIM,
    FixturePolicyAdapter,
    PolicyAdapterError,
    REGISTERED_POLICY_IDS,
    index_entry,
    list_registered_policy_ids,
    load_all_registered_metadata,
    load_policy_metadata,
    load_registry_index,
    validate_ee_delta_gripper,
)


SCHEMA_DIR = Path("evaluation/schemas")
REGISTRY_DIR = Path("evaluation/registry/policies")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validator(name: str) -> Draft202012Validator:
    schema = load_json(SCHEMA_DIR / name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_registry_index_and_metadata_validate() -> None:
    index = load_registry_index()
    validator("policy_registry_index.schema.json").validate(index)
    assert list_registered_policy_ids() == list(REGISTERED_POLICY_IDS)

    meta_validator = validator("policy_adapter_metadata.schema.json")
    for policy_id in REGISTERED_POLICY_IDS:
        meta = load_policy_metadata(policy_id)
        meta_validator.validate(meta)
        assert meta["claims_task_success"] is False
        assert meta["action_schema_version"] == "panda_ee_delta_gripper_v0"
        entry = index_entry(policy_id)
        assert entry["runtime_owner_repository"] == "ros2-arm-teleoperation-suite"
        assert Path(entry["metadata_path"]).is_file()


def test_act_oracle_moveit_registry_facts() -> None:
    act = load_policy_metadata("scene_act_lerobot_e3_nominal")
    assert act["checkpoint_hash"].startswith("948e2949")
    assert act["policy_name"] == "scene_act_lerobot"

    oracle = load_policy_metadata("isaac_scripted_oracle_v2b")
    assert oracle["checkpoint_hash"] == "oracle_scripted_v2b"
    assert oracle["policy_name"] == "isaac_scripted_oracle"

    moveit = load_policy_metadata("moveit_rule_baseline")
    assert moveit["checkpoint_hash"] == "not_applicable"
    assert index_entry("moveit_rule_baseline")["implementation_status"] == (
        "documented_plan_only"
    )


def test_load_all_registered_metadata_immutable_keys() -> None:
    all_meta = load_all_registered_metadata()
    assert set(all_meta) == set(REGISTERED_POLICY_IDS)
    # Registry files must stay under evaluation/registry (not evidence/).
    for path in REGISTRY_DIR.glob("*.json"):
        assert "evidence" not in path.parts


def test_fixture_adapter_round_trip_and_schema() -> None:
    identity = load_policy_metadata("scene_act_lerobot_e3_nominal")
    adapter = FixturePolicyAdapter(identity)
    adapter.load_policy(None)
    adapter.reset({"seed": 3000, "suite_id": "baseline", "instruction": "pick"})
    obs = adapter.build_observation({"state": [0.1] * 8})
    raw = adapter.predict_action(obs, instruction="pick up the red block")
    assert len(raw) == ACTION_DIM
    exported = adapter.export_action(adapter.validate_action(raw))
    assert exported[-1] == 1.0
    report = adapter.report_metadata()
    validator("policy_adapter_metadata.schema.json").validate(report)
    assert report["claims_task_success"] is False
    adapter.close()


def test_fixture_adapter_rejects_task_success_claim() -> None:
    identity = load_policy_metadata("isaac_scripted_oracle_v2b")
    identity = dict(identity)
    identity["claims_task_success"] = True
    with pytest.raises(PolicyAdapterError):
        FixturePolicyAdapter(identity)


def test_validate_ee_delta_gripper_rejects_bad_dim() -> None:
    with pytest.raises(PolicyAdapterError):
        validate_ee_delta_gripper([0.0] * 6)


def test_benchmark_spec_fixture_gates_ood() -> None:
    path = Path("evaluation/examples/benchmark_spec_baseline_id_ood_fixture.json")
    payload = load_json(path)
    validator("benchmark_spec.schema.json").validate(payload)
    assert payload["slices"]["baseline"]["enabled"] is True
    assert payload["slices"]["id"]["enabled"] is False
    assert payload["slices"]["ood_position"]["enabled"] is False
    assert payload["hard_gate"]["current_learned_policy_lift_verified"] is False
    assert payload["reporting"]["interface_pass_is_not_task_pass"] is True

    payload["slices"]["ood_position"]["enabled"] = True
    # Schema allows enabled=true; hard-gate semantics are enforced by tests/docs.
    validator("benchmark_spec.schema.json").validate(payload)
    # Restore semantic guard for the authoritative fixture file.
    restored = load_json(path)
    assert restored["slices"]["ood_position"]["enabled"] is False


def test_benchmark_spec_rejects_unknown_slice() -> None:
    path = Path("evaluation/examples/benchmark_spec_baseline_id_ood_fixture.json")
    payload = load_json(path)
    payload["slices"]["ood_appearance"] = payload["slices"]["ood_position"]
    with pytest.raises(ValidationError):
        validator("benchmark_spec.schema.json").validate(payload)


def test_three_repo_boundary_runtime_owners() -> None:
    index = load_registry_index()
    for entry in index["policies"]:
        assert entry["runtime_owner_repository"] != "robot-arm-episode-data-lab"
        assert "may_infer_physical_success" not in entry
