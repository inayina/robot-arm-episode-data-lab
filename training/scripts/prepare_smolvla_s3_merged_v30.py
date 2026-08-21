#!/usr/bin/env python3
"""Build one LeRobot v3.0 training root from accepted v2.1 episode trees.

The SmolVLA trainer accepts one ``dataset.root`` while an immutable S3 release
may reference multiple upstream roots. This tool copies each source into a
scratch tree, optionally filters to a release split (train-only by default for
Recovery), converts the copies with LeRobot's official v2.1→v3.0 converter,
aggregates them, normalizes the aggregate Arrow schema, and load-smokes it.
It never modifies the source trees or immutable release metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.smolvla_s3.state15 import STATE15_DIM, compose_state15  # noqa: E402
from training.smolvla_s3.visual_allowlist import (  # noqa: E402
    DATASET_WRIST,
    VARIANT_A,
    VARIANT_B,
    audit_visual_keys,
    dataset_visual_keys_from_video_tree,
)


STAT_KEYS = (
    "observation.state",
    "observation.ee_pose",
    "observation.object_pose",
    "observation.ft",
    "observation.gripper",
    "action",
    "success",
    "safety_estop",
    "drive_fault",
)

PROVENANCE_NAME = "train_root_provenance.json"
PROVENANCE_CONTRACT = "smolvla_s3_train_root_provenance_v0"
STATE_CONTRACT_SOURCE7 = "source7"
STATE_CONTRACT_RECOVERY15 = "recovery15"


def _sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _video_keys_for_source(source: Path, info: dict[str, Any]) -> list[str]:
    """Fail-closed scene / scene+wrist video keys. Rejects tactile/depth/third cam."""
    info_keys = [
        key
        for key, feature in (info.get("features") or {}).items()
        if isinstance(feature, dict) and feature.get("dtype") == "video"
    ]
    if not info_keys:
        info_keys = ["observation.images.scene"]
    tree_keys = dataset_visual_keys_from_video_tree(source)
    if set(tree_keys) != set(info_keys):
        raise ValueError(
            f"{source}: video tree {tree_keys} != info.json video keys {info_keys}"
        )
    variant = VARIANT_B if DATASET_WRIST in info_keys else VARIANT_A
    report = audit_visual_keys(
        variant=variant,
        stage="train_root_source",
        observed_keys=tree_keys,
    )
    if not report["passed"]:
        raise ValueError(
            f"{source}: visual allowlist failed "
            f"unexpected={report['unexpected_visual_keys']} "
            f"missing={report['missing_required_visual_keys']}"
        )
    preferred = ["observation.images.scene", "observation.images.wrist"]
    return [key for key in preferred if key in info_keys] + [
        key for key in info_keys if key not in preferred
    ]


def parse_episode_ref(ref: str) -> tuple[str, int]:
    """Parse ``<source_name>/episode_000003`` → ``(source_name, 3)``."""
    if "/" not in ref:
        raise ValueError(f"invalid episode ref (missing '/'): {ref}")
    source_name, episode_id = ref.rsplit("/", 1)
    if not source_name or not episode_id.startswith("episode_"):
        raise ValueError(f"invalid episode ref: {ref}")
    try:
        index = int(episode_id.split("_", 1)[1])
    except ValueError as exc:
        raise ValueError(f"invalid episode ref index: {ref}") from exc
    return source_name, index


def load_splits(splits_json: Path) -> dict[str, list[str]]:
    payload = json.loads(splits_json.read_text(encoding="utf-8"))
    required = ("train", "validation", "benchmark")
    missing = [name for name in required if name not in payload]
    if missing:
        raise ValueError(f"{splits_json} missing splits: {missing}")
    return {
        name: [str(ref) for ref in payload[name]]
        for name in ("train", "validation", "benchmark")
    }


def selected_indices_by_source(
    splits: dict[str, list[str]],
    *,
    include_split: str,
    source_names: list[str],
) -> dict[str, list[int]]:
    if include_split not in splits:
        raise ValueError(f"unknown include-split: {include_split}")
    wanted = list(splits[include_split])
    by_source: dict[str, list[int]] = {name: [] for name in source_names}
    unknown: list[str] = []
    for ref in wanted:
        source_name, index = parse_episode_ref(ref)
        if source_name not in by_source:
            unknown.append(ref)
            continue
        by_source[source_name].append(index)
    if unknown:
        raise ValueError(
            "episode refs do not match provided --source roots: "
            + ", ".join(unknown)
        )
    for name, indices in by_source.items():
        if len(indices) != len(set(indices)):
            raise ValueError(f"duplicate episode indices for source {name}")
        if indices != sorted(indices):
            # Keep release order within a source; do not silently reorder.
            pass
    empty = [name for name, indices in by_source.items() if not indices]
    if empty:
        raise ValueError(
            f"after split filter these sources have zero episodes: {empty}"
        )
    return by_source


def materialize_filtered_v21_root(
    source: Path,
    dest: Path,
    selected_original_indices: list[int],
) -> dict[str, Any]:
    """Copy selected v2.1 episodes into ``dest`` and renumber them 0..N-1."""
    if dest.exists():
        raise FileExistsError(f"refuse to overwrite scratch tree: {dest}")
    if not selected_original_indices:
        raise ValueError(f"no episodes selected for source {source}")

    info = json.loads((source / "meta" / "info.json").read_text(encoding="utf-8"))
    episodes = [
        json.loads(line)
        for line in (source / "meta" / "episodes.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    by_index = {int(row["episode_index"]): row for row in episodes}
    video_keys = _video_keys_for_source(source, info)

    (dest / "meta").mkdir(parents=True)
    (dest / "data" / "chunk-000").mkdir(parents=True)

    new_episodes: list[dict[str, Any]] = []
    total_frames = 0
    mapping: list[dict[str, Any]] = []
    for new_index, old_index in enumerate(selected_original_indices):
        if old_index not in by_index:
            raise KeyError(f"{source}: missing episode_index={old_index}")
        src_parquet = (
            source / "data" / "chunk-000" / f"episode_{old_index:06d}.parquet"
        )
        dst_parquet = (
            dest / "data" / "chunk-000" / f"episode_{new_index:06d}.parquet"
        )
        if not src_parquet.is_file():
            raise FileNotFoundError(src_parquet)
        shutil.copy2(src_parquet, dst_parquet)

        for video_key in video_keys:
            src_video = (
                source
                / "videos"
                / "chunk-000"
                / video_key
                / f"episode_{old_index:06d}.mp4"
            )
            dst_video = (
                dest
                / "videos"
                / "chunk-000"
                / video_key
                / f"episode_{new_index:06d}.mp4"
            )
            if not src_video.is_file():
                raise FileNotFoundError(src_video)
            dst_video.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_video, dst_video)

        old_meta = dict(by_index[old_index])
        length = int(old_meta.get("length") or pq.read_metadata(dst_parquet).num_rows)
        new_meta = {
            **old_meta,
            "episode_index": new_index,
            "episode_id": f"episode_{new_index:06d}",
            "length": length,
        }
        new_episodes.append(new_meta)
        total_frames += length
        mapping.append(
            {
                "filtered_index": new_index,
                "source_episode_index": old_index,
                "source_name": source.name,
                "episode_ref": f"{source.name}/episode_{old_index:06d}",
                "num_frames": length,
            }
        )

    info = dict(info)
    info["total_episodes"] = len(selected_original_indices)
    info["total_frames"] = total_frames
    info["total_videos"] = len(selected_original_indices) * len(video_keys)
    info["splits"] = {"train": f"0:{len(selected_original_indices)}"}
    (dest / "meta" / "info.json").write_text(
        json.dumps(info, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (dest / "meta" / "episodes.jsonl").write_text(
        "\n".join(json.dumps(row, separators=(",", ":")) for row in new_episodes)
        + "\n",
        encoding="utf-8",
    )
    for name in ("tasks.jsonl", "stats.json"):
        src = source / "meta" / name
        if src.is_file():
            shutil.copy2(src, dest / "meta" / name)

    return {
        "source": str(source.resolve()),
        "dest": str(dest.resolve()),
        "num_episodes": len(selected_original_indices),
        "num_frames": total_frames,
        "mapping": mapping,
    }


def build_provenance(
    *,
    splits_json: Path,
    include_split: str,
    splits: dict[str, list[str]],
    episode_refs: list[str],
    source_roots: list[Path],
    num_frames: int,
    filtered_mappings: list[dict[str, Any]],
) -> dict[str, Any]:
    train = set(splits["train"])
    validation = set(splits["validation"])
    benchmark = set(splits["benchmark"])
    selected = set(episode_refs)
    leak = sorted(selected & (validation | benchmark | (train - selected)))
    return {
        "contract_version": PROVENANCE_CONTRACT,
        "include_split": include_split,
        "splits_json": str(splits_json.resolve()),
        "splits_sha256": _sha256_file(splits_json),
        "episode_refs": list(episode_refs),
        "num_episodes": len(episode_refs),
        "num_frames": int(num_frames),
        "source_roots": [str(path.resolve()) for path in source_roots],
        "filtered_mappings": filtered_mappings,
        "validation_benchmark_intersection": sorted(
            selected & (validation | benchmark)
        ),
        "unexpected_refs": leak,
        "passed_split_isolation": not (selected & (validation | benchmark))
        and selected == set(splits[include_split]),
    }


def validate_train_root_against_splits(
    train_root: Path,
    splits_json: Path,
    *,
    include_split: str = "train",
) -> dict[str, Any]:
    """Fail closed if a training root contains validation/benchmark refs."""
    errors: list[str] = []
    splits = load_splits(splits_json)
    provenance_path = train_root / PROVENANCE_NAME
    info_path = train_root / "meta" / "info.json"
    if not provenance_path.is_file():
        errors.append(f"missing {PROVENANCE_NAME}")
        return {
            "passed": False,
            "errors": errors,
            "go_no_go": "no_go",
            "reason": "missing_train_root_provenance",
        }
    if not info_path.is_file():
        errors.append("missing meta/info.json")
        return {
            "passed": False,
            "errors": errors,
            "go_no_go": "no_go",
            "reason": "missing_info_json",
        }

    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    info = json.loads(info_path.read_text(encoding="utf-8"))
    expected_refs = list(splits[include_split])
    actual_refs = [str(ref) for ref in provenance.get("episode_refs", [])]
    splits_sha = _sha256_file(splits_json)

    if provenance.get("contract_version") != PROVENANCE_CONTRACT:
        errors.append("provenance contract_version mismatch")
    if provenance.get("include_split") != include_split:
        errors.append(
            f"include_split mismatch: {provenance.get('include_split')} != {include_split}"
        )
    if provenance.get("splits_sha256") != splits_sha:
        errors.append("splits_sha256 mismatch vs release splits.json")
    if actual_refs != expected_refs:
        errors.append(
            "episode_refs do not match release "
            f"{include_split} split "
            f"(got {len(actual_refs)}, expected {len(expected_refs)})"
        )
    leak = sorted(
        set(actual_refs)
        & (set(splits["validation"]) | set(splits["benchmark"]))
    )
    if leak:
        errors.append(f"validation/benchmark refs present in train root: {leak}")
    total_episodes = int(info.get("total_episodes", -1))
    if total_episodes != len(expected_refs):
        errors.append(
            f"info.json total_episodes={total_episodes} != "
            f"len({include_split})={len(expected_refs)}"
        )
    if int(provenance.get("num_episodes", -1)) != len(expected_refs):
        errors.append("provenance.num_episodes mismatch")
    if int(info.get("total_frames", -1)) != int(provenance.get("num_frames", -2)):
        errors.append("info.json total_frames != provenance.num_frames")

    return {
        "passed": not errors,
        "errors": errors,
        "go_no_go": "go" if not errors else "no_go",
        "include_split": include_split,
        "expected_num_episodes": len(expected_refs),
        "actual_num_episodes": total_episodes,
        "splits_sha256": splits_sha,
        "episode_refs": actual_refs,
        "validation_benchmark_intersection": leak,
        "provenance_path": str(provenance_path),
    }


def _stats(values: list[object]) -> dict[str, object]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim == 1:
        array = array.reshape(-1, 1)
    return {
        "min": array.min(axis=0).tolist(),
        "max": array.max(axis=0).tolist(),
        "mean": array.mean(axis=0).tolist(),
        "std": array.std(axis=0).tolist(),
        "count": [int(array.shape[0])],
    }


def _write_episode_stats(root: Path) -> None:
    info = json.loads((root / "meta" / "info.json").read_text(encoding="utf-8"))
    rows = []
    for episode_index in range(int(info["total_episodes"])):
        table = pq.read_table(
            root
            / "data"
            / "chunk-000"
            / f"episode_{episode_index:06d}.parquet"
        )
        episode_stats = {
            key: _stats(
                [table.column(key)[row].as_py() for row in range(table.num_rows)]
            )
            for key in STAT_KEYS
        }
        rows.append(
            json.dumps(
                {"episode_index": episode_index, "stats": episode_stats},
                separators=(",", ":"),
            )
        )
    (root / "meta" / "episodes_stats.jsonl").write_text(
        "\n".join(rows) + "\n", encoding="utf-8"
    )


def _convert(root: Path, repo_id: str) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "lerobot.scripts.convert_dataset_v21_to_v30",
            f"--repo-id={repo_id}",
            f"--root={root}",
            "--push-to-hub=false",
            "--force-conversion",
        ],
        check=True,
    )
    info = json.loads((root / "meta" / "info.json").read_text(encoding="utf-8"))
    if info.get("codebase_version") != "v3.0":
        raise RuntimeError(f"conversion did not produce v3.0: {root}")


def _fixed_list(values: list[object], size: int) -> pa.Array:
    return pa.array(values, type=pa.list_(pa.float32(), list_size=size))


def _state_values(
    values: dict[str, list[object]], state_contract: str
) -> tuple[list[list[float]], int]:
    if state_contract == STATE_CONTRACT_SOURCE7:
        return (
            [
                np.asarray(value, dtype=np.float32).reshape(-1).tolist()
                for value in values["observation.state"]
            ],
            7,
        )
    if state_contract != STATE_CONTRACT_RECOVERY15:
        raise ValueError(f"unknown state contract: {state_contract}")
    composed = [
        compose_state15(
            joint_position=joints,
            ee_pose_xyzw=ee,
            measured_gripper=gripper,
        ).tolist()
        for joints, ee, gripper in zip(
            values["observation.state"],
            values["observation.ee_pose"],
            values["observation.gripper"],
            strict=True,
        )
    ]
    return composed, STATE15_DIM


def _normalize_aggregate(
    root: Path, *, state_contract: str = STATE_CONTRACT_SOURCE7
) -> None:
    info_path = root / "meta" / "info.json"
    info = json.loads(info_path.read_text(encoding="utf-8"))
    fps = float(info["fps"])
    data_path = root / "data" / "chunk-000" / "file-000.parquet"
    episodes_path = (
        root / "meta" / "episodes" / "chunk-000" / "file-000.parquet"
    )
    table = pq.read_table(data_path)
    episodes = pq.read_table(episodes_path).to_pandas()

    episode_index = np.zeros(table.num_rows, dtype=np.int64)
    frame_index = np.zeros(table.num_rows, dtype=np.int64)
    from_timestamps: list[float] = []
    to_timestamps: list[float] = []
    cumulative_seconds = 0.0
    for _, episode in episodes.iterrows():
        start = int(episode["dataset_from_index"])
        stop = int(episode["dataset_to_index"])
        index = int(episode["episode_index"])
        episode_index[start:stop] = index
        frame_index[start:stop] = np.arange(stop - start, dtype=np.int64)
        from_timestamps.append(cumulative_seconds)
        cumulative_seconds += (stop - start) / fps
        to_timestamps.append(cumulative_seconds)

    values = {name: table.column(name).to_pylist() for name in table.column_names}
    policy_state_values, policy_state_dim = _state_values(values, state_contract)
    language_values = [
        "pick up the target object" if value is None else str(value)
        for value in values["language_instruction"]
    ]
    task_values = [
        language if value is None else str(value)
        for value, language in zip(
            values["task"], language_values, strict=True
        )
    ]
    arrays: dict[str, pa.Array] = {
        "index": pa.array(np.arange(table.num_rows), type=pa.int64()),
        "episode_index": pa.array(episode_index, type=pa.int64()),
        "frame_index": pa.array(frame_index, type=pa.int64()),
        "timestamp": pa.array(frame_index / fps, type=pa.float32()),
        "task_index": pa.array(values["task_index"], type=pa.int64()),
        "next.done": pa.array(values["next.done"], type=pa.bool_()),
        "next.reward": pa.array(values["next.reward"], type=pa.float32()),
        "task": pa.array(task_values, type=pa.string()),
        "language_instruction": pa.array(
            language_values, type=pa.string()
        ),
        "success": pa.array(values["success"], type=pa.bool_()),
        "safety_estop": pa.array(values["safety_estop"], type=pa.bool_()),
        "drive_fault": pa.array(values["drive_fault"], type=pa.bool_()),
        "observation.state": _fixed_list(policy_state_values, policy_state_dim),
        "observation.ee_pose": _fixed_list(values["observation.ee_pose"], 7),
        "observation.object_pose": _fixed_list(
            values["observation.object_pose"], 7
        ),
        "observation.ft": _fixed_list(values["observation.ft"], 6),
        "observation.gripper": pa.array(
            [
                float(value[0]) if isinstance(value, list) else float(value)
                for value in values["observation.gripper"]
            ],
            type=pa.float32(),
        ),
        "action": _fixed_list(values["action"], 8),
    }
    if "task_phase" in values:
        arrays["task_phase"] = pa.array(
            ["unknown" if value is None else str(value) for value in values["task_phase"]],
            type=pa.string(),
        )
    else:
        info["features"].pop("task_phase", None)
    pq.write_table(pa.table(arrays), data_path)

    # aggregate_datasets keeps these canonical LeRobot columns in parquet but
    # does not currently add them to the aggregate info.json feature map.
    # Hugging Face datasets requires the metadata and parquet column names to
    # match exactly when LeRobotDataset supplies an explicit feature schema.
    info["features"].update(
        {
            "observation.state": {
                "dtype": "float32",
                "shape": [policy_state_dim],
                "names": None,
            },
            "next.done": {
                "dtype": "bool",
                "shape": [1],
                "names": None,
            },
            "next.reward": {
                "dtype": "float32",
                "shape": [1],
                "names": None,
            },
            "task": {
                "dtype": "string",
                "shape": [1],
                "names": None,
            },
        }
    )
    info["policy_state_contract"] = state_contract
    info_path.write_text(
        json.dumps(info, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    video_keys = _video_keys_for_source(root, info)
    if not video_keys:
        video_keys = ["observation.images.scene"]
    for key in video_keys:
        episodes[f"videos/{key}/from_timestamp"] = from_timestamps
        episodes[f"videos/{key}/to_timestamp"] = to_timestamps
    pq.write_table(
        pa.Table.from_pandas(episodes, preserve_index=False), episodes_path
    )

    image_stats = {
        "min": [[[0.0]], [[0.0]], [[0.0]]],
        "max": [[[1.0]], [[1.0]], [[1.0]]],
        "mean": [[[0.485]], [[0.456]], [[0.406]]],
        "std": [[[0.229]], [[0.224]], [[0.225]]],
        "count": [int(table.num_rows)],
    }
    stats_path = root / "meta" / "stats.json"
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    stats["observation.state"] = _stats(policy_state_values)
    for key in video_keys:
        stats[key] = image_stats
    stats_path.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def materialize_merged_train_root(
    *,
    sources: list[Path],
    output: Path,
    repo_id: str,
    splits_json: Path | None,
    include_split: str,
    allow_unfiltered: bool,
    state_contract: str = STATE_CONTRACT_SOURCE7,
    skip_lerobot_load_smoke: bool = False,
    video_backend: str | None = None,
) -> dict[str, Any]:
    sources = [path.resolve() for path in sources]
    output = output.resolve()
    if output.exists():
        raise SystemExit(f"refuse to overwrite output: {output}")
    if not sources or not all(path.is_dir() for path in sources):
        raise SystemExit(f"need existing source roots: {sources}")
    if splits_json is None and not allow_unfiltered:
        raise SystemExit(
            "refusing unfiltered merge (split leak risk). Pass --splits-json "
            "and --include-split train, or explicit --allow-unfiltered."
        )
    if len(sources) < 2 and splits_json is None:
        raise SystemExit(f"need at least two existing source roots: {sources}")

    filtered_mappings: list[dict[str, Any]] = []
    episode_refs: list[str] = []
    work_roots: list[Path] = []

    if splits_json is not None:
        splits = load_splits(splits_json)
        by_source = selected_indices_by_source(
            splits,
            include_split=include_split,
            source_names=[path.name for path in sources],
        )
        episode_refs = list(splits[include_split])
        for index, source in enumerate(sources):
            work = output.parent / f".{output.name}_work_{index}"
            summary = materialize_filtered_v21_root(
                source, work, by_source[source.name]
            )
            filtered_mappings.extend(summary["mapping"])
            _write_episode_stats(work)
            _convert(work, f"{repo_id}_source_{index}")
            work_roots.append(work)
    else:
        print(
            "[warn] building unfiltered merged root; validation/benchmark "
            "episodes may leak into training",
            file=sys.stderr,
        )
        for index, source in enumerate(sources):
            work = output.parent / f".{output.name}_work_{index}"
            if work.exists():
                raise SystemExit(f"refuse to overwrite scratch tree: {work}")
            shutil.copytree(source, work)
            _write_episode_stats(work)
            _convert(work, f"{repo_id}_source_{index}")
            work_roots.append(work)

    if len(work_roots) == 1:
        shutil.move(str(work_roots[0]), str(output))
    else:
        from lerobot.datasets.dataset_tools import aggregate_datasets

        aggregate_datasets(
            repo_ids=[f"{repo_id}_source_{i}" for i in range(len(work_roots))],
            aggr_repo_id=repo_id,
            roots=work_roots,
            aggr_root=output,
        )
        for work in work_roots:
            shutil.rmtree(work, ignore_errors=True)
    _normalize_aggregate(output, state_contract=state_contract)
    tree_keys = dataset_visual_keys_from_video_tree(output)
    variant = VARIANT_B if DATASET_WRIST in tree_keys else VARIANT_A
    visual_report = audit_visual_keys(
        variant=variant,
        stage="train_root_merged",
        observed_keys=tree_keys,
    )
    if not visual_report["passed"]:
        raise RuntimeError(
            "merged train root visual allowlist failed "
            f"unexpected={visual_report['unexpected_visual_keys']} "
            f"missing={visual_report['missing_required_visual_keys']}"
        )

    info = json.loads(
        (output / "meta" / "info.json").read_text(encoding="utf-8")
    )
    if splits_json is not None:
        provenance = build_provenance(
            splits_json=splits_json,
            include_split=include_split,
            splits=load_splits(splits_json),
            episode_refs=episode_refs,
            source_roots=sources,
            num_frames=int(info["total_frames"]),
            filtered_mappings=filtered_mappings,
        )
        if not provenance["passed_split_isolation"]:
            raise RuntimeError(
                "split isolation failed while writing provenance: "
                f"{provenance['validation_benchmark_intersection']}"
            )
        if int(info["total_episodes"]) != len(episode_refs):
            raise RuntimeError(
                f"merged total_episodes={info['total_episodes']} != "
                f"len({include_split})={len(episode_refs)}"
            )
        (output / PROVENANCE_NAME).write_text(
            json.dumps(
                {**provenance, "policy_state_contract": state_contract},
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    sample_action_shape: list[int] | None = None
    if not skip_lerobot_load_smoke:
        from lerobot.datasets.lerobot_dataset import LeRobotDataset

        dataset = LeRobotDataset(
            repo_id=repo_id,
            root=output,
            video_backend=video_backend,
        )
        if len(dataset) != int(info["total_frames"]):
            raise RuntimeError("LeRobotDataset length does not match info.json")
        sample = dataset[0]
        if tuple(sample["action"].shape) != (8,):
            raise RuntimeError(f"unexpected action shape: {sample['action'].shape}")
        if tuple(sample["observation.state"].shape) != (
            15 if state_contract == STATE_CONTRACT_RECOVERY15 else 7,
        ):
            raise RuntimeError(
                "unexpected observation.state shape: "
                f"{sample['observation.state'].shape}"
            )
        sample_action_shape = list(sample["action"].shape)
        if variant == VARIANT_B:
            missing = [
                key
                for key in ("observation.images.scene", "observation.images.wrist")
                if key not in sample
            ]
            if missing:
                raise RuntimeError(
                    f"B LeRobot sample missing visual keys: {missing}"
                )


    report = {
        "passed": True,
        "output": str(output),
        "repo_id": repo_id,
        "codebase_version": info["codebase_version"],
        "total_episodes": info["total_episodes"],
        "total_frames": info["total_frames"],
        "sample_action_shape": sample_action_shape,
        "policy_state_contract": state_contract,
        "observation_state_dim": (
            15 if state_contract == STATE_CONTRACT_RECOVERY15 else 7
        ),
        "include_split": include_split if splits_json else None,
        "splits_json": str(splits_json.resolve()) if splits_json else None,
        "provenance": PROVENANCE_NAME if splits_json else None,
        "visual_keys": tree_keys,
        "visual_allowlist_variant": variant,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, action="append", default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--repo-id", default="local/smolvla_s3_merged")
    parser.add_argument("--splits-json", type=Path, default=None)
    parser.add_argument("--include-split", default="train")
    parser.add_argument(
        "--state-contract",
        choices=[STATE_CONTRACT_SOURCE7, STATE_CONTRACT_RECOVERY15],
        default=STATE_CONTRACT_SOURCE7,
        help="Compose Recovery state[15], or preserve the legacy source state[7].",
    )
    parser.add_argument(
        "--allow-unfiltered",
        action="store_true",
        help="Explicit opt-in to merge every episode (legacy leaky path).",
    )
    parser.add_argument(
        "--validate-train-root",
        type=Path,
        default=None,
        help="Validate an existing train root against --splits-json (no build).",
    )
    parser.add_argument(
        "--skip-lerobot-load-smoke",
        action="store_true",
        help="Skip LeRobotDataset load smoke (tests / offline hosts).",
    )
    parser.add_argument(
        "--video-backend",
        choices=["pyav", "torchcodec", "video_reader"],
        default=None,
        help="Explicit LeRobot video decoder for the load smoke.",
    )
    args = parser.parse_args(argv)

    if args.validate_train_root is not None:
        if args.splits_json is None:
            raise SystemExit("--validate-train-root requires --splits-json")
        report = validate_train_root_against_splits(
            args.validate_train_root.resolve(),
            args.splits_json.resolve(),
            include_split=args.include_split,
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["passed"] else 2

    if not args.source or args.output is None:
        raise SystemExit("--source (repeatable) and --output are required to build")

    report = materialize_merged_train_root(
        sources=list(args.source),
        output=args.output,
        repo_id=args.repo_id,
        splits_json=args.splits_json.resolve() if args.splits_json else None,
        include_split=args.include_split,
        allow_unfiltered=bool(args.allow_unfiltered),
        state_contract=args.state_contract,
        skip_lerobot_load_smoke=bool(args.skip_lerobot_load_smoke),
        video_backend=args.video_backend,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
