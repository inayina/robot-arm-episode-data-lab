#!/usr/bin/env python3
"""Phase-aware QA for SmolVLA S3 v3 scene-only collections (read-only)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CFG = ROOT / "configs" / "smolvla_s3" / "v3_phaseaware50.yaml"


def _hysteresis_edges(
    values: list[float], *, closed_le: float = 0.4, open_ge: float = 0.6
) -> tuple[int, int]:
    state: str | None = None
    closes = 0
    reopens = 0
    for raw in values:
        value = float(raw)
        new_state = "closed" if value <= closed_le else "open" if value >= open_ge else None
        if new_state is None:
            continue
        if state == "open" and new_state == "closed":
            closes += 1
        elif state == "closed" and new_state == "open":
            reopens += 1
        state = new_state
    return closes, reopens


def audit_episode(parquet: Path, thresholds: dict[str, Any]) -> dict[str, Any]:
    table = pq.read_table(parquet)
    action = np.asarray(
        [table.column("action")[i].as_py() for i in range(table.num_rows)],
        dtype=np.float64,
    )
    grips = action[:, 7].tolist()
    closes, reopens = _hysteresis_edges(grips)
    # Ramp length: frames from first <0.95 open to first sustained closed.
    open_idx = next((i for i, g in enumerate(grips) if g >= 0.95), None)
    close_idx = next((i for i, g in enumerate(grips) if g <= 0.4), None)
    ramp = None
    if open_idx is not None and close_idx is not None and close_idx > open_idx:
        ramp = int(close_idx - open_idx)
    steps = np.linalg.norm(np.diff(action[:, :3], axis=0), axis=1) if len(action) > 1 else np.array([0.0])
    p90 = float(np.percentile(steps, 90))
    failures: list[str] = []
    if closes != int(thresholds["expert_binary_close_transitions"]):
        failures.append(f"close_transitions={closes}")
    if reopens > int(thresholds["reopen_count_max"]):
        failures.append(f"reopens={reopens}")
    if float(min(grips)) < float(thresholds["gripper_cmd_min"]) - 1e-6:
        failures.append("gripper_cmd_below_0")
    if float(max(grips)) > float(thresholds["gripper_cmd_max"]) + 1e-6:
        failures.append("gripper_cmd_above_1")
    if ramp is not None and not (
        int(thresholds["close_ramp_frames_min"])
        <= ramp
        <= int(thresholds["close_ramp_frames_max"])
    ):
        failures.append(f"close_ramp_frames={ramp}")
    if p90 > float(thresholds["max_ee_step_l2_p90_m"]):
        failures.append(f"ee_step_l2_p90={p90:.4f}")
    return {
        "parquet": str(parquet),
        "num_frames": int(table.num_rows),
        "close_transitions": closes,
        "reopens": reopens,
        "close_ramp_frames": ramp,
        "ee_step_l2_p90": p90,
        "gripper_cmd_min": float(min(grips)),
        "gripper_cmd_max": float(max(grips)),
        "passed": len(failures) == 0,
        "failures": failures,
    }


def audit_sources(sources: list[Path], cfg: dict[str, Any]) -> dict[str, Any]:
    thresholds = dict(cfg["phaseaware_thresholds"])
    episodes: list[dict[str, Any]] = []
    for src in sources:
        info = json.loads((src / "meta" / "info.json").read_text(encoding="utf-8"))
        n = int(info["total_episodes"])
        for i in range(n):
            parquet = src / "data" / "chunk-000" / f"episode_{i:06d}.parquet"
            row = audit_episode(parquet, thresholds)
            row["episode_ref"] = f"{src.name}/episode_{i:06d}"
            episodes.append(row)
    passed = all(e["passed"] for e in episodes) and len(episodes) > 0
    return {
        "profile": "phaseaware50",
        "num_episodes": len(episodes),
        "passed": passed,
        "gate": "phaseaware50_pass" if passed else "phaseaware50_hold",
        "episodes": episodes,
        "builds_release": False,
        "triggers_train": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CFG)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    report = audit_sources([p.resolve() for p in args.source], cfg)
    text = json.dumps(report, indent=2) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
