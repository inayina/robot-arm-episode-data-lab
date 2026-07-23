#!/usr/bin/env python3
"""Prepare immutable SmolVLA S3 release metadata from upstream LeRobot v2.1 absolute-EEF+RGB.

Does NOT copy videos into the release (records source paths + hashes).
Does NOT overwrite upstream or ACT ee_delta releases.
Does NOT train / download weights / run Isaac.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

# Optional Recovery imports (state[15] / PEFT live in training.smolvla_s3).
import sys as _sys
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
from training.smolvla_s3.state15 import (
    STATE15_DIM,
    compose_state15_from_row,
    rewrite_parquet_observation_state15,
    state15_contract_dict,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES = [
    Path(
        "/home/ina/dev/ros2-arm-teleoperation-suite/data/"
        "e2_red_500hz_seed52_closelift5_20260720"
    ),
    Path(
        "/home/ina/dev/ros2-arm-teleoperation-suite/data/"
        "e2_red_500hz_seed53_closelift5_20260720"
    ),
]
RELEASE_ID = "smolvla_s3_abs_eef_rgb_v0"
SCHEMA_VERSION = "smolvla_s3_abs_eef_rgb_v0"
POLICY_ACTION_SEMANTICS = "absolute_eef_gripper_v0"
QUAT_ORDER = "xyzw"


def _sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _git_head(repo: Path) -> str | None:
    try:
        return (
            subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                text=True,
            )
            .strip()
        )
    except Exception:
        return None


def _normalize_xyzw(q: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(q))
    if n < 1e-8:
        raise ValueError("quaternion near zero")
    q = q / n
    if q[3] < 0:
        q = -q
    return q


def _load_episodes(source_root: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    info = json.loads((source_root / "meta" / "info.json").read_text(encoding="utf-8"))
    episodes: list[dict[str, Any]] = []
    n_eps = int(info["total_episodes"])
    for i in range(n_eps):
        parquet = source_root / "data" / "chunk-000" / f"episode_{i:06d}.parquet"
        video = (
            source_root
            / "videos"
            / "chunk-000"
            / "observation.images.scene"
            / f"episode_{i:06d}.mp4"
        )
        table = pq.read_table(parquet)
        names = set(table.column_names)
        required = {
            "action",
            "observation.state",
            "observation.ee_pose",
            "observation.gripper",
            "language_instruction",
            "timestamp",
            "frame_index",
        }
        missing = sorted(required - names)
        if missing:
            raise ValueError(f"{parquet}: missing {missing}")
        if not video.is_file():
            raise ValueError(f"missing RGB video: {video}")

        actions = []
        states = []
        ee_poses = []
        states15 = []
        grips_m = []
        grips_c = []
        quats = []
        xyz = []
        langs = set()
        ts = []
        for row_i in range(table.num_rows):
            action = np.asarray(table.column("action")[row_i].as_py(), dtype=np.float64)
            if action.shape[0] == 7:
                raise ValueError(f"{parquet} row {row_i}: refusing ee_delta[7]")
            if action.shape[0] != 8:
                raise ValueError(f"{parquet} row {row_i}: action dim {action.shape[0]}")
            state = np.asarray(
                table.column("observation.state")[row_i].as_py(), dtype=np.float64
            )
            if state.shape[0] not in (7, 15):
                raise ValueError(f"state dim {state.shape[0]}")
            ee_pose = np.asarray(
                table.column("observation.ee_pose")[row_i].as_py(), dtype=np.float64
            ).reshape(-1)
            if ee_pose.shape[0] != 7:
                raise ValueError(f"ee_pose dim {ee_pose.shape[0]}")
            grip_m = float(
                np.asarray(
                    table.column("observation.gripper")[row_i].as_py(), dtype=np.float64
                ).reshape(-1)[0]
            )
            q = _normalize_xyzw(action[3:7].copy())
            actions.append(action.tolist())
            states.append(state.tolist())
            ee_poses.append(ee_pose.tolist())
            if state.shape[0] == 15:
                states15.append(state.astype(np.float32).tolist())
            else:
                states15.append(
                    compose_state15_from_row(
                        {
                            "observation.state": state,
                            "observation.ee_pose": ee_pose,
                            "observation.gripper": grip_m,
                        }
                    ).tolist()
                )
            grips_m.append(grip_m)
            grips_c.append(float(action[7]))
            quats.append(q.tolist())
            xyz.append(action[:3].tolist())
            langs.add(str(table.column("language_instruction")[row_i].as_py()))
            ts.append(float(table.column("timestamp")[row_i].as_py()))

        # chunk indices: action horizon placeholder (S3 trains with chunk construction)
        n = table.num_rows
        chunk_size = 50
        action_delta_indices = list(range(chunk_size))

        # video frame count via OpenCV
        import cv2

        cap = cv2.VideoCapture(str(video))
        vframes = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        if vframes != n:
            raise ValueError(
                f"video/parquet length mismatch {video}: video={vframes} parquet={n}"
            )

        ep_id = f"{source_root.name}/episode_{i:06d}"
        rel_parquet = f"{source_root.name}/data/chunk-000/episode_{i:06d}.parquet"
        rel_video = (
            f"{source_root.name}/videos/chunk-000/observation.images.scene/"
            f"episode_{i:06d}.mp4"
        )
        episodes.append(
            {
                "episode_id": ep_id,
                "source_root": str(source_root),
                "source_name": source_root.name,
                "episode_index": i,
                "num_frames": n,
                "parquet_path": str(parquet),
                "parquet_relpath": rel_parquet,
                "parquet_sha256": _sha256_file(parquet),
                "video_path": str(video),
                "video_relpath": rel_video,
                "video_sha256": _sha256_file(video),
                "rgb_complete": True,
                "action_dim": 8,
                "state_dim": 7,
                "state15_dim": STATE15_DIM,
                "language_instructions": sorted(langs),
                "gripper_cmd_min": float(min(grips_c)),
                "gripper_cmd_max": float(max(grips_c)),
                "gripper_measured_min": float(min(grips_m)),
                "gripper_measured_max": float(max(grips_m)),
                "quat_order": QUAT_ORDER,
                "quat_norm_min": float(
                    min(np.linalg.norm(np.asarray(quats), axis=1))
                ),
                "quat_norm_max": float(
                    max(np.linalg.norm(np.asarray(quats), axis=1))
                ),
                "timestamp_min": float(min(ts)),
                "timestamp_max": float(max(ts)),
                "action_chunk_size": chunk_size,
                "action_delta_indices": action_delta_indices,
                "valid_mask_all_true": True,
                "_actions": actions,
                "_states": states,
                "_ee_poses": ee_poses,
                "_states15": states15,
                "_grips_m": grips_m,
            }
        )
    return episodes


def _assign_splits(episodes: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Deterministic split with no leakage.

    Per source:
    - 5 eps → train3 / val1 / bench1 (seed52/53 legacy)
    - 10 eps → train6 / val2 / bench2 (grip-timing packs)
    - other → ~60/20/20
    """
    if len(episodes) < 6:
        raise ValueError(f"need >=6 episodes for S3 split, got {len(episodes)}")
    ids = [e["episode_id"] for e in episodes]
    train, val, bench = [], [], []
    by_source: dict[str, list[str]] = {}
    for e in episodes:
        by_source.setdefault(e["source_name"], []).append(e["episode_id"])
    for _src, ep_ids in sorted(by_source.items()):
        ep_ids = sorted(ep_ids)
        n = len(ep_ids)
        if n == 5:
            train.extend(ep_ids[:3])
            val.append(ep_ids[3])
            bench.append(ep_ids[4])
        elif n == 10:
            train.extend(ep_ids[:6])
            val.extend(ep_ids[6:8])
            bench.extend(ep_ids[8:10])
        else:
            n_train = max(1, int(round(n * 0.6)))
            n_val = max(1, int(round(n * 0.2))) if n >= 5 else 0
            n_bench = n - n_train - n_val
            if n_bench < 0:
                n_train = n
                n_val = 0
                n_bench = 0
            train.extend(ep_ids[:n_train])
            val.extend(ep_ids[n_train : n_train + n_val])
            bench.extend(ep_ids[n_train + n_val :])
    # uniqueness
    all_ids = train + val + bench
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("split leakage detected")
    if set(all_ids) != set(ids):
        raise ValueError("split does not cover all episodes")
    return {"train": train, "validation": val, "benchmark": bench}


def _assign_splits_phaseaware50(
    episodes: list[dict[str, Any]],
    *,
    position_by_source: dict[str, str],
) -> dict[str, list[str]]:
    """P0–P3: 9 train + 1 validation each; P4: 10 benchmark (held-out)."""
    train: list[str] = []
    val: list[str] = []
    bench: list[str] = []
    by_source: dict[str, list[dict[str, Any]]] = {}
    for e in episodes:
        by_source.setdefault(e["source_name"], []).append(e)
    for src, rows in sorted(by_source.items()):
        pos = position_by_source.get(src)
        if pos is None:
            # Infer from source name tokens like ..._P0_... or ...seed60_p0_...
            upper = src.upper()
            for cand in ("P0", "P1", "P2", "P3", "P4"):
                if f"_{cand}_" in f"_{upper}_" or f"SEED{60 + int(cand[1])}" in upper.replace("_", ""):
                    pos = cand
                    break
        if pos is None:
            raise ValueError(f"phaseaware50: cannot map source to position: {src}")
        ep_ids = [e["episode_id"] for e in sorted(rows, key=lambda r: r["episode_index"])]
        if len(ep_ids) != 10:
            raise ValueError(f"phaseaware50 expects 10 eps for {src}/{pos}, got {len(ep_ids)}")
        if pos == "P4":
            bench.extend(ep_ids)
        elif pos in {"P0", "P1", "P2", "P3"}:
            train.extend(ep_ids[:9])
            val.append(ep_ids[9])
        else:
            raise ValueError(f"unknown position id: {pos}")
    all_ids = train + val + bench
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("phaseaware50 split leakage")
    if set(all_ids) != {e["episode_id"] for e in episodes}:
        raise ValueError("phaseaware50 split does not cover all episodes")
    if not (len(train) == 36 and len(val) == 4 and len(bench) == 10):
        raise ValueError(
            f"phaseaware50 expected 36/4/10, got {len(train)}/{len(val)}/{len(bench)}"
        )
    return {"train": train, "validation": val, "benchmark": bench}


def _norm_stats(
    episodes: list[dict[str, Any]],
    train_ids: set[str],
    *,
    compose_state15: bool = False,
) -> dict[str, Any]:
    actions = []
    states8 = []
    states15 = []
    for e in episodes:
        if e["episode_id"] not in train_ids:
            continue
        for a, s, g, s15 in zip(
            e["_actions"], e["_states"], e["_grips_m"], e["_states15"], strict=True
        ):
            actions.append(a)
            states8.append(list(s[:7]) + [g])
            states15.append(s15)
    A = np.asarray(actions, dtype=np.float64)
    S = np.asarray(states8, dtype=np.float64)
    S15 = np.asarray(states15, dtype=np.float64)
    out = {
        "policy_action_semantics": POLICY_ACTION_SEMANTICS,
        "computed_on_split": "train",
        "action8": {
            "mean": A.mean(axis=0).tolist(),
            "std": np.maximum(A.std(axis=0), 1e-6).tolist(),
            "names": [
                "ee_x",
                "ee_y",
                "ee_z",
                "quat_x",
                "quat_y",
                "quat_z",
                "quat_w",
                "gripper_cmd",
            ],
        },
        "state8": {
            "mean": S.mean(axis=0).tolist(),
            "std": np.maximum(S.std(axis=0), 1e-6).tolist(),
            "names": [
                "joint_0",
                "joint_1",
                "joint_2",
                "joint_3",
                "joint_4",
                "joint_5",
                "joint_6",
                "gripper_measured",
            ],
        },
        "expert_scale": {
            "ee_xyz_span": (A[:, :3].max(0) - A[:, :3].min(0)).tolist(),
            "ee_step_l2_p50": float(
                np.percentile(
                    np.linalg.norm(np.diff(A[:, :3], axis=0), axis=1), 50
                )
            )
            if len(A) > 1
            else None,
            "ee_step_l2_p90": float(
                np.percentile(
                    np.linalg.norm(np.diff(A[:, :3], axis=0), axis=1), 90
                )
            )
            if len(A) > 1
            else None,
            "gripper_cmd_range": [float(A[:, 7].min()), float(A[:, 7].max())],
        },
    }
    if compose_state15:
        out["state_contract"] = state15_contract_dict()
        out["state15"] = {
            "mean": S15.mean(axis=0).tolist(),
            "std": np.maximum(S15.std(axis=0), 1e-6).tolist(),
            "names": (
                [f"joint_{i}" for i in range(7)]
                + ["ee_x", "ee_y", "ee_z", "quat_x", "quat_y", "quat_z", "quat_w"]
                + ["gripper_measured"]
            ),
        }
        out["policy_state"] = "observation.state[15]"
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "releases" / RELEASE_ID,
    )
    parser.add_argument(
        "--release-id",
        type=str,
        default=RELEASE_ID,
        help="Immutable release id (also used as schema_version label).",
    )
    parser.add_argument(
        "--source",
        type=Path,
        action="append",
        default=None,
        help="Upstream LeRobot v2.1 dataset root (repeatable).",
    )
    parser.add_argument(
        "--split-policy",
        choices=("legacy", "phaseaware50"),
        default="legacy",
        help="legacy=per-source 60/20/20 packs; phaseaware50=36/4/10 by P0–P4.",
    )
    parser.add_argument(
        "--compose-state15",
        action="store_true",
        help="Record state[15] contract + norms; materialize rewritten parquets.",
    )
    parser.add_argument(
        "--position-map-json",
        type=Path,
        default=None,
        help='JSON map {"source_name":"P0",...} for phaseaware50 splits.',
    )
    parser.add_argument(
        "--cameras",
        default="scene",
        help="Comma-separated camera keys for manifest (default: scene).",
    )
    args = parser.parse_args()
    sources = args.source or DEFAULT_SOURCES
    out: Path = args.output_dir
    release_id = str(args.release_id).strip() or RELEASE_ID
    schema_version = release_id
    compose_state15 = bool(args.compose_state15)
    cameras = [c.strip() for c in str(args.cameras).split(",") if c.strip()]
    if out.exists() and any(out.iterdir()):
        # immutable: refuse overwrite unless only regenerating identical release id folder empty of foreign files
        raise SystemExit(
            f"refuse to overwrite existing release dir: {out}\n"
            "Delete only if intentionally rebuilding the same release_id offline."
        )

    episodes: list[dict[str, Any]] = []
    for src in sources:
        episodes.extend(_load_episodes(Path(src)))

    position_by_source: dict[str, str] = {}
    if args.position_map_json is not None:
        position_by_source = {
            str(k): str(v)
            for k, v in __import__("json").loads(
                args.position_map_json.read_text(encoding="utf-8")
            ).items()
        }
    if args.split_policy == "phaseaware50":
        splits = _assign_splits_phaseaware50(
            episodes, position_by_source=position_by_source
        )
    else:
        splits = _assign_splits(episodes)
    train_ids = set(splits["train"])
    norms = _norm_stats(episodes, train_ids, compose_state15=compose_state15)

    mid_head = _git_head(ROOT)
    up_head = _git_head(Path("/home/ina/dev/ros2-arm-teleoperation-suite"))

    validation = {
        "passed": True,
        "checks": {
            "no_split_leakage": True,
            "no_ee_delta7": True,
            "rgb_complete_rate": 1.0,
            "quat_order": QUAT_ORDER,
            "quat_normalized": True,
            "gripper_cmd_in_01": all(
                0.0 <= e["gripper_cmd_min"] and e["gripper_cmd_max"] <= 1.0
                for e in episodes
            ),
            "video_parquet_aligned": True,
            "action_semantics": POLICY_ACTION_SEMANTICS,
            "refuses_act_delta_release": True,
        },
        "notes": [
            "Release is metadata+hash freeze over upstream raw LeRobot v2.1 trees.",
            "Videos/parquet remain at source paths; AutoDL must sync sources by hash.",
            "Does not rewrite upstream or ACT ee_delta releases.",
        ],
    }
    if not validation["checks"]["gripper_cmd_in_01"]:
        validation["passed"] = False

    file_hashes = {}
    out.mkdir(parents=True, exist_ok=False)
    materialized_state15: list[dict] = []
    if compose_state15:
        lerobot_root = out / "lerobot_state15"
        for e in episodes:
            src_parquet = Path(e["parquet_path"])
            dst = (
                lerobot_root
                / e["source_name"]
                / "data"
                / "chunk-000"
                / f"episode_{int(e['episode_index']):06d}.parquet"
            )
            meta = rewrite_parquet_observation_state15(src_parquet, dst)
            e["state15_parquet_path"] = str(dst)
            e["state15_parquet_sha256"] = _sha256_file(dst)
            e["state_dim"] = STATE15_DIM
            materialized_state15.append(meta)
        (out / "state15_materialization.json").write_text(
            json.dumps(
                {
                    "contract": state15_contract_dict(),
                    "episodes": materialized_state15,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    index_rows = []
    for e in episodes:
        row = {k: v for k, v in e.items() if not k.startswith("_")}
        index_rows.append(row)
    (out / "episode_index.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in index_rows),
        encoding="utf-8",
    )
    (out / "splits.json").write_text(
        json.dumps(splits, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out / "norm_stats.json").write_text(
        json.dumps(norms, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out / "validation_report.json").write_text(
        json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    sources_md = [
        "# SmolVLA S3 release sources",
        "",
        f"release_id: `{release_id}`",
        "",
        "Upstream trees (do not modify):",
        "",
    ]
    for src in sources:
        sources_md.append(f"- `{src}`")
    sources_md.append("")
    (out / "SOURCES.md").write_text("\n".join(sources_md) + "\n", encoding="utf-8")

    hash_names = [
        "episode_index.jsonl",
        "splits.json",
        "norm_stats.json",
        "validation_report.json",
        "SOURCES.md",
    ]
    if compose_state15:
        hash_names.append("state15_materialization.json")
    for name in hash_names:
        file_hashes[name] = _sha256_file(out / name)

    # preflight subset: first two train episodes, first 32 frames conceptually
    preflight = {
        "episode_ids": splits["train"][:2],
        "max_frames_per_episode": 32,
        "approx_train_steps": "20-50",
        "purpose": "S3 preflight only",
    }
    (out / "preflight_subset.json").write_text(
        json.dumps(preflight, indent=2) + "\n", encoding="utf-8"
    )
    file_hashes["preflight_subset.json"] = _sha256_file(out / "preflight_subset.json")

    manifest = {
        "contract_version": "smolvla_s3_release_manifest_v0",
        "release_id": release_id,
        "schema_version": schema_version,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "policy_action_semantics": POLICY_ACTION_SEMANTICS,
        "quaternion_order": QUAT_ORDER,
        "claims_task_success": False,
        "trained": False,
        "ran_isaac": False,
        "immutable": True,
        "overwrites_upstream": False,
        "overwrites_act_delta_release": False,
        "source_commit_midstream": mid_head,
        "source_commit_upstream": up_head,
        "num_episodes": len(episodes),
        "num_frames": int(sum(e["num_frames"] for e in episodes)),
        "splits": splits,
        "scene_rgb_complete_rate": 1.0,
        "fields": {
            "joint_state": (
                "observation.state[15]" if compose_state15 else "observation.state[7]"
            ),
            "policy_state": (
                "observation.state[15]=joint[7]+ee_pose_xyzw[7]+gripper[1]"
                if compose_state15
                else "observation.state[7]"
            ),
            "gripper_measured": "observation.gripper[1]",
            "gripper_cmd": "action[7]",
            "absolute_eef_xyz": "action[0:3]",
            "quaternion_xyzw": "action[3:7]",
            "language_instruction": "language_instruction",
            "camera": (
                ", ".join(f"observation.images.{c}" for c in cameras)
                + " mp4 @ 10Hz"
            ),
            "timestamps": "timestamp",
            "action_chunk_indices": "action_delta_indices constructed chunk_size=50",
            "valid_mask": "all-true for accepted episodes",
        },
        "split_policy": args.split_policy,
        "cameras": cameras,
        "state_contract": state15_contract_dict() if compose_state15 else None,
        "compose_state15": compose_state15,
        "grasp_assist_enabled": False,
        "normalization_stats_file": "norm_stats.json",
        "episode_index_file": "episode_index.jsonl",
        "validation_report_file": "validation_report.json",
        "file_sha256": file_hashes,
        "source_dataset_roots": [str(s) for s in sources],
        "s2_baseline_ref": {
            "ee_rmse_m": 0.2734163848429447,
            "gripper_accuracy": 0.0,
            "report": "evaluation/examples/smolvla_gate_s2_report.json",
        },
        "go_no_go": "go" if validation["passed"] else "no_go",
    }
    # Fingerprint of sibling artifacts only. Do not embed manifest.json self-hash
    # (circular). AutoDL should verify release_content_sha256 + on-disk sha256sum.
    content_h = hashlib.sha256()
    for name in sorted(file_hashes):
        content_h.update(name.encode("utf-8"))
        content_h.update(file_hashes[name].encode("utf-8"))
    manifest["release_content_sha256"] = content_h.hexdigest()
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "release_id": release_id,
                "output_dir": str(out),
                "num_episodes": manifest["num_episodes"],
                "num_frames": manifest["num_frames"],
                "go_no_go": manifest["go_no_go"],
                "release_content_sha256": manifest["release_content_sha256"],
                "manifest_sha256": _sha256_file(out / "manifest.json"),
                "splits": splits,
            },
            ensure_ascii=False,
        )
    )
    return 0 if validation["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
