#!/usr/bin/env python3
"""Build a multimodal episode collage from a real recorded episode.

Does not invent waveforms. If an image modality is missing from the episode,
the panel is labeled unavailable or sourced from a separately proven still
with its own provenance — never a synthetic curve.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

MIDSTREAM = Path(__file__).resolve().parents[1]
UPSTREAM = Path("/home/ina/dev/ros2-arm-teleoperation-suite")
DEFAULT_OUT = MIDSTREAM / "docs/portfolio/assets"
M6_TACTILE_L = UPSTREAM / "media/m6/tactile_left_view.png"
M6_TACTILE_R = UPSTREAM / "media/m6/tactile_right_view.png"
CAPTION = "visualization regenerated from recorded evidence"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_episode(root: Path) -> dict[str, Path]:
    parquet = list(root.rglob("episode_*.parquet"))
    if not parquet:
        parquet = list(root.rglob("*.parquet"))
    if not parquet:
        raise FileNotFoundError(f"no parquet under {root}")
    pq = parquet[0]
    meta_candidates = list(root.rglob("meta.json"))
    meta = next((p for p in meta_candidates if "episode_" in str(p)), meta_candidates[0] if meta_candidates else None)
    videos = {
        "scene": next(iter((root.rglob("observation.images.scene/episode_*.mp4"))), None),
        "wrist": next(iter((root.rglob("observation.images.wrist/episode_*.mp4"))), None),
    }
    return {"parquet": pq, "meta": meta, "scene_mp4": videos["scene"], "wrist_mp4": videos["wrist"]}


def _extract_frame(mp4: Path, dest: Path, t_frac: float = 0.45) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(mp4),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    duration = float(probe.stdout.strip() or "1")
    t = max(0.0, min(duration * t_frac, max(0.0, duration - 0.05)))
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{t:.3f}",
            "-i",
            str(mp4),
            "-frames:v",
            "1",
            str(dest),
        ],
        check=True,
        capture_output=True,
    )
    return dest


def _series(table, name: str, index: int | None = None) -> np.ndarray:
    col = table[name]
    vals = col.to_pylist()
    if index is None:
        return np.asarray([float(v[0]) if isinstance(v, (list, tuple)) else float(v) for v in vals], dtype=float)
    return np.asarray([float(v[index]) for v in vals], dtype=float)


def render(episode_root: Path, out_dir: Path) -> dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt
    import pyarrow.parquet as pq

    found = _find_episode(episode_root)
    table = pq.read_table(found["parquet"])
    names = set(table.column_names)
    n = table.num_rows
    if n < 5:
        raise RuntimeError(f"episode too short for waveforms: {n} frames")

    ts = np.asarray(table["timestamp"].to_pylist(), dtype=float)
    t = ts - ts[0]
    state0 = _series(table, "observation.state", 0) if "observation.state" in names else None
    ee_z = _series(table, "observation.ee_pose", 2) if "observation.ee_pose" in names else None
    grip = _series(table, "observation.gripper", 0) if "observation.gripper" in names else None
    action_g = _series(table, "action", 7) if "action" in names else None

    missing_curves = [
        label
        for label, arr in [
            ("joint", state0),
            ("ee_z", ee_z),
            ("gripper", grip),
            ("action_g", action_g),
        ]
        if arr is None
    ]
    if missing_curves:
        raise RuntimeError(f"refusing to invent curves; missing {missing_curves}")

    frames_dir = out_dir / "frames"
    scene_png = None
    wrist_png = None
    if found["scene_mp4"] and found["scene_mp4"].exists():
        scene_png = _extract_frame(found["scene_mp4"], frames_dir / "scene_frame.png")
    if found["wrist_mp4"] and found["wrist_mp4"].exists():
        wrist_png = _extract_frame(found["wrist_mp4"], frames_dir / "wrist_frame.png")

    meta = {}
    if found["meta"] and found["meta"].exists():
        meta = json.loads(found["meta"].read_text())

    fig = plt.figure(figsize=(14.4, 8.2), dpi=140)
    fig.patch.set_facecolor("white")
    fig.suptitle(
        "Real episode snapshot: renderer images + parquet signals",
        fontsize=16,
        fontweight="bold",
        y=0.98,
    )
    fig.text(
        0.5,
        0.935,
        f"{CAPTION} · {n} frames · MuJoCo · waveform snippet, not task success",
        ha="center",
        fontsize=10,
        color="#64748b",
    )

    gs = fig.add_gridspec(
        3,
        4,
        height_ratios=[1.15, 1.0, 1.0],
        hspace=0.38,
        wspace=0.28,
        left=0.06,
        right=0.98,
        top=0.90,
        bottom=0.10,
    )

    def _show(ax, path: Path | None, title: str, note: str) -> None:
        ax.set_title(title, fontsize=11)
        ax.set_xticks([])
        ax.set_yticks([])
        if path is None or not path.exists():
            ax.text(0.5, 0.5, "unavailable in this episode", ha="center", va="center", color="#94a3b8")
            ax.set_xlabel(note, fontsize=8, color="#64748b")
            return
        ax.imshow(mpimg.imread(path))
        ax.set_xlabel(note, fontsize=8, color="#64748b")

    _show(fig.add_subplot(gs[0, 0]), scene_png, "Scene RGB", "from episode mp4")
    _show(fig.add_subplot(gs[0, 1]), wrist_png, "Wrist RGB", "current wrist remount if this run used it")
    tactile_note = "M6 media still · not this episode's parquet"
    _show(fig.add_subplot(gs[0, 2]), M6_TACTILE_L if M6_TACTILE_L.exists() else None, "Tactile L", tactile_note)
    _show(fig.add_subplot(gs[0, 3]), M6_TACTILE_R if M6_TACTILE_R.exists() else None, "Tactile R", tactile_note)

    axj = fig.add_subplot(gs[1, :2])
    axj.plot(t, state0, color="#2563eb", lw=1.6)
    axj.set_ylabel("joint 0 (rad)")
    axj.set_title("observation.state[0]")
    axj.grid(True, alpha=0.25)

    axe = fig.add_subplot(gs[1, 2:])
    axe.plot(t, ee_z, color="#059669", lw=1.6)
    axe.set_ylabel("z (m)")
    axe.set_title("observation.ee_pose[2]")
    axe.grid(True, alpha=0.25)

    axg = fig.add_subplot(gs[2, :2])
    axg.plot(t, grip, color="#7c3aed", lw=1.6)
    axg.set_ylabel("gripper")
    axg.set_xlabel("time (s)")
    axg.set_title("observation.gripper")
    axg.grid(True, alpha=0.25)

    axa = fig.add_subplot(gs[2, 2:])
    axa.plot(t, action_g, color="#c2410c", lw=1.6)
    axa.set_ylabel("action[7]")
    axa.set_xlabel("time (s)")
    axa.set_title("action gripper cmd")
    axa.grid(True, alpha=0.25)

    fill = (meta.get("metadata") or {}).get("action_fill") or meta.get("action_fill")
    gate = meta.get("upstream_gate")
    success = meta.get("success")
    fig.text(
        0.5,
        0.02,
        (
            f"upstream_gate={gate} · recorded success flag={success} · action_fill={fill} · "
            "this capture used validation_mode=none so success is not a physical lift claim · "
            "tactile stills are M6 media if labeled"
        ),
        ha="center",
        fontsize=8,
        color="#64748b",
    )

    png = out_dir / "multimodal_episode.png"
    fig.savefig(png, facecolor="white")
    plt.close(fig)

    provenance = {
        "figure": "multimodal_episode",
        "caption_class": CAPTION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "episode_root": str(episode_root),
        "n_frames": n,
        "duration_s": float(t[-1]) if len(t) else None,
        "joint0_ptp": float(np.ptp(state0)),
        "ee_z_ptp": float(np.ptp(ee_z)),
        "meta": {
            "success": success,
            "upstream_gate": gate,
            "action_fill": fill,
            "task": meta.get("task"),
        },
        "claims_task_success": False,
        "sources": {
            "parquet": {"path": str(found["parquet"]), "sha256": _sha256(found["parquet"])},
            "meta": {"path": str(found["meta"]), "sha256": _sha256(found["meta"])} if found["meta"] else None,
            "scene_mp4": str(found["scene_mp4"]) if found["scene_mp4"] else None,
            "wrist_mp4": str(found["wrist_mp4"]) if found["wrist_mp4"] else None,
            "tactile_left": {"path": str(M6_TACTILE_L), "sha256": _sha256(M6_TACTILE_L), "note": "M6 media still"}
            if M6_TACTILE_L.exists()
            else None,
            "tactile_right": {"path": str(M6_TACTILE_R), "sha256": _sha256(M6_TACTILE_R), "note": "M6 media still"}
            if M6_TACTILE_R.exists()
            else None,
        },
    }
    (out_dir / "provenance" / "multimodal_episode.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )
    return provenance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "provenance").mkdir(exist_ok=True)
    print(json.dumps(render(args.episode_root, args.out_dir), indent=2))


if __name__ == "__main__":
    main()
