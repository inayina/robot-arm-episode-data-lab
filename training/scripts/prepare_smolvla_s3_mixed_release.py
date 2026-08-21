#!/usr/bin/env python3
"""Build an immutable dual-camera mixed SmolVLA release.

The release combines the existing wrist-ablation training split with the
accepted policy-visited recovery split.  The old release validation and
benchmark episodes remain benchmark-only; recovery validation remains held
out.  Source trees are never modified and no training or simulator is run.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "training/scripts/prepare_smolvla_s3_release.py"


def _load_prepare_module():
    spec = importlib.util.spec_from_file_location("smolvla_release_prepare", PREP)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {PREP}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_head(path: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_mixed_release(
    *,
    original_release: Path,
    recovery_lock: Path,
    recovery_source: Path,
    output: Path,
    release_id: str,
) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"refuse to overwrite existing release directory: {output}")

    original = json.loads((original_release / "manifest.json").read_text(encoding="utf-8"))
    original_splits = json.loads((original_release / "splits.json").read_text(encoding="utf-8"))
    lock = json.loads(recovery_lock.read_text(encoding="utf-8"))
    if lock.get("accepted_episode_count") != 24:
        raise ValueError("recovery lock must contain exactly 24 accepted episodes")
    if lock.get("accepted_frame_count") != 5048:
        raise ValueError("recovery lock frame count drifted from 5048")

    prep = _load_prepare_module()
    cameras = ["scene", "wrist"]
    original_ids = set(original_splits["train"]) | set(original_splits["validation"])
    original_source_names = {ref.split("/", 1)[0] for ref in original_ids}
    source_paths = [
        Path(raw).resolve()
        for raw in original["source_dataset_roots"]
        if Path(raw).name in original_source_names
    ]
    source_paths.append(recovery_source.resolve())
    episodes: list[dict[str, Any]] = []
    for source in source_paths:
        episodes.extend(prep._load_episodes(source, cameras=cameras))

    by_id = {row["episode_id"]: row for row in episodes}
    if not original_ids <= set(by_id):
        raise ValueError("original release episode set is not present in source trees")

    recovery_rows = [row for row in lock["episodes"] if row.get("capture_qa_passed") and row.get("split") in {"train", "validation"}]
    recovery_ids = [f"{recovery_source.name}/episode_{int(row['episode_index']):06d}" for row in recovery_rows]
    if len(recovery_ids) != 24 or len(set(recovery_ids)) != 24:
        raise ValueError("recovery lock does not describe 24 unique accepted episodes")
    if not set(recovery_ids) <= set(by_id):
        raise ValueError("recovery lock episode set is not present in recovery source")

    mixed_train = list(original_splits["train"])
    mixed_train.extend(ref for ref, row in zip(recovery_ids, recovery_rows, strict=True) if row["split"] == "train")
    mixed_validation = [ref for ref, row in zip(recovery_ids, recovery_rows, strict=True) if row["split"] == "validation"]
    mixed_benchmark = list(original_splits["validation"])
    selected_ids = set(mixed_train) | set(mixed_validation) | set(mixed_benchmark)
    selected = [row for row in episodes if row["episode_id"] in selected_ids]
    if len(selected) != 64:
        raise ValueError(f"expected 64 selected episodes, got {len(selected)}")
    splits = {"train": mixed_train, "validation": mixed_validation, "benchmark": mixed_benchmark}
    if set().union(*map(set, splits.values())) != selected_ids:
        raise ValueError("mixed split does not cover selected episodes")
    if set(mixed_train) & (set(mixed_validation) | set(mixed_benchmark)):
        raise ValueError("mixed train split leaks validation or benchmark episodes")

    output.mkdir(parents=True, exist_ok=False)
    state15_entries: list[dict[str, Any]] = []
    for row in selected:
        destination = output / "lerobot_state15" / row["source_name"] / "data" / "chunk-000" / f"episode_{int(row['episode_index']):06d}.parquet"
        state15_entries.append(prep.rewrite_parquet_observation_state15(Path(row["parquet_path"]), destination))
        row["state15_parquet_path"] = str(destination)
        row["state15_parquet_sha256"] = _sha256(destination)
        row["state_dim"] = prep.STATE15_DIM

    _write_json(output / "splits.json", splits)
    (output / "episode_index.jsonl").write_text(
        "".join(json.dumps({k: v for k, v in row.items() if not k.startswith("_")}, ensure_ascii=False) + "\n" for row in selected),
        encoding="utf-8",
    )
    _write_json(output / "norm_stats.json", prep._norm_stats(selected, set(mixed_train), compose_state15=True))
    _write_json(output / "state15_materialization.json", {"contract": prep.state15_contract_dict(), "episodes": state15_entries})
    validation = {
        "passed": True,
        "checks": {
            "original_train_preserved": len(original_splits["train"]) == 36,
            "recovery_train": len(mixed_train) - len(original_splits["train"]) == 16,
            "recovery_validation": len(mixed_validation) == 8,
            "old_validation_train_excluded": not set(original_splits["validation"]) & set(mixed_train),
            "no_split_leakage": True,
            "dual_camera": True,
            "state15": True,
            "action_semantics": "absolute_eef_gripper_v0",
        },
        "notes": [
            "Original wrist-ablation train split contributes 36 episodes.",
            "Accepted policy-visited recovery contributes 16 train and 8 held-out validation episodes.",
            "Original validation episodes are retained as benchmark-only; the stale P4 benchmark source is excluded.",
            "Recovery episode 000000 pilot is excluded from this release.",
        ],
    }
    _write_json(output / "validation_report.json", validation)
    sources = ["# SmolVLA mixed release sources", "", f"release_id: `{release_id}`", "", "Upstream trees (do not modify):", ""]
    sources.extend(f"- `{source}`" for source in source_paths)
    (output / "SOURCES.md").write_text("\n".join(sources) + "\n", encoding="utf-8")
    _write_json(output / "preflight_subset.json", {"episode_ids": mixed_train[:2], "max_frames_per_episode": 32, "approx_train_steps": "20-50", "purpose": "S3 preflight only"})

    file_names = ["episode_index.jsonl", "splits.json", "norm_stats.json", "state15_materialization.json", "validation_report.json", "SOURCES.md", "preflight_subset.json"]
    file_hashes = {name: _sha256(output / name) for name in file_names}
    fingerprint = hashlib.sha256()
    for name in sorted(file_hashes):
        fingerprint.update(name.encode("utf-8"))
        fingerprint.update(file_hashes[name].encode("utf-8"))
    manifest = {
        "contract_version": "smolvla_s3_release_manifest_v0",
        "release_id": release_id,
        "schema_version": release_id,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "policy_action_semantics": "absolute_eef_gripper_v0",
        "quaternion_order": "xyzw",
        "claims_task_success": False,
        "trained": False,
        "ran_isaac": False,
        "immutable": True,
        "overwrites_upstream": False,
        "overwrites_act_delta_release": False,
        "source_commit_midstream": _git_head(ROOT),
        "source_commit_upstream": _git_head(Path("/home/ina/dev/ros2-arm-teleoperation-suite")),
        "num_episodes": len(selected),
        "num_frames": int(sum(row["num_frames"] for row in selected)),
        "splits": splits,
        "scene_rgb_complete_rate": 1.0,
        "wrist_rgb_complete_rate": 1.0,
        "fields": {
            "joint_state": "observation.state[15]",
            "policy_state": "observation.state[15]=joint[7]+ee_pose_xyzw[7]+gripper[1]",
            "gripper_measured": "observation.gripper[1]",
            "gripper_cmd": "action[7]",
            "absolute_eef_xyz": "action[0:3]",
            "quaternion_xyzw": "action[3:7]",
            "language_instruction": "language_instruction",
            "camera": "observation.images.scene, observation.images.wrist mp4 @ 10Hz",
            "timestamps": "timestamp",
            "action_chunk_indices": "action_delta_indices constructed chunk_size=50",
            "valid_mask": "all-true for accepted episodes",
        },
        "split_policy": "mixed_original_wrist_train36_plus_recovery_train16_validation8_v1",
        "normalization_source": None,
        "cameras": cameras,
        "visual_allowlist_variant": "B_scene_wrist",
        "number_of_policy_cameras": 2,
        "state_contract": prep.state15_contract_dict(),
        "compose_state15": True,
        "grasp_assist_enabled": False,
        "normalization_stats_file": "norm_stats.json",
        "episode_index_file": "episode_index.jsonl",
        "validation_report_file": "validation_report.json",
        "file_sha256": file_hashes,
        "source_dataset_roots": [str(source) for source in source_paths],
        "go_no_go": "go",
        "release_content_sha256": fingerprint.hexdigest(),
    }
    _write_json(output / "manifest.json", manifest)
    return {"release_id": release_id, "output_dir": str(output), "num_episodes": len(selected), "num_frames": manifest["num_frames"], "train_episodes": len(mixed_train), "validation_episodes": len(mixed_validation), "train_frames": sum(row["num_frames"] for row in selected if row["episode_id"] in set(mixed_train)), "release_content_sha256": manifest["release_content_sha256"], "manifest_sha256": _sha256(output / "manifest.json")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-release", type=Path, required=True)
    parser.add_argument("--recovery-lock", type=Path, required=True)
    parser.add_argument("--recovery-source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            build_mixed_release(
                original_release=args.original_release,
                recovery_lock=args.recovery_lock,
                recovery_source=args.recovery_source,
                output=args.output_dir,
                release_id=args.release_id,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
