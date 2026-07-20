#!/usr/bin/env python3
"""Summarize one bounded ACT-to-Isaac execution without overstating task success."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pose_xyz(path: Path) -> list[float]:
    payload = next(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    position = payload["pose"]["position"]
    return [float(position[axis]) for axis in ("x", "y", "z")]


def gpu_metrics(path: Path) -> dict:
    gpu, memory = [], []
    with path.open(encoding="utf-8") as handle:
        for row in csv.reader(handle):
            if len(row) < 3:
                continue
            gpu.append(float(row[1]))
            memory.append(float(row[2]))
    return {
        "samples": len(gpu),
        "gpu_percent_mean": float(np.mean(gpu)),
        "gpu_percent_peak": float(np.max(gpu)),
        "vram_mib_start": memory[0],
        "vram_mib_peak": float(np.max(memory)),
    }


def main() -> int:
    args = parse_args()
    report_path = args.evidence / "report.json"
    runtime = json.loads(report_path.read_text(encoding="utf-8"))
    release = json.loads((args.release / "manifest.json").read_text(encoding="utf-8"))
    initial_object = pose_xyz(args.evidence / "initial_object_pose.txt")
    final_object = pose_xyz(args.evidence / "final_object_pose.txt")
    displacement = math.dist(initial_object, final_object)
    bin_error = math.hypot(final_object[0] - 0.4, final_object[1] + 0.35)
    latencies = np.asarray(
        [float(action["inference_latency_ms"]) for action in runtime["actions"]]
    )
    gripper = [float(action["bounded_action"][6]) for action in runtime["actions"]]

    interface_pass = runtime.get("status") == "PASS"
    task_pass = False
    task_reason = (
        "no_close_action_and_final_object_unchanged"
        if min(gripper, default=1.0) >= 0.99 and displacement < 1e-4
        else "task_success_not_established"
    )
    summary = {
        "artifact_type": "bounded_isaac_act_evaluation_summary",
        "evidence_level": "real_isaac_execution_with_endpoint_task_check",
        "checkpoint": {
            "path": str(args.checkpoint.resolve()),
            "sha256": sha256(args.checkpoint),
            "release_id": runtime.get("checkpoint_release_id"),
        },
        "release": {
            "path": str(args.release.resolve()),
            "release_id": release["release_id"],
            "episodes": release["num_episodes"],
            "frames": release["num_frames"],
            "upstream_gate": release["filter_rules"]["upstream_gate"],
        },
        "interface_execution": {
            "status": "PASS" if interface_pass else "FAIL",
            "requested_actions": runtime["requested_actions"],
            "completed_actions": runtime["completed_actions"],
            "execution_status": runtime["execution_status"],
            "safety_ok": runtime["final_safety_ok"],
            "estop": runtime["final_safety_estop"],
            "ee_excursion_m": runtime["max_observed_ee_excursion_m"],
            "joint_excursion_rad": runtime["max_observed_joint_excursion_rad"],
        },
        "inference": {
            "latency_ms_p50": float(np.percentile(latencies, 50)),
            "latency_ms_p95": float(np.percentile(latencies, 95)),
            "latency_ms_max": float(np.max(latencies)),
            "clipped_actions": sum(bool(action["action_clipped"]) for action in runtime["actions"]),
        },
        "task": {
            "status": "PASS" if task_pass else "FAIL",
            "reason": task_reason,
            "runtime_ground_truth_evaluator": False,
            "initial_object_xyz": initial_object,
            "final_object_xyz": final_object,
            "endpoint_displacement_m": displacement,
            "final_left_bin_xy_error_m": bin_error,
            "minimum_gripper_command": min(gripper, default=None),
            "limitation": "Only endpoint object poses were recorded; no continuous lift maximum is claimed.",
        },
        "system": gpu_metrics(args.evidence / "gpu_during_policy.csv"),
        "source_evidence": {
            "directory": str(args.evidence.resolve()),
            "runtime_report_sha256": sha256(report_path),
        },
        "claim_boundary": (
            "This run proves checkpoint loading, online inference, bounded Isaac execution, "
            "safety handling, and report generation. It does not prove pick/place success."
        ),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    json_path = args.output / "summary.json"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    markdown = f"""# Bounded ACT → Isaac evaluation

- Interface/execution: **{summary['interface_execution']['status']}** ({runtime['completed_actions']}/{runtime['requested_actions']} actions)
- Task: **{summary['task']['status']}** — `{task_reason}`
- Safety: ok={runtime['final_safety_ok']}, estop={runtime['final_safety_estop']}
- Inference latency p50/p95/max: {summary['inference']['latency_ms_p50']:.2f} / {summary['inference']['latency_ms_p95']:.2f} / {summary['inference']['latency_ms_max']:.2f} ms
- Object endpoint displacement: {displacement:.9f} m
- Final left-bin XY error: {bin_error:.4f} m
- GPU mean/peak: {summary['system']['gpu_percent_mean']:.2f}% / {summary['system']['gpu_percent_peak']:.2f}%
- VRAM start/peak: {summary['system']['vram_mib_start']:.0f} / {summary['system']['vram_mib_peak']:.0f} MiB

{summary['claim_boundary']}
"""
    (args.output / "report.md").write_text(markdown, encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
