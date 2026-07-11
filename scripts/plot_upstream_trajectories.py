#!/usr/bin/env python3
"""Generate a 3D spatial plot of the end-effector trajectories across all 30 episodes."""

import json
from pathlib import Path
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # Register 3D projection

REPO_ROOT = Path("/home/ina/robot-sim-lab/robot-arm-episode-data-lab")
DATASET_RELEASE = REPO_ROOT / "data/exports/panda_30_release"
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


def main():
    jsonl_path = DATASET_RELEASE / "frames.jsonl"
    if not jsonl_path.exists():
        print(f"Error: Dataset release not found at {jsonl_path}")
        return 1

    set_style()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading dataset frames...")
    episodes_data = {}
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            ep_idx = int(row["episode_index"])
            ee_pose = row.get("observation.ee_pose")
            
            if ee_pose:
                if ep_idx not in episodes_data:
                    episodes_data[ep_idx] = []
                episodes_data[ep_idx].append(ee_pose[:3])  # Save (x, y, z)

    print(f"Loaded {len(episodes_data)} episodes. Generating 3D plot...")
    
    fig = plt.figure(figsize=(9, 7))
    ax = fig.add_subplot(111, projection="3d")
    
    # Enable grid
    ax.grid(True, linestyle="--", alpha=0.5)

    # Plot each episode's trajectory
    for ep_idx, path in episodes_data.items():
        path = np.asarray(path)
        # Use a colormap or standard color to make it look clean
        ax.plot(path[:, 0], path[:, 1], path[:, 2], alpha=0.6, linewidth=1.2, color="#0f766e" if ep_idx == 0 else "#0d9488")

    # Highlight episode 0 to show a single path clearly
    ep0_path = np.asarray(episodes_data[0])
    ax.plot(ep0_path[:, 0], ep0_path[:, 1], ep0_path[:, 2], color="#0f766e", linewidth=2.5, label="Example Trajectory (Ep 0)")
    
    # Highlight start and end positions
    ax.scatter(ep0_path[0, 0], ep0_path[0, 1], ep0_path[0, 2], color="#ef4444", s=50, zorder=5, label="Hover Start")
    ax.scatter(ep0_path[-1, 0], ep0_path[-1, 1], ep0_path[-1, 2], color="#22c55e", s=50, zorder=5, label="Release End")

    ax.set_title("Franka Panda 3D Teleoperation Trajectories (30 Episodes)", pad=15)
    ax.set_xlabel("X Coordinate (meters)")
    ax.set_ylabel("Y Coordinate (meters)")
    ax.set_zlabel("Z Coordinate (meters)")
    
    # Set view angle for good perspective
    ax.view_init(elev=25, azim=-45)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cbd5e1", loc="upper left")

    plt.tight_layout()
    out_path = OUTPUT_DIR / "panda_teleop_trajectories_3d.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    
    print(f"Saved: {out_path}")
    return 0


import numpy as np
if __name__ == "__main__":
    exit(main())
