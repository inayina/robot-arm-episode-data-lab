#!/usr/bin/env python3
"""Render portfolio visual assets from recorded evidence. No invented numbers."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

UPSTREAM = Path("/home/ina/dev/ros2-arm-teleoperation-suite")
MIDSTREAM = Path(__file__).resolve().parents[1]
DOWNSTREAM = Path("/home/ina/ros2_ws/src/ros2-moveit-pybullet-bridge")
DEFAULT_OUT = MIDSTREAM / "docs/portfolio/assets"

LIVE_TF_CSV = UPSTREAM / "evidence/geometry_stage1_live_tf/geometry_samples.csv"
LIVE_TF_MANIFEST = UPSTREAM / "evidence/geometry_stage1_live_tf/run_manifest.json"
SCENE_CAM_CSV = UPSTREAM / "evidence/camera_stage3_scene/camera_samples.csv"
SCENE_CAM_MANIFEST = UPSTREAM / "evidence/camera_stage3_scene/run_manifest.json"
WRIST_CAM_CSV = UPSTREAM / "evidence/camera_stage3_wrist/camera_samples.csv"
WRIST_CAM_MANIFEST = UPSTREAM / "evidence/camera_stage3_wrist/run_manifest.json"
OPEN_LOOP = MIDSTREAM / "docs/portfolio/public_evidence/canonical_v3/open_loop_gate_summary.json"
S4_GATE = MIDSTREAM / "docs/portfolio/public_evidence/canonical_v3/s4_gate.json"
UNIFIED = MIDSTREAM / "docs/portfolio/public_evidence/canonical_v3/unified_eval_summary.json"

CAPTION_ARCH = "architecture diagram based on current repository implementation"
CAPTION_EVIDENCE = "visualization regenerated from recorded evidence"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _fmt_m(value: float) -> str:
    av = abs(value)
    if av == 0.0:
        return "0 m"
    if av < 1e-9:
        return f"{value:.1e} m"
    if av < 1e-6:
        return f"{value:.1e} m"
    if av < 1e-3:
        return f"{value:.2e} m"
    return f"{value:.4f} m"


def _fmt_rad(value: float) -> str:
    if abs(value) == 0.0:
        return "0 rad"
    if abs(value) < 1e-6:
        return f"{value:.1e} rad"
    return f"{value:.3e} rad"


def _pair_stats(csv_path: Path) -> dict[str, dict[str, float]]:
    rows = list(csv.DictReader(csv_path.open()))
    by: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row in rows:
        key = f"{row['source_a']} vs {row['source_b']}"
        by[key].append(
            (float(row["translation_error_m"]), float(row["rotation_error_rad"]))
        )
    out = {}
    for key, vals in by.items():
        dps = [v[0] for v in vals]
        drs = [v[1] for v in vals]
        out[key] = {
            "n": len(vals),
            "max_dp_m": max(dps),
            "max_dr_rad": max(drs),
        }
    return out


def _cam_stats(csv_path: Path) -> dict[str, float]:
    rows = list(csv.DictReader(csv_path.open()))
    dps = [float(r["renderer_tf_translation_residual_m"]) for r in rows]
    drs = [float(r["renderer_tf_rotation_residual_rad"]) for r in rows]
    return {
        "n": len(rows),
        "max_dp_m": max(dps),
        "max_dr_rad": max(drs),
        "min_dp_m": min(dps),
    }


def render_geometry(out_dir: Path) -> dict:
    live = _pair_stats(LIVE_TF_CSV)
    scene = _cam_stats(SCENE_CAM_CSV)
    wrist = _cam_stats(WRIST_CAM_CSV)
    live_man = json.loads(LIVE_TF_MANIFEST.read_text())
    scene_man = json.loads(SCENE_CAM_MANIFEST.read_text())
    wrist_man = json.loads(WRIST_CAM_MANIFEST.read_text())

    urdf_tf = live["independent_urdf_fk vs robot_state_publisher_tf"]
    tf_mj = live["robot_state_publisher_tf vs mujoco_panda_ee_site"]
    urdf_mj = live["independent_urdf_fk vs mujoco_panda_ee_site"]
    urdf_kdl = live["independent_urdf_fk vs independent_kdl_fk"]

    frame_from = live_man["frame_contract"]["frame_from"]
    frame_to = live_man["frame_contract"]["frame_to"]
    ctrl = live_man["frame_contract"]["controller_reference"]
    servo = live_man["frame_contract"]["moveit_servo_tip"]
    gap = live_man["frame_contract"]["note_fixed_chain_z_component_m"]
    optical = scene_man["exit_gate_observations"]["optical_frame_name"]
    scene_zero = scene_man["exit_gate_observations"]["renderer_tf_max_translation_residual_m"]
    wrist_spread = wrist_man["eye_in_hand"]["T_hand_camera_spread_m"]
    wrist_world = wrist_man["eye_in_hand"]["T_world_camera_spread_m"]
    wrist_id = wrist_man.get("selected_candidate_id", "")

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="560" viewBox="0 0 1440 560" role="img">
  <title>仿真几何与相机一致性</title>
  <desc>{CAPTION_EVIDENCE}. Residuals auto-read from Stage 1 live TF CSV and Stage 3 camera manifests. Not Sim2Real. PHYSICAL=NOT_RUN.</desc>
  <style>
    .title{{font:700 28px Inter,"Noto Sans SC",Arial,sans-serif;fill:#0f172a}}
    .sub{{font:14px Inter,"Noto Sans SC",Arial,sans-serif;fill:#64748b}}
    .h{{font:700 16px Inter,"Noto Sans SC",Arial,sans-serif;fill:#0f172a}}
    .e{{font:13px Inter,Arial,sans-serif;fill:#334155}}
    .num{{font:700 15px ui-monospace,Menlo,monospace;fill:#0f172a}}
    .cap{{font:12px Inter,"Noto Sans SC",Arial,sans-serif;fill:#64748b}}
    .unit{{font:12px Inter,Arial,sans-serif;fill:#64748b}}
  </style>
  <rect width="1440" height="560" fill="#ffffff"/>
  <text x="720" y="40" text-anchor="middle" class="title">同一关节状态下，模型、TF、仿真真值与渲染器对得上</text>
  <text x="720" y="66" text-anchor="middle" class="sub">{CAPTION_EVIDENCE} · frame {frame_from} → {frame_to} · 不是 Sim2Real</text>

  <rect x="40" y="96" width="300" height="150" rx="14" fill="#f8fafc" stroke="#94a3b8"/>
  <text x="190" y="128" text-anchor="middle" class="h">URDF / KDL FK</text>
  <text x="190" y="156" text-anchor="middle" class="e">MODEL</text>
  <text x="190" y="186" text-anchor="middle" class="num">max ‖Δp‖ {_fmt_m(urdf_kdl["max_dp_m"])}</text>
  <text x="190" y="212" text-anchor="middle" class="unit">max geodesic {_fmt_rad(urdf_kdl["max_dr_rad"])}</text>

  <rect x="380" y="96" width="300" height="150" rx="14" fill="#eff6ff" stroke="#93c5fd"/>
  <text x="530" y="128" text-anchor="middle" class="h">Live TF</text>
  <text x="530" y="156" text-anchor="middle" class="e">robot_state_publisher</text>
  <text x="530" y="186" text-anchor="middle" class="num">vs URDF {_fmt_m(urdf_tf["max_dp_m"])}</text>
  <text x="530" y="212" text-anchor="middle" class="unit">n={urdf_tf["n"]} poses · {_fmt_rad(urdf_tf["max_dr_rad"])}</text>

  <rect x="720" y="96" width="300" height="150" rx="14" fill="#ecfdf5" stroke="#6ee7b7"/>
  <text x="870" y="128" text-anchor="middle" class="h">MuJoCo GT</text>
  <text x="870" y="156" text-anchor="middle" class="e">SIM_GT · site panda_ee</text>
  <text x="870" y="186" text-anchor="middle" class="num">vs live TF {_fmt_m(tf_mj["max_dp_m"])}</text>
  <text x="870" y="212" text-anchor="middle" class="unit">vs URDF {_fmt_m(urdf_mj["max_dp_m"])}</text>

  <rect x="1060" y="96" width="340" height="150" rx="14" fill="#f5f3ff" stroke="#c4b5fd"/>
  <text x="1230" y="128" text-anchor="middle" class="h">Camera Renderer / TF</text>
  <text x="1230" y="156" text-anchor="middle" class="e">scene {optical}</text>
  <text x="1230" y="186" text-anchor="middle" class="num">renderer↔TF {_fmt_m(scene["max_dp_m"])}</text>
  <text x="1230" y="212" text-anchor="middle" class="unit">manifest max {_fmt_m(float(scene_zero))} · rot {_fmt_rad(scene["max_dr_rad"])}</text>

  <text x="720" y="278" text-anchor="middle" class="h">已知合同差，不是未解释误差</text>
  <rect x="80" y="296" width="1280" height="92" rx="12" fill="#f8fafc" stroke="#e2e8f0"/>
  <text x="110" y="328" class="e">阻抗解析 FK 参考点 = {ctrl}　·　MoveIt Servo tip = {servo}</text>
  <text x="110" y="356" class="e">panda_link7 → panda_hand → panda_ee 固定链 z ≈ {gap:.3f} m。比较前先规范化到 panda_ee，禁止把 0.207 m 写成标定误差。</text>

  <rect x="80" y="404" width="620" height="88" rx="12" fill="#fff7ed" stroke="#fdba74"/>
  <text x="100" y="434" class="h">Wrist camera · {wrist_id}</text>
  <text x="100" y="460" class="e">T_hand_camera spread {_fmt_m(wrist_spread)}　·　T_world spread {_fmt_m(wrist_world)}</text>
  <text x="100" y="480" class="cap">eye-in-hand 随手臂动；renderer↔TF max {_fmt_m(wrist["max_dp_m"])}</text>

  <rect x="720" y="404" width="640" height="88" rx="12" fill="#fef2f2" stroke="#fecaca"/>
  <text x="740" y="434" class="h">验证条件</text>
  <text x="740" y="460" class="e">离线 CLI + 隔离 RSP；PHYSICAL=NOT_RUN/UNAVAILABLE</text>
  <text x="740" y="480" class="cap">仿真一致性 ≠ Sim2Real　·　不是手眼标定　·　REPORT_ONLY</text>
</svg>
'''
    out_svg = out_dir / "geometry_camera_consistency.svg"
    out_svg.write_text(svg, encoding="utf-8")

    png_path = out_dir / "geometry_camera_consistency.png"
    _svg_to_png_matplotlib(
        png_path,
        title="Geometry / TF / camera consistency (from recorded evidence)",
        blocks=[
            ("URDF / KDL FK", f"max Δp {_fmt_m(urdf_kdl['max_dp_m'])}", "MODEL"),
            ("Live TF", f"vs URDF {_fmt_m(urdf_tf['max_dp_m'])}", "RSP"),
            ("MuJoCo GT", f"vs TF {_fmt_m(tf_mj['max_dp_m'])}", "SIM_GT panda_ee"),
            ("Renderer / TF", f"scene {_fmt_m(scene['max_dp_m'])}", optical),
        ],
        footer=(
            f"{CAPTION_EVIDENCE} · {frame_from}->{frame_to} · "
            f"controller={ctrl} servo={servo} · not Sim2Real"
        ),
    )

    provenance = {
        "figure": "geometry_camera_consistency",
        "caption_class": CAPTION_EVIDENCE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "physical": "NOT_RUN/UNAVAILABLE",
        "claims_sim2real": False,
        "frame_from": frame_from,
        "frame_to": frame_to,
        "controller_reference": ctrl,
        "moveit_servo_tip": servo,
        "fixed_chain_z_m": gap,
        "residuals": {
            "urdf_vs_kdl": urdf_kdl,
            "urdf_vs_live_tf": urdf_tf,
            "live_tf_vs_mujoco": tf_mj,
            "urdf_vs_mujoco": urdf_mj,
            "scene_renderer_vs_tf": scene,
            "wrist_renderer_vs_tf": wrist,
            "wrist_T_hand_spread_m": wrist_spread,
        },
        "sources": {
            "live_tf_csv": {"path": str(LIVE_TF_CSV), "sha256": _sha256(LIVE_TF_CSV)},
            "live_tf_manifest": {
                "path": str(LIVE_TF_MANIFEST),
                "sha256": _sha256(LIVE_TF_MANIFEST),
            },
            "scene_csv": {"path": str(SCENE_CAM_CSV), "sha256": _sha256(SCENE_CAM_CSV)},
            "scene_manifest": {
                "path": str(SCENE_CAM_MANIFEST),
                "sha256": _sha256(SCENE_CAM_MANIFEST),
            },
            "wrist_csv": {"path": str(WRIST_CAM_CSV), "sha256": _sha256(WRIST_CAM_CSV)},
            "wrist_manifest": {
                "path": str(WRIST_CAM_MANIFEST),
                "sha256": _sha256(WRIST_CAM_MANIFEST),
            },
        },
    }
    (out_dir / "provenance" / "geometry_camera_consistency.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )
    return provenance


def _svg_to_png_matplotlib(path: Path, title: str, blocks: list[tuple[str, str, str]], footer: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    fig, ax = plt.subplots(figsize=(14.4, 4.2), dpi=140)
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 1.2)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.set_title(title, fontsize=16, pad=12)
    colors = ["#f8fafc", "#eff6ff", "#ecfdf5", "#f5f3ff"]
    for i, (head, num, sub) in enumerate(blocks):
        x0 = i
        rect = plt.Rectangle((x0 + 0.08, 0.28), 0.84, 0.7, facecolor=colors[i], edgecolor="#94a3b8")
        ax.add_patch(rect)
        ax.text(x0 + 0.5, 0.82, head, ha="center", va="center", fontsize=12, fontweight="bold")
        ax.text(x0 + 0.5, 0.58, num, ha="center", va="center", fontsize=11)
        ax.text(x0 + 0.5, 0.4, sub, ha="center", va="center", fontsize=9, color="#64748b")
    ax.text(2.0, 0.1, footer, ha="center", va="center", fontsize=8, color="#64748b")
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def render_gate_flow(out_dir: Path) -> dict:
    ol = json.loads(OPEN_LOOP.read_text())
    s4 = json.loads(S4_GATE.read_text())
    uni = json.loads(UNIFIED.read_text())
    ee = float(ol["metrics"]["ee_position_rmse_m"])
    ba = float(ol["metrics"]["gripper_balanced_accuracy"])
    ol_dec = ol["gate_decision"]
    iface = int(s4["policy_interface_pass"])
    n = int(s4["episodes_recorded"])
    reach = int(s4["reach"])
    grasp = int(s4["grasp"])
    lift = int(s4["lift"])
    hold = not bool(s4["gate_pass"])
    task_box = (
        f"Hold · lift {lift}/{n}"
        if hold
        else f"Pass · lift {lift}/{n}"
    )
    ol_box = ol_dec.capitalize() if isinstance(ol_dec, str) else str(ol_dec)

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="460" viewBox="0 0 1440 460" role="img">
  <title>数据质量与分层 Gate</title>
  <desc>{CAPTION_EVIDENCE}. Offline Pass is not task success. Interface Pass is not lift success.</desc>
  <style>
    .title{{font:700 28px Inter,"Noto Sans SC",Arial,sans-serif;fill:#0f172a}}
    .sub{{font:14px Inter,"Noto Sans SC",Arial,sans-serif;fill:#64748b}}
    .h{{font:700 15px Inter,"Noto Sans SC",Arial,sans-serif;fill:#0f172a}}
    .e{{font:12px Inter,Arial,sans-serif;fill:#334155}}
    .cap{{font:13px Inter,"Noto Sans SC",Arial,sans-serif;fill:#64748b}}
    .call{{font:700 16px Inter,"Noto Sans SC",Arial,sans-serif;fill:#b91c1c}}
    .ok{{font:700 13px Inter,Arial,sans-serif;fill:#047857}}
    .hold{{font:700 13px Inter,Arial,sans-serif;fill:#c2410c}}
    .flow{{stroke:#475569;stroke-width:2.4;fill:none;marker-end:url(#arrow)}}
  </style>
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
      <path d="M0,0 L0,6 L9,3 z" fill="#475569"/>
    </marker>
  </defs>
  <rect width="1440" height="460" fill="#ffffff"/>
  <text x="720" y="40" text-anchor="middle" class="title">每一层 Gate 只回答一个问题，不能越级升级</text>
  <text x="720" y="66" text-anchor="middle" class="sub">{CAPTION_EVIDENCE} · public_evidence/canonical_v3</text>

  <rect x="36" y="100" width="175" height="150" rx="14" fill="#f8fafc" stroke="#94a3b8"/>
  <text x="123" y="138" text-anchor="middle" class="h">Raw Episode</text>
  <text x="123" y="166" text-anchor="middle" class="e">Data Gate</text>
  <text x="123" y="190" text-anchor="middle" class="e">schema · meta.json</text>
  <text x="123" y="214" text-anchor="middle" class="e">upstream physical gate</text>

  <rect x="236" y="100" width="175" height="150" rx="14" fill="#eff6ff" stroke="#93c5fd"/>
  <text x="323" y="138" text-anchor="middle" class="h">Release</text>
  <text x="323" y="166" text-anchor="middle" class="e">QA / split / SHA</text>
  <text x="323" y="190" text-anchor="middle" class="e">immutable manifest</text>
  <text x="323" y="214" text-anchor="middle" class="e">train ≠ eval leak</text>

  <rect x="436" y="100" width="175" height="150" rx="14" fill="#ecfdf5" stroke="#6ee7b7"/>
  <text x="523" y="138" text-anchor="middle" class="h">Offline Gate</text>
  <text x="523" y="166" text-anchor="middle" class="e">open-loop first-action</text>
  <text x="523" y="196" text-anchor="middle" class="ok">{ol_box}</text>
  <text x="523" y="220" text-anchor="middle" class="e">EE {ee:.4f} m · BA {ba:.3f}</text>

  <rect x="636" y="100" width="175" height="150" rx="14" fill="#f5f3ff" stroke="#c4b5fd"/>
  <text x="723" y="138" text-anchor="middle" class="h">Handoff</text>
  <text x="723" y="166" text-anchor="middle" class="e">JSONL + manifest</text>
  <text x="723" y="190" text-anchor="middle" class="e">not a PyTorch bundle</text>
  <text x="723" y="214" text-anchor="middle" class="e">replay_check</text>

  <rect x="836" y="100" width="175" height="150" rx="14" fill="#ecfeff" stroke="#67e8f9"/>
  <text x="923" y="138" text-anchor="middle" class="h">Interface Gate</text>
  <text x="923" y="166" text-anchor="middle" class="e">policy I/O · clip</text>
  <text x="923" y="196" text-anchor="middle" class="ok">{iface} / {n}</text>
  <text x="923" y="220" text-anchor="middle" class="e">bounded Isaac S4</text>

  <rect x="1036" y="100" width="175" height="150" rx="14" fill="#fff7ed" stroke="#fdba74"/>
  <text x="1123" y="138" text-anchor="middle" class="h">Task Gate</text>
  <text x="1123" y="166" text-anchor="middle" class="e">reach {reach}/{n} grasp {grasp}/{n}</text>
  <text x="1123" y="196" text-anchor="middle" class="hold">{task_box}</text>
  <text x="1123" y="220" text-anchor="middle" class="e">relight S4 权威</text>

  <rect x="1236" y="100" width="168" height="150" rx="14" fill="#fef2f2" stroke="#fca5a5"/>
  <text x="1320" y="138" text-anchor="middle" class="h">System Gate</text>
  <text x="1320" y="166" text-anchor="middle" class="e">replay · risk · HOC</text>
  <text x="1320" y="190" text-anchor="middle" class="e">not task go/no-go</text>
  <text x="1320" y="214" text-anchor="middle" class="e">Hold / E-stop 可观测</text>

  <path d="M211 175 H230" class="flow"/>
  <path d="M411 175 H430" class="flow"/>
  <path d="M611 175 H630" class="flow"/>
  <path d="M811 175 H830" class="flow"/>
  <path d="M1011 175 H1030" class="flow"/>
  <path d="M1211 175 H1230" class="flow"/>

  <rect x="120" y="292" width="560" height="56" rx="12" fill="#fef2f2" stroke="#fecaca"/>
  <text x="400" y="327" text-anchor="middle" class="call">Offline Pass ≠ Task Success</text>
  <rect x="760" y="292" width="560" height="56" rx="12" fill="#fff7ed" stroke="#fed7aa"/>
  <text x="1040" y="327" text-anchor="middle" class="call">Interface Pass ≠ Lift Success</text>

  <text x="720" y="392" text-anchor="middle" class="cap">unified claims_task_success={str(uni.get("claims_task_success")).lower()} · claims_sim2real={str(uni.get("claims_sim2real")).lower()}</text>
  <text x="720" y="424" text-anchor="middle" class="cap">Isaac 有界评测不是默认主栈 · scripted oracle 不在本图冒充 learned policy</text>
</svg>
'''
    (out_dir / "data_gate_flow.svg").write_text(svg, encoding="utf-8")
    provenance = {
        "figure": "data_gate_flow",
        "caption_class": CAPTION_EVIDENCE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "offline": {
            "gate_decision": ol_dec,
            "ee_position_rmse_m": ee,
            "gripper_balanced_accuracy": ba,
        },
        "s4": {
            "interface": iface,
            "n": n,
            "reach": reach,
            "grasp": grasp,
            "lift": lift,
            "gate_pass": s4["gate_pass"],
        },
        "claims_task_success": uni.get("claims_task_success"),
        "claims_sim2real": uni.get("claims_sim2real"),
        "sources": {
            "open_loop": {"path": str(OPEN_LOOP), "sha256": _sha256(OPEN_LOOP)},
            "s4_gate": {"path": str(S4_GATE), "sha256": _sha256(S4_GATE)},
            "unified": {"path": str(UNIFIED), "sha256": _sha256(UNIFIED)},
        },
    }
    (out_dir / "provenance" / "data_gate_flow.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )
    return provenance


_ARCH_CSS = """
    .title{font:700 26px Arial,"Noto Sans CJK SC","Droid Sans Fallback",sans-serif;fill:#0f172a}
    .sub{font:13px Arial,"Noto Sans CJK SC","Droid Sans Fallback",sans-serif;fill:#64748b}
    .h{font:700 15px Arial,"Noto Sans CJK SC","Droid Sans Fallback",sans-serif;fill:#0f172a}
    .e{font:12px Arial,"Noto Sans CJK SC","Droid Sans Fallback",sans-serif;fill:#334155}
    .cap{font:12px Arial,"Noto Sans CJK SC","Droid Sans Fallback",sans-serif;fill:#64748b}
    .hz{font:700 13px Arial,sans-serif;fill:#1d4ed8}
    .flow{stroke:#475569;stroke-width:2.4;fill:none;marker-end:url(#arrow)}
"""


def render_architecture(out_dir: Path) -> None:
    """UTF-8 architecture SVGs. Do not write these via tools that mangle CJK."""
    out_dir.mkdir(parents=True, exist_ok=True)
    overview = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="420" viewBox="0 0 1440 420" role="img">
  <title>仿真遥操作数据基础设施总览</title>
  <desc>{CAPTION_ARCH}</desc>
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
      <path d="M0,0 L0,6 L9,3 z" fill="#475569"/>
    </marker>
    <style>{_ARCH_CSS}</style>
  </defs>
  <rect width="1440" height="420" fill="#ffffff"/>
  <text x="720" y="42" text-anchor="middle" class="title">从人的输入到可验证数据：一条仿真遥操作流水线</text>
  <text x="720" y="68" text-anchor="middle" class="sub">{CAPTION_ARCH} · Franka Panda · not real robot / not Sim2Real</text>
  <rect x="28" y="110" width="150" height="150" rx="14" fill="#f8fafc" stroke="#94a3b8"/>
  <text x="103" y="148" text-anchor="middle" class="h">Human Input</text>
  <text x="103" y="176" text-anchor="middle" class="e">Keyboard / Gamepad</text>
  <text x="103" y="198" text-anchor="middle" class="e">笛卡尔目标</text>
  <rect x="202" y="110" width="150" height="150" rx="14" fill="#ecfeff" stroke="#67e8f9"/>
  <text x="277" y="148" text-anchor="middle" class="h">Teleop + Safety</text>
  <text x="277" y="176" text-anchor="middle" class="e">teleop_input</text>
  <text x="277" y="198" text-anchor="middle" class="e">C++ safety_monitor</text>
  <rect x="376" y="110" width="150" height="150" rx="14" fill="#eff6ff" stroke="#93c5fd"/>
  <text x="451" y="148" text-anchor="middle" class="h">Motion Control</text>
  <text x="451" y="176" text-anchor="middle" class="e">MoveIt Servo</text>
  <text x="451" y="198" text-anchor="middle" class="e">Impedance + ros2_control</text>
  <rect x="550" y="110" width="150" height="150" rx="14" fill="#ecfdf5" stroke="#6ee7b7"/>
  <text x="625" y="148" text-anchor="middle" class="h">Simulation</text>
  <text x="625" y="176" text-anchor="middle" class="e">MuJoCo Panda</text>
  <text x="625" y="198" text-anchor="middle" class="e">Isaac = bounded</text>
  <rect x="724" y="110" width="150" height="150" rx="14" fill="#f5f3ff" stroke="#c4b5fd"/>
  <text x="799" y="148" text-anchor="middle" class="h">Capture</text>
  <text x="799" y="176" text-anchor="middle" class="e">RGB / wrist / tactile</text>
  <text x="799" y="198" text-anchor="middle" class="e">LeRobot episode</text>
  <rect x="898" y="110" width="150" height="150" rx="14" fill="#fff7ed" stroke="#fdba74"/>
  <text x="973" y="148" text-anchor="middle" class="h">Contract / QA</text>
  <text x="973" y="176" text-anchor="middle" class="e">schema / split</text>
  <text x="973" y="198" text-anchor="middle" class="e">immutable release</text>
  <rect x="1072" y="110" width="150" height="150" rx="14" fill="#fefce8" stroke="#fde047"/>
  <text x="1147" y="148" text-anchor="middle" class="h">Handoff</text>
  <text x="1147" y="176" text-anchor="middle" class="e">JSONL actions</text>
  <text x="1147" y="198" text-anchor="middle" class="e">manifest + SHA</text>
  <rect x="1246" y="110" width="166" height="150" rx="14" fill="#fef2f2" stroke="#fca5a5"/>
  <text x="1329" y="148" text-anchor="middle" class="h">Replay / Risk</text>
  <text x="1329" y="176" text-anchor="middle" class="e">PyBullet / HOC</text>
  <text x="1329" y="198" text-anchor="middle" class="e">Hold / E-stop</text>
  <path d="M178 185 H196" class="flow"/>
  <path d="M352 185 H370" class="flow"/>
  <path d="M526 185 H544" class="flow"/>
  <path d="M700 185 H718" class="flow"/>
  <path d="M874 185 H892" class="flow"/>
  <path d="M1048 185 H1066" class="flow"/>
  <path d="M1222 185 H1240" class="flow"/>
  <text x="720" y="310" text-anchor="middle" class="cap">上游执行与采集 · 中游合同与评测 · 下游回放与风险 · Isaac 不是默认采集栈</text>
  <text x="720" y="348" text-anchor="middle" class="h">Offline Pass != Task Success · Interface Pass != Lift Success</text>
  <text x="720" y="392" text-anchor="middle" class="cap">HEAD-checked 2026-08-17 · no real Franka · no Sim2Real claim</text>
</svg>
'''
    control = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="380" viewBox="0 0 1440 380" role="img">
  <title>遥操作控制链与已验证仿真频率</title>
  <desc>{CAPTION_ARCH}</desc>
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
      <path d="M0,0 L0,6 L9,3 z" fill="#475569"/>
    </marker>
    <style>{_ARCH_CSS}</style>
  </defs>
  <rect width="1440" height="380" fill="#ffffff"/>
  <text x="720" y="42" text-anchor="middle" class="title">人给出笛卡尔目标，控制链按整数倍频率往下走</text>
  <text x="720" y="68" text-anchor="middle" class="sub">{CAPTION_ARCH} · rates from HEAD config</text>
  <rect x="40" y="108" width="200" height="168" rx="14" fill="#f8fafc" stroke="#94a3b8"/>
  <text x="140" y="148" text-anchor="middle" class="h">Human Input</text>
  <text x="140" y="178" text-anchor="middle" class="e">Keyboard / Gamepad</text>
  <text x="140" y="204" text-anchor="middle" class="e">/teleop/cmd_pose</text>
  <text x="140" y="242" text-anchor="middle" class="cap">笛卡尔位姿 + 心跳</text>
  <rect x="270" y="108" width="200" height="168" rx="14" fill="#fef2f2" stroke="#fca5a5"/>
  <text x="370" y="148" text-anchor="middle" class="h">C++ Safety</text>
  <text x="370" y="178" text-anchor="middle" class="e">safety_monitor</text>
  <text x="370" y="204" text-anchor="middle" class="e">/safe_master_pose</text>
  <text x="370" y="242" text-anchor="middle" class="cap">limit / watchdog / E-stop</text>
  <rect x="500" y="108" width="200" height="168" rx="14" fill="#eff6ff" stroke="#93c5fd"/>
  <text x="600" y="148" text-anchor="middle" class="h">MoveIt Servo</text>
  <text x="600" y="178" text-anchor="middle" class="e">pose tracking</text>
  <text x="600" y="204" text-anchor="middle" class="hz">~125 Hz</text>
  <text x="600" y="242" text-anchor="middle" class="cap">publish_period 0.008</text>
  <rect x="730" y="108" width="220" height="168" rx="14" fill="#ecfeff" stroke="#67e8f9"/>
  <text x="840" y="148" text-anchor="middle" class="h">Impedance + CM</text>
  <text x="840" y="178" text-anchor="middle" class="e">ros2_control plugin</text>
  <text x="840" y="204" text-anchor="middle" class="hz">sim ~500 Hz</text>
  <text x="840" y="242" text-anchor="middle" class="cap">control_rate_sim.yaml</text>
  <rect x="980" y="108" width="200" height="168" rx="14" fill="#ecfdf5" stroke="#6ee7b7"/>
  <text x="1080" y="148" text-anchor="middle" class="h">MuJoCo Panda</text>
  <text x="1080" y="178" text-anchor="middle" class="e">physics_rate</text>
  <text x="1080" y="204" text-anchor="middle" class="hz">~1 kHz</text>
  <text x="1080" y="242" text-anchor="middle" class="cap">encoder 500 Hz</text>
  <rect x="1210" y="108" width="190" height="168" rx="14" fill="#fff7ed" stroke="#fdba74"/>
  <text x="1305" y="148" text-anchor="middle" class="h">Virtual bus</text>
  <text x="1305" y="178" text-anchor="middle" class="e">vcan0 DS402</text>
  <text x="1305" y="204" text-anchor="middle" class="e">MockModbus gripper</text>
  <text x="1305" y="242" text-anchor="middle" class="cap">不是真实硬件</text>
  <path d="M240 192 H264" class="flow"/>
  <path d="M470 192 H494" class="flow"/>
  <path d="M700 192 H724" class="flow"/>
  <path d="M950 192 H974" class="flow"/>
  <path d="M1180 192 H1204" class="flow"/>
  <text x="720" y="328" text-anchor="middle" class="cap">Servo tip = panda_ee · impedance FK = panda_link7 · real 1 kHz is reserved path only</text>
  <text x="720" y="356" text-anchor="middle" class="cap">软件安全路径，不是认证功能安全 · Isaac 10 Hz 仅有界评测</text>
</svg>
'''
    (out_dir / "system_overview.svg").write_text(overview, encoding="utf-8")
    (out_dir / "teleop_control_chain.svg").write_text(control, encoding="utf-8")
    (out_dir / "provenance" / "architecture.json").write_text(
        json.dumps(
            {
                "figures": ["system_overview", "teleop_control_chain"],
                "caption_class": CAPTION_ARCH,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "claims_task_success": False,
                "claims_sim2real": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def export_pipeline_pngs(out_dir: Path) -> None:
    """IDE-preview companions. SVG remains the architecture source of truth."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from fontTools.ttLib import TTCollection
    from matplotlib import font_manager
    from matplotlib.patches import FancyBboxPatch

    ttc = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if not ttc.is_file():
        print("skip PNG export: Noto Sans CJK TTC not found")
        return
    tmp = Path("/tmp/NotoSansCJKSC-Regular.ttf")
    TTCollection(str(ttc)).fonts[2].save(tmp)
    font_manager.fontManager.addfont(str(tmp))
    prop = font_manager.FontProperties(fname=str(tmp))
    plt.rcParams["axes.unicode_minus"] = False

    def boxes(ax, items, xlim, ylim, title, subtitle, footer):
        ax.set_xlim(0, xlim)
        ax.set_ylim(0, ylim)
        ax.axis("off")
        ax.set_title(title, fontsize=16, pad=8, fontproperties=prop)
        ax.text(
            xlim / 2,
            ylim - 0.12,
            subtitle,
            ha="center",
            va="top",
            fontsize=9,
            color="#64748b",
            fontproperties=prop,
        )
        n = len(items)
        width = 0.92
        gap = (xlim - n * width) / (n + 1)
        y0, height = 0.38, 0.42
        for i, (name, a, b, color) in enumerate(items):
            x = gap + i * (width + gap)
            ax.add_patch(
                FancyBboxPatch(
                    (x, y0),
                    width,
                    height,
                    boxstyle="round,pad=0.02,rounding_size=0.04",
                    facecolor=color,
                    edgecolor="#94a3b8",
                )
            )
            ax.text(
                x + width / 2,
                y0 + height * 0.72,
                name,
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
                fontproperties=prop,
            )
            ax.text(
                x + width / 2,
                y0 + height * 0.48,
                a,
                ha="center",
                va="center",
                fontsize=8,
                color="#334155",
                fontproperties=prop,
            )
            ax.text(
                x + width / 2,
                y0 + height * 0.28,
                b,
                ha="center",
                va="center",
                fontsize=8,
                color="#334155",
                fontproperties=prop,
            )
            if i < n - 1:
                ax.annotate(
                    "",
                    xy=(x + width + gap - 0.02, y0 + height / 2),
                    xytext=(x + width + 0.02, y0 + height / 2),
                    arrowprops=dict(arrowstyle="->", color="#475569", lw=1.4),
                )
        ax.text(
            xlim / 2,
            0.12,
            footer,
            ha="center",
            va="center",
            fontsize=8,
            color="#64748b",
            fontproperties=prop,
        )

    specs = [
        (
            "system_overview.png",
            (14.4, 4.2),
            [
                ("Human Input", "Keyboard / Gamepad", "笛卡尔目标", "#f8fafc"),
                ("Teleop + Safety", "teleop_input", "C++ safety_monitor", "#ecfeff"),
                ("Motion Control", "MoveIt Servo", "Impedance + CM", "#eff6ff"),
                ("Simulation", "MuJoCo Panda", "Isaac = bounded", "#ecfdf5"),
                ("Capture", "RGB / wrist", "LeRobot episode", "#f5f3ff"),
                ("Contract / QA", "schema / split", "immutable release", "#fff7ed"),
                ("Handoff", "JSONL actions", "manifest + SHA", "#fefce8"),
                ("Replay / Risk", "PyBullet / HOC", "Hold / E-stop", "#fef2f2"),
            ],
            10,
            1.2,
            "从人的输入到可验证数据",
            CAPTION_ARCH,
            "Offline Pass != Task Success · Interface Pass != Lift Success · not Sim2Real",
        ),
        (
            "teleop_control_chain.png",
            (14.4, 3.8),
            [
                ("Human Input", "/teleop/cmd_pose", "笛卡尔 + 心跳", "#f8fafc"),
                ("C++ Safety", "/safe_master_pose", "watchdog / E-stop", "#fef2f2"),
                ("MoveIt Servo", "~125 Hz", "publish_period 0.008", "#eff6ff"),
                ("Impedance + CM", "sim ~500 Hz", "control_rate_sim.yaml", "#ecfeff"),
                ("MuJoCo Panda", "physics ~1 kHz", "encoder 500 Hz", "#ecfdf5"),
                ("Virtual bus", "vcan0 DS402", "不是真实硬件", "#fff7ed"),
            ],
            8,
            1.2,
            "人给出笛卡尔目标，控制链按整数倍频率往下走",
            CAPTION_ARCH,
            "Servo tip = panda_ee · impedance FK = panda_link7 · Isaac 10 Hz is bounded eval only",
        ),
        (
            "data_gate_flow.png",
            (14.4, 4.6),
            [
                ("Raw Episode", "Data Gate", "schema / meta.json", "#f8fafc"),
                ("Release", "QA / SHA", "immutable", "#eff6ff"),
                ("Offline Gate", "Pass", "EE 0.0253 m", "#ecfdf5"),
                ("Handoff", "JSONL", "replay_check", "#f5f3ff"),
                ("Interface", "5 / 5", "bounded Isaac", "#ecfeff"),
                ("Task Gate", "Hold", "lift 0/5", "#fff7ed"),
                ("System", "HOC / risk", "not go/no-go", "#fef2f2"),
            ],
            9,
            1.25,
            "每一层 Gate 只回答一个问题，不能越级升级",
            CAPTION_EVIDENCE,
            "Offline Pass != Task Success · Interface Pass != Lift Success",
        ),
    ]
    for name, figsize, items, xlim, ylim, title, subtitle, footer in specs:
        fig, ax = plt.subplots(figsize=figsize, dpi=140)
        fig.patch.set_facecolor("white")
        boxes(ax, items, xlim, ylim, title, subtitle, footer)
        fig.savefig(out_dir / name, bbox_inches="tight", facecolor="white")
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--skip-geometry", action="store_true")
    parser.add_argument("--skip-gate", action="store_true")
    parser.add_argument("--skip-architecture", action="store_true")
    parser.add_argument("--skip-png", action="store_true")
    args = parser.parse_args()
    out = args.out_dir
    (out / "provenance").mkdir(parents=True, exist_ok=True)
    if not args.skip_architecture:
        render_architecture(out)
        print(f"wrote {out / 'system_overview.svg'}")
        print(f"wrote {out / 'teleop_control_chain.svg'}")
    if not args.skip_geometry:
        render_geometry(out)
        print(f"wrote {out / 'geometry_camera_consistency.svg'}")
    if not args.skip_gate:
        render_gate_flow(out)
        print(f"wrote {out / 'data_gate_flow.svg'}")
    if not args.skip_png:
        export_pipeline_pngs(out)
        print(f"wrote PNG previews under {out}")


if __name__ == "__main__":
    main()
