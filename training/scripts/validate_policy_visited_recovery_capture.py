#!/usr/bin/env python3
"""Fail-closed acceptance for manually captured policy-visited recovery episodes.

This tool does not drive MuJoCo and does not create a training release.  It
connects an operator-authored handoff manifest to the immutable upstream
episode sidecars, rejecting a recovery sample unless its policy failure,
teleop takeover, dual-camera/action contract, and GT Lift evidence agree.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "policy_visited_recovery_capture_v1"
EXPECTED_TASK = "pick up the red box and place it in the left bin"
EXPECTED_CAMERAS = {"scene", "wrist"}
EXPECTED_PHASES = {"ALIGN", "DESCEND", "CLOSE", "LIFT"}
EXPECTED_FAILURES = {
    "NO_MEANINGFUL_APPROACH",
    "MISALIGNED",
    "NO_DESCENT",
    "NO_CLOSE",
    "CLOSE_NO_CONTACT",
    "GRASP_NO_LIFT",
}
EXPECTED_EXPERT_SOURCES = {
    "human_teleop",
    "scripted_oracle_privileged_gt",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _episode_meta(path: Path) -> tuple[Path, dict[str, Any]]:
    candidate = path / "meta.json" if path.is_dir() else path
    if not candidate.is_file():
        raise ValueError(f"episode meta.json missing: {candidate}")
    return candidate.resolve(), _load_json(candidate)


def _metadata(meta: dict[str, Any]) -> dict[str, Any]:
    value = meta.get("metadata", {})
    if not isinstance(value, dict):
        raise ValueError("episode metadata must be an object")
    return value


def _value(meta: dict[str, Any], metadata: dict[str, Any], key: str) -> Any:
    return meta.get(key, metadata.get(key))


def validate_capture(manifest_path: Path) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = _load_json(manifest_path)
    errors: list[str] = []
    warnings: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(
        manifest.get("contract_version") == CONTRACT_VERSION,
        f"contract_version must be {CONTRACT_VERSION}",
    )
    require(manifest.get("simulation_backend") == "mujoco", "simulation_backend must be mujoco")
    require(manifest.get("claims_task_success") is False, "capture manifest must not claim task success")
    require(
        manifest.get("expert_source") in EXPECTED_EXPERT_SOURCES,
        "expert_source must identify human_teleop or scripted_oracle_privileged_gt",
    )
    invariant = manifest.get("invariant")
    require(isinstance(invariant, dict), "invariant object missing")
    if not isinstance(invariant, dict):
        invariant = {}
    require(invariant.get("task") == EXPECTED_TASK, "task text differs from frozen policy task")
    require(set(invariant.get("cameras", [])) == EXPECTED_CAMERAS, "invariant cameras must be scene+wrist")
    require(invariant.get("state_contract") == "observation.state[15]", "state contract must be observation.state[15]")
    require(invariant.get("action_semantics") == "ee_pose_gripper_cmd_v1", "action semantics mismatch")
    require(invariant.get("grasp_assist_enabled") is False, "grasp_assist_enabled must be false")
    require(invariant.get("object_pose_is_policy_input") is False, "object_pose must not be a policy input")

    rollout = manifest.get("policy_rollout")
    require(isinstance(rollout, dict), "policy_rollout object missing")
    if not isinstance(rollout, dict):
        rollout = {}
    evidence_dir = rollout.get("evidence_dir")
    require(isinstance(evidence_dir, str) and bool(evidence_dir), "policy rollout evidence_dir missing")
    if isinstance(evidence_dir, str) and evidence_dir:
        evidence = (manifest_path.parent / evidence_dir).resolve()
        require(evidence.is_dir(), f"policy rollout evidence directory missing: {evidence}")
    failure = rollout.get("failure_type")
    require(failure in EXPECTED_FAILURES, f"unsupported failure_type: {failure!r}")
    onset = rollout.get("failure_onset_action_index")
    require(isinstance(onset, int) and onset >= 0, "failure_onset_action_index must be a non-negative integer")
    require(
        isinstance(rollout.get("completed_actions"), int) and rollout["completed_actions"] > 0,
        "policy rollout completed_actions must be positive",
    )

    episodes = manifest.get("episodes")
    require(isinstance(episodes, list) and episodes, "at least one recovery episode is required")
    accepted: list[dict[str, Any]] = []
    for index, item in enumerate(episodes if isinstance(episodes, list) else []):
        prefix = f"episodes[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        rel = item.get("episode_meta")
        if not isinstance(rel, str) or not rel:
            errors.append(f"{prefix}.episode_meta missing")
            continue
        try:
            path, meta = _episode_meta((manifest_path.parent / rel).resolve())
            md = _metadata(meta)
        except ValueError as exc:
            errors.append(f"{prefix}: {exc}")
            continue
        phases = md.get("task_phases")
        phase_buckets = item.get("phase_buckets")
        require(isinstance(phase_buckets, list) and phase_buckets, f"{prefix}.phase_buckets missing")
        if isinstance(phase_buckets, list):
            require(
                set(phase_buckets).issubset(EXPECTED_PHASES),
                f"{prefix}.phase_buckets contain unsupported phase",
            )
        require(meta.get("success") is True, f"{prefix} is not a committed successful episode")
        require(_value(meta, md, "command_missing") is False, f"{prefix} contains hold-filled action")
        require(
            _value(meta, md, "action_fill") == "teleop_command",
            f"{prefix} action_fill must be teleop_command",
        )
        require(_value(meta, md, "action_semantics") == "ee_pose_gripper_cmd_v1", f"{prefix} action semantics mismatch")
        require(set(_value(meta, md, "visual_streams") or []) == EXPECTED_CAMERAS, f"{prefix} requires scene+wrist")
        require(float(_value(meta, md, "capture_fps") or 0.0) == 10.0, f"{prefix} capture_fps must be 10")
        require(_value(meta, md, "simulator_backend") == "mujoco", f"{prefix} simulator backend must be mujoco")
        require(isinstance(phases, list) and "LIFT" in phases, f"{prefix} must contain upstream GT LIFT")
        require(
            md.get("task_phase_source") == "upstream_continuous_task_evaluator",
            f"{prefix} task phase source mismatch",
        )
        require(
            md.get("task_phase_semantics") == "continuous_gt_achieved_subgoal_frontier",
            f"{prefix} task phase semantics mismatch",
        )
        require(_value(meta, md, "upstream_gate") == "teleop", f"{prefix} upstream_gate must be teleop")
        accepted.append(
            {
                "episode_meta": str(path),
                "phase_buckets": phase_buckets,
                "recorded_task_phases": phases if isinstance(phases, list) else [],
            }
        )

    phase_coverage = {
        phase: sum(phase in (episode.get("phase_buckets") or []) for episode in accepted)
        for phase in sorted(EXPECTED_PHASES)
    }
    for phase, count in phase_coverage.items():
        if count == 0:
            warnings.append(f"no accepted recovery episode declared phase bucket {phase}")

    return {
        "contract_version": CONTRACT_VERSION,
        "capture_manifest": str(manifest_path),
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "accepted_episodes": accepted if not errors else [],
        "phase_coverage_by_episode": phase_coverage,
        "claims_task_success": False,
        "expert_source": manifest.get("expert_source"),
        "next_gate": "release_not_authorized" if not errors else "fix_capture_contract",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-manifest", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    args = parser.parse_args()
    report = validate_capture(args.capture_manifest)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "output_report": str(args.output_report)}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
