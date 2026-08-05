#!/usr/bin/env python3
"""Run the four CPU-only policy onboarding cases and emit a PoC summary."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.policy_onboarding import validate_bundle


DEFAULT_FIXTURE = ROOT / "evaluation" / "examples" / "policy_onboarding_fixture"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/policy_onboarding_poc"),
        help="Report destination; existing unrelated files are preserved",
    )
    args = parser.parse_args()

    base = args.fixture_root / "base"
    cases = sorted((args.fixture_root / "cases").glob("*.json"))
    if not base.is_dir() or not cases:
        print("fixture root must contain base/ and cases/*.json", file=sys.stderr)
        return 4

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    all_expected = True
    for case_path in cases:
        case = json.loads(case_path.read_text(encoding="utf-8"))
        report = validate_bundle(base, case_path)
        failing_reasons = [
            check["reason_code"]
            for check in report["checks"]
            if check["status"] != "pass"
        ]
        expected_status = case["expected_status"]
        expected_reason = case["expected_reason_code"]
        matched = report["status"] == expected_status and (
            expected_reason == "none" or expected_reason in failing_reasons
        )
        all_expected &= matched
        report_path = args.output_dir / f"{case['case_id']}.preflight_report.json"
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        results.append(
            {
                "case_id": case["case_id"],
                "expected_status": expected_status,
                "actual_status": report["status"],
                "expected_reason_code": expected_reason,
                "actual_failure_reason_codes": failing_reasons,
                "matched": matched,
                "report": report_path.name,
            }
        )

    summary = {
        "report_version": "solution_policy_onboarding_poc_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "fixture_root": str(args.fixture_root),
        "all_cases_matched": all_expected,
        "cases": results,
        "claims_task_success": False,
        "claims_sim2real": False,
        "claims_online_autonomous_grasp": False,
        "authorized_simulation": False,
        "authorized_training": False,
        "authorized_real_robot": False,
    }
    summary_path = args.output_dir / "poc_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for result in results:
        marker = "PASS" if result["matched"] else "MISMATCH"
        print(f"[{marker}] {result['case_id']}: {result['actual_status']}")
    print(f"summary: {summary_path}")
    print("Not task success / Not Sim2Real / Not real robot")
    return 0 if all_expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
