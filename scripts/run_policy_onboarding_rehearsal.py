#!/usr/bin/env python3
"""Run two timed onboarding batches and compare normalized results."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.policy_onboarding import validate_bundle


DEFAULT_FIXTURE = ROOT / "evaluation" / "examples" / "policy_onboarding_fixture"


def _normalized_report(report: dict) -> dict:
    """Remove volatile provenance while retaining every decision field."""

    return {
        "report_version": report["report_version"],
        "bundle_id": report["bundle_id"],
        "case_id": report["case_id"],
        "status": report["status"],
        "next_allowed_stage": report["next_allowed_stage"],
        "checks": report["checks"],
        "claims_task_success": report["claims_task_success"],
        "claims_sim2real": report["claims_sim2real"],
        "claims_online_autonomous_grasp": report["claims_online_autonomous_grasp"],
        "authorized_simulation": report["authorized_simulation"],
        "authorized_training": report["authorized_training"],
        "authorized_real_robot": report["authorized_real_robot"],
    }


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        print(f"refusing to overwrite non-empty evidence directory: {args.output_dir}", file=sys.stderr)
        return 4
    args.output_dir.mkdir(parents=True, exist_ok=True)

    base = args.fixture_root / "base"
    case_paths = sorted((args.fixture_root / "cases").glob("*.json"))
    if not base.is_dir() or len(case_paths) != 4:
        print("rehearsal requires one base bundle and exactly four cases", file=sys.stderr)
        return 4

    run_records = []
    normalized_runs = []
    for run_number in (1, 2):
        run_dir = args.output_dir / f"run_{run_number}"
        run_dir.mkdir()
        started = perf_counter()
        reports = []
        case_matches = []
        for case_path in case_paths:
            case = json.loads(case_path.read_text(encoding="utf-8"))
            report = validate_bundle(base, case_path)
            reasons = [
                check["reason_code"]
                for check in report["checks"]
                if check["status"] != "pass"
            ]
            matched = report["status"] == case["expected_status"] and (
                case["expected_reason_code"] == "none"
                or case["expected_reason_code"] in reasons
            )
            case_matches.append(matched)
            reports.append(report)
            (run_dir / f"{case['case_id']}.preflight_report.json").write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        elapsed_ms = (perf_counter() - started) * 1000.0
        normalized = [_normalized_report(report) for report in reports]
        normalized_sha = hashlib.sha256(_canonical_bytes(normalized)).hexdigest()
        normalized_runs.append(normalized)
        run_records.append(
            {
                "run_number": run_number,
                "batch_validation_and_write_elapsed_ms": round(elapsed_ms, 3),
                "all_cases_matched": all(case_matches),
                "normalized_sha256": normalized_sha,
                "case_statuses": {
                    report["case_id"]: report["status"] for report in reports
                },
            }
        )

    equivalent = normalized_runs[0] == normalized_runs[1]
    all_cases_matched = all(run["all_cases_matched"] for run in run_records)
    summary = {
        "report_version": "solution_policy_onboarding_rehearsal_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rehearsal_runs": 2,
        "timing_scope": "four_case_validation_plus_json_report_write_in_process",
        "runs": run_records,
        "normalized_equivalent": equivalent,
        "all_cases_matched": all_cases_matched,
        "acceptance": {
            "nfr_02_reproducibility": "pass" if equivalent else "hold",
            "poc_fixture_expectations": "pass" if all_cases_matched else "hold",
            "recorded_eight_minute_demo": "not_run",
        },
        "claims_task_success": False,
        "claims_sim2real": False,
        "claims_online_autonomous_grasp": False,
        "authorized_simulation": False,
        "authorized_training": False,
        "authorized_real_robot": False,
    }
    summary_path = args.output_dir / "rehearsal_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"run 1: {run_records[0]['batch_validation_and_write_elapsed_ms']:.3f} ms")
    print(f"run 2: {run_records[1]['batch_validation_and_write_elapsed_ms']:.3f} ms")
    print(f"normalized equivalent: {equivalent}")
    print(f"all fixture expectations matched: {all_cases_matched}")
    print(f"summary: {summary_path}")
    print("Not task success / Not Sim2Real / Not real robot")
    return 0 if equivalent and all_cases_matched else 1


if __name__ == "__main__":
    raise SystemExit(main())
