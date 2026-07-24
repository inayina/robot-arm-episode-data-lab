#!/usr/bin/env python3
"""Normalize existing eval evidence into unified_eval_report_v0 JSON.

Examples:
  python3 training/scripts/normalize_unified_eval_report.py \\
    --open-loop runs/smolvla_s3/openloop_.../s3_open_loop_summary.json \\
    --policy-runner evidence/downstream/smolvla_v3_ep0_benchmark_summary.json \\
    --isaac-s4 evidence/smolvla_s4_bounded5_.../s4_gate.json \\
    --bundle-out evidence/smolvla_v3_eval_framework_20260724/smolvla_v3_eval_framework_bundle.json

Does not retrain, expand seeds, or claim task success / Sim2Real.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.unified_report import (  # noqa: E402
    build_framework_bundle,
    normalize_path_auto,
    validate_unified_report,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--open-loop", type=Path, default=None)
    parser.add_argument("--policy-runner", type=Path, default=None)
    parser.add_argument("--isaac-s4", type=Path, default=None)
    parser.add_argument(
        "--input",
        type=Path,
        action="append",
        default=[],
        help="Auto-detect backend from filename; may repeat.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Write per-backend unified_eval_report.json files here.",
    )
    parser.add_argument(
        "--bundle-out",
        type=Path,
        default=None,
        help="Write combined smolvla_v3_eval_framework_bundle.json.",
    )
    parser.add_argument(
        "--bundle-id",
        type=str,
        default="smolvla_v3_eval_framework",
    )
    parser.add_argument(
        "--risk-readiness",
        type=Path,
        default=None,
        help=(
            "Optional offline risk readiness JSON (P3). Attached as "
            "bundle appendix only; never overrides failure_lane / task GT."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths: list[Path] = []
    if args.open_loop:
        paths.append(args.open_loop)
    if args.policy_runner:
        paths.append(args.policy_runner)
    if args.isaac_s4:
        paths.append(args.isaac_s4)
    paths.extend(args.input)
    if not paths:
        raise SystemExit("provide at least one --open-loop/--policy-runner/--isaac-s4/--input")

    reports = []
    for path in paths:
        report = normalize_path_auto(path)
        errs = validate_unified_report(report)
        if errs:
            raise SystemExit(f"{path}: {errs}")
        reports.append(report)
        if args.out_dir is not None:
            out = args.out_dir / f"{report['backend_id']}_unified_eval_report.json"
            write_json(out, report)
            print(f"wrote {out}")

    risk_appendix = None
    if args.risk_readiness is not None:
        risk_payload = json.loads(args.risk_readiness.read_text(encoding="utf-8"))
        # Prefer compact appendix if present; else store a slim pointer.
        primary = risk_payload.get("primary") or {}
        agg = primary.get("aggregation") or {}
        risk_appendix = {
            "artifact_type": risk_payload.get("artifact_type"),
            "contract_version": risk_payload.get("contract_version"),
            "evaluation_run_id": risk_payload.get("evaluation_run_id"),
            "evidence_path": str(args.risk_readiness.resolve()),
            "claims_task_success": False,
            "overrides_failure_lane": False,
            "use_as_task_go_no_go": False,
            "risk_level": agg.get("level"),
            "composite_score": agg.get("composite_score"),
            "primary_driver": agg.get("primary_driver"),
            "recommendation": agg.get("recommendation"),
            "dimensions": {
                d["dimension"]: d["raw_score"]
                for d in (agg.get("dimensions") or [])
                if isinstance(d, dict) and "dimension" in d
            },
            "non_claims": list(risk_payload.get("non_claims") or []),
        }

    if args.bundle_out is not None:
        bundle = build_framework_bundle(
            reports,
            bundle_id=args.bundle_id,
            risk_readiness_appendix=risk_appendix,
        )
        write_json(args.bundle_out, bundle)
        print(f"wrote {args.bundle_out}")
    elif args.out_dir is None:
        if len(reports) == 1 and risk_appendix is None:
            print(json.dumps(reports[0], indent=2, ensure_ascii=False))
        else:
            print(
                json.dumps(
                    build_framework_bundle(
                        reports,
                        bundle_id=args.bundle_id,
                        risk_readiness_appendix=risk_appendix,
                    ),
                    indent=2,
                    ensure_ascii=False,
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
