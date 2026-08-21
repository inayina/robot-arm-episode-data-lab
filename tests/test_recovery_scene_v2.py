from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = ROOT / "configs" / "smolvla_s3" / "recovery_scene_v2"
OBJECTS = {
    "object_red_box",
    "object_blue_cylinder",
    "object_green_sphere",
}
EXPECTED_RED = {
    "P0": (0.36, -0.10),
    "P1": (0.40, 0.10),
    "P2": (0.44, -0.06),
    "P3": (0.38, 0.06),
}
EXPECTED_DISTRACTORS = {
    "object_blue_cylinder": (0.55, -0.18),
    "object_green_sphere": (0.55, 0.18),
}


def test_scene_v2_fixes_all_objects_with_safe_separation() -> None:
    for case_id, expected_red in EXPECTED_RED.items():
        payload = yaml.safe_load((CONFIG_ROOT / f"{case_id}.yaml").read_text())
        domain = payload["domain_randomization"]
        assert domain["enabled"] is True
        assert domain["seed"] == 42
        positions = domain["object"]["initial_pos_by_object"]
        assert set(positions) == OBJECTS
        assert tuple(positions["object_red_box"]) == expected_red
        for object_name, expected_xy in EXPECTED_DISTRACTORS.items():
            assert tuple(positions[object_name]) == expected_xy

        names = sorted(positions)
        for left_index, left_name in enumerate(names):
            for right_name in names[left_index + 1 :]:
                left = positions[left_name]
                right = positions[right_name]
                distance = math.hypot(left[0] - right[0], left[1] - right[1])
                assert distance >= 0.15, (
                    f"{case_id}: {left_name}/{right_name} separation {distance:.4f} m"
                )


def test_scene_v2_freezes_visual_and_red_yaw_contract() -> None:
    for case_id in EXPECTED_RED:
        payload = yaml.safe_load((CONFIG_ROOT / f"{case_id}.yaml").read_text())
        domain = payload["domain_randomization"]
        assert domain["camera"]["scene_camera"]["pos_noise"] == [0.0, 0.0]
        assert domain["camera"]["scene_camera"]["rot_noise"] == [0.0, 0.0]
        assert domain["lighting"]["key"]["diffuse_noise"] == [0.0, 0.0]
        assert domain["object"]["yaw_range_deg_by_object"]["object_red_box"] == [
            -6.74912045,
            -6.74912045,
        ]


def test_scene_v2_lock_matches_config_bytes_and_release_boundary() -> None:
    lock = json.loads((CONFIG_ROOT / "lock.json").read_text())
    assert lock["contract_version"] == "smolvla_recovery_scene_v2"
    assert lock["minimum_pairwise_xy_separation_m"] == 0.15
    assert lock["target_only_ablation_is_release_eligible"] is False
    for filename, expected_sha in lock["sha256"].items():
        actual_sha = hashlib.sha256((CONFIG_ROOT / filename).read_bytes()).hexdigest()
        assert actual_sha == expected_sha
