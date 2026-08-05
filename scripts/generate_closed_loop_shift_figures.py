#!/usr/bin/env python3
"""Render RA-WP2 figures from a frozen closed-loop shift JSON report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "evidence/closed_loop_shift_v1/report.json"
DEFAULT_OUTPUT = ROOT / "docs/portfolio/tracks/research_assistant"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    analysis = report["analysis"]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    bins = analysis["normalized_progress_bins"]
    x = [item["bin_index"] + 1 for item in bins]
    energy = [item["distance"]["energy_distance_normalized"] for item in bins]
    w1 = [item["distance"]["mean_wasserstein1_normalized"] for item in bins]
    energy_low = [item["energy_distance_episode_bootstrap"]["ci95_low"] for item in bins]
    energy_high = [item["energy_distance_episode_bootstrap"]["ci95_high"] for item in bins]

    fig, left = plt.subplots(figsize=(8.8, 4.8))
    left.plot(x, energy, marker="o", linewidth=2, label="Pooled energy distance")
    left.fill_between(x, energy_low, energy_high, alpha=0.18, label="Episode-bootstrap median 95% interval")
    left.set_xlabel("Normalized episode-progress bin (proxy, not task phase)")
    left.set_ylabel("Energy distance (train-normalized state15)")
    left.grid(alpha=0.25)
    right = left.twinx()
    right.plot(x, w1, marker="s", color="#d95f02", linewidth=2, label="Mean per-dim W1")
    right.set_ylabel("Mean Wasserstein-1 (normalized)")
    handles_a, labels_a = left.get_legend_handles_labels()
    handles_b, labels_b = right.get_legend_handles_labels()
    left.legend(handles_a + handles_b, labels_a + labels_b, loc="upper left", fontsize=8)
    left.set_title("RA-WP2: autonomous state shift grows over normalized progress")
    fig.text(0.5, 0.01, "Diagnostic only · phase unavailable · not causal proof · not task success", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    temporal_path = args.output_dir / "closed_loop_shift_progress.png"
    fig.savefig(temporal_path, dpi=180)
    plt.close(fig)

    dimensions = sorted(
        analysis["global_distance"]["per_dimension"],
        key=lambda item: item["wasserstein1_normalized"],
        reverse=True,
    )
    names = [item["name"] for item in dimensions]
    values = [item["wasserstein1_normalized"] for item in dimensions]
    fig, axis = plt.subplots(figsize=(9.2, 5.2))
    axis.barh(names[::-1], values[::-1], color="#4c78a8")
    axis.set_xlabel("Wasserstein-1 in frozen train-normalized units")
    axis.set_title("Global train vs autonomous shift by state15 dimension")
    axis.grid(axis="x", alpha=0.25)
    fig.text(0.5, 0.01, "Descriptive ranking only · correlated dimensions · no multiple-testing claim", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    dimensions_path = args.output_dir / "closed_loop_shift_dimensions.png"
    fig.savefig(dimensions_path, dpi=180)
    plt.close(fig)

    print(f"wrote {temporal_path}")
    print(f"wrote {dimensions_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
