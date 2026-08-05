#!/usr/bin/env python3
"""Run true upstream-GT phase-conditioned shift analysis on v1/v2 telemetry."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.closed_loop_shift import NormStats
from evaluation.phase_conditioned_shift import (
    PHASE_SEMANTICS,
    align_observations_to_timeline,
    analyze_phase_conditioned_shift,
)
from training.scripts.analyze_closed_loop_shift import DEFAULT_RELEASE, load_train_episodes


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_train_phase_annotations(
    path: Path, train_states: dict[str, np.ndarray]
) -> dict[str, list[str]]:
    rows = _jsonl(path)
    if rows and rows[0].get("contract_version") == "panda_train_frame_phase_manifest_v1":
        rows = rows[1:]
    grouped: dict[str, dict[int, str]] = {}
    for row in rows:
        if row.get("contract_version") != "panda_train_frame_phase_v1":
            raise ValueError("train phase annotations must use panda_train_frame_phase_v1")
        if row.get("phase_source") != "upstream_continuous_task_evaluator":
            raise ValueError("train phase source is not upstream Task GT")
        if row.get("phase_semantics") != PHASE_SEMANTICS:
            raise ValueError("train phase semantics mismatch")
        grouped.setdefault(str(row["episode_id"]), {})[int(row["frame_index"])] = str(row["phase"])
    if set(grouped) != set(train_states):
        raise ValueError("train phase annotation episode identities do not match frozen train split")
    result = {}
    for episode_id, states in train_states.items():
        mapping = grouped[episode_id]
        if set(mapping) != set(range(len(states))):
            raise ValueError(f"{episode_id}: incomplete frame-level phase annotations")
        result[episode_id] = [mapping[index] for index in range(len(states))]
    return result


def load_online_aligned(root: Path, *, max_age_ms: float) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    observation_paths = sorted(root.glob("trials/seed_*/telemetry/observations.jsonl"))
    if not observation_paths:
        raise ValueError("no online observation telemetry found")
    aligned = {}
    hashes = {}
    for observation_path in observation_paths:
        trial = observation_path.parents[2]
        timeline_path = trial / "gt_events.jsonl"
        if not timeline_path.is_file() or not timeline_path.stat().st_size:
            raise ValueError(f"{trial.name}: missing non-empty upstream Task GT timeline")
        observations = _jsonl(observation_path)
        timeline = _jsonl(timeline_path)
        episode_id = str(observations[0].get("episode_id")) if observations else trial.name
        aligned[episode_id] = align_observations_to_timeline(
            observations, timeline, max_age_ms=max_age_ms
        )
        hashes[episode_id] = {
            "observations_sha256": _sha256(observation_path),
            "task_timeline_sha256": _sha256(timeline_path),
        }
    return aligned, hashes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--train-phase-annotations", type=Path, required=True)
    parser.add_argument("--online-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-alignment-age-ms", type=float, default=100.0)
    parser.add_argument("--bootstrap-iterations", type=int, default=2000)
    args = parser.parse_args()
    if args.output.exists():
        print(f"refusing to overwrite existing report: {args.output}", file=sys.stderr)
        return 4
    try:
        train, train_provenance = load_train_episodes(args.release.resolve())
        phases = load_train_phase_annotations(args.train_phase_annotations.resolve(), train)
        online, online_hashes = load_online_aligned(
            args.online_evidence.resolve(), max_age_ms=args.max_alignment_age_ms
        )
        norm = _json(args.release / "norm_stats.json")["state15"]
        stats = NormStats.from_sequences(norm["mean"], norm["std"], norm["names"])
        analysis = analyze_phase_conditioned_shift(
            train,
            phases,
            online,
            stats,
            bootstrap_iterations=args.bootstrap_iterations,
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"phase-conditioned analysis refused: {exc}", file=sys.stderr)
        return 3
    report = {
        "contract_version": "phase_conditioned_shift_report_v1",
        "artifact_type": "phase_conditioned_shift_report",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if analysis["phase_results"] else "insufficient_phase_coverage",
        "provenance": {
            "train": train_provenance,
            "train_phase_annotations_sha256": _sha256(args.train_phase_annotations),
            "online": online_hashes,
        },
        "method": {
            "join_clock": "system_monotonic_ns",
            "max_alignment_age_ms": args.max_alignment_age_ms,
            "phase_source": "upstream_continuous_task_evaluator",
            "phase_semantics": PHASE_SEMANTICS,
            "proxy": False,
            "terminal_nonachievement_onset_exact": False,
            "uncertainty": "episode-level median bootstrap",
        },
        "analysis": analysis,
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
    print("Diagnostic only / Not causal proof / Not task success / Not Sim2Real")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
