#!/usr/bin/env python3
"""Generate SmolVLA Recovery v3 / bounded S4 portfolio figures from frozen evidence.

Reads only existing evidence artifacts (no re-evaluation) and renders PNG figures
into docs/portfolio/. Every figure carries the honest-claims footer required by
AGENTS.md 8.6: open-loop Pass / interface Pass / ran_isaac=true are NOT task
success and NOT Sim2Real.

Inputs (canonical, overridable via CLI):
  - midstream runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/s3_open_loop_report.json
  - midstream evidence/smolvla_s4_bounded5_20260724T203700Z/{s4_gate.json,episode_results.jsonl,trials/seed_*/report.json}
  - downstream evidence/downstream/smolvla_v3_ep0_policyrunner_20260724T213800Z/benchmark_timeseries.csv (+ benchmark_summary.json)
  - midstream evidence/smolvla_v3_eval_framework_20260724/*.json (unified eval envelope)

Usage:
  python3 scripts/generate_smolvla_v3_portfolio_figures.py [--out-dir docs/portfolio]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

MIDSTREAM = Path(__file__).resolve().parents[1]
DOWNSTREAM = Path("/home/ina/ros2_ws/src/ros2-moveit-pybullet-bridge")

OPEN_LOOP_REPORT = (
    MIDSTREAM
    / "runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/s3_open_loop_report.json"
)
S4_EVIDENCE = MIDSTREAM / "evidence/smolvla_s4_bounded5_20260724T203700Z"
POLICYRUNNER_DIR = (
    DOWNSTREAM / "evidence/downstream/smolvla_v3_ep0_policyrunner_20260724T213800Z"
)
FRAMEWORK_DIR = MIDSTREAM / "evidence/smolvla_v3_eval_framework_20260724"

DISCLAIMER = "Not task success / not Sim2Real (AGENTS 8.6)"

POSITION_RE = re.compile(r"_(P[0-4])_")


def _footer(fig, evidence: str) -> None:
    fig.text(
        0.01,
        0.01,
        f"Evidence: {evidence}\n{DISCLAIMER}",
        fontsize=8,
        color="dimgray",
        va="bottom",
    )


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return float("nan")
    idx = min(int(round(q * (len(sorted_vals) - 1))), len(sorted_vals) - 1)
    return sorted_vals[idx]


def fig_downstream_timeseries(out_dir: Path) -> Path:
    """PolicyRunner smoke: command latency timeline + distribution."""
    rows = list(csv.DictReader(open(POLICYRUNNER_DIR / "benchmark_timeseries.csv")))
    summary = json.load(open(POLICYRUNNER_DIR / "benchmark_summary.json"))
    t0 = float(rows[0]["monotonic_sec"])
    ts, lat = [], []
    for r in rows:
        if r["latency_ms"]:
            ts.append(float(r["monotonic_sec"]) - t0)
            lat.append(float(r["latency_ms"]))
    lat_sorted = sorted(lat)
    p50 = _percentile(lat_sorted, 0.50)
    p95 = _percentile(lat_sorted, 0.95)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4), width_ratios=[2, 1])
    ax1.plot(ts, lat, lw=0.6, color="#2a7f7f", alpha=0.85)
    ax1.set_yscale("log")
    ax1.set_xlabel("time since episode start (s)")
    ax1.set_ylabel("command latency (ms, log)")
    ax1.set_title(
        f"PolicyRunner 1-ep smoke command latency\n"
        f"{len(lat)} samples · mean {summary['mean_latency_ms']:.1f} ms · "
        f"max {summary['max_latency_ms']:.0f} ms"
    )
    ax1.axhline(p50, color="#c08a2d", ls="--", lw=1, label=f"p50 = {p50:.1f} ms")
    ax1.axhline(p95, color="#b0413e", ls="--", lw=1, label=f"p95 = {p95:.1f} ms")
    ax1.legend(fontsize=8)

    ax2.hist(lat, bins=60, color="#4878a8", alpha=0.85)
    ax2.set_xscale("log")
    ax2.set_xlabel("command latency (ms, log)")
    ax2.set_ylabel("count")
    ax2.set_title(
        f"distribution · strategy={summary['strategy']}\n"
        f"mode={summary['panda_command_mode']} · is_closed_loop=false"
    )

    fig.suptitle(
        "SmolVLA v3 ep0 handoff → downstream PolicyRunner (PyBullet) — interface smoke only",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    _footer(fig, "ros2-moveit-pybullet-bridge/evidence/downstream/smolvla_v3_ep0_policyrunner_20260724T213800Z/")
    out = out_dir / "smolvla_v3_downstream_policyrunner_timeseries.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def fig_openloop_paired(out_dir: Path) -> Path:
    """Prospective open-loop gate_v3: base vs LoRA paired metrics + latency."""
    d = json.load(open(OPEN_LOOP_REPORT))
    base_m, lora_m = d["base"]["metrics"], d["lora"]["metrics"]
    panels = [
        ("EE position RMSE (m)", "ee_position_rmse_m", "{:.4f}"),
        ("gripper accuracy", "gripper_accuracy", "{:.4f}"),
        ("action smoothness jerk", "action_smoothness_jerk", "{:.4f}"),
        ("action saturation ratio", "action_saturation_ratio", "{:.4f}"),
    ]
    fig, axes = plt.subplots(1, 5, figsize=(14, 4.2))
    colors = ["#9aa5ad", "#2a9d8f"]
    for ax, (title, key, fmt) in zip(axes[:4], panels):
        vals = [base_m[key], lora_m[key]]
        bars = ax.bar(["base\n(no LoRA)", "Recovery v3\nLoRA"], vals, color=colors)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v, fmt.format(v),
                    ha="center", va="bottom", fontsize=9)
        ax.set_title(title, fontsize=10)
        ax.margins(y=0.18)

    ax = axes[4]
    labels = ["p50", "p95", "max"]
    base_lat = [d["base"][f"latency_ms_{k}"] for k in ("p50", "p95", "max")]
    lora_lat = [d["lora"][f"latency_ms_{k}"] for k in ("p50", "p95", "max")]
    x = range(len(labels))
    w = 0.38
    ax.bar([i - w / 2 for i in x], base_lat, w, color=colors[0], label="base")
    ax.bar([i + w / 2 for i in x], lora_lat, w, color=colors[1], label="LoRA")
    ax.set_xticks(list(x), labels)
    ax.set_ylabel("open-loop inference latency (ms)")
    ax.set_title(f"latency ({d.get('gpu_name', 'GPU')})", fontsize=10)
    ax.legend(fontsize=8)

    fig.suptitle(
        "Prospective open-loop (eval_gate_v3, 10 ep / seeds 70–74): base vs Recovery v3 LoRA — paired offline metrics",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    _footer(fig, "runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/s3_open_loop_report.json")
    out = out_dir / "smolvla_v3_openloop_base_vs_lora_paired.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def fig_openloop_per_position(out_dir: Path) -> Path:
    """Prospective open-loop gate_v3: per-position (P0–P4) LoRA breakdown."""
    d = json.load(open(OPEN_LOOP_REPORT))
    per: dict[str, list[dict]] = {}
    for ep in d["per_episode_raw_results"]["lora"]:
        m = POSITION_RE.search(ep["episode_ref"])
        pos = m.group(1) if m else "?"
        per.setdefault(pos, []).append(ep["metrics"])
    positions = sorted(per)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4))
    w = 0.38
    for i, pos in enumerate(positions):
        for j, m in enumerate(per[pos]):
            ax1.bar(i + (j - 0.5) * w, m["ee_position_rmse_m"], w * 0.92,
                    color="#2a9d8f" if j == 0 else "#57b8ac",
                    label=("eval ep0" if i == 0 and j == 0 else
                           "eval ep1" if i == 0 and j == 1 else None))
            ax2.bar(i + (j - 0.5) * w, m["gripper_accuracy"], w * 0.92,
                    color="#4878a8" if j == 0 else "#7ba3cc")
    overall = d["lora"]["metrics"]["ee_position_rmse_m"]
    ax1.axhline(overall, color="#b0413e", ls="--", lw=1,
                label=f"overall RMSE = {overall:.4f} m")
    ax1.set_xticks(range(len(positions)), positions)
    ax1.set_ylabel("EE position RMSE (m)")
    ax1.set_title("per-position EE RMSE (LoRA, 2 eval episodes each)")
    ax1.legend(fontsize=8)

    ax2.set_xticks(range(len(positions)), positions)
    ax2.set_ylim(0.9, 1.005)
    ax2.set_ylabel("gripper accuracy")
    ax2.set_title("per-position gripper accuracy (LoRA)")

    fig.suptitle(
        "Prospective open-loop (eval_gate_v3): held-out seeds 70–74 by randomized position P0–P4",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0.07, 1, 0.94))
    _footer(fig, "runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/s3_open_loop_report.json")
    out = out_dir / "smolvla_v3_openloop_per_position.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def fig_s4_per_seed(out_dir: Path) -> Path:
    """Bounded Isaac S4: per-seed subgoal matrix + runtime aggressiveness/latency."""
    episodes = [json.loads(l) for l in open(S4_EVIDENCE / "episode_results.jsonl")]
    episodes.sort(key=lambda e: e["identity"]["seed"])
    seeds = [e["identity"]["seed"] for e in episodes]
    subgoal_names = ["reach", "grasp", "lift", "transport", "place", "release"]

    trials = {}
    for p in sorted((S4_EVIDENCE / "trials").glob("seed_*/report.json")):
        trials[int(p.parent.name.split("_")[1])] = json.load(open(p))

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13, 4.2), width_ratios=[1.3, 1, 1])

    grid = [[1 if e["subgoals"].get(s) else 0 for s in subgoal_names] for e in episodes]
    ax1.imshow(grid, cmap="Greens", vmin=0, vmax=1.6, aspect="auto")
    ax1.set_xticks(range(len(subgoal_names)), subgoal_names, rotation=30, ha="right")
    ax1.set_yticks(range(len(seeds)), [f"seed {s}" for s in seeds])
    for yi, row in enumerate(grid):
        for xi, v in enumerate(row):
            ax1.text(xi, yi, "✓" if v else "–", ha="center", va="center",
                     color="darkgreen" if v else "gray", fontsize=11)
    ax1.set_title("continuous-GT subgoals per seed\n(reach 3/5 · grasp 1/5 · lift 0/5)", fontsize=10)

    ee = [trials[s]["max_observed_ee_excursion_m"] for s in seeds]
    ax2.bar([f"s{s}" for s in seeds], ee, color="#4878a8")
    ax2.set_ylabel("max EE excursion (m)")
    ax2.set_title("per-seed max observed EE excursion\n(150/150 actions each, all clamped safe)", fontsize=10)

    lat = [trials[s]["inference_latency_ms_p50"] for s in seeds]
    ax3.bar([f"s{s}" for s in seeds], lat, color="#2a9d8f")
    ax3.set_ylabel("inference latency p50 (ms)")
    ax3.set_title("per-seed policy latency p50\n(interface 5/5 PASS)", fontsize=10)

    fig.suptitle(
        "SmolVLA S4 bounded Isaac (seeds 1–5, ran_isaac=true): per-seed detail — gate result Hold (lift 0/5)",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0.08, 1, 0.94))
    _footer(fig, "evidence/smolvla_s4_bounded5_20260724T203700Z/{episode_results.jsonl, trials/seed_*/report.json}")
    out = out_dir / "smolvla_s4_bounded5_per_seed.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def fig_framework_summary(out_dir: Path) -> Path:
    """Unified eval envelope: one-figure cross-backend summary."""
    backends = [
        ("smolvla_open_loop", "Open-loop (gate_v3)\nRTX 4090D, 10 ep held-out"),
        ("downstream_policy_runner", "Downstream PolicyRunner\nPyBullet 1-ep smoke"),
        ("isaac_s4_bounded", "Isaac S4 bounded\nseeds 1–5 online"),
    ]
    reports = {}
    for bid, _ in backends:
        for f in FRAMEWORK_DIR.glob("*unified_eval_report.json"):
            r = json.load(open(f))
            if r["backend_id"] == bid:
                reports[bid] = r

    gate_style = {
        "pass": ("#2a9d8f", "PASS"),
        "smoke_complete": ("#7a7f85", "SMOKE COMPLETE"),
        "bounded_s4_hold_or_incomplete": ("#c0632d", "HOLD"),
    }

    def _key_lines(bid: str, r: dict) -> list[str]:
        c = r["columns"]
        if bid == "smolvla_open_loop":
            i, b = c["interface"]["metrics"], c["behavior"]["metrics"]
            return [
                f"latency p50 {i['latency_ms_p50']:.0f} ms / p95 {i['latency_ms_p95']:.0f} ms",
                f"close offset {b['lora_close_offset_frames_signed']:.1f} frames",
                f"raw OOB beyond-ε (both edges) {b['lora_raw_gripper_oob_beyond_epsilon_ratio']:.2%}",
                "task column: not evaluated",
            ]
        if bid == "downstream_policy_runner":
            i = c["interface"]["metrics"]
            return [
                f"{i['completed_episodes']}/{i['episodes']} ep · {i['timeseries_rows']} timeseries rows",
                f"latency mean {i['mean_latency_ms']:.0f} ms / max {i['max_latency_ms']:.0f} ms",
                f"health alarm <1s: {i['health_alarm_detected_within_1s']}",
                "is_closed_loop=false · task not evaluated",
            ]
        i, t = c["interface"]["metrics"], c["task"]["metrics"]
        return [
            f"interface {i['policy_interface_pass']}/{i['seeds_planned']} · ran_isaac={i['ran_isaac']}",
            f"reach {t['reach']}/5 · grasp {t['grasp']}/5 · lift {t['lift']}/5",
            f"outcome_success {t['outcome_success']}/5 (threshold {t['pass_threshold']})",
            "failure_lane=task_gt",
        ]

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6))
    for ax, (bid, title) in zip(axes, backends):
        r = reports[bid]
        color, label = gate_style.get(r["gate_decision"], ("#7a7f85", r["gate_decision"]))
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.add_patch(plt.Rectangle((0.02, 0.80), 0.96, 0.17, color=color, alpha=0.9))
        ax.text(0.5, 0.885, label, ha="center", va="center", color="white",
                fontsize=13, fontweight="bold")
        ax.text(0.5, 0.70, title, ha="center", va="center", fontsize=10)
        for k, line in enumerate(_key_lines(bid, r)):
            ax.text(0.05, 0.55 - 0.11 * k, line, fontsize=9, va="center")
        ax.text(0.05, 0.06, "claims_task_success=false", fontsize=8, color="#b0413e")
        ax.add_patch(plt.Rectangle((0.02, 0.02), 0.96, 0.96, fill=False,
                                   edgecolor="lightgray"))

    fig.suptitle(
        "SmolVLA Recovery v3 — unified_eval_report_v0 envelope: three backends, one contract "
        "(interface / behavior / task / offline columns)",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0.07, 1, 0.93))
    _footer(fig, "evidence/smolvla_v3_eval_framework_20260724/*.json (bundle: smolvla_v3_eval_framework_bundle.json)")
    out = out_dir / "smolvla_v3_eval_framework_summary.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def fig_ee_vs_s2(out_dir: Path) -> Path:
    """Regenerable version of the EE RMSE vs S2 baseline bar chart."""
    import yaml

    d = json.load(open(OPEN_LOOP_REPORT))
    gate = yaml.safe_load(open(MIDSTREAM / "configs/smolvla_s3/eval_gate_v3.yaml"))
    s2 = gate["baselines"]["s2_ee_rmse_m"]
    v3 = d["lora"]["metrics"]["ee_position_rmse_m"]
    rel = d["gate_decision_detail"]["relative_ee_improvement_vs_s2"]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(
        ["S2 baseline\n(open-loop)", "Recovery v3 LoRA\n(prospective gate_v3)"],
        [s2, v3],
        color=["#9aa5ad", "#2a9d8f"],
        width=0.55,
    )
    for b, v in zip(bars, (s2, v3)):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.3f} m",
                ha="center", va="bottom", fontsize=12)
    ax.text(0.5, 0.92, f"relative improvement ≈ {rel:.1%} vs S2",
            transform=ax.transAxes, ha="center", color="#2a6f7f", fontsize=11)
    ax.set_ylabel("EE RMSE (m)")
    ax.set_title("Prospective open-loop EE RMSE\nPass under eval_gate_v3 (≠ task success)")
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    _footer(fig, "runs/.../openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/ + configs/smolvla_s3/eval_gate_v3.yaml baselines")
    out = out_dir / "smolvla_recovery_v3_openloop_ee_vs_s2.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def fig_s4_funnel(out_dir: Path) -> Path:
    """Regenerable version of the bounded S4 funnel chart."""
    g = json.load(open(S4_EVIDENCE / "s4_gate.json"))
    stages = ["interface", "reach", "grasp", "lift", "outcome"]
    counts = [g["policy_interface_pass"], g["reach"], g["grasp"], g["lift"],
              g["outcome_success"]]
    n = g["seeds_planned"]

    fig, ax = plt.subplots(figsize=(10, 5.4))
    colors = ["#2a9d8f", "#4878a8", "#e0b34d", "#9aa5ad", "#9aa5ad"]
    bars = ax.bar(stages, counts, color=colors, width=0.6)
    for b, c in zip(bars, counts):
        ax.text(b.get_x() + b.get_width() / 2, c + 0.08, f"{c}/{n}",
                ha="center", va="bottom", fontsize=12)
    ax.axhline(g["pass_threshold"], color="gray", ls="--", lw=1,
               label=f"pass_threshold={g['pass_threshold']} lift")
    ax.set_ylim(0, n + 0.6)
    ax.set_ylabel(f"count / {n} seeds")
    ax.set_title(
        f"SmolVLA S4 bounded Isaac (seeds 1–{n}): "
        f"{'Pass' if g['gate_pass'] else 'Hold'}\n"
        f"interface {counts[0]}/{n} · reach {counts[1]}/{n} · "
        f"grasp {counts[2]}/{n} · lift {counts[3]}/{n}"
    )
    ax.legend()
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    _footer(fig, "evidence/smolvla_s4_bounded5_20260724T203700Z/s4_gate.json")
    out = out_dir / "smolvla_s4_bounded5_funnel.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=MIDSTREAM / "docs/portfolio")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for fn in (
        fig_ee_vs_s2,
        fig_openloop_paired,
        fig_openloop_per_position,
        fig_s4_funnel,
        fig_s4_per_seed,
        fig_downstream_timeseries,
        fig_framework_summary,
    ):
        out = fn(args.out_dir)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
