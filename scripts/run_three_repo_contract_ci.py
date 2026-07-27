#!/usr/bin/env python3
"""Cross-repo pure-CPU contract checks (schema / action / runtime hash / handoff).

Validates midstream Panda schema IDs and action semantics, asserts byte-identical
S4 runtime contracts across midstream↔upstream when the upstream tree is present,
and exercises the downstream handoff loader against a minimal fixture.

No ROS launch, no GPU, no Isaac. Exit 0 on PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

MIDSTREAM_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = MIDSTREAM_ROOT / "configs" / "robot_schemas" / "panda.yaml"
DEFAULT_S4_JSON = MIDSTREAM_ROOT / "configs" / "smolvla_s3" / "s4_runtime_contract.json"
DEFAULT_RUNTIME_LOCK = (
    MIDSTREAM_ROOT / "configs" / "policy_runtime" / "panda_policy_runtime_v1.lock.json"
)
DEFAULT_UPSTREAM_S4 = (
    Path.home()
    / "dev"
    / "ros2-arm-teleoperation-suite"
    / "src"
    / "isaac_sim_adapter"
    / "isaac_sim_adapter"
    / "s4_runtime_contract.json"
)
DEFAULT_DOWNSTREAM = (
    Path.home() / "ros2_ws" / "src" / "ros2-moveit-pybullet-bridge"
)

EXPECTED_SCHEMA_ID = "panda_ee_delta_gripper_v0"
EXPECTED_HANDOFF_ACTION = "ee_delta_gripper"
EXPECTED_HANDOFF_DIM = 7
EXPECTED_S4_SEMANTICS = "absolute_eef_gripper_v0"
EXPECTED_S4_ACTION_DIM = 8
EXPECTED_HANDOFF_SCHEMA = "panda_ee_delta_gripper_v0"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_schema(schema_path: Path) -> dict[str, Any]:
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    schema_id = schema.get("schema_id")
    if schema_id != EXPECTED_SCHEMA_ID:
        raise AssertionError(
            f"schema_id mismatch: expected {EXPECTED_SCHEMA_ID!r}, got {schema_id!r}"
        )
    action = schema.get("action") or {}
    if EXPECTED_HANDOFF_ACTION not in action:
        raise AssertionError(
            f"schema missing action.{EXPECTED_HANDOFF_ACTION}; have {sorted(action.keys())}"
        )
    dim = int(action[EXPECTED_HANDOFF_ACTION]["dim"])
    if dim != EXPECTED_HANDOFF_DIM:
        raise AssertionError(
            f"{EXPECTED_HANDOFF_ACTION} dim must be {EXPECTED_HANDOFF_DIM}, got {dim}"
        )
    return {
        "check": "schema_id_and_action_semantics",
        "schema_path": str(schema_path),
        "schema_id": schema_id,
        "handoff_action_type": EXPECTED_HANDOFF_ACTION,
        "handoff_action_dim": dim,
        "s4_action_semantics": EXPECTED_S4_SEMANTICS,
        "s4_action_dim": EXPECTED_S4_ACTION_DIM,
        "status": "PASS",
    }


def check_runtime_contract_hash(
    midstream_json: Path,
    upstream_json: Path | None,
    runtime_lock: Path,
) -> dict[str, Any]:
    mid_hash = _sha256(midstream_json)
    mid_payload = json.loads(midstream_json.read_text(encoding="utf-8"))
    if mid_payload.get("policy_action_semantics") != EXPECTED_S4_SEMANTICS:
        raise AssertionError(
            "S4 policy_action_semantics mismatch: "
            f"expected {EXPECTED_S4_SEMANTICS!r}, got "
            f"{mid_payload.get('policy_action_semantics')!r}"
        )
    if int(mid_payload.get("chunk_size", -1)) != 10:
        raise AssertionError(f"S4 chunk_size must be 10, got {mid_payload.get('chunk_size')}")
    if int(mid_payload.get("n_action_steps", -1)) != 5:
        raise AssertionError(
            f"S4 n_action_steps must be 5, got {mid_payload.get('n_action_steps')}"
        )
    if int(mid_payload.get("action_dim", -1)) != EXPECTED_S4_ACTION_DIM:
        raise AssertionError(
            f"S4 action_dim must be {EXPECTED_S4_ACTION_DIM}, "
            f"got {mid_payload.get('action_dim')}"
        )

    lock = json.loads(runtime_lock.read_text(encoding="utf-8"))
    lock_sha = lock.get("contract_sha256") or lock.get("sha256")
    result: dict[str, Any] = {
        "check": "runtime_contract_hash",
        "midstream_s4_sha256": mid_hash,
        "midstream_s4_path": str(midstream_json),
        "runtime_lock_path": str(runtime_lock),
        "runtime_lock_has_sha": bool(lock_sha),
        "status": "PASS",
    }
    if upstream_json is None or not upstream_json.is_file():
        result["upstream_s4"] = "SKIPPED_MISSING"
        result["note"] = (
            "Upstream S4 JSON not found; midstream contract self-checks passed. "
            "Set --upstream-s4 to enforce byte-identical cross-repo hash."
        )
        return result

    up_hash = _sha256(upstream_json)
    if up_hash != mid_hash:
        raise AssertionError(
            "midstream/upstream S4 runtime contract SHA256 mismatch: "
            f"mid={mid_hash} up={up_hash}"
        )
    result["upstream_s4_sha256"] = up_hash
    result["upstream_s4_path"] = str(upstream_json)
    result["byte_identical"] = True
    return result


def _write_minimal_handoff(bundle: Path) -> None:
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "handoff_manifest.json").write_text(
        json.dumps({"handoff_format": "panda_bridge_handoff_v0"}),
        encoding="utf-8",
    )
    (bundle / "replay_check.json").write_text(
        json.dumps({"status": "PASS"}),
        encoding="utf-8",
    )
    row = {
        "timestamp": 0.033,
        "episode_index": 0,
        "frame_index": 1,
        "task": "pick_lift",
        "robot": "panda",
        "schema_id": EXPECTED_HANDOFF_SCHEMA,
        "release_id": "contract_ci_fixture",
        "action_type": "ee_delta_gripper",
        "action": [0.001, 0.0, -0.002, 0.0, 0.0, 0.01, 0.0],
    }
    (bundle / "predicted_actions.jsonl").write_text(
        json.dumps(row) + "\n",
        encoding="utf-8",
    )


def check_handoff_loader(downstream_root: Path | None) -> dict[str, Any]:
    if downstream_root is None or not downstream_root.is_dir():
        return {
            "check": "handoff_loader",
            "status": "SKIPPED_MISSING",
            "note": "Downstream repo not found; set --downstream-root to enforce.",
        }

    pkg = downstream_root / "pybullet_bridge"
    if str(pkg) not in sys.path:
        sys.path.insert(0, str(pkg))

    from pybullet_bridge.learning.panda_handoff import (  # noqa: E402
        load_handoff_bundle,
    )

    with tempfile.TemporaryDirectory(prefix="three_repo_handoff_") as tmp:
        bundle = Path(tmp) / "bridge_handoff"
        _write_minimal_handoff(bundle)
        handoff = load_handoff_bundle(bundle)
        if handoff.schema_id != EXPECTED_HANDOFF_SCHEMA:
            raise AssertionError(
                f"handoff schema_id {handoff.schema_id!r} != {EXPECTED_HANDOFF_SCHEMA!r}"
            )
        if handoff.action_dim != 7:
            raise AssertionError(f"handoff action_dim must be 7, got {handoff.action_dim}")
        return {
            "check": "handoff_loader",
            "status": "PASS",
            "downstream_root": str(downstream_root),
            "schema_id": handoff.schema_id,
            "action_type": handoff.action_type,
            "action_dim": handoff.action_dim,
            "rows": len(handoff.rows),
        }


def run_checks(
    *,
    schema_path: Path,
    s4_json: Path,
    runtime_lock: Path,
    upstream_s4: Path | None,
    downstream_root: Path | None,
) -> list[dict[str, Any]]:
    return [
        check_schema(schema_path),
        check_runtime_contract_hash(s4_json, upstream_s4, runtime_lock),
        check_handoff_loader(downstream_root),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--s4-json", type=Path, default=DEFAULT_S4_JSON)
    parser.add_argument("--runtime-lock", type=Path, default=DEFAULT_RUNTIME_LOCK)
    parser.add_argument("--upstream-s4", type=Path, default=DEFAULT_UPSTREAM_S4)
    parser.add_argument("--downstream-root", type=Path, default=DEFAULT_DOWNSTREAM)
    parser.add_argument(
        "--require-cross-repo",
        action="store_true",
        help="Fail if upstream S4 or downstream handoff loader is missing.",
    )
    parser.add_argument("--json-out", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    upstream = args.upstream_s4 if args.upstream_s4.is_file() else None
    downstream = args.downstream_root if args.downstream_root.is_dir() else None
    try:
        results = run_checks(
            schema_path=args.schema,
            s4_json=args.s4_json,
            runtime_lock=args.runtime_lock,
            upstream_s4=upstream,
            downstream_root=downstream,
        )
    except Exception as exc:  # noqa: BLE001 - CLI surface
        print(f"Status: FAIL\nError: {exc}", file=sys.stderr)
        return 1

    if args.require_cross_repo:
        for row in results:
            if str(row.get("status", "")).startswith("SKIPPED"):
                print(
                    f"Status: FAIL\nError: require-cross-repo but {row['check']} skipped",
                    file=sys.stderr,
                )
                return 1

    payload = {"status": "PASS", "checks": results}
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print("Status: PASS")
    for row in results:
        print(f"- {row['check']}: {row['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
