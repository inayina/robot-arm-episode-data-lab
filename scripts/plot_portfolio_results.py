#!/usr/bin/env python3
"""Generate high-quality portfolio plots from EDA and MLP training results."""

import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[1]
EDA_JSON = REPO_ROOT / "training/reports/panda_30_low_dim_eda.json"
METRICS_JSON = REPO_ROOT / "training/reports/panda_mlp_bc/mlp_metrics.json"
LINEAR_SAME_SPLIT_JSON = REPO_ROOT / "docs/portfolio/linear_same_split_metrics.json"
OUTPUT_DIR = REPO_ROOT / "assets/diagrams"


def set_style():
    """Set clean, modern plotting style."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 14,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "figure.titlesize": 16,
        "grid.color": "#e2e8f0",
        "grid.linewidth": 0.8,
        "axes.edgecolor": "#94a3b8",
        "axes.linewidth": 1.0,
    })


def plot_joint_reversals(eda_data):
    """Plot boxplot of joint reversal rates for 7 axes across 30 episodes."""
    episodes = eda_data.get("episodes", [])
    if not episodes:
        print("No episode data found for reversal plot.")
        return

    # Collect reversal rates by axis: shape (30, 7)
    reversal_rates = []
    for ep in episodes:
        reversal_rates.append(ep["joint_reversal_rate_by_axis"])
    reversal_rates = np.asarray(reversal_rates)  # (N, 7)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.grid(True, linestyle="--", alpha=0.7, zorder=0)

    # Boxplot of the 7 joint axes
    bp = ax.boxplot(
        reversal_rates,
        patch_artist=True,
        zorder=3,
        widths=0.6,
        medianprops=dict(color="#b91c1c", linewidth=1.5),
        boxprops=dict(facecolor="#3b82f6", color="#1d4ed8", alpha=0.8),
        whiskerprops=dict(color="#1d4ed8"),
        capprops=dict(color="#1d4ed8"),
    )

    # Add 10% Quality Gate threshold line
    ax.axhline(y=0.10, color="#ef4444", linestyle="--", linewidth=1.5,
               label="Quality Gate Limit (10%)", zorder=4)

    ax.set_title("Franka Panda Joint Reversal Rate Distribution (30 Episodes)", pad=15)
    ax.set_xlabel("Joint Axis (1-7)")
    ax.set_ylabel("Reversal Rate (Direction Changes / Frame)")
    ax.set_xticklabels([f"Joint {i+1}" for i in range(7)])
    ax.set_ylim(-0.01, 0.15)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cbd5e1")

    plt.tight_layout()
    out_path = OUTPUT_DIR / "eda_joint_reversals_distribution.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_joint_steps(eda_data):
    """Plot p99 joint step sizes for each episode against the 0.02 rad threshold."""
    episodes = eda_data.get("episodes", [])
    if not episodes:
        return

    ep_indices = [ep["episode_index"] for ep in episodes]
    p99_steps = [ep["joint_abs_step_rad"]["p99"] for ep in episodes]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.grid(True, linestyle="--", alpha=0.7, zorder=0)

    # Draw bar chart for the 30 episodes
    bars = ax.bar(ep_indices, p99_steps, color="#10b981", edgecolor="#047857", alpha=0.85, zorder=3, width=0.6)

    # Add 0.02 rad Quality Gate threshold line
    ax.axhline(y=0.02, color="#ef4444", linestyle="--", linewidth=1.5,
               label="Quality Gate Jerkiness Limit (0.02 rad)", zorder=4)

    ax.set_title("99th Percentile Joint Step Size per Episode (Quality Gate Validation)", pad=15)
    ax.set_xlabel("Episode Index")
    ax.set_ylabel("Joint Step P99 (radians)")
    ax.set_xticks(ep_indices)
    ax.set_xticklabels([str(idx) for idx in ep_indices], rotation=45)
    ax.set_ylim(0, 0.025)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cbd5e1", loc="upper right")

    plt.tight_layout()
    out_path = OUTPUT_DIR / "eda_joint_step_p99_gate.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_loss_comparison(metrics_data, linear_metrics):
    """Plot Linear Regression vs MLP BC Train & Test Loss comparison."""
    mlp_train = metrics_data.get("train_loss", 0.0491)
    mlp_test = metrics_data.get("test_loss", 0.2350)

    linear_train = linear_metrics["train_normalized_mse"]
    linear_test = linear_metrics["test_normalized_mse"]

    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.grid(True, linestyle="--", alpha=0.7, zorder=0)

    # Data setup
    models = ["Linear Regression\n(Baseline)", "MLP Policy\n(Non-linear BC)"]
    train_losses = [linear_train, mlp_train]
    test_losses = [linear_test, mlp_test]

    x = np.arange(len(models))
    width = 0.3  # width of the bars

    # Plot grouped bars
    rects1 = ax.bar(x - width/2, train_losses, width, label='Train MSE Loss (24 Eps)', color='#3b82f6', edgecolor='#1d4ed8', alpha=0.9, zorder=3)
    rects2 = ax.bar(x + width/2, test_losses, width, label='Test MSE Loss (6 Eps)', color='#f59e0b', edgecolor='#d97706', alpha=0.9, zorder=3)

    # Add values on top of bars
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f"{height:.4f}",
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom', fontweight='bold', fontsize=10)

    autolabel(rects1)
    autolabel(rects2)

    ax.set_title("Model Comparison: Linear Regression vs. MLP Policy", pad=15)
    ax.set_ylabel("Normalized Mean Squared Error (MSE)")
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_ylim(0, max(max(train_losses), max(test_losses)) * 1.18)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cbd5e1", loc="upper right")

    plt.tight_layout()
    out_path = OUTPUT_DIR / "mlp_bc_loss_comparison.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


def main():
    set_style()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if EDA_JSON.exists():
        print(f"Loading EDA JSON: {EDA_JSON}")
        with open(EDA_JSON, "r", encoding="utf-8") as f:
            eda_data = json.load(f)
        plot_joint_reversals(eda_data)
        plot_joint_steps(eda_data)
    else:
        print(f"EDA JSON not found: {EDA_JSON}")

    if METRICS_JSON.exists() and LINEAR_SAME_SPLIT_JSON.exists():
        print(f"Loading Metrics JSON: {METRICS_JSON}")
        with open(METRICS_JSON, "r", encoding="utf-8") as f:
            metrics_data = json.load(f)
        print(f"Loading Linear Same-Split JSON: {LINEAR_SAME_SPLIT_JSON}")
        with open(LINEAR_SAME_SPLIT_JSON, "r", encoding="utf-8") as f:
            linear_metrics = json.load(f)
        plot_loss_comparison(metrics_data, linear_metrics)
    else:
        print(f"Metrics JSON not found: {METRICS_JSON} or {LINEAR_SAME_SPLIT_JSON}")


if __name__ == "__main__":
    main()
