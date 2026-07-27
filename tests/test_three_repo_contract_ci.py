"""CPU-only tests for the three-repo contract CI entrypoint."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_three_repo_contract_ci import (
    check_handoff_loader,
    check_runtime_contract_hash,
    check_schema,
    run_checks,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "configs" / "robot_schemas" / "panda.yaml"
S4 = ROOT / "configs" / "smolvla_s3" / "s4_runtime_contract.json"
LOCK = ROOT / "configs" / "policy_runtime" / "panda_policy_runtime_v1.lock.json"
UPSTREAM_S4 = (
    Path.home()
    / "dev"
    / "ros2-arm-teleoperation-suite"
    / "src"
    / "isaac_sim_adapter"
    / "isaac_sim_adapter"
    / "s4_runtime_contract.json"
)
DOWNSTREAM = Path.home() / "ros2_ws" / "src" / "ros2-moveit-pybullet-bridge"


def test_schema_id_and_action_semantics() -> None:
    result = check_schema(SCHEMA)
    assert result["status"] == "PASS"
    assert result["schema_id"] == "panda_ee_delta_gripper_v0"
    assert result["handoff_action_dim"] == 7
    assert result["s4_action_semantics"] == "absolute_eef_gripper_v0"


def test_runtime_contract_self_hash() -> None:
    result = check_runtime_contract_hash(S4, None, LOCK)
    assert result["status"] == "PASS"
    assert len(result["midstream_s4_sha256"]) == 64


@pytest.mark.skipif(not UPSTREAM_S4.is_file(), reason="upstream tree not mounted")
def test_runtime_contract_byte_identical_with_upstream() -> None:
    result = check_runtime_contract_hash(S4, UPSTREAM_S4, LOCK)
    assert result["byte_identical"] is True


@pytest.mark.skipif(not DOWNSTREAM.is_dir(), reason="downstream tree not mounted")
def test_handoff_loader_accepts_fixture() -> None:
    result = check_handoff_loader(DOWNSTREAM)
    assert result["status"] == "PASS"
    assert result["action_dim"] == 7


def test_run_checks_midstream_only() -> None:
    results = run_checks(
        schema_path=SCHEMA,
        s4_json=S4,
        runtime_lock=LOCK,
        upstream_s4=None,
        downstream_root=None,
    )
    assert results[0]["status"] == "PASS"
    assert results[1]["status"] == "PASS"
    assert results[2]["status"] == "SKIPPED_MISSING"
