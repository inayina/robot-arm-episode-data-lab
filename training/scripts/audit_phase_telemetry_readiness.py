#!/usr/bin/env python3
"""Audit whether frozen evidence can support true phase-conditioned analysis."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts.analyze_closed_loop_shift import DEFAULT_RELEASE, DEFAULT_S4


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--online-evidence", type=Path, default=DEFAULT_S4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        print(f"refusing to overwrite existing audit: {args.output}")
        return 4

    index_rows = _jsonl(args.release / "episode_index.jsonl")
    train_ids = set(json.loads((args.release / "splits.json").read_text())["train"])
    train_rows = [row for row in index_rows if row["episode_id"] in train_ids]
    phase_columns = set()
    for row in train_rows:
        schema = pq.read_schema(row["state15_parquet_path"])
        phase_columns.update(name for name in schema.names if "phase" in name.lower())

    observation_paths = sorted(args.online_evidence.glob("trials/seed_*/telemetry/observations.jsonl"))
    timeline_paths = sorted(args.online_evidence.glob("trials/seed_*/gt_events.jsonl"))
    online_rows = [_jsonl(path) for path in observation_paths]
    timeline_rows = [_jsonl(path) for path in timeline_paths]
    v2_rows = sum(
        row.get("contract_version") == "smolvla_observation_telemetry_v2"
        for rows in online_rows for row in rows
    )
    timeline_v1_rows = sum(
        row.get("contract_version") == "panda_task_timeline_v1"
        for rows in timeline_rows for row in rows
    )
    blockers = []
    if not phase_columns:
        blockers.append("train_split_missing_frame_level_upstream_task_phase")
    if v2_rows != sum(map(len, online_rows)) or v2_rows == 0:
        blockers.append("online_observations_missing_monotonic_v2_contract")
    if timeline_v1_rows == 0:
        blockers.append("online_task_gt_timeline_missing_or_empty")

    report = {
        "contract_version": "phase_telemetry_readiness_v1",
        "artifact_type": "phase_telemetry_readiness_report",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if not blockers else "blocked_missing_source_telemetry",
        "inputs": {
            "release": str(args.release),
            "online_evidence": str(args.online_evidence),
            "release_manifest_sha256": _sha(args.release / "manifest.json"),
            "online_gate_sha256": _sha(args.online_evidence / "s4_gate.json"),
        },
        "audit": {
            "train_episodes": len(train_rows),
            "train_phase_columns": sorted(phase_columns),
            "online_observation_files": len(observation_paths),
            "online_observation_rows": sum(map(len, online_rows)),
            "online_observation_v2_rows": v2_rows,
            "online_task_timeline_files": len(timeline_paths),
            "online_task_timeline_v1_rows": timeline_v1_rows,
        },
        "blockers": blockers,
        "required_new_evidence": {
            "expert_reference": "frame-level panda_train_frame_phase_v1 from upstream GT",
            "autonomous": "same-seed observation telemetry v2 + Task GT timeline v1",
            "may_reuse_old_rows_by_inference": False,
        },
        "analysis_executed": False,
        "diagnostic_only": True,
        "gate_eligible": False,
        "claims_causal_proof": False,
        "claims_task_success": False,
        "claims_sim2real": False,
        "claims_real_robot": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "blockers": blockers}, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
