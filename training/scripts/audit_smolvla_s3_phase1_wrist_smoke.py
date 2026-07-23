#!/usr/bin/env python3
"""Phase-1 wrist smoke audit: visibility, sync, blur proxies (no train/release).

Audits accepted LeRobot v2.1 trees with scene+wrist RGB. GPU latency profiler
remains optional and is reported as not-run unless --live-gpu-profiler is set.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]


def _load_episode_meta(source: Path) -> dict[str, Any]:
    info = json.loads((source / "meta" / "info.json").read_text(encoding="utf-8"))
    return info


def _first_close_index(grips: np.ndarray, threshold: float = 0.5) -> int | None:
    for index, value in enumerate(grips.tolist()):
        if float(value) <= threshold:
            return index
    return None


def _laplacian_var(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _nonzero_ratio(frame_bgr: np.ndarray) -> float:
    if frame_bgr.size == 0:
        return 0.0
    return float(np.count_nonzero(frame_bgr) / frame_bgr.size)


def _red_target_ratio(frame_bgr: np.ndarray) -> float:
    """Return the fraction of pixels consistent with the red-box material."""
    if frame_bgr.size == 0:
        return 0.0
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    mask = (
        ((hue <= 10) | (hue >= 170))
        & (saturation >= 80)
        & (value >= 40)
    )
    return float(np.mean(mask))


def _sample_indices(n: int, max_samples: int = 24) -> list[int]:
    if n <= 0:
        return []
    if n <= max_samples:
        return list(range(n))
    return sorted({int(round(i)) for i in np.linspace(0, n - 1, max_samples)})


def audit_episode(source: Path, episode_index: int) -> dict[str, Any]:
    parquet = source / "data" / "chunk-000" / f"episode_{episode_index:06d}.parquet"
    scene_video = (
        source
        / "videos"
        / "chunk-000"
        / "observation.images.scene"
        / f"episode_{episode_index:06d}.mp4"
    )
    wrist_video = (
        source
        / "videos"
        / "chunk-000"
        / "observation.images.wrist"
        / f"episode_{episode_index:06d}.mp4"
    )
    table = pq.read_table(parquet)
    n = table.num_rows
    ee = np.asarray(
        [table.column("observation.ee_pose")[i].as_py() for i in range(n)],
        dtype=np.float64,
    )
    obj = np.asarray(
        [table.column("observation.object_pose")[i].as_py() for i in range(n)],
        dtype=np.float64,
    )
    grip = np.asarray(
        [
            float(np.asarray(table.column("action")[i].as_py(), dtype=np.float64)[7])
            for i in range(n)
        ],
        dtype=np.float64,
    )
    ts = np.asarray(
        [float(table.column("timestamp")[i].as_py()) for i in range(n)],
        dtype=np.float64,
    )
    joints = np.asarray(
        [table.column("observation.state")[i].as_py() for i in range(n)],
        dtype=np.float64,
    )
    measured_grip = np.asarray(
        [
            float(
                np.asarray(
                    table.column("observation.gripper")[i].as_py(), dtype=np.float64
                ).reshape(-1)[0]
            )
            for i in range(n)
        ],
        dtype=np.float64,
    )

    xy_err = np.linalg.norm(ee[:, :2] - obj[:, :2], axis=1)
    z_gap = ee[:, 2] - obj[:, 2]
    close_i = _first_close_index(grip)
    last3cm = [
        i
        for i in range(n)
        if xy_err[i] <= 0.03 and 0.0 <= z_gap[i] <= 0.05
    ]
    if not last3cm and close_i is not None:
        last3cm = list(range(max(0, close_i - 15), close_i + 1))

    failures: list[str] = []
    if not scene_video.is_file():
        failures.append("missing_scene_video")
    if not wrist_video.is_file():
        failures.append("missing_wrist_video")
    if joints.shape[1] != 7:
        failures.append(f"joint_state_dim={joints.shape[1]}")
    if ee.shape[1] != 7:
        failures.append(f"ee_pose_dim={ee.shape[1]}")

    scene_cap = cv2.VideoCapture(str(scene_video)) if scene_video.is_file() else None
    wrist_cap = cv2.VideoCapture(str(wrist_video)) if wrist_video.is_file() else None
    scene_frames = int(scene_cap.get(cv2.CAP_PROP_FRAME_COUNT)) if scene_cap else -1
    wrist_frames = int(wrist_cap.get(cv2.CAP_PROP_FRAME_COUNT)) if wrist_cap else -1
    if scene_frames != n:
        failures.append(f"scene_frame_mismatch video={scene_frames} parquet={n}")
    if wrist_frames != n:
        failures.append(f"wrist_frame_mismatch video={wrist_frames} parquet={n}")

    sample_idxs = _sample_indices(n)
    approach_idxs = [i for i in sample_idxs if i in set(last3cm)] or sample_idxs[-8:]
    wrist_nonzero: list[float] = []
    scene_nonzero: list[float] = []
    wrist_blur: list[float] = []
    scene_blur: list[float] = []
    wrist_target_red: list[float] = []
    wrist_out_of_view = 0

    def _read(cap, index: int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        return frame if ok else None

    for index in approach_idxs:
        if scene_cap is not None:
            scene = _read(scene_cap, index)
            if scene is not None:
                scene_nonzero.append(_nonzero_ratio(scene))
                scene_blur.append(_laplacian_var(cv2.cvtColor(scene, cv2.COLOR_BGR2GRAY)))
        if wrist_cap is not None:
            wrist = _read(wrist_cap, index)
            if wrist is not None:
                ratio = _nonzero_ratio(wrist)
                wrist_nonzero.append(ratio)
                wrist_target_red.append(_red_target_ratio(wrist))
                gray = cv2.cvtColor(wrist, cv2.COLOR_BGR2GRAY)
                wrist_blur.append(_laplacian_var(gray))
                # crude out-of-view / crushed exposure proxy
                if ratio < 0.02 or float(gray.mean()) < 8.0:
                    wrist_out_of_view += 1

    if scene_cap is not None:
        scene_cap.release()
    if wrist_cap is not None:
        wrist_cap.release()

    dt = np.diff(ts)
    sync = {
        "timestamp_dt_mean_s": float(dt.mean()) if len(dt) else None,
        "timestamp_dt_max_s": float(dt.max()) if len(dt) else None,
        "scene_frames": scene_frames,
        "wrist_frames": wrist_frames,
        "parquet_frames": n,
        "frame_count_aligned": scene_frames == wrist_frames == n,
    }
    if not sync["frame_count_aligned"]:
        failures.append("dual_stream_frame_count_mismatch")

    # Heuristic gates for smoke (not v3 release QA).
    if last3cm and wrist_nonzero and float(np.mean(wrist_nonzero)) < 0.05:
        failures.append("wrist_near_black_in_last_3cm")
    if approach_idxs and wrist_out_of_view / max(len(approach_idxs), 1) > 0.5:
        failures.append("wrist_out_of_view_rate_high")
    target_visible_fraction = (
        float(np.mean(np.asarray(wrist_target_red) >= 5.0e-4))
        if wrist_target_red
        else 0.0
    )
    if last3cm and wrist_target_red and target_visible_fraction < 0.75:
        failures.append(
            "wrist_red_target_not_consistently_visible_in_last_3cm"
        )

    state15_ok = joints.shape[1] == 7 and ee.shape[1] == 7 and measured_grip.ndim == 1
    return {
        "episode_ref": f"{source.name}/episode_{episode_index:06d}",
        "num_frames": n,
        "object_xy0": obj[0, :2].tolist(),
        "first_close_frame": close_i,
        "last_3cm_frame_count": len(last3cm),
        "state15_components_present": state15_ok,
        "sync": sync,
        "wrist_nonzero_mean_last3cm": float(np.mean(wrist_nonzero)) if wrist_nonzero else None,
        "scene_nonzero_mean_last3cm": float(np.mean(scene_nonzero)) if scene_nonzero else None,
        "wrist_laplacian_var_mean": float(np.mean(wrist_blur)) if wrist_blur else None,
        "scene_laplacian_var_mean": float(np.mean(scene_blur)) if scene_blur else None,
        "wrist_red_target_ratio_mean_last3cm": (
            float(np.mean(wrist_target_red)) if wrist_target_red else None
        ),
        "wrist_red_target_visible_fraction_last3cm": target_visible_fraction,
        "wrist_out_of_view_samples": wrist_out_of_view,
        "failures": failures,
        "passed": not failures,
    }


def audit_sources(
    sources: list[Path], *, expected_episodes: int = 4
) -> dict[str, Any]:
    episodes: list[dict[str, Any]] = []
    for source in sources:
        info = _load_episode_meta(source)
        for index in range(int(info["total_episodes"])):
            episodes.append(audit_episode(source, index))
    positions = sorted(
        {
            (round(ep["object_xy0"][0], 3), round(ep["object_xy0"][1], 3))
            for ep in episodes
        }
    )
    return {
        "mode": "phase1_wrist_smoke_audit",
        "builds_release": False,
        "triggers_train": False,
        "sources": [str(path) for path in sources],
        "num_episodes": len(episodes),
        "expected_episodes": expected_episodes,
        "distinct_object_xy_rounded_mm": positions,
        "episodes": episodes,
        "gpu_latency_profiler": {
            "passed": False,
            "ran": False,
            "notes": "CPU audit only; run GPU profiler separately after human GPU approval.",
        },
        "passed": (
            all(ep["passed"] for ep in episodes)
            and len(episodes) == expected_episodes
        ),
        "gate": "phase1_wrist_smoke_pass"
        if all(ep["passed"] for ep in episodes)
        and len(episodes) == expected_episodes
        else "phase1_wrist_smoke_hold",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--expected-episodes", type=int, default=4)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.expected_episodes < 1:
        parser.error("--expected-episodes must be >= 1")
    report = audit_sources(
        [path.resolve() for path in args.source],
        expected_episodes=args.expected_episodes,
    )
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
