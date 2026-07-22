#!/usr/bin/env python3
"""Export absolute-EEF (scheme B) active-channel fixture JSONL.

Accepts upstream-like JSONL or LeRobot parquet episodes with ``action[8]``.
Does not load VLA weights, train, or run Isaac.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evaluation.vla_contract import export_frames, write_frames_jsonl
from evaluation.vla_contract.absolute_eef import (
    load_rows_from_jsonl,
    load_rows_from_parquet,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--input-jsonl",
        type=Path,
        help="JSONL of upstream/adapted rows with ee_pose_gripper[8] actions",
    )
    src.add_argument(
        "--input-parquet",
        type=Path,
        help="Upstream LeRobot episode parquet with absolute action[8]",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        required=True,
        help="Output absolute-EEF fixture JSONL",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional cap on exported frames",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=1,
        help="Parquet sampling stride (ignored for JSONL unless --max-frames)",
    )
    parser.add_argument(
        "--prefer-cmd-neq-measured",
        action="store_true",
        help="Prefer parquet rows where gripper_cmd differs from measured",
    )
    parser.add_argument(
        "--provenance-json",
        type=Path,
        default=None,
        help="Optional sidecar with export provenance (no task-success claims)",
    )
    args = parser.parse_args()

    if args.input_jsonl is not None:
        rows = load_rows_from_jsonl(args.input_jsonl)
        if args.max_frames is not None:
            rows = rows[: max(0, int(args.max_frames))]
        source = str(args.input_jsonl)
        source_kind = "jsonl"
    else:
        rows = load_rows_from_parquet(
            args.input_parquet,
            max_frames=args.max_frames,
            stride=args.stride,
            prefer_cmd_neq_measured=args.prefer_cmd_neq_measured,
        )
        source = str(args.input_parquet)
        source_kind = "parquet"

    frames = export_frames(rows)
    write_frames_jsonl(args.output_jsonl, frames)
    print(f"wrote {len(frames)} frames -> {args.output_jsonl}")

    if args.provenance_json is not None:
        neq = sum(1 for f in frames if f.get("gripper_split", {}).get("cmd_neq_measured"))
        payload = {
            "contract_version": "vla_absolute_eef_export_provenance_v0",
            "artifact_type": "vla_absolute_eef_export_provenance",
            "source_kind": source_kind,
            "source_path": source,
            "output_path": str(args.output_jsonl),
            "frame_count": len(frames),
            "cmd_neq_measured_count": neq,
            "policy_action_semantics": "absolute_eef_gripper_v0",
            "quaternion_order": "xyzw",
            "claims_task_success": False,
            "claims_official_layout_verified": False,
            "notes": [
                "Scheme B fixture only; not VLA open-loop metrics.",
                "Refuse midstream ee_delta_gripper[7] as absolute action.",
            ],
        }
        args.provenance_json.parent.mkdir(parents=True, exist_ok=True)
        args.provenance_json.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"wrote provenance -> {args.provenance_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
