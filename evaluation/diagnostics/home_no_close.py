"""Read-only HOME_NO_CLOSE distribution diagnostics (no training, no Isaac).

Produces histograms for home-like vs close-like frames and parses smoke logs
for ``deploy_n_action_steps``. Never claims task success or mutates evidence.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


DEPLOY_STEP_RE = re.compile(
    r"ACT deploy n_action_steps=(?P<steps>\d+)\s+\(chunk_size=(?P<chunk>\d+)\)"
)


class HomeNoCloseDiagError(ValueError):
    """Diagnostic interface failure."""


def _as_action7(row: Mapping[str, Any]) -> list[float]:
    action = row.get("action")
    if action is None or len(action) != 7:
        raise HomeNoCloseDiagError("expected release action ee_delta_gripper[7]")
    values = [float(x) for x in action]
    if not all(math.isfinite(v) for v in values):
        raise HomeNoCloseDiagError("non-finite action")
    return values


def label_stage(gripper_cmd: float) -> str:
    """Heuristic stage label for release frames (not runtime GT)."""
    g = float(gripper_cmd)
    if g >= 0.95:
        return "home_like"
    if g <= 0.55:
        return "close_like"
    return "transition"


def histogram(values: Sequence[float], *, edges: Sequence[float]) -> dict[str, Any]:
    if len(edges) < 2:
        raise HomeNoCloseDiagError("histogram needs >=2 edges")
    counts = [0 for _ in range(len(edges) - 1)]
    for value in values:
        placed = False
        for i in range(len(edges) - 1):
            lo, hi = edges[i], edges[i + 1]
            if (value >= lo and value < hi) or (i == len(edges) - 2 and value == hi):
                counts[i] += 1
                placed = True
                break
        if not placed:
            # Out of range → clamp into end bins.
            if value < edges[0]:
                counts[0] += 1
            else:
                counts[-1] += 1
    return {
        "edges": [float(x) for x in edges],
        "counts": counts,
        "n": len(values),
    }


def summarize_actions(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    by_stage: dict[str, list[list[float]]] = {
        "home_like": [],
        "close_like": [],
        "transition": [],
    }
    for row in rows:
        action = _as_action7(row)
        stage = label_stage(action[6])
        by_stage[stage].append(action)

    grip_edges = [0.0, 0.2, 0.4, 0.55, 0.7, 0.85, 0.95, 1.01]
    delta_edges = [0.0, 1e-4, 1e-3, 5e-3, 1e-2, 2e-2, 5e-2, 1.0]

    stage_stats: dict[str, Any] = {}
    for stage, actions in by_stage.items():
        grips = [a[6] for a in actions]
        delta_l2 = [
            math.sqrt(sum(v * v for v in a[:6])) for a in actions
        ]
        near_zero = sum(1 for d in delta_l2 if d < 1e-3)
        stage_stats[stage] = {
            "count": len(actions),
            "gripper_cmd": {
                "mean": (sum(grips) / len(grips)) if grips else None,
                "min": min(grips) if grips else None,
                "max": max(grips) if grips else None,
                "histogram": histogram(grips, edges=grip_edges),
            },
            "delta_xyzrpy_l2": {
                "mean": (sum(delta_l2) / len(delta_l2)) if delta_l2 else None,
                "near_zero_lt_1e-3_count": near_zero,
                "near_zero_lt_1e-3_frac": (
                    near_zero / len(delta_l2) if delta_l2 else None
                ),
                "histogram": histogram(delta_l2, edges=delta_edges),
            },
        }

    return {
        "stage_counts": {k: v["count"] for k, v in stage_stats.items()},
        "stages": stage_stats,
    }


def parse_deploy_n_action_steps(log_text: str) -> list[dict[str, int]]:
    found: list[dict[str, int]] = []
    for match in DEPLOY_STEP_RE.finditer(log_text):
        found.append(
            {
                "deploy_n_action_steps": int(match.group("steps")),
                "chunk_size": int(match.group("chunk")),
            }
        )
    return found


def collect_deploy_steps_from_evidence(evidence_dir: Path) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    for log_path in sorted(evidence_dir.glob("seeds/*/policy.log")):
        text = log_path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_deploy_n_action_steps(text)
        for item in parsed:
            hits.append({"log_path": str(log_path), **item})
    unique = Counter(
        (h["deploy_n_action_steps"], h["chunk_size"]) for h in hits
    )
    return {
        "matches": hits,
        "unique_pairs": [
            {"deploy_n_action_steps": a, "chunk_size": b, "count": c}
            for (a, b), c in sorted(unique.items())
        ],
    }


def build_report(
    *,
    frames_path: Path,
    evidence_dir: Path | None = None,
    max_frames: int | None = None,
) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in frames_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if max_frames is not None:
        rows = rows[: max(0, int(max_frames))]
    action_summary = summarize_actions(rows)
    deploy = (
        collect_deploy_steps_from_evidence(evidence_dir)
        if evidence_dir is not None
        else {"matches": [], "unique_pairs": []}
    )
    return {
        "contract_version": "act_home_no_close_diag_v0",
        "artifact_type": "act_home_no_close_diagnostic",
        "claims_task_success": False,
        "mutates_evidence": False,
        "frames_path": str(frames_path),
        "frame_count": len(rows),
        "action_distribution": action_summary,
        "deploy_n_action_steps": deploy,
        "hypotheses_touched": [
            "home_vs_close_gripper_cmd_distribution",
            "home_vs_close_delta_near_zero",
            "deploy_n_action_steps_from_smoke_logs",
        ],
        "notes": [
            "Read-only diagnostic for ACT_HOME_NO_CLOSE_HYPOTHESIS_MATRIX.md §3.",
            "Does not authorize retraining or E4.",
        ],
    }


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
