"""Frozen policy metadata registry (identity cards only).

Does not load weights or mutate evidence/checkpoints.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REGISTRY_DIR = Path(__file__).resolve().parent.parent / "registry" / "policies"
INDEX_PATH = REGISTRY_DIR / "index.json"

REGISTERED_POLICY_IDS = (
    "scene_act_lerobot_e3_nominal",
    "isaac_scripted_oracle_v2b",
    "moveit_rule_baseline",
)


def registry_path(policy_id: str) -> Path:
    return REGISTRY_DIR / f"{policy_id}.json"


def list_registered_policy_ids() -> list[str]:
    return list(REGISTERED_POLICY_IDS)


def load_registry_index() -> dict[str, Any]:
    payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    if payload.get("artifact_type") != "policy_registry_index":
        raise ValueError("invalid policy registry index artifact_type")
    ids = [entry["registry_id"] for entry in payload["policies"]]
    if ids != list(REGISTERED_POLICY_IDS):
        raise ValueError(
            f"registry index ids {ids} != expected {list(REGISTERED_POLICY_IDS)}"
        )
    return payload


def load_policy_metadata(policy_id: str) -> dict[str, Any]:
    if policy_id not in REGISTERED_POLICY_IDS:
        raise KeyError(f"unregistered policy id: {policy_id}")
    path = registry_path(policy_id)
    if not path.is_file():
        raise FileNotFoundError(f"missing metadata file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("claims_task_success") is not False:
        raise ValueError(f"{policy_id}: claims_task_success must be false")
    if payload.get("action_schema_version") != "panda_ee_delta_gripper_v0":
        raise ValueError(f"{policy_id}: unexpected action_schema_version")
    return payload


def load_all_registered_metadata() -> dict[str, dict[str, Any]]:
    load_registry_index()
    return {policy_id: load_policy_metadata(policy_id) for policy_id in REGISTERED_POLICY_IDS}


def index_entry(policy_id: str) -> dict[str, Any]:
    index = load_registry_index()
    for entry in index["policies"]:
        if entry["registry_id"] == policy_id:
            return entry
    raise KeyError(policy_id)
