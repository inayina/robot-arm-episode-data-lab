from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path("training/scripts/validate_policy_visited_recovery_capture.py")
SPEC = importlib.util.spec_from_file_location("policy_visited_capture", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _manifest(root: Path, episode_meta: Path) -> Path:
    evidence = root / "evidence"
    evidence.mkdir(parents=True)
    manifest = root / "capture.json"
    _write_json(
        manifest,
        {
            "contract_version": "policy_visited_recovery_capture_v1",
            "simulation_backend": "mujoco",
            "claims_task_success": False,
            "expert_source": "human_teleop",
            "invariant": {
                "task": "pick up the red box and place it in the left bin",
                "cameras": ["scene", "wrist"],
                "state_contract": "observation.state[15]",
                "action_semantics": "ee_pose_gripper_cmd_v1",
                "grasp_assist_enabled": False,
                "object_pose_is_policy_input": False,
            },
            "policy_rollout": {
                "evidence_dir": "evidence",
                "failure_type": "NO_MEANINGFUL_APPROACH",
                "failure_onset_action_index": 0,
                "completed_actions": 100,
            },
            "episodes": [
                {
                    "episode_meta": str(episode_meta.relative_to(root)),
                    "phase_buckets": ["ALIGN", "DESCEND", "CLOSE", "LIFT"],
                }
            ],
        },
    )
    return manifest


def _episode(root: Path, *, command_missing: bool = False) -> Path:
    meta = root / "episodes" / "episode_000000" / "meta.json"
    _write_json(
        meta,
        {
            "success": True,
            "upstream_gate": "teleop",
            "visual_streams": ["scene", "wrist"],
            "capture_fps": 10.0,
            "action_semantics": "ee_pose_gripper_cmd_v1",
            "action_fill": "teleop_command",
            "command_missing": command_missing,
            "simulator_backend": "mujoco",
            "metadata": {
                "task_phase_source": "upstream_continuous_task_evaluator",
                "task_phase_semantics": "continuous_gt_achieved_subgoal_frontier",
                "task_phases": ["HOVER", "DESCEND", "CLOSE", "LIFT"],
            },
        },
    )
    return meta


def test_policy_visited_capture_accepts_real_teleop_dual_camera_lift(tmp_path: Path) -> None:
    meta = _episode(tmp_path)
    report = MODULE.validate_capture(_manifest(tmp_path, meta))
    assert report["passed"] is True
    assert report["next_gate"] == "release_not_authorized"
    assert report["claims_task_success"] is False
    assert report["phase_coverage_by_episode"] == {
        "ALIGN": 1, "CLOSE": 1, "DESCEND": 1, "LIFT": 1,
    }


def test_policy_visited_capture_rejects_hold_filled_actions(tmp_path: Path) -> None:
    meta = _episode(tmp_path, command_missing=True)
    report = MODULE.validate_capture(_manifest(tmp_path, meta))
    assert report["passed"] is False
    assert any("hold-filled" in error for error in report["errors"])
