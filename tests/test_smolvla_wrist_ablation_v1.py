"""Fail-closed visual allowlist and H_knuckle_z05 geometry for wrist ablation v1."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from training.smolvla_s3.policy_features import (
    CAMERA_VARIANT_SCENE_ONLY,
    CAMERA_VARIANT_SCENE_PLUS_WRIST,
    camera_rename_map,
    image_feature_keys,
    policy_visual_features,
)
from training.smolvla_s3.visual_allowlist import (
    DATASET_SCENE,
    DATASET_WRIST,
    POLICY_CAMERA1,
    POLICY_CAMERA2,
    VARIANT_A,
    VARIANT_B,
    audit_visual_keys,
    merge_stage_audits,
)
from training.smolvla_s3.wrist_geometry_contract import (
    DEFAULT_UPSTREAM_XML,
    H_KNUCKLE_Z05,
    audit_wrist_geometry,
    parse_wrist_camera_xml,
)

ROOT = Path(__file__).resolve().parents[1]


def test_allowlist_a_is_exactly_one_camera() -> None:
    report = audit_visual_keys(
        variant=VARIANT_A,
        stage="dataset",
        observed_keys=[DATASET_SCENE],
    )
    assert report["passed"] is True
    assert report["number_of_policy_cameras"] == 1
    assert report["mapped_policy_visual_keys"] == [POLICY_CAMERA1]


def test_allowlist_b_is_exactly_two_cameras() -> None:
    report = audit_visual_keys(
        variant=VARIANT_B,
        stage="dataset",
        observed_keys=[DATASET_SCENE, DATASET_WRIST],
    )
    assert report["passed"] is True
    assert report["number_of_policy_cameras"] == 2
    assert report["mapped_policy_visual_keys"] == [POLICY_CAMERA1, POLICY_CAMERA2]


def test_allowlist_rejects_tactile_and_camera3() -> None:
    tactile = audit_visual_keys(
        variant=VARIANT_B,
        stage="dataset",
        observed_keys=[DATASET_SCENE, DATASET_WRIST, "observation.images.tactile_left"],
    )
    assert tactile["passed"] is False
    assert "observation.images.tactile_left" in tactile["unexpected_visual_keys"]

    cam3 = audit_visual_keys(
        variant=VARIANT_B,
        stage="checkpoint",
        observed_keys=[POLICY_CAMERA1, POLICY_CAMERA2, "observation.images.camera3"],
    )
    assert cam3["passed"] is False
    assert "observation.images.camera3" in cam3["unexpected_visual_keys"]
    assert any("third_camera" in item or "unexpected" in item for item in cam3["failures"])


def test_policy_visual_features_never_emit_third_camera() -> None:
    a = policy_visual_features(CAMERA_VARIANT_SCENE_ONLY)
    b = policy_visual_features(CAMERA_VARIANT_SCENE_PLUS_WRIST)
    assert image_feature_keys(a) == [POLICY_CAMERA1]
    assert image_feature_keys(b) == [POLICY_CAMERA1, POLICY_CAMERA2]
    assert "observation.images.camera3" not in a
    assert "observation.images.camera3" not in b
    assert camera_rename_map(CAMERA_VARIANT_SCENE_PLUS_WRIST)[DATASET_WRIST] == POLICY_CAMERA2


def test_merge_stage_audits_writes_required_fields() -> None:
    report = merge_stage_audits(
        variant=VARIANT_B,
        stages={
            "dataset": [DATASET_SCENE, DATASET_WRIST],
            "release": [DATASET_SCENE, DATASET_WRIST],
            "training": [POLICY_CAMERA1, POLICY_CAMERA2],
            "checkpoint": [POLICY_CAMERA1, POLICY_CAMERA2],
            "runtime": [POLICY_CAMERA1, POLICY_CAMERA2],
        },
    )
    assert report["passed"] is True
    assert report["number_of_policy_cameras"] == 2
    assert report["unexpected_visual_keys"] == []
    assert report["authorized_to_train"] is False


def test_head_xml_is_h_knuckle_z05() -> None:
    report = audit_wrist_geometry(DEFAULT_UPSTREAM_XML)
    assert report["passed"] is True
    assert report["matches_H_knuckle_z05"] is True
    assert report["matches_historical_B_look_fingers"] is False
    parsed = parse_wrist_camera_xml(DEFAULT_UPSTREAM_XML.read_text(encoding="utf-8"))
    assert parsed["pos"] == H_KNUCKLE_Z05["pos"]


def test_geometry_rejects_b_look_fingers() -> None:
    xml = '<camera name="wrist_camera" pos="0.0 0.0 -0.02" xyaxes="1 0 0 0 -1 0" fovy="70.0" />'
    report = audit_wrist_geometry(xml_text=xml)
    assert report["passed"] is False
    assert report["matches_historical_B_look_fingers"] is True


def test_wrist_ablation_config_is_not_authorized_to_train() -> None:
    cfg = yaml.safe_load(
        (ROOT / "configs" / "smolvla_s3" / "wrist_ablation_v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert cfg["experiment_id"] == "smolvla_wrist_ablation_v1"
    assert cfg["authorized_to_train"] is False
    assert cfg["authorized_isaac"] is False
    assert cfg["builds_release"] is True
    assert cfg["parent_release_id"] == (
        "smolvla_wrist_ablation_v1_panda_abs_eef_scene_wrist_phaseaware50"
    )
    assert cfg["inference"]["camera_variant"] == "scene_plus_wrist"
    assert cfg["inference"]["empty_cameras"] == 0
    assert cfg["historical_v3_immutable"] is True
    assert cfg["visual_allowlist"]["B_scene_wrist"]["number_of_policy_cameras"] == 2


def test_cpu_preflight_rejects_tactile_and_passes_allowlist(tmp_path: Path) -> None:
    from training.scripts import preflight_smolvla_wrist_ablation as preflight

    cfg = yaml.safe_load(
        (ROOT / "configs" / "smolvla_s3" / "wrist_ablation_v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    report = preflight.run_preflight(cfg, live_forward=False)
    assert report["passed"] is True
    assert report["tactile_rejected"] is True
    assert report["replace_strips_camera3"] is True
    assert report["authorized_to_train"] is False
    out = tmp_path / "policy_visual_input_audit.json"
    out.write_text(json.dumps(report["visual_allowlist_B"], indent=2) + "\n")
    payload = json.loads(out.read_text())
    assert payload["number_of_policy_cameras"] == 2
    assert payload["passed"] is True


def test_phase1_audit_rejects_tactile_video_tree(tmp_path: Path) -> None:
    import cv2
    from tests.test_smolvla_s3_recovery_decisions import P1

    source = tmp_path / "seed_tactile"
    (source / "meta").mkdir(parents=True)
    (source / "data" / "chunk-000").mkdir(parents=True)
    n = 5
    table = pa.table(
        {
            "observation.state": pa.array([[0.0] * 7] * n, type=pa.list_(pa.float32())),
            "observation.ee_pose": pa.array(
                [[0.4, 0.0, 0.05, 0, 0, 0, 1]] * n, type=pa.list_(pa.float32())
            ),
            "observation.object_pose": pa.array(
                [[0.4, 0.0, 0.025, 0, 0, 0, 1]] * n, type=pa.list_(pa.float32())
            ),
            "observation.gripper": pa.array([1.0] * n, type=pa.float32()),
            "action": pa.array(
                [[0.4, 0.0, 0.05, 0, 0, 0, 1, 1.0]] * n, type=pa.list_(pa.float32())
            ),
            "timestamp": pa.array([0.1 * i for i in range(n)], type=pa.float32()),
        }
    )
    pq.write_table(table, source / "data" / "chunk-000" / "episode_000000.parquet")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    for cam in ("observation.images.scene", "observation.images.wrist", "observation.images.tactile_left"):
        cam_dir = source / "videos" / "chunk-000" / cam
        cam_dir.mkdir(parents=True)
        writer = cv2.VideoWriter(str(cam_dir / "episode_000000.mp4"), fourcc, 10.0, (32, 24))
        for _ in range(n):
            writer.write(np.full((24, 32, 3), 40, dtype=np.uint8))
        writer.release()
    (source / "meta" / "info.json").write_text(
        json.dumps({"total_episodes": 1, "total_frames": n}) + "\n", encoding="utf-8"
    )
    report = P1.audit_episode(source, 0)
    assert report["passed"] is False
    assert "observation.images.tactile_left" in report["visual_allowlist"]["unexpected_visual_keys"]


def test_wrist_ablation_phaseaware50_yaml_is_dual_camera_not_train() -> None:
    cfg = yaml.safe_load(
        (ROOT / "configs" / "smolvla_s3" / "wrist_ablation_v1_phaseaware50.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert cfg["release_id"] == (
        "smolvla_wrist_ablation_v1_panda_abs_eef_scene_wrist_phaseaware50"
    )
    assert cfg["release_id"] != "smolvla_s3_panda_abs_eef_scene_v3_phaseaware50"
    assert cfg["cameras"] == ["scene", "wrist"]
    assert cfg["enable_wrist_camera"] is True
    assert cfg["enable_tactile"] is False
    assert cfg["publish_depth"] is False
    assert cfg["authorized_to_train"] is False
    assert cfg["authorized_isaac"] is False
    assert cfg["splits"] == {"train": 36, "validation": 4, "benchmark": 10}
    assert set(cfg["positions"]) == {"P0", "P1", "P2", "P3", "P4"}
    assert cfg["positions"]["P0"]["seed"] == 60
    assert cfg["positions"]["P4"]["xy"] == [0.48, 0.00]
    assert cfg["phaseaware_thresholds"]["close_ramp_frames_min"] == 4
    v3 = yaml.safe_load(
        (ROOT / "configs" / "smolvla_s3" / "v3_phaseaware50.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert v3["phaseaware_thresholds"]["close_ramp_frames_min"] == 5
    assert v3["release_id"] == "smolvla_s3_panda_abs_eef_scene_v3_phaseaware50"


def _write_camera_mp4(
    root: Path, camera: str, ep: int, n_frames: int, color: tuple[int, int, int]
) -> Path:
    import cv2

    vid_dir = root / "videos" / "chunk-000" / f"observation.images.{camera}"
    vid_dir.mkdir(parents=True, exist_ok=True)
    video = vid_dir / f"episode_{ep:06d}.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (32, 24))
    frame = np.zeros((24, 32, 3), dtype=np.uint8)
    frame[:] = color
    for _ in range(n_frames):
        writer.write(frame)
    writer.release()
    return video


def _write_dual_camera_tree(
    tmp: Path, name: str, n_eps: int = 10, n_frames: int = 8
) -> Path:
    from tests.test_smolvla_s3_v3_phaseaware_release import _write_source_tree

    root = _write_source_tree(tmp, name, n_eps=n_eps)
    for ep in range(n_eps):
        scene = (
            root
            / "videos/chunk-000/observation.images.scene"
            / f"episode_{ep:06d}.mp4"
        )
        if not scene.is_file():
            import pytest

            pytest.skip("OpenCV mp4 writer unavailable")
        _write_camera_mp4(root, "wrist", ep, n_frames, (0, 0, 255))
    return root


def _load_prepare_mod():
    import importlib.util

    prep_path = ROOT / "training/scripts/prepare_smolvla_s3_release.py"
    spec = importlib.util.spec_from_file_location("prepare_smolvla_s3_release", prep_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_normalize_cameras_rejects_third_and_tactile() -> None:
    import pytest

    mod = _load_prepare_mod()
    assert mod._normalize_cameras(["scene"]) == ["scene"]
    assert mod._normalize_cameras(["scene", "wrist"]) == ["scene", "wrist"]
    with pytest.raises(ValueError, match="scene,wrist"):
        mod._normalize_cameras(["scene", "wrist", "tactile_left"])
    with pytest.raises(ValueError, match="scene,wrist"):
        mod._normalize_cameras(["wrist"])


def test_dual_camera_release_hashes_wrist_and_rejects_tactile(tmp_path: Path) -> None:
    import sys

    import pytest

    from training.scripts.validate_smolvla_s3_release import validate_release

    mod = _load_prepare_mod()
    sources = []
    pos_map = {}
    for i, pid in enumerate(["P0", "P1", "P2", "P3", "P4"]):
        name = (
            f"e2_red_500hz_seed{60 + i}_wrist_ablation_v1_{pid}_phaseaware10_fixture"
        )
        root = _write_dual_camera_tree(tmp_path, name, n_eps=10)
        sources.append(root)
        pos_map[name] = pid

    pos_json = tmp_path / "position_map.json"
    pos_json.write_text(json.dumps(pos_map) + "\n", encoding="utf-8")
    out = tmp_path / "release_wrist"
    argv = [
        "prepare_smolvla_s3_release.py",
        "--output-dir",
        str(out),
        "--release-id",
        "smolvla_wrist_ablation_v1_panda_abs_eef_scene_wrist_phaseaware50",
        "--split-policy",
        "phaseaware50",
        "--compose-state15",
        "--position-map-json",
        str(pos_json),
        "--cameras",
        "scene,wrist",
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
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["cameras"] == ["scene", "wrist"]
    assert manifest["visual_allowlist_variant"] == "B_scene_wrist"
    assert manifest["number_of_policy_cameras"] == 2
    assert manifest["wrist_rgb_complete_rate"] == 1.0
    index_rows = [
        json.loads(line)
        for line in (out / "episode_index.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert all(row.get("wrist_rgb_complete") for row in index_rows)
    assert all(row.get("wrist_video_sha256") for row in index_rows)
    report = validate_release(out)
    assert report["passed"] is True, report["errors"]

    dual = _write_dual_camera_tree(tmp_path, "tactile_src", n_eps=1)
    (dual / "videos/chunk-000/observation.images.tactile_left").mkdir()
    with pytest.raises(ValueError, match="visual allowlist failed"):
        mod._load_episodes(dual, cameras=["scene", "wrist"])

    dual_a = _write_dual_camera_tree(tmp_path, "dual_for_a", n_eps=1)
    with pytest.raises(ValueError, match="visual allowlist failed"):
        mod._load_episodes(dual_a, cameras=["scene"])
