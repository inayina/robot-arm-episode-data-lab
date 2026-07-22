#!/usr/bin/env python3
"""Read-only ACT HOME_NO_CLOSE distribution diagnostic.

Does not train, download weights, or rewrite evidence directories.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evaluation.diagnostics.home_no_close import build_report, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frames-jsonl",
        type=Path,
        required=True,
        help="Midstream release frames.jsonl with ee_delta_gripper[7]",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=None,
        help="Optional evidence dir with seeds/*/policy.log for deploy_n_action_steps",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        required=True,
        help="Diagnostic report JSON path (outside evidence/ preferred)",
    )
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args()

    report = build_report(
        frames_path=args.frames_jsonl,
        evidence_dir=args.evidence_dir,
        max_frames=args.max_frames,
    )
    write_report(args.output_json, report)
    stages = report["action_distribution"]["stage_counts"]
    deploy = report["deploy_n_action_steps"]["unique_pairs"]
    print(
        f"wrote {args.output_json} "
        f"frames={report['frame_count']} stages={stages} deploy={deploy}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
