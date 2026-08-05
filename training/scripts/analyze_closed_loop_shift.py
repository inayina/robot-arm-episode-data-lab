#!/usr/bin/env python3
"""Run RA-WP2 on frozen train state15 and authoritative relight S4 telemetry."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.closed_loop_shift import NormStats, analyze_closed_loop_shift


DEFAULT_RELEASE = ROOT / "data/releases/smolvla_s3_panda_abs_eef_scene_v3_phaseaware50"
DEFAULT_S4 = ROOT / "evidence/smolvla_s4_bounded5_relight_20260724T151711Z"


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_train_episodes(release: Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    manifest = _json(release / "manifest.json")
    splits = _json(release / "splits.json")
    index_rows = _jsonl(release / "episode_index.jsonl")
    index = {row["episode_id"]: row for row in index_rows}
    train_ids = splits["train"]
    if len(train_ids) != 36 or set(train_ids) & set(splits["validation"] + splits["benchmark"]):
        raise ValueError("expected leakage-free 36-episode training split")
    episodes = {}
    parquet_hashes = {}
    for episode_id in train_ids:
        row = index.get(episode_id)
        if row is None:
            raise ValueError(f"training episode absent from index: {episode_id}")
        state_path = Path(row["state15_parquet_path"])
        if not state_path.is_file():
            source_name, episode_name = episode_id.split("/", 1)
            state_path = release / "lerobot_state15" / source_name / "data/chunk-000" / f"{episode_name}.parquet"
        if not state_path.is_file() or _sha256(state_path) != row["state15_parquet_sha256"]:
            raise ValueError(f"state15 parquet identity mismatch: {episode_id}")
        table = pq.read_table(state_path, columns=["observation.state"])
        values = np.asarray(table.column("observation.state").to_pylist(), dtype=np.float64)
        if values.ndim != 2 or values.shape[1] != 15:
            raise ValueError(f"state15 dimension mismatch: {episode_id}")
        episodes[episode_id] = values
        parquet_hashes[episode_id] = row["state15_parquet_sha256"]
    provenance = {
        "release_id": manifest["release_id"],
        "release_content_sha256": manifest["release_content_sha256"],
        "manifest_sha256": _sha256(release / "manifest.json"),
        "splits_sha256": _sha256(release / "splits.json"),
        "episode_index_sha256": _sha256(release / "episode_index.jsonl"),
        "norm_stats_sha256": _sha256(release / "norm_stats.json"),
        "training_episode_parquet_sha256": parquet_hashes,
    }
    return episodes, provenance


def load_online_episodes(s4_root: Path) -> tuple[dict[str, np.ndarray], dict[str, list[float]], dict[str, Any]]:
    telemetry_paths = sorted(s4_root.glob("trials/seed_*/telemetry/observations.jsonl"))
    if len(telemetry_paths) != 5:
        raise ValueError("expected authoritative relight telemetry for exactly five seeds")
    episodes = {}
    commands = {}
    hashes = {}
    for path in telemetry_paths:
        seed = path.parents[1].name
        rows = _jsonl(path)
        if len(rows) != 150 or [row.get("index") for row in rows] != list(range(150)):
            raise ValueError(f"{seed}: expected 150 ordered telemetry rows")
        values = np.asarray([row["state15"] for row in rows], dtype=np.float64)
        episodes[seed] = values
        commands[seed] = [float(row["gripper_cmd"]) for row in rows]
        hashes[seed] = _sha256(path)
    gate = _json(s4_root / "s4_gate.json")
    if gate.get("ran_isaac") is not True or gate.get("gate_pass") is not False:
        raise ValueError("S4 identity is not the authoritative bounded Hold run")
    provenance = {
        "s4_evidence_id": s4_root.name,
        "s4_gate_sha256": _sha256(s4_root / "s4_gate.json"),
        "episode_results_sha256": _sha256(s4_root / "episode_results.jsonl"),
        "telemetry_sha256": hashes,
        "seeds": [1, 2, 3, 4, 5],
        "authoritative_result": {
            "interface": gate["policy_interface_pass"],
            "reach": gate["reach"],
            "grasp": gate["grasp"],
            "lift": gate["lift"],
            "gate_pass": gate["gate_pass"],
        },
    }
    return episodes, commands, provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--s4-evidence", type=Path, default=DEFAULT_S4)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-iterations", type=int, default=2000)
    args = parser.parse_args()
    if args.output.exists():
        print(f"refusing to overwrite existing report: {args.output}", file=sys.stderr)
        return 4
    try:
        train, train_provenance = load_train_episodes(args.release.resolve())
        online, commands, online_provenance = load_online_episodes(args.s4_evidence.resolve())
        norm_payload = _json(args.release / "norm_stats.json")["state15"]
        stats = NormStats.from_sequences(
            norm_payload["mean"], norm_payload["std"], norm_payload["names"]
        )
        analysis = analyze_closed_loop_shift(
            train,
            online,
            stats,
            online_gripper_commands=commands,
            bootstrap_iterations=args.bootstrap_iterations,
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"closed-loop shift analysis failed: {exc}", file=sys.stderr)
        return 3

    temporal = analysis["temporal_assessment"]
    report = {
        "contract_version": "closed_loop_shift_report_v1",
        "artifact_type": "closed_loop_shift_report",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "provenance": {
            "train": train_provenance,
            "online": online_provenance,
            "source_paths": {
                "release": str(args.release),
                "s4_evidence": str(args.s4_evidence),
            },
        },
        "method": {
            "state_contract": "observation.state[15]=joint7+ee_pose_xyzw7+measured_gripper1",
            "normalization": "frozen train norm_stats state15",
            "univariate_metric": "empirical Wasserstein-1 on 512 shared quantiles",
            "multivariate_metric": "energy distance; deterministic cap 1024 frames per side",
            "uncertainty": "episode-level median bootstrap",
            "bootstrap_iterations": args.bootstrap_iterations,
            "bootstrap_seed": 20260730,
            "conditioning": "six equal normalized-progress bins; proxy only",
            "phase_conditioned_status": "unavailable_no_reliable_phase_field",
            "failure_onset_alignment_status": "unavailable_empty_gt_events_and_no_event_timestamp_in_observations",
            "privileged_object_pose_used_in_policy_state": False,
        },
        "analysis": analysis,
        "conclusion": {
            "h2_assessment": temporal["h2_assessment"],
            "supports_temporal_distribution_shift": temporal["directional_temporal_shift"],
            "phase_specific_claim_allowed": False,
            "failure_precedence_claim_allowed": False,
            "interpretation": (
                "Existing telemetry can quantify global and normalized-progress state shift. "
                "Because reliable task phases and failure-onset events are absent, the result "
                "cannot establish phase-specific or causal covariate shift."
            ),
        },
        "diagnostic_only": True,
        "gate_eligible": False,
        "claims_causal_proof": False,
        "claims_task_success": False,
        "claims_sim2real": False,
        "claims_real_robot": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    print(json.dumps({"counts": analysis["counts"], "conclusion": report["conclusion"]}, indent=2))
    print("Diagnostic only / Not causal proof / Not task success / Not Sim2Real")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
