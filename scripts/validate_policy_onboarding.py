#!/usr/bin/env python3
"""Validate a policy onboarding bundle without loading policy code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.policy_onboarding import validate_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--case", type=Path, help="Optional documented fixture mutation")
    parser.add_argument("--output", type=Path, help="Write the JSON report to this path")
    args = parser.parse_args()

    try:
        report = validate_bundle(args.bundle, args.case)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"onboarding preflight could not run: {exc}", file=sys.stderr)
        return 4

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return {"pass": 0, "hold": 2, "invalid": 3}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
