#!/usr/bin/env python3
"""Phase-1 wrist smoke audit: visibility, sync, blur, geometry (no train/release).

Fail-closed visual allowlist: scene + H_knuckle_z05 wrist only.
Tactile / depth / extra cameras are unexpected keys, not ignored.
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
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from training.smolvla_s3.visual_allowlist import (  # noqa: E402
    VARIANT_B,
    dataset_visual_keys_from_info,
    dataset_visual_keys_from_video_tree,
    merge_stage_audits,
)
from training.smolvla_s3.wrist_geometry_contract import (  # noqa: E402
    DEFAULT_UPSTREAM_XML,
    audit_wrist_geometry,
)

HOLD_ACTION = "hold_from_ee"
EXPERT_ACTION = "teleop_command"
RED_VISIBLE_MIN = 5.0e-4


def _load_episode_meta(source: Path) -> dict[str, Any]:
    return json.loads((source / "meta" / "info.json").read_text(encoding="utf-8"))


def _sidecar_meta(source: Path, episode_index: int) -> dict[str, Any] | None:
    path = source / f"episode_{episode_index:06d}" / "meta.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


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


def _brightness(gray: np.ndarray) -> float:
    if gray.size == 0:
        return 0.0
    return float(gray.mean())


def _red_mask(frame_bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    return ((hue <= 10) | (hue >= 170)) & (saturation >= 80) & (value >= 40)


def _red_target_ratio(frame_bgr: np.ndarray) -> float:
    """Return the fraction of pixels consistent with the red-box material."""
    if frame_bgr.size == 0:
        return 0.0
    return float(np.mean(_red_mask(frame_bgr)))


def _finger_gray_ratio(frame_bgr: np.ndarray) -> float:
    """Proxy: desaturated mid-bright pixels in the lower third (not semantic seg)."""
    if frame_bgr.size == 0:
        return 0.0
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    h = frame_bgr.shape[0]
    lower = hsv[int(h * 2 / 3) :, :, :]
    sat = lower[:, :, 1]
    val = lower[:, :, 2]
    red = _red_mask(frame_bgr)[int(h * 2 / 3) :, :]
    fingerish = (sat < 50) & (val >= 40) & (val <= 230) & (~red)
    return float(np.mean(fingerish))


def _sample_indices(n: int, max_samples: int = 24) -> list[int]:
    if n <= 0:
        return []
    if n <= max_samples:
        return list(range(n))
    return sorted({int(round(i)) for i in np.linspace(0, n - 1, max_samples)})


def _window_indices(
    *,
    n: int,
    xy_err: np.ndarray,
    z_gap: np.ndarray,
    xy_max: float,
    z_max: float,
) -> list[int]:
    return [
        i
        for i in range(n)
        if xy_err[i] <= xy_max and 0.0 <= z_gap[i] <= z_max
    ]


def _summarize(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.mean(values))


def _read_frame(cap, index: int):
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = cap.read()
    return frame if ok else None


def _frame_metrics(frame_bgr: np.ndarray) -> dict[str, float]:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return {
        "nonzero": _nonzero_ratio(frame_bgr),
        "brightness": _brightness(gray),
        "laplacian_var": _laplacian_var(gray),
        "red_ratio": _red_target_ratio(frame_bgr),
        "finger_gray_ratio": _finger_gray_ratio(frame_bgr),
    }


def _aggregate_stream(
    caps,
    indices: list[int],
    *,
    collect_out_of_view: bool = False,
) -> dict[str, Any]:
    scene_cap, wrist_cap = caps
    scene_red: list[float] = []
    wrist_red: list[float] = []
    wrist_nonzero: list[float] = []
    scene_nonzero: list[float] = []
    wrist_bright: list[float] = []
    scene_bright: list[float] = []
    wrist_blur: list[float] = []
    scene_blur: list[float] = []
    wrist_finger: list[float] = []
    series: list[dict[str, Any]] = []
    out_of_view = 0
    occlusion_hits = 0
    pixel_equal = 0
    compared = 0
    for index in indices:
        scene = _read_frame(scene_cap, index) if scene_cap is not None else None
        wrist = _read_frame(wrist_cap, index) if wrist_cap is not None else None
        scene_m = _frame_metrics(scene) if scene is not None else None
        wrist_m = _frame_metrics(wrist) if wrist is not None else None
        if scene_m:
            scene_red.append(scene_m["red_ratio"])
            scene_nonzero.append(scene_m["nonzero"])
            scene_bright.append(scene_m["brightness"])
            scene_blur.append(scene_m["laplacian_var"])
        if wrist_m:
            wrist_red.append(wrist_m["red_ratio"])
            wrist_nonzero.append(wrist_m["nonzero"])
            wrist_bright.append(wrist_m["brightness"])
            wrist_blur.append(wrist_m["laplacian_var"])
            wrist_finger.append(wrist_m["finger_gray_ratio"])
            if collect_out_of_view and (
                wrist_m["nonzero"] < 0.02 or wrist_m["brightness"] < 8.0
            ):
                out_of_view += 1
            occlusion = (
                wrist_m["brightness"] >= 25.0
                and wrist_m["red_ratio"] < RED_VISIBLE_MIN
                and wrist_m["finger_gray_ratio"] >= 0.15
                and (scene_m is None or scene_m["red_ratio"] >= RED_VISIBLE_MIN)
            )
            if occlusion:
                occlusion_hits += 1
        if scene is not None and wrist is not None:
            compared += 1
            if scene.shape == wrist.shape and np.array_equal(scene, wrist):
                pixel_equal += 1
        series.append(
            {
                "index": index,
                "scene_red_ratio": None if scene_m is None else scene_m["red_ratio"],
                "wrist_red_ratio": None if wrist_m is None else wrist_m["red_ratio"],
            }
        )
    visible = (
        float(np.mean(np.asarray(wrist_red) >= RED_VISIBLE_MIN)) if wrist_red else 0.0
    )
    return {
        "count": len(indices),
        "wrist_target_visible_fraction": visible,
        "wrist_target_pixel_ratio": _summarize(wrist_red),
        "scene_target_pixel_ratio": _summarize(scene_red),
        "wrist_nonzero_mean": _summarize(wrist_nonzero),
        "scene_nonzero_mean": _summarize(scene_nonzero),
        "wrist_brightness_mean": _summarize(wrist_bright),
        "scene_brightness_mean": _summarize(scene_bright),
        "wrist_laplacian_var_mean": _summarize(wrist_blur),
        "scene_laplacian_var_mean": _summarize(scene_blur),
        "wrist_finger_gray_ratio_mean": _summarize(wrist_finger),
        "occlusion_proxy_fraction": (
            float(occlusion_hits / max(len(indices), 1)) if indices else None
        ),
        "occlusion_proxy_is_semantic_segmentation": False,
        "wrist_out_of_view_samples": out_of_view,
        "identical_scene_wrist_frames": pixel_equal,
        "compared_scene_wrist_frames": compared,
        "red_ratio_series": series,
    }


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
    names = set(table.column_names)
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
    last3cm = _window_indices(n=n, xy_err=xy_err, z_gap=z_gap, xy_max=0.03, z_max=0.05)
    last5cm = _window_indices(n=n, xy_err=xy_err, z_gap=z_gap, xy_max=0.05, z_max=0.08)
    if not last3cm and close_i is not None:
        last3cm = list(range(max(0, close_i - 15), close_i + 1))
    close_window = (
        list(range(max(0, close_i - 10), min(n, close_i + 6)))
        if close_i is not None
        else []
    )
    approach = [
        i
        for i in range(n)
        if (close_i is None or i < close_i) and xy_err[i] > 0.05
    ]

    failures: list[str] = []
    if not scene_video.is_file():
        failures.append("missing_scene_video")
    if not wrist_video.is_file():
        failures.append("missing_wrist_video")
    if joints.shape[1] != 7:
        failures.append(f"joint_state_dim={joints.shape[1]}")
    if ee.shape[1] != 7:
        failures.append(f"ee_pose_dim={ee.shape[1]}")

    sidecar = _sidecar_meta(source, episode_index)
    sidecar_present = sidecar is not None
    sidecar = sidecar or {}
    action_fill = sidecar.get("action_fill")
    if "action_fill" in names:
        fills = [str(table.column("action_fill")[i].as_py()) for i in range(n)]
        if any(value == HOLD_ACTION for value in fills):
            action_fill = HOLD_ACTION
    if action_fill == HOLD_ACTION:
        failures.append("hold_from_ee_pseudo_action")
    elif sidecar_present and action_fill != EXPERT_ACTION:
        failures.append(f"action_fill={action_fill}")
    if sidecar.get("command_missing") is True:
        failures.append("command_missing_true")

    ee_travel = float(np.linalg.norm(ee[-1, :3] - ee[0, :3])) if n else 0.0
    grip_range = float(grip.max() - grip.min()) if n else 0.0
    if ee_travel < 0.04 or grip_range < 0.2:
        failures.append("not_dynamic_approach_close_lift")

    scene_cap = cv2.VideoCapture(str(scene_video)) if scene_video.is_file() else None
    wrist_cap = cv2.VideoCapture(str(wrist_video)) if wrist_video.is_file() else None
    scene_frames = int(scene_cap.get(cv2.CAP_PROP_FRAME_COUNT)) if scene_cap else -1
    wrist_frames = int(wrist_cap.get(cv2.CAP_PROP_FRAME_COUNT)) if wrist_cap else -1
    if scene_frames != n:
        failures.append(f"scene_frame_mismatch video={scene_frames} parquet={n}")
    if wrist_frames != n:
        failures.append(f"wrist_frame_mismatch video={wrist_frames} parquet={n}")

    caps = (scene_cap, wrist_cap)
    last3 = _aggregate_stream(caps, last3cm, collect_out_of_view=True)
    last5 = _aggregate_stream(caps, last5cm)
    close_m = _aggregate_stream(caps, close_window)
    approach_idxs = [
        i for i in _sample_indices(n) if i in set(approach)
    ] or approach[:8]
    approach_m = _aggregate_stream(caps, approach_idxs)

    if scene_cap is not None:
        scene_cap.release()
    if wrist_cap is not None:
        wrist_cap.release()

    dt = np.diff(ts)
    unique_ts = len(np.unique(np.round(ts, 6)))
    duplicate_ts = int(n - unique_ts)
    sync = {
        "timestamp_dt_mean_s": float(dt.mean()) if len(dt) else None,
        "timestamp_dt_max_s": float(dt.max()) if len(dt) else None,
        "timestamp_dt_min_s": float(dt.min()) if len(dt) else None,
        "duplicate_timestamps": duplicate_ts,
        "missing_frame_proxy": int(scene_frames != n or wrist_frames != n),
        "scene_frames": scene_frames,
        "wrist_frames": wrist_frames,
        "parquet_frames": n,
        "frame_count_aligned": scene_frames == wrist_frames == n,
    }
    if not sync["frame_count_aligned"]:
        failures.append("dual_stream_frame_count_mismatch")
    if duplicate_ts > 0:
        failures.append("duplicate_timestamps")
    if len(dt) and float(dt.max()) > 0.5:
        failures.append("timestamp_gap_gt_0_5s")

    if last3cm and last3["wrist_nonzero_mean"] is not None and last3["wrist_nonzero_mean"] < 0.05:
        failures.append("wrist_near_black_in_last_3cm")
    if last3cm and last3["wrist_out_of_view_samples"] / max(len(last3cm), 1) > 0.5:
        failures.append("wrist_out_of_view_rate_high")
    target_visible_fraction = last3["wrist_target_visible_fraction"]
    if last3cm and last3["wrist_target_pixel_ratio"] is not None and target_visible_fraction < 0.75:
        failures.append("wrist_red_target_not_consistently_visible_in_last_3cm")
    if last3["compared_scene_wrist_frames"] and last3["identical_scene_wrist_frames"] == last3["compared_scene_wrist_frames"]:
        failures.append("scene_wrist_identical_pixels")

    info = _load_episode_meta(source)
    visual = merge_stage_audits(
        variant=VARIANT_B,
        stages={
            "dataset": dataset_visual_keys_from_info(info)
            or dataset_visual_keys_from_video_tree(source),
            "release": dataset_visual_keys_from_video_tree(source),
        },
    )
    if not visual["passed"]:
        failures.append("unexpected_visual_keys")
        failures.extend(f"visual:{key}" for key in visual["unexpected_visual_keys"])

    geometry = audit_wrist_geometry(DEFAULT_UPSTREAM_XML)
    if not geometry["passed"]:
        failures.append("wrist_geometry_contract_failed")
        failures.extend(geometry["failures"])

    state15_ok = joints.shape[1] == 7 and ee.shape[1] == 7 and measured_grip.ndim == 1
    # Keep last-3cm field names used by the original smoke tests/reports.
    return {
        "episode_ref": f"{source.name}/episode_{episode_index:06d}",
        "num_frames": n,
        "object_xy0": obj[0, :2].tolist(),
        "first_close_frame": close_i,
        "last_3cm_frame_count": len(last3cm),
        "last_5cm_frame_count": len(last5cm),
        "close_window_frame_count": len(close_window),
        "state15_components_present": state15_ok,
        "action_fill": action_fill,
        "command_missing": sidecar.get("command_missing"),
        "ee_travel_m": ee_travel,
        "gripper_action_range": grip_range,
        "sync": sync,
        "windows": {
            "approach": approach_m,
            "last_5cm": last5,
            "last_3cm": last3,
            "close_window": close_m,
        },
        "wrist_nonzero_mean_last3cm": last3["wrist_nonzero_mean"],
        "scene_nonzero_mean_last3cm": last3["scene_nonzero_mean"],
        "wrist_laplacian_var_mean": last3["wrist_laplacian_var_mean"],
        "scene_laplacian_var_mean": last3["scene_laplacian_var_mean"],
        "wrist_red_target_ratio_mean_last3cm": last3["wrist_target_pixel_ratio"],
        "wrist_red_target_visible_fraction_last3cm": target_visible_fraction,
        "scene_red_target_ratio_mean_last3cm": last3["scene_target_pixel_ratio"],
        "wrist_out_of_view_samples": last3["wrist_out_of_view_samples"],
        "occlusion_proxy_fraction_last3cm": last3["occlusion_proxy_fraction"],
        "visual_allowlist": visual,
        "wrist_geometry": geometry,
        "failures": sorted(set(failures)),
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
    geometry = audit_wrist_geometry(DEFAULT_UPSTREAM_XML)
    visual_failed = [
        key
        for ep in episodes
        for key in (ep.get("visual_allowlist") or {}).get("unexpected_visual_keys", [])
    ]
    passed = (
        all(ep["passed"] for ep in episodes)
        and len(episodes) == expected_episodes
        and geometry["passed"]
    )
    return {
        "mode": "phase1_wrist_smoke_audit",
        "experiment_id": "smolvla_wrist_ablation_v1",
        "builds_release": False,
        "triggers_train": False,
        "sources": [str(path) for path in sources],
        "num_episodes": len(episodes),
        "expected_episodes": expected_episodes,
        "distinct_object_xy_rounded_mm": positions,
        "episodes": episodes,
        "wrist_geometry": geometry,
        "unexpected_visual_keys": sorted(set(visual_failed)),
        "gpu_latency_profiler": {
            "passed": False,
            "ran": False,
            "notes": "CPU audit only; run GPU profiler separately after human GPU approval.",
        },
        "passed": passed,
        "gate": "phase1_wrist_smoke_pass" if passed else "phase1_wrist_smoke_hold",
        "historical_phase1_hold_not_inherited": True,
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
