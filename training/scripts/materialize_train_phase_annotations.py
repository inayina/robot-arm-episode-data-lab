#!/usr/bin/env python3
"""Materialize upstream Task GT frame phases for phase-conditioned analysis."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.phase_conditioned_shift import PHASE_SEMANTICS
from training.scripts.analyze_closed_loop_shift import DEFAULT_RELEASE


CONTRACT_VERSION = "panda_train_frame_phase_v1"
PHASE_SOURCE = "upstream_continuous_task_evaluator"


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _meta_path(source_root: Path, episode_name: str) -> Path:
    return source_root / episode_name / "meta.json"


def _phases_from_source_parquet(path: Path) -> list[str] | None:
    schema = pq.read_schema(path)
    if "task_phase" not in schema.names:
        return None
    table = pq.read_table(path, columns=["task_phase"])
    return [str(value.as_py()) for value in table.column("task_phase")]


def _phases_from_meta(path: Path) -> list[str] | None:
    if not path.is_file():
        return None
    payload = _json(path)
    metadata = payload.get("metadata") or {}
    phases = payload.get("task_phases") or metadata.get("task_phases")
    if phases is None:
        return None
    if metadata.get("task_phase_source", PHASE_SOURCE) != PHASE_SOURCE:
        raise ValueError(f"{path}: task_phase_source is not upstream Task GT")
    if metadata.get("task_phase_semantics", PHASE_SEMANTICS) != PHASE_SEMANTICS:
        raise ValueError(f"{path}: task_phase_semantics mismatch")
    return [str(phase) for phase in phases]


def materialize_rows(release: Path, *, allow_unavailable: bool = False) -> list[dict[str, Any]]:
    splits = _json(release / "splits.json")
    index_rows = _jsonl(release / "episode_index.jsonl")
    by_id = {row["episode_id"]: row for row in index_rows}
    rows: list[dict[str, Any]] = []
    for episode_id in splits["train"]:
        row = by_id[episode_id]
        source_root = Path(row["source_root"])
        episode_name = episode_id.split("/", 1)[1]
        source_parquet = Path(row["parquet_path"])
        phases = _phases_from_source_parquet(source_parquet) if source_parquet.is_file() else None
        if phases is None:
            phases = _phases_from_meta(_meta_path(source_root, episode_name))
        if phases is None:
            raise ValueError(f"{episode_id}: missing upstream frame-level task phases")
        if len(phases) != int(row["num_frames"]):
            raise ValueError(f"{episode_id}: phase length does not match num_frames")
        if not allow_unavailable and any(phase == "UNAVAILABLE" for phase in phases):
            raise ValueError(f"{episode_id}: contains UNAVAILABLE task phase")
        for frame_index, phase in enumerate(phases):
            rows.append(
                {
                    "contract_version": CONTRACT_VERSION,
                    "artifact_type": "train_frame_phase",
                    "episode_id": episode_id,
                    "frame_index": frame_index,
                    "phase": phase,
                    "phase_source": PHASE_SOURCE,
                    "phase_semantics": PHASE_SEMANTICS,
                    "claims_task_success": False,
                    "claims_causal_proof": False,
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-unavailable", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        print(f"refusing to overwrite existing annotations: {args.output}", file=sys.stderr)
        return 4
    try:
        rows = materialize_rows(args.release.resolve(), allow_unavailable=args.allow_unavailable)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"phase annotation materialization failed: {exc}", file=sys.stderr)
        return 3
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "contract_version": "panda_train_frame_phase_manifest_v1",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "release": str(args.release),
                    "rows": len(rows),
                    "diagnostic_only": True,
                    "claims_task_success": False,
                    "claims_causal_proof": False,
                },
                sort_keys=True,
            )
            + "\n"
        )
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    print(f"wrote {len(rows)} rows -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
