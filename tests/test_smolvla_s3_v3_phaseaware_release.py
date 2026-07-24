"""Fixture E2E: state15 materialization + phaseaware50 split + train-only gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from training.smolvla_s3.peft_targets import (  # noqa: E402
    normalize_full_training_modules,
    normalize_target_modules,
    target_modules_fingerprint,
)
from training.smolvla_s3.state15 import (  # noqa: E402
    compose_state15,
    rewrite_parquet_observation_state15,
)


def _write_minimal_episode(root: Path, *, ep: int, n_frames: int = 8) -> Path:
    data = root / "data" / "chunk-000"
    data.mkdir(parents=True, exist_ok=True)
    vid_dir = root / "videos" / "chunk-000" / "observation.images.scene"
    vid_dir.mkdir(parents=True, exist_ok=True)
    (root / "meta").mkdir(parents=True, exist_ok=True)

    rows = {
        "action": [[0.4, 0.0, 0.1, 0.0, 0.0, 0.0, 1.0, 1.0 if i < 4 else 0.0] for i in range(n_frames)],
        "observation.state": [[0.1 * j for j in range(7)] for _ in range(n_frames)],
        "observation.ee_pose": [[0.4, 0.0, 0.1, 0.0, 0.0, 0.0, 1.0] for _ in range(n_frames)],
        "observation.object_pose": [[0.4, 0.0, 0.02, 0.0, 0.0, 0.0, 1.0] for _ in range(n_frames)],
        "observation.ft": [[0.0] * 6 for _ in range(n_frames)],
        "observation.gripper": [1.0 if i < 4 else 0.0 for i in range(n_frames)],
        "language_instruction": ["pick up the red box"] * n_frames,
        "timestamp": [i * 0.1 for i in range(n_frames)],
        "frame_index": list(range(n_frames)),
        "success": [True] * n_frames,
        "safety_estop": [False] * n_frames,
        "drive_fault": [False] * n_frames,
    }
    parquet = data / f"episode_{ep:06d}.parquet"
    pq.write_table(pa.table(rows), parquet)

    # Tiny valid-ish mp4 via OpenCV if available; else skip video hash in release tests.
    try:
        import cv2

        video = vid_dir / f"episode_{ep:06d}.mp4"
        writer = cv2.VideoWriter(
            str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (32, 24)
        )
        for _ in range(n_frames):
            writer.write(np.zeros((24, 32, 3), dtype=np.uint8))
        writer.release()
    except Exception:
        pass

    info = {
        "codebase_version": "v2.1",
        "total_episodes": ep + 1,
        "total_frames": (ep + 1) * n_frames,
        "fps": 10.0,
    }
    # rewrite total after all eps written by caller
    (root / "meta" / "info.json").write_text(json.dumps(info) + "\n", encoding="utf-8")
    return parquet


def _write_source_tree(tmp: Path, name: str, n_eps: int = 10) -> Path:
    root = tmp / name
    for i in range(n_eps):
        _write_minimal_episode(root, ep=i, n_frames=8)
    info = {
        "codebase_version": "v2.1",
        "total_episodes": n_eps,
        "total_frames": n_eps * 8,
        "fps": 10.0,
    }
    (root / "meta" / "info.json").write_text(json.dumps(info) + "\n", encoding="utf-8")
    return root


def test_peft_regex_not_character_split() -> None:
    cfg = yaml.safe_load(
        (ROOT / "configs/smolvla_s3/recovery_decisions.yaml").read_text(encoding="utf-8")
    )
    raw = cfg["peft"]["target_modules"]
    assert isinstance(normalize_target_modules(raw), str)
    fp = target_modules_fingerprint(raw)
    assert len(fp) == 1
    assert "state_proj" in fp[0]
    assert normalize_full_training_modules(cfg["peft"]["full_training_modules"]) == []


def test_rewrite_parquet_state15(tmp_path: Path) -> None:
    src_root = _write_source_tree(tmp_path, "src_a", n_eps=1)
    src = src_root / "data/chunk-000/episode_000000.parquet"
    dst = tmp_path / "out.parquet"
    rewrite_parquet_observation_state15(src, dst)
    table = pq.read_table(dst)
    state = np.asarray(table.column("observation.state")[0].as_py(), dtype=np.float32)
    assert state.shape == (15,)
    expect = compose_state15(
        joint_position=[0.1 * j for j in range(7)],
        ee_pose_xyzw=[0.4, 0.0, 0.1, 0.0, 0.0, 0.0, 1.0],
        measured_gripper=1.0,
    )
    assert np.allclose(state, expect)


def test_phaseaware50_split_and_release_fixture(tmp_path: Path) -> None:
    import importlib.util

    prep_path = ROOT / "training/scripts/prepare_smolvla_s3_release.py"
    spec = importlib.util.spec_from_file_location("prepare_smolvla_s3_release", prep_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    sources = []
    pos_map = {}
    for i, pid in enumerate(["P0", "P1", "P2", "P3", "P4"]):
        name = f"e2_red_500hz_seed{60 + i}_v3_{pid}_phaseaware10_fixture"
        root = _write_source_tree(tmp_path, name, n_eps=10)
        # Ensure videos exist for release loader
        for ep in range(10):
            v = (
                root
                / "videos/chunk-000/observation.images.scene"
                / f"episode_{ep:06d}.mp4"
            )
            if not v.is_file():
                pytest.skip("OpenCV mp4 writer unavailable")
        sources.append(root)
        pos_map[name] = pid

    pos_json = tmp_path / "position_map.json"
    pos_json.write_text(json.dumps(pos_map) + "\n", encoding="utf-8")
    out = tmp_path / "release_v3"
    argv = [
        "prepare_smolvla_s3_release.py",
        "--output-dir",
        str(out),
        "--release-id",
        "smolvla_s3_panda_abs_eef_scene_v3_phaseaware50",
        "--split-policy",
        "phaseaware50",
        "--compose-state15",
        "--position-map-json",
        str(pos_json),
        "--cameras",
        "scene",
    ]
    for src in sources:
        argv.extend(["--source", str(src)])

    old = sys.argv
    try:
        sys.argv = argv
        rc = mod.main()
    finally:
        sys.argv = old
    assert rc == 0
    splits = json.loads((out / "splits.json").read_text(encoding="utf-8"))
    assert len(splits["train"]) == 36
    assert len(splits["validation"]) == 4
    assert len(splits["benchmark"]) == 10
    assert not (set(splits["train"]) & set(splits["validation"]))
    assert not (set(splits["train"]) & set(splits["benchmark"]))
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["compose_state15"] is True
    assert manifest["fields"]["joint_state"] == "observation.state[15]"
    assert (out / "state15_materialization.json").is_file()
    norms = json.loads((out / "norm_stats.json").read_text(encoding="utf-8"))
    assert "state15" in norms
    assert len(norms["state15"]["mean"]) == 15


def test_prospective_eval_only_release_has_no_training_refs(tmp_path: Path) -> None:
    import importlib.util

    prep_path = ROOT / "training/scripts/prepare_smolvla_s3_release.py"
    spec = importlib.util.spec_from_file_location(
        "prepare_smolvla_s3_release_eval_only", prep_path
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    source = _write_source_tree(
        tmp_path, "e2_red_500hz_seed65_v3_prospective_P0_eval2_fixture", n_eps=2
    )
    for ep in range(2):
        video = (
            source
            / "videos/chunk-000/observation.images.scene"
            / f"episode_{ep:06d}.mp4"
        )
        if not video.is_file():
            pytest.skip("OpenCV mp4 writer unavailable")

    normalization_release = tmp_path / "training_release"
    normalization_release.mkdir()
    (normalization_release / "manifest.json").write_text(
        json.dumps({"release_id": "training_release_fixture"}) + "\n",
        encoding="utf-8",
    )
    frozen_norms = {
        "policy_action_semantics": "absolute_eef_gripper_v0",
        "computed_on_split": "train",
        "state15": {"mean": [0.0] * 15, "std": [1.0] * 15},
    }
    (normalization_release / "norm_stats.json").write_text(
        json.dumps(frozen_norms) + "\n", encoding="utf-8"
    )

    out = tmp_path / "prospective_release"
    argv = [
        "prepare_smolvla_s3_release.py",
        "--output-dir",
        str(out),
        "--release-id",
        "smolvla_s3_recovery_v3_prospective_eval10_fixture",
        "--split-policy",
        "prospective_eval_only",
        "--normalization-source-release",
        str(normalization_release),
        "--compose-state15",
        "--cameras",
        "scene",
        "--source",
        str(source),
    ]
    old = sys.argv
    try:
        sys.argv = argv
        rc = mod.main()
    finally:
        sys.argv = old
    assert rc == 0

    splits = json.loads((out / "splits.json").read_text(encoding="utf-8"))
    assert splits["train"] == []
    assert splits["validation"] == []
    assert len(splits["benchmark"]) == 2
    assert json.loads((out / "norm_stats.json").read_text()) == frozen_norms
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["split_policy"] == "prospective_eval_only"
    assert manifest["normalization_source"]["release_id"] == "training_release_fixture"


def test_v3_schema_yaml_matches_release_id() -> None:
    cfg = yaml.safe_load(
        (ROOT / "configs/smolvla_s3/v3_phaseaware50.yaml").read_text(encoding="utf-8")
    )
    assert cfg["release_id"] == "smolvla_s3_panda_abs_eef_scene_v3_phaseaware50"
    assert cfg["enable_wrist_camera"] is False
    assert cfg["splits"] == {"train": 36, "validation": 4, "benchmark": 10}
    assert set(cfg["positions"]) == {"P0", "P1", "P2", "P3", "P4"}
