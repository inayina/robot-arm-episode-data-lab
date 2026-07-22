#!/usr/bin/env python3
"""Validate SmolVLA S3 canonical release (split leak, schema, hashes, gripper/quat)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RELEASE = ROOT / "data" / "releases" / "smolvla_s3_abs_eef_rgb_v0"


def _sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def validate_release(release_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    manifest_path = release_dir / "manifest.json"
    if not manifest_path.is_file():
        return {"passed": False, "errors": [f"missing {manifest_path}"], "warnings": []}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    splits = json.loads((release_dir / "splits.json").read_text(encoding="utf-8"))
    validation = json.loads(
        (release_dir / "validation_report.json").read_text(encoding="utf-8")
    )
    norms = json.loads((release_dir / "norm_stats.json").read_text(encoding="utf-8"))
    index_rows = [
        json.loads(line)
        for line in (release_dir / "episode_index.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    # hashes (except self-hash of manifest which includes itself — verify others)
    for name, expected in manifest.get("file_sha256", {}).items():
        if name == "manifest.json":
            continue
        path = release_dir / name
        if not path.is_file():
            errors.append(f"missing hashed file: {name}")
            continue
        got = _sha256_file(path)
        if got != expected:
            errors.append(f"hash mismatch {name}: expected {expected[:12]}… got {got[:12]}…")

    train = set(splits["train"])
    val = set(splits["validation"])
    bench = set(splits["benchmark"])
    if train & val or train & bench or val & bench:
        errors.append("split leakage detected")
    ids = {r["episode_id"] for r in index_rows}
    if train | val | bench != ids:
        errors.append("splits do not cover episode_index exactly")

    if manifest.get("policy_action_semantics") != "absolute_eef_gripper_v0":
        errors.append("wrong policy_action_semantics")
    if manifest.get("quaternion_order") != "xyzw":
        errors.append("quaternion_order must be xyzw")
    if float(manifest.get("scene_rgb_complete_rate", 0)) < 1.0:
        errors.append("scene_rgb_complete_rate < 1.0")

    for row in index_rows:
        if not row.get("rgb_complete"):
            errors.append(f"incomplete RGB: {row['episode_id']}")
        if int(row.get("action_dim", 0)) != 8:
            errors.append(f"action_dim!=8: {row['episode_id']}")
        if row.get("gripper_cmd_min", -1) < 0 or row.get("gripper_cmd_max", 2) > 1:
            errors.append(f"gripper_cmd out of [0,1]: {row['episode_id']}")
        if float(row.get("quat_norm_min", 0)) < 0.99 or float(row.get("quat_norm_max", 2)) > 1.01:
            errors.append(f"quat not unit: {row['episode_id']}")
        # source files must still exist and match hash (portable via S3_UPSTREAM_DATA_ROOT)
        upstream_root = Path(
            __import__("os").environ.get(
                "S3_UPSTREAM_DATA_ROOT",
                "/home/ina/dev/ros2-arm-teleoperation-suite/data",
            )
        )
        for kind in ("parquet", "video"):
            abs_key = f"{kind}_path"
            rel_key = f"{kind}_relpath"
            sha_key = f"{kind}_sha256"
            candidates = [Path(row[abs_key])]
            if rel_key in row:
                candidates.append(upstream_root / row[rel_key])
            found = next((p for p in candidates if p.is_file()), None)
            if found is None:
                errors.append(f"missing source {kind}: tried {candidates}")
                continue
            got = _sha256_file(found)
            if got != row[sha_key]:
                errors.append(f"source hash drift {found}")

    if norms.get("policy_action_semantics") != "absolute_eef_gripper_v0":
        errors.append("norm_stats semantics mismatch")
    if norms.get("computed_on_split") != "train":
        errors.append("norm_stats must be train-only")

    if not validation.get("passed"):
        errors.append("validation_report.passed is false")

    # refuse ACT delta release confusion
    if "ee_delta" in str(manifest.get("release_id", "")).lower():
        errors.append("release_id looks like ee_delta")

    required_fields = [
        "release_id",
        "source_commit_midstream",
        "num_episodes",
        "num_frames",
        "splits",
        "scene_rgb_complete_rate",
        "fields",
        "file_sha256",
        "schema_version",
    ]
    for f in required_fields:
        if f not in manifest:
            errors.append(f"manifest missing {f}")

    fields = manifest.get("fields", {})
    for key in (
        "joint_state",
        "gripper_measured",
        "gripper_cmd",
        "absolute_eef_xyz",
        "quaternion_xyzw",
        "language_instruction",
        "timestamps",
        "action_chunk_indices",
        "valid_mask",
    ):
        if key not in fields:
            errors.append(f"fields missing {key}")

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "release_id": manifest.get("release_id"),
        "num_episodes": manifest.get("num_episodes"),
        "num_frames": manifest.get("num_frames"),
        "go_no_go": "go" if not errors else "no_go",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    report = validate_release(args.release_dir)
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
