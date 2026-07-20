#!/usr/bin/env python3
"""Aggregate episode_results.jsonl + run_manifest into contract summary.json."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--place-success-go-threshold",
        type=float,
        default=0.5,
        help="Overall place success rate required for go_no_go=go",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if n <= 0:
        return None, None, None
    p = successes / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return p, max(0.0, center - margin), min(1.0, center + margin)


def rate_metric(successes: int, n: int) -> dict[str, Any]:
    rate, lo, hi = wilson_interval(successes, n)
    return {
        "numerator": int(successes),
        "denominator": int(n),
        "rate": rate,
        "ci_method": "wilson" if n > 0 else "not_computed",
        "ci95_low": lo,
        "ci95_high": hi,
    }


def bool_count(rows: Iterable[dict[str, Any]], key_path: tuple[str, ...]) -> tuple[int, int]:
    yes = 0
    total = 0
    for row in rows:
        if row.get("execution_status") != "completed":
            continue
        if not row.get("outcome", {}).get("runtime_evaluated"):
            continue
        node: Any = row
        for key in key_path:
            if not isinstance(node, dict) or key not in node:
                node = None
                break
            node = node[key]
        if node is None:
            continue
        total += 1
        if bool(node):
            yes += 1
    return yes, total


def aggregate(run_dir: Path, place_go_threshold: float) -> dict[str, Any]:
    run_manifest_path = run_dir / "run_manifest.json"
    episode_path = run_dir / "episode_results.jsonl"
    manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    rows = load_jsonl(episode_path)
    planned_seeds = list(manifest.get("scenario", {}).get("seeds") or [])
    planned = len(planned_seeds)

    completed = sum(1 for r in rows if r.get("execution_status") == "completed")
    aborted = sum(1 for r in rows if r.get("execution_status") == "aborted")
    infra = sum(
        1 for r in rows if r.get("execution_status") == "infrastructure_failure"
    )

    success_yes = sum(
        1
        for r in rows
        if r.get("execution_status") == "completed"
        and r.get("outcome", {}).get("success") is True
    )
    success_den = sum(
        1
        for r in rows
        if r.get("execution_status") == "completed"
        and r.get("outcome", {}).get("success") is not None
    )

    subgoals = {}
    for name in ("reach", "grasp", "lift", "transport", "place", "release"):
        yes, total = bool_count(rows, ("subgoals", name))
        subgoals[name] = rate_metric(yes, total)

    fail_counter: Counter[tuple[str, str]] = Counter()
    for row in rows:
        if row.get("outcome", {}).get("success") is True:
            continue
        stage = row.get("outcome", {}).get("failure_stage") or "system"
        reason = row.get("outcome", {}).get("failure_reason") or "unknown"
        if row.get("execution_status") == "infrastructure_failure":
            stage = "system"
            reason = reason or "infrastructure_failure"
        fail_counter[(str(stage), str(reason))] += 1
    fail_total = sum(fail_counter.values()) or 1
    failure_pareto = [
        {
            "failure_stage": stage,
            "failure_reason": reason,
            "count": count,
            "fraction": count / fail_total,
        }
        for (stage, reason), count in fail_counter.most_common()
    ]

    by_seed = {int(r["identity"]["seed"]): r for r in rows if "identity" in r}
    seed_results = []
    for seed in planned_seeds:
        row = by_seed.get(int(seed))
        if row is None:
            seed_results.append(
                {
                    "seed": int(seed),
                    "execution_status": "planned",
                    "success": None,
                    "failure_reason": None,
                }
            )
            continue
        seed_results.append(
            {
                "seed": int(seed),
                "execution_status": row.get("execution_status", "completed"),
                "success": row.get("outcome", {}).get("success"),
                "failure_reason": row.get("outcome", {}).get("failure_reason"),
            }
        )

    top_failure_videos = []
    for row in rows:
        if row.get("outcome", {}).get("success") is True:
            continue
        video = (row.get("evidence") or {}).get("video_path")
        if not video:
            continue
        video_path = Path(str(video))
        if not video_path.is_file():
            # Suite copies to videos/seed_XXXX.mp4
            alt = run_dir / "videos" / f"seed_{row['identity']['seed']}.mp4"
            if alt.is_file():
                video_path = alt
            else:
                continue
        top_failure_videos.append(
            {
                "seed": int(row["identity"]["seed"]),
                "failure_reason": str(
                    row.get("outcome", {}).get("failure_reason") or "failed"
                ),
                "video_path": str(video_path),
            }
        )
        if len(top_failure_videos) >= 5:
            break

    overall = rate_metric(success_yes, success_den)
    rate = overall["rate"]
    if rate is None:
        go_status = "requires_review"
        go_reason = "Diagnostic suite incomplete or no completed runtime outcomes."
    elif rate >= place_go_threshold:
        go_status = "go"
        go_reason = (
            f"Place/overall success rate {rate:.3f} met threshold "
            f"{place_go_threshold:.3f}."
        )
    else:
        go_status = "no_go"
        go_reason = (
            "Diagnostic suite execution completed, but task capability did not "
            f"meet place/overall threshold {place_go_threshold:.3f} "
            f"(rate={rate:.3f})."
        )

    execution_status = "completed" if completed + aborted + infra >= planned else "partial"
    if planned and completed + aborted + infra == 0:
        execution_status = "aborted"

    summary = {
        "contract_version": "evaluation_contract_v0",
        "artifact_type": "summary",
        "evaluation_run_id": manifest["evaluation_run_id"],
        "execution_status": execution_status,
        "evidence_level": "runtime_observed",
        "source": {
            "run_manifest_path": str(run_manifest_path),
            "run_manifest_sha256": sha256_file(run_manifest_path),
            "episode_results_path": str(episode_path),
            "episode_results_sha256": sha256_file(episode_path),
            "aggregator_repository": "robot-arm-episode-data-lab",
        },
        "counts": {
            "planned": planned,
            "completed": completed,
            "aborted": aborted,
            "infrastructure_failure": infra,
        },
        "overall_success": overall,
        "per_suite": [
            {
                "suite_id": "nominal",
                "success": overall,
            }
        ],
        "subgoal_funnel": subgoals,
        "failure_pareto": failure_pareto,
        "seed_results": seed_results,
        "repeatability": {
            "repeated_seed_count": 0,
            "flaky_seed_count": 0,
            "agreement_rate": None,
        },
        "baseline_delta": {
            "baseline_run_id": None,
            "success_rate_delta": None,
            "comparison_status": "not_requested",
        },
        "top_failure_videos": top_failure_videos,
        "recommendations": {
            "data_collection": [
                "Do not expand uniformly to 50 episodes while home CLOSE_MISALIGNED persists.",
                "Prioritize home→pregrasp alignment / approach_xy quality over more XY-align volume.",
            ],
            "model_changes": [
                "Keep E3 default checkpoint as 30-ep descend until home place rate improves.",
            ],
            "simulator_calibration": [
                "Treat Isaac continuous GT as diagnostic under domain gap vs MuJoCo training.",
            ],
        },
        "go_no_go": {"status": go_status, "reason": go_reason},
        "limitations": [
            "Bounded home_start Isaac diagnostic; not Sim2Real and not real-robot deployment.",
            "Overall success is ContinuousTaskEvaluator place/lift truth, not interface PASS.",
            "Warmstart was not part of this suite; do not equate warm close with home autonomy.",
            "Failure videos may be missing when ffmpeg/camera path failed for a seed.",
        ],
    }
    return summary


def main() -> int:
    args = parse_args()
    summary = aggregate(args.run_dir, args.place_success_go_threshold)
    output = args.output or (args.run_dir / "summary.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    print(
        "overall_success="
        f"{summary['overall_success']['rate']} "
        f"go_no_go={summary['go_no_go']['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
