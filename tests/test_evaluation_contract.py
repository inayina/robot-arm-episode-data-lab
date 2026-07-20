from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


SCHEMA_DIR = Path("evaluation/schemas")
EXAMPLE_DIR = Path("evaluation/examples/nominal_contract_fixture")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def validator(name: str) -> Draft202012Validator:
    schema = load_json(SCHEMA_DIR / name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.mark.parametrize(
    "schema_name",
    [
        "run_manifest.schema.json",
        "episode_result.schema.json",
        "summary.schema.json",
    ],
)
def test_evaluation_schemas_are_valid_draft_2020_12(schema_name: str) -> None:
    validator(schema_name)


def test_nominal_contract_fixture_validates_and_has_fixed_seeds() -> None:
    run_manifest = load_json(EXAMPLE_DIR / "run_manifest.json")
    episode_rows = load_jsonl(EXAMPLE_DIR / "episode_results.jsonl")
    summary = load_json(EXAMPLE_DIR / "summary.json")
    suite = load_json(EXAMPLE_DIR / "nominal_suite.json")

    validator("run_manifest.schema.json").validate(run_manifest)
    episode_validator = validator("episode_result.schema.json")
    for row in episode_rows:
        episode_validator.validate(row)
    validator("summary.schema.json").validate(summary)

    expected_seeds = [101, 202, 303]
    assert suite["seeds"] == expected_seeds
    assert run_manifest["scenario"]["seeds"] == expected_seeds
    assert [row["identity"]["seed"] for row in episode_rows] == expected_seeds
    assert [row["seed"] for row in summary["seed_results"]] == expected_seeds
    assert summary["counts"] == {
        "planned": 3,
        "completed": 0,
        "aborted": 0,
        "infrastructure_failure": 0,
    }


def test_ownership_preserves_three_repo_boundary() -> None:
    manifest = load_json(EXAMPLE_DIR / "run_manifest.json")
    ownership = manifest["ownership"]

    assert ownership["runtime_ground_truth"] == {
        "repository": "ros2-arm-teleoperation-suite",
        "responsibility": (
            "Evaluate reach/grasp/lift/transport/place/release from runtime "
            "simulator ground truth and publish the authoritative physical outcome."
        ),
        "may_infer_physical_success": True,
    }
    assert ownership["offline_aggregation"]["repository"] == "robot-arm-episode-data-lab"
    assert ownership["offline_aggregation"]["may_infer_physical_success"] is False
    assert ownership["risk_review"]["repository"] == "ros2-moveit-pybullet-bridge"
    assert ownership["risk_review"]["may_infer_physical_success"] is False


def test_contract_fixture_cannot_claim_runtime_success() -> None:
    row = load_jsonl(EXAMPLE_DIR / "episode_results.jsonl")[0]
    row["outcome"]["success"] = True

    with pytest.raises(ValidationError):
        validator("episode_result.schema.json").validate(row)


def test_completed_episode_requires_runtime_ground_truth_and_evidence() -> None:
    row = load_jsonl(EXAMPLE_DIR / "episode_results.jsonl")[0]
    row["evidence_level"] = "runtime_observed"
    row["execution_status"] = "completed"

    with pytest.raises(ValidationError):
        validator("episode_result.schema.json").validate(row)


def test_completed_run_requires_resolved_provenance_and_thresholds() -> None:
    manifest = load_json(EXAMPLE_DIR / "run_manifest.json")
    manifest["evidence_level"] = "runtime_observed"
    manifest["execution_status"] = "completed"

    with pytest.raises(ValidationError):
        validator("run_manifest.schema.json").validate(manifest)


def test_contract_summary_cannot_claim_execution() -> None:
    summary = load_json(EXAMPLE_DIR / "summary.json")
    summary["counts"]["completed"] = 1
    summary["overall_success"].update(
        {"numerator": 1, "denominator": 1, "rate": 1.0}
    )

    with pytest.raises(ValidationError):
        validator("summary.schema.json").validate(summary)


def test_fail_safe_and_nfr_contracts_are_complete_without_fake_values() -> None:
    manifest = load_json(EXAMPLE_DIR / "run_manifest.json")
    fail_safe = {item["condition"]: item for item in manifest["fail_safe_contract"]}

    assert set(fail_safe) == {
        "stale_command",
        "stale_state",
        "dds_qos_mismatch",
        "reset_timeout",
        "policy_timeout",
    }
    assert fail_safe["dds_qos_mismatch"]["response"] == "fail_preflight"
    assert fail_safe["reset_timeout"]["response"] == "abort_and_clear_history"
    assert fail_safe["stale_command"]["response"] == "hold_then_abort"
    assert fail_safe["stale_state"]["response"] == "hold_then_abort"
    assert fail_safe["policy_timeout"]["response"] == "hold_then_abort"

    assert len(manifest["nfr_evidence_contract"]) >= 8
    assert all(item["evidence_path"] for item in manifest["nfr_evidence_contract"])

    rows = load_jsonl(EXAMPLE_DIR / "episode_results.jsonl")
    for row in rows:
        assert all(value is None for value in row["system_performance"].values())
        assert row["outcome"]["runtime_evaluated"] is False
        assert row["outcome"]["success"] is None


def test_aggregate_evaluation_summary_produces_valid_runtime_summary(tmp_path: Path) -> None:
    import importlib.util
    import sys

    script = Path("training/scripts/aggregate_evaluation_summary.py")
    spec = importlib.util.spec_from_file_location("aggregate_evaluation_summary", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "videos").mkdir()
    seeds = list(range(2000, 2020))
    manifest = load_json(EXAMPLE_DIR / "run_manifest.json")
    manifest["evaluation_run_id"] = "e3_nominal20_unit_test"
    manifest["execution_status"] = "completed"
    manifest["evidence_level"] = "runtime_observed"
    manifest["scenario"]["seeds"] = seeds
    manifest["provenance"]["model"]["checkpoint_sha256"] = "a" * 64
    manifest["provenance"]["model"]["checkpoint_path"] = "/tmp/ckpt.pt"
    manifest["provenance"]["model"]["model_commit"] = "b" * 40
    manifest["provenance"]["dataset"]["manifest_sha256"] = "c" * 64
    manifest["provenance"]["dataset"]["manifest_path"] = "/tmp/manifest.json"
    for repo in ("upstream", "midstream", "downstream"):
        manifest["provenance"]["repositories"][repo]["commit_sha"] = "d" * 40
    manifest["action_contract"]["future_runtime_adapter"]["implementation_status"] = (
        "implemented"
    )
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest) + "\n")

    rows = []
    for idx, seed in enumerate(seeds):
        video = run_dir / "videos" / f"seed_{seed}.mp4"
        video.write_bytes(b"fake")
        runtime = run_dir / f"runtime_{seed}.log"
        events = run_dir / f"events_{seed}.jsonl"
        nfr = run_dir / f"nfr_{seed}.json"
        runtime.write_text("ok\n")
        events.write_text("")
        nfr.write_text("{}\n")
        success = idx == 0  # one synthetic success
        row = {
            "contract_version": "evaluation_contract_v0",
            "artifact_type": "episode_result",
            "evaluation_run_id": "e3_nominal20_unit_test",
            "execution_status": "completed",
            "evidence_level": "runtime_observed",
            "identity": {
                "model_id": "unit",
                "backend": "isaac",
                "scene_id": "panda_pick_place_v1",
                "suite_id": "nominal",
                "seed": seed,
                "episode_index": idx,
            },
            "timestamps": {
                "simulation_start_s": None,
                "simulation_end_s": None,
                "ros_start_s": None,
                "ros_end_s": None,
                "monotonic_start_s": 0.0,
                "monotonic_end_s": 1.0,
                "reset_completed_monotonic_s": 0.0,
                "first_valid_state_monotonic_s": 0.1,
            },
            "outcome": {
                "runtime_evaluated": True,
                "evaluator": {
                    "owner_repository": "ros2-arm-teleoperation-suite",
                    "evaluator_id": "panda_continuous_gt_v0",
                    "evaluator_version": "0.1.0",
                    "ground_truth_source": "runtime_ground_truth",
                },
                "success": success,
                "timeout": False,
                "failure_stage": None if success else "lift",
                "failure_reason": None if success else "lift_failed",
            },
            "subgoals": {
                "reach": True,
                "grasp": True,
                "lift": success,
                "transport": success,
                "place": success,
                "release": success,
            },
            "motion": {
                "completion_time_s": 1.0,
                "ee_tracking_rmse_m": None,
                "ee_tracking_p95_m": None,
                "ee_tracking_max_m": None,
                "path_length_m": 0.1,
                "smoothness_jerk_rms": None,
            },
            "contact_safety": {
                "collision_count": 0,
                "drop_detected": False,
                "slip_detected": False,
                "peak_force_n": 0.0,
                "peak_torque_nm": None,
                "joint_limit_event_count": None,
                "estop_triggered": False,
            },
            "data_health": {
                "missing_frame_count": None,
                "stale_state_count": None,
                "stale_command_count": None,
                "reused_frame_count": None,
                "dropped_frame_count": None,
                "recorder_hz": None,
            },
            "system_performance": {
                "physics_fps": None,
                "real_time_factor": None,
                "cpu_percent": None,
                "rss_mb": None,
                "gpu_percent": None,
                "vram_mb": None,
                "frame_time_p95_ms": None,
                "command_age_p50_ms": None,
                "command_age_p95_ms": None,
                "command_age_max_ms": None,
                "state_age_p50_ms": None,
                "state_age_p95_ms": None,
                "state_age_max_ms": None,
                "control_frequency_hz": None,
                "state_frequency_hz": None,
                "watchdog_latency_ms": None,
                "reset_recovery_ms": None,
            },
            "fail_safe_events": [],
            "evidence": {
                "raw_episode_path": str(run_dir / f"raw_{seed}"),
                "video_path": str(video),
                "runtime_log_path": str(runtime),
                "event_log_path": str(events),
                "nfr_sample_path": str(nfr),
            },
        }
        rows.append(row)
        validator("episode_result.schema.json").validate(row)

    (run_dir / "episode_results.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n"
    )
    summary = mod.aggregate(run_dir, place_go_threshold=0.5)
    assert summary["counts"]["planned"] == 20
    assert summary["counts"]["completed"] == 20
    assert summary["overall_success"]["numerator"] == 1
    assert summary["go_no_go"]["status"] == "no_go"
    assert len(summary["top_failure_videos"]) == 5
    validator("summary.schema.json").validate(summary)


def test_unknown_fields_are_rejected() -> None:
    manifest = copy.deepcopy(load_json(EXAMPLE_DIR / "run_manifest.json"))
    manifest["uncontracted_field"] = "must fail"

    with pytest.raises(ValidationError):
        validator("run_manifest.schema.json").validate(manifest)
