from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


SCHEMA_DIR = Path("evaluation/schemas")
EXAMPLE_DIR = Path("evaluation/examples")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validator(name: str) -> Draft202012Validator:
    schema = load_json(SCHEMA_DIR / name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.mark.parametrize(
    "schema_name",
    [
        "vla_panda_active_channel_spec.schema.json",
        "vla_execution_adapter_contract.schema.json",
    ],
)
def test_v05_schemas_are_valid(schema_name: str) -> None:
    validator(schema_name)


def test_active_channel_fixture_is_scheme_b_and_unverified() -> None:
    payload = load_json(EXAMPLE_DIR / "vla_panda_active_channel_spec_fixture.json")
    validator("vla_panda_active_channel_spec.schema.json").validate(payload)
    assert payload["policy_action_semantics"] == "absolute_eef_gripper_v0"
    assert payload["quaternion_order"] == "xyzw"
    assert payload["mask_padding"] is True
    assert payload["normalization"]["ignore_padding_dims"] is True
    assert payload["claims_official_layout_verified"] is False
    assert payload["channels"]["arm_joints"]["active_width"] == 7
    assert payload["channels"]["ee_pose"]["active_width"] == 7
    # Padding width must cover unused half of dual-arm slots.
    assert (
        payload["channels"]["arm_joints"]["canonical_width"]
        - payload["channels"]["arm_joints"]["active_width"]
        == 7
    )


def test_active_channel_fixture_rejects_claiming_official_layout() -> None:
    payload = load_json(EXAMPLE_DIR / "vla_panda_active_channel_spec_fixture.json")
    payload["claims_official_layout_verified"] = True
    with pytest.raises(ValidationError):
        validator("vla_panda_active_channel_spec.schema.json").validate(payload)


def test_execution_adapter_fixture_forbids_task_success_and_is_plan_only() -> None:
    payload = load_json(EXAMPLE_DIR / "vla_execution_adapter_contract_fixture.json")
    validator("vla_execution_adapter_contract.schema.json").validate(payload)
    assert payload["claims_task_success"] is False
    assert payload["implementation_status"] == "documented_plan_only"
    assert "vla_raw_output != ee_delta_gripper" in payload["forbidden_equivalences"]
    assert "selected_active_channels != reversible_map_to_delta" in payload[
        "forbidden_equivalences"
    ]


def test_execution_adapter_rejects_task_success_true() -> None:
    payload = load_json(EXAMPLE_DIR / "vla_execution_adapter_contract_fixture.json")
    payload["claims_task_success"] = True
    with pytest.raises(ValidationError):
        validator("vla_execution_adapter_contract.schema.json").validate(payload)


def test_v05_doc_exists_and_rejects_simple_delta_mapping_language() -> None:
    doc = Path("docs/VLA_GATE_V05_PANDA_ACTION_CONTRACT.md").read_text(encoding="utf-8")
    assert "Canonical channel selection" in doc
    assert "Policy action semantics" in doc
    assert "Execution adapter conversion" in doc
    assert "可逆" in doc
    assert "方案 B" in doc
    assert "不得**把 delta 当作 LingBot EE pose 同义词" in doc
    assert "不是** LingBot 默认语义" in doc
