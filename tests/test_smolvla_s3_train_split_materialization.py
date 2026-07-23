"""Tests for SmolVLA S3 train-only split materialization (Phase 0-A)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "training" / "scripts" / "prepare_smolvla_s3_merged_v30.py"
SPEC = importlib.util.spec_from_file_location("smolvla_s3_merged_v30_test", SCRIPT)
assert SPEC and SPEC.loader
MERGE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MERGE
SPEC.loader.exec_module(MERGE)

V2_RELEASE = ROOT / "data" / "releases" / "smolvla_s3_abs_eef_rgb_v2_griptiming_lateclose"
V0_RELEASE = ROOT / "data" / "releases" / "smolvla_s3_abs_eef_rgb_v0"


def _write_minimal_v21_root(path: Path, *, n_episodes: int, frames_each: int = 3) -> None:
    (path / "meta").mkdir(parents=True)
    (path / "data" / "chunk-000").mkdir(parents=True)
    video_dir = path / "videos" / "chunk-000" / "observation.images.scene"
    video_dir.mkdir(parents=True)

    episodes = []
    for index in range(n_episodes):
        table = pa.table(
            {
                "observation.state": pa.array(
                    [[float(i)] * 7 for i in range(frames_each)],
                    type=pa.list_(pa.float32()),
                ),
                "observation.ee_pose": pa.array(
                    [[0.1, 0.2, 0.3, 0.0, 0.0, 0.0, 1.0]] * frames_each,
                    type=pa.list_(pa.float32()),
                ),
                "observation.object_pose": pa.array(
                    [[0.0] * 7] * frames_each,
                    type=pa.list_(pa.float32()),
                ),
                "observation.ft": pa.array(
                    [[0.0] * 6] * frames_each,
                    type=pa.list_(pa.float32()),
                ),
                "observation.gripper": pa.array(
                    [1.0] * frames_each, type=pa.float32()
                ),
                "action": pa.array(
                    [[0.1, 0.2, 0.3, 0.0, 0.0, 0.0, 1.0, 1.0]] * frames_each,
                    type=pa.list_(pa.float32()),
                ),
                "success": pa.array([True] * frames_each),
                "safety_estop": pa.array([False] * frames_each),
                "drive_fault": pa.array([False] * frames_each),
                "language_instruction": pa.array(
                    ["pick up the red box"] * frames_each
                ),
                "timestamp": pa.array(
                    [0.1 * i for i in range(frames_each)], type=pa.float32()
                ),
                "frame_index": pa.array(list(range(frames_each)), type=pa.int64()),
            }
        )
        pq.write_table(
            table, path / "data" / "chunk-000" / f"episode_{index:06d}.parquet"
        )
        (video_dir / f"episode_{index:06d}.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
        episodes.append(
            {
                "episode_index": index,
                "episode_id": f"episode_{index:06d}",
                "tasks": ["pick up the red box"],
                "length": frames_each,
            }
        )

    info = {
        "codebase_version": "v2.1",
        "robot_type": "panda",
        "total_episodes": n_episodes,
        "total_frames": n_episodes * frames_each,
        "total_tasks": 1,
        "total_videos": n_episodes,
        "total_chunks": 1,
        "chunks_size": 1000,
        "fps": 10.0,
        "splits": {"train": f"0:{n_episodes}"},
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4",
        "features": {
            "observation.state": {"dtype": "float32", "shape": [7], "names": None},
            "observation.images.scene": {
                "dtype": "video",
                "shape": [240, 320, 3],
                "names": ["height", "width", "channel"],
            },
            "action": {"dtype": "float32", "shape": [8], "names": None},
        },
    }
    (path / "meta" / "info.json").write_text(
        json.dumps(info, indent=2) + "\n", encoding="utf-8"
    )
    (path / "meta" / "episodes.jsonl").write_text(
        "\n".join(json.dumps(row) for row in episodes) + "\n", encoding="utf-8"
    )
    (path / "meta" / "tasks.jsonl").write_text(
        json.dumps({"task_index": 0, "task": "pick up the red box"}) + "\n",
        encoding="utf-8",
    )
    (path / "meta" / "stats.json").write_text("{}\n", encoding="utf-8")


def test_parse_episode_ref_and_v2_split_counts() -> None:
    source, index = MERGE.parse_episode_ref(
        "e2_red_500hz_seed56_griptiming_lateclose10_20260723/episode_000007"
    )
    assert source == "e2_red_500hz_seed56_griptiming_lateclose10_20260723"
    assert index == 7

    splits = MERGE.load_splits(V2_RELEASE / "splits.json")
    assert len(splits["train"]) == 12
    assert len(splits["validation"]) == 4
    assert len(splits["benchmark"]) == 4
    assert not (
        set(splits["train"])
        & set(splits["validation"])
        & set(splits["benchmark"])
    )
    assert not (set(splits["train"]) & set(splits["validation"]))
    assert not (set(splits["train"]) & set(splits["benchmark"]))


def test_selected_indices_by_source_for_v2_fixture() -> None:
    splits = MERGE.load_splits(V2_RELEASE / "splits.json")
    source_names = [
        "e2_red_500hz_seed56_griptiming_lateclose10_20260723",
        "e2_red_500hz_seed57_griptiming_lateclose10_20260723",
    ]
    by_source = MERGE.selected_indices_by_source(
        splits, include_split="train", source_names=source_names
    )
    assert by_source[source_names[0]] == [0, 1, 2, 3, 4, 5]
    assert by_source[source_names[1]] == [0, 1, 2, 3, 4, 5]
    assert sum(len(v) for v in by_source.values()) == 12


def test_materialize_filtered_v21_renumbers_and_drops_held_out(tmp_path: Path) -> None:
    source = tmp_path / "seed_a"
    _write_minimal_v21_root(source, n_episodes=5, frames_each=4)
    dest = tmp_path / "filtered"
    summary = MERGE.materialize_filtered_v21_root(source, dest, [0, 1, 2])

    info = json.loads((dest / "meta" / "info.json").read_text(encoding="utf-8"))
    episodes = [
        json.loads(line)
        for line in (dest / "meta" / "episodes.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    assert info["total_episodes"] == 3
    assert info["total_frames"] == 12
    assert info["splits"] == {"train": "0:3"}
    assert [row["episode_index"] for row in episodes] == [0, 1, 2]
    assert (dest / "data" / "chunk-000" / "episode_000000.parquet").is_file()
    assert (dest / "data" / "chunk-000" / "episode_000002.parquet").is_file()
    assert not (dest / "data" / "chunk-000" / "episode_000003.parquet").exists()
    assert summary["mapping"][0]["episode_ref"] == f"{source.name}/episode_000000"
    assert summary["mapping"][2]["source_episode_index"] == 2


def test_validate_train_root_rejects_leak_and_accepts_clean(tmp_path: Path) -> None:
    splits = {
        "train": ["seed_a/episode_000000", "seed_a/episode_000001"],
        "validation": ["seed_a/episode_000002"],
        "benchmark": ["seed_a/episode_000003"],
    }
    splits_path = tmp_path / "splits.json"
    splits_path.write_text(json.dumps(splits, indent=2) + "\n", encoding="utf-8")

    train_root = tmp_path / "train_root"
    (train_root / "meta").mkdir(parents=True)
    (train_root / "meta" / "info.json").write_text(
        json.dumps({"total_episodes": 2, "total_frames": 8}) + "\n",
        encoding="utf-8",
    )
    provenance = MERGE.build_provenance(
        splits_json=splits_path,
        include_split="train",
        splits=splits,
        episode_refs=list(splits["train"]),
        source_roots=[tmp_path / "seed_a"],
        num_frames=8,
        filtered_mappings=[],
    )
    (train_root / MERGE.PROVENANCE_NAME).write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    ok = MERGE.validate_train_root_against_splits(
        train_root, splits_path, include_split="train"
    )
    assert ok["passed"] is True
    assert ok["expected_num_episodes"] == 2
    assert ok["validation_benchmark_intersection"] == []

    # Inject a validation ref into provenance → No-Go.
    bad = dict(provenance)
    bad["episode_refs"] = list(splits["train"]) + list(splits["validation"])
    bad["num_episodes"] = 3
    (train_root / MERGE.PROVENANCE_NAME).write_text(
        json.dumps(bad, indent=2) + "\n", encoding="utf-8"
    )
    (train_root / "meta" / "info.json").write_text(
        json.dumps({"total_episodes": 3, "total_frames": 8}) + "\n",
        encoding="utf-8",
    )
    leaked = MERGE.validate_train_root_against_splits(
        train_root, splits_path, include_split="train"
    )
    assert leaked["passed"] is False
    assert leaked["go_no_go"] == "no_go"
    assert "seed_a/episode_000002" in leaked["validation_benchmark_intersection"]


def test_v0_and_v2_release_splits_are_disjoint() -> None:
    for release in (V0_RELEASE, V2_RELEASE):
        splits = MERGE.load_splits(release / "splits.json")
        train, val, bench = map(set, (splits["train"], splits["validation"], splits["benchmark"]))
        assert not (train & val)
        assert not (train & bench)
        assert not (val & bench)


def test_recovery_state_values_compose_joint_ee_gripper() -> None:
    values = {
        "observation.state": [[0, 1, 2, 3, 4, 5, 6]],
        "observation.ee_pose": [[0.4, 0.1, 0.2, 0, 0, 0, 1]],
        "observation.gripper": [0.75],
    }
    state, dim = MERGE._state_values(values, MERGE.STATE_CONTRACT_RECOVERY15)
    assert dim == 15
    import numpy as np

    np.testing.assert_allclose(
        state,
        [[0, 1, 2, 3, 4, 5, 6, 0.4, 0.1, 0.2, 0, 0, 0, 1, 0.75]],
        rtol=1e-6,
    )


def test_normalize_aggregate_writes_state15_metadata_and_stats(
    tmp_path: Path,
) -> None:
    root = tmp_path / "aggregate"
    (root / "data" / "chunk-000").mkdir(parents=True)
    (root / "meta" / "episodes" / "chunk-000").mkdir(parents=True)
    (root / "meta" / "info.json").write_text(
        json.dumps({"fps": 10.0, "features": {}}) + "\n", encoding="utf-8"
    )
    (root / "meta" / "stats.json").write_text("{}\n", encoding="utf-8")
    rows = 2
    pq.write_table(
        pa.table(
            {
                "task_index": pa.array([0, 0], type=pa.int64()),
                "next.done": pa.array([False, True]),
                "next.reward": pa.array([0.0, 1.0], type=pa.float32()),
                "task": pa.array(["pick", "pick"]),
                "language_instruction": pa.array(["pick", "pick"]),
                "success": pa.array([True, True]),
                "safety_estop": pa.array([False, False]),
                "drive_fault": pa.array([False, False]),
                "observation.state": pa.array(
                    [[0.0] * 7, [1.0] * 7], type=pa.list_(pa.float32())
                ),
                "observation.ee_pose": pa.array(
                    [[0.4, 0.0, 0.2, 0, 0, 0, 1]] * rows,
                    type=pa.list_(pa.float32()),
                ),
                "observation.object_pose": pa.array(
                    [[0.0] * 7] * rows, type=pa.list_(pa.float32())
                ),
                "observation.ft": pa.array(
                    [[0.0] * 6] * rows, type=pa.list_(pa.float32())
                ),
                "observation.gripper": pa.array([1.0, 0.0], type=pa.float32()),
                "action": pa.array(
                    [[0.0] * 8] * rows, type=pa.list_(pa.float32())
                ),
            }
        ),
        root / "data" / "chunk-000" / "file-000.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "episode_index": pa.array([0], type=pa.int64()),
                "dataset_from_index": pa.array([0], type=pa.int64()),
                "dataset_to_index": pa.array([2], type=pa.int64()),
            }
        ),
        root / "meta" / "episodes" / "chunk-000" / "file-000.parquet",
    )

    MERGE._normalize_aggregate(
        root, state_contract=MERGE.STATE_CONTRACT_RECOVERY15
    )

    table = pq.read_table(root / "data" / "chunk-000" / "file-000.parquet")
    assert len(table.column("observation.state")[0].as_py()) == 15
    info = json.loads((root / "meta" / "info.json").read_text(encoding="utf-8"))
    stats = json.loads((root / "meta" / "stats.json").read_text(encoding="utf-8"))
    assert info["features"]["observation.state"]["shape"] == [15]
    assert info["policy_state_contract"] == "recovery15"
    assert len(stats["observation.state"]["mean"]) == 15
