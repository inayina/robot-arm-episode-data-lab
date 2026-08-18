"""Frozen H_knuckle_z05 wrist-camera geometry contract (simulation DESIGN_NOMINAL).

Old Phase-1 Hold used B_look_fingers (inside palm). That pose is forbidden here.
This module only audits XML / candidate IDs. It does not remount the camera.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

DEFAULT_UPSTREAM_XML = Path(
    "/home/ina/dev/ros2-arm-teleoperation-suite/config/models/franka_panda.xml"
)

H_KNUCKLE_Z05 = {
    "candidate_id": "H_knuckle_z05",
    "pose_class": "DESIGN_NOMINAL",
    "pos": (0.0, 0.0, 0.05),
    "xyaxes": (1.0, 0.0, 0.0, 0.0, -1.0, 0.0),
    "fovy_deg": 70.0,
}

# Historical inside-palm mount. Must not appear in the live XML.
B_LOOK_FINGERS = {
    "candidate_id": "B_look_fingers",
    "pos": (0.0, 0.0, -0.02),
}

_CAMERA_RE = re.compile(
    r'<camera name="wrist_camera"\s+pos="([^"]+)"\s+xyaxes="([^"]+)"\s+fovy="([^"]+)"\s*/>'
)


def _floats(text: str) -> tuple[float, ...]:
    return tuple(float(part) for part in text.split())


def parse_wrist_camera_xml(xml_text: str) -> dict[str, Any]:
    match = _CAMERA_RE.search(xml_text)
    if match is None:
        raise ValueError("wrist_camera element not found in XML")
    pos = _floats(match.group(1))
    xyaxes = _floats(match.group(2))
    fovy = float(match.group(3))
    if len(pos) != 3 or len(xyaxes) != 6:
        raise ValueError(f"unexpected wrist_camera pose encoding: {match.group(0)}")
    return {"pos": pos, "xyaxes": xyaxes, "fovy_deg": fovy, "raw": match.group(0)}


def _close(left: tuple[float, ...], right: tuple[float, ...], atol: float = 1e-6) -> bool:
    if len(left) != len(right):
        return False
    return all(abs(a - b) <= atol for a, b in zip(left, right, strict=True))


def audit_wrist_geometry(
    xml_path: Path | None = None, *, xml_text: str | None = None
) -> dict[str, Any]:
    path = Path(xml_path) if xml_path is not None else DEFAULT_UPSTREAM_XML
    text = xml_text if xml_text is not None else path.read_text(encoding="utf-8")
    parsed = parse_wrist_camera_xml(text)
    matches_h = (
        _close(parsed["pos"], H_KNUCKLE_Z05["pos"])
        and _close(parsed["xyaxes"], H_KNUCKLE_Z05["xyaxes"])
        and abs(parsed["fovy_deg"] - H_KNUCKLE_Z05["fovy_deg"]) <= 1e-6
    )
    matches_b = _close(parsed["pos"], B_LOOK_FINGERS["pos"])
    failures: list[str] = []
    if not matches_h:
        failures.append("xml_wrist_pose_is_not_H_knuckle_z05")
    if matches_b:
        failures.append("xml_wrist_pose_matches_historical_B_look_fingers")
    if "B_look_fingers" in text and matches_b:
        failures.append("historical_B_look_fingers_contamination")
    return {
        "xml_path": str(path),
        "expected_candidate_id": H_KNUCKLE_Z05["candidate_id"],
        "expected": {
            "pos": list(H_KNUCKLE_Z05["pos"]),
            "xyaxes": list(H_KNUCKLE_Z05["xyaxes"]),
            "fovy_deg": H_KNUCKLE_Z05["fovy_deg"],
            "pose_class": H_KNUCKLE_Z05["pose_class"],
        },
        "parsed": {
            "pos": list(parsed["pos"]),
            "xyaxes": list(parsed["xyaxes"]),
            "fovy_deg": parsed["fovy_deg"],
            "raw": parsed["raw"],
        },
        "matches_H_knuckle_z05": matches_h,
        "matches_historical_B_look_fingers": matches_b,
        "orientation_flip_override_present": False,
        "failures": failures,
        "passed": not failures,
    }
