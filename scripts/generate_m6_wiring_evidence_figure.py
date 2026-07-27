#!/usr/bin/env python3
"""Render the M6 ROS/DDS fault-response evidence figure from raw trace JSON.

The figure deliberately reports wiring decisions rather than task success.  The
M6 smoke uses a mock policy backend and does not launch a simulator or model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch


EXPECTED_EXECUTION = ("EXECUTED", "HELD", "ESTOPPED")
EXPECTED_SAFETY = ("RUN", "HOLD", "E_STOP")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _extract_rows(smoke: dict[str, Any], hoc: dict[str, Any]) -> list[dict[str, Any]]:
    if smoke.get("status") != "PASS":
        raise ValueError("M6 smoke status is not PASS")
    scope = smoke.get("scope", {})
    required_scope = {
        "ran_ros_dds_wiring": True,
        "uses_mock_policy_backend": True,
        "ran_simulator": False,
        "ran_training": False,
        "claims_task_success": False,
    }
    for key, expected in required_scope.items():
        if scope.get(key) is not expected:
            raise ValueError(f"unexpected M6 scope {key}={scope.get(key)!r}")

    trace = hoc.get("runtime_trace_report", {})
    if trace.get("issues") != []:
        raise ValueError(f"runtime trace has issues: {trace.get('issues')!r}")
    commands = trace.get("commands", [])
    if len(commands) != 3:
        raise ValueError(f"expected 3 correlated commands, got {len(commands)}")

    rows: list[dict[str, Any]] = []
    for index, command in enumerate(commands):
        policy = command.get("policy_command", {})
        execution_events = command.get("execution", [])
        task_events = command.get("task_gt", [])
        safety_events = command.get("safety", [])
        if len(execution_events) != 1 or len(task_events) != 1:
            raise ValueError(f"command {index + 1} is missing a unique execution/task event")

        execution = execution_events[0]
        desired_safety = EXPECTED_SAFETY[index]
        matching_safety = [
            event
            for event in safety_events
            if event.get("actual_decision") == desired_safety
        ]
        if not matching_safety:
            raise ValueError(
                f"command {index + 1} has no safety decision {desired_safety}"
            )
        safety = min(
            matching_safety,
            key=lambda event: abs(float(event.get("t", 0.0)) - float(execution.get("t", 0.0))),
        )
        task = task_events[0]

        actual_execution = execution.get("decision")
        if actual_execution != EXPECTED_EXECUTION[index]:
            raise ValueError(
                f"command {index + 1} execution={actual_execution!r}, "
                f"expected {EXPECTED_EXECUTION[index]!r}"
            )
        if task.get("task_status") != "UNAVAILABLE":
            raise ValueError(f"command {index + 1} unexpectedly has task GT")

        brain_events = command.get("brain", [])
        brain = brain_events[0] if brain_events else {}
        rows.append(
            {
                "command_sequence": int(policy["command_sequence"]),
                "relative_trace_time_sec": round(float(execution["t"]), 6),
                "inference_latency_ms": float(policy["inference_latency_ms"]),
                "queue_depth": int(brain.get("queue_depth", 0)),
                "execution_decision": actual_execution,
                "execution_accepted": bool(execution.get("accepted")),
                "safety_level": safety.get("level_name"),
                "safety_actual_decision": safety.get("actual_decision"),
                "safety_reason": safety.get("safety_decision_reason"),
                "task_gt": task.get("task_status"),
                "task_gt_reason": task.get("reason_code"),
            }
        )
    return rows


def _component(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    facecolor: str,
    edgecolor: str,
    title: str,
    subtitle: str,
    badge: str,
    text_color: str = "#172033",
) -> None:
    patch = FancyBboxPatch(
        (x - width / 2, y - height / 2),
        width,
        height,
        boxstyle="round,pad=0.018,rounding_size=0.035",
        linewidth=1.4,
        facecolor=facecolor,
        edgecolor=edgecolor,
    )
    ax.add_patch(patch)
    ax.text(x, y + 0.13, title, ha="center", va="center", fontsize=12.2,
            fontweight="bold", color=text_color)
    ax.text(x, y - 0.10, subtitle, ha="center", va="center", fontsize=9.0,
            color="#526075")
    ax.text(
        x,
        y - height / 2 + 0.12,
        badge,
        ha="center",
        va="center",
        fontsize=7.7,
        fontweight="bold",
        color=edgecolor,
    )


def _arrow(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    label: str,
    *,
    color: str = "#50627A",
    label_offset: tuple[float, float] = (0.0, 0.18),
    dashed: bool = False,
    connectionstyle: str = "arc3",
) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={
            "arrowstyle": "-|>",
            "lw": 1.8,
            "color": color,
            "linestyle": "--" if dashed else "-",
            "connectionstyle": connectionstyle,
            "shrinkA": 2,
            "shrinkB": 2,
        },
    )
    mid_x = (start[0] + end[0]) / 2 + label_offset[0]
    mid_y = (start[1] + end[1]) / 2 + label_offset[1]
    ax.text(
        mid_x,
        mid_y,
        label,
        ha="center",
        va="center",
        fontsize=8.2,
        color=color,
        bbox={"boxstyle": "round,pad=0.18", "facecolor": "#F7F9FC", "edgecolor": "none"},
    )


def _result_card(
    ax: plt.Axes,
    x: float,
    color: str,
    facecolor: str,
    title: str,
    path: str,
    result: str,
) -> None:
    patch = FancyBboxPatch(
        (x, 0.32),
        4.55,
        1.22,
        boxstyle="round,pad=0.02,rounding_size=0.10",
        linewidth=1.5,
        facecolor=facecolor,
        edgecolor=color,
    )
    ax.add_patch(patch)
    ax.text(x + 0.22, 1.28, title, ha="left", va="center", fontsize=11.0,
            fontweight="bold", color=color)
    ax.text(x + 0.22, 0.93, path, ha="left", va="center", fontsize=8.8,
            color="#526075")
    ax.text(x + 0.22, 0.57, result, ha="left", va="center", fontsize=11.2,
            fontweight="bold", color="#172033")


def render(rows: list[dict[str, Any]], output: Path, generated_at: str) -> None:
    cjk_font = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    font_family = "DejaVu Sans"
    if cjk_font.exists():
        font_manager.fontManager.addfont(str(cjk_font))
        font_family = font_manager.FontProperties(fname=str(cjk_font)).get_name()
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [font_family, "DejaVu Sans"],
            "axes.unicode_minus": False,
        }
    )
    fig, ax = plt.subplots(figsize=(16.0, 9.0), facecolor="#F7F9FC")
    ax.set_facecolor("#F7F9FC")
    ax.set_xlim(0.0, 16.0)
    ax.set_ylim(0.0, 9.0)
    ax.axis("off")

    ax.text(0.45, 8.55, "风险信号如何阻断策略命令", fontsize=23, fontweight="bold",
            color="#111827", ha="left", va="center")
    ax.text(
        0.45,
        8.12,
        "命令向右，安全反馈向上，运行证据汇入 HOC；底部三条路径来自同一次 M6 ROS 2/DDS smoke",
        fontsize=11.2,
        color="#526075",
        ha="left",
        va="center",
    )

    # Legend makes the test boundary visible before the reader follows arrows.
    legend = [
        ("#E8F1FF", "#5A8DEE", "M6 mock endpoint"),
        ("#E8F7EF", "#2F9E66", "real ROS node"),
        ("#EEF1F5", "#9099A8", "not started in M6"),
    ]
    for index, (face, edge, label) in enumerate(legend):
        x = 10.0 + index * 1.85
        ax.add_patch(FancyBboxPatch((x, 8.25), 0.28, 0.22,
                                   boxstyle="round,pad=0.01,rounding_size=0.03",
                                   facecolor=face, edgecolor=edge, linewidth=1.1))
        ax.text(x + 0.37, 8.36, label, fontsize=8.2, color="#526075",
                ha="left", va="center")

    _component(ax, 1.65, 6.35, 2.45, 1.28, "#E8F1FF", "#5A8DEE",
               "Brain / Policy", "produce action + health", "MOCK IN M6")
    _component(ax, 5.35, 6.35, 2.55, 1.28, "#E8F1FF", "#5A8DEE",
               "Execution gate", "accept / hold / estop command", "MOCK ADAPTER IN M6")
    _component(ax, 9.05, 6.35, 2.55, 1.28, "#EEF1F5", "#9099A8",
               "Controller + actuator", "Servo → controller → bus/drive", "NOT STARTED")
    _component(ax, 12.65, 6.35, 2.45, 1.28, "#EEF1F5", "#9099A8",
               "Task GT", "reach / grasp / lift truth", "UNAVAILABLE IN M6")

    _component(ax, 1.65, 3.92, 2.45, 1.28, "#E8F1FF", "#5A8DEE",
               "Risk source", "inject R0 / R2 / R3", "MOCK IN M6")
    _component(ax, 5.35, 3.92, 2.55, 1.28, "#E8F7EF", "#2F9E66",
               "RiskToSafetyBridge", "risk → proposed/applied action", "REAL ROS NODE")
    _component(ax, 9.05, 3.92, 2.55, 1.28, "#E8F1FF", "#5A8DEE",
               "Safety latch service", "TriggerEstop → /safety/estop", "MOCK SERVICE IN M6")
    _component(ax, 13.35, 3.92, 3.05, 1.58, "#E8F7EF", "#2F9E66",
               "HOC evidence", "Brain · Execution · Safety · Task GT", "REAL NODE · 3/3 CORRELATED")

    _arrow(ax, (2.90, 6.35), (4.05, 6.35), "/policy/command", color="#426FC0")
    _arrow(ax, (6.65, 6.35), (7.75, 6.35), "bounded command", color="#9099A8",
           dashed=True)
    _arrow(ax, (10.35, 6.35), (11.40, 6.35), "physical state", color="#9099A8",
           dashed=True)
    _arrow(ax, (2.90, 3.92), (4.05, 3.92), "/risk/status", color="#426FC0")
    _arrow(ax, (6.65, 3.92), (7.75, 3.92), "/safety/trigger_estop", color="#C33F4A",
           label_offset=(0.0, 0.30))
    _arrow(ax, (5.05, 5.72), (5.05, 4.57), "/policy/execution_report",
           color="#526075", label_offset=(-0.88, 0.0))
    _arrow(ax, (5.65, 4.57), (5.65, 5.72), "/policy/runtime_hold",
           color="#D18B00", label_offset=(0.80, 0.0))
    _arrow(
        ax,
        (9.05, 4.57),
        (6.55, 5.88),
        "/safety/estop",
        color="#C33F4A",
        label_offset=(0.15, 0.18),
        connectionstyle="arc3,rad=-0.20",
    )

    # Observability is a separate consumer path; it does not sit in the command loop.
    _arrow(ax, (6.65, 6.03), (11.82, 4.42), "HOC: command + health + execution",
           color="#2F9E66", label_offset=(0.45, 0.22))
    ax.plot([6.65, 6.65, 11.20], [3.28, 2.78, 2.78], color="#2F9E66", lw=1.8)
    ax.annotate(
        "",
        xy=(11.84, 3.35),
        xytext=(11.20, 2.78),
        arrowprops={"arrowstyle": "-|>", "lw": 1.8, "color": "#2F9E66"},
    )
    ax.text(8.85, 2.94, "HOC: risk + safety decision", ha="center", va="center",
            fontsize=8.2, color="#2F9E66",
            bbox={"boxstyle": "round,pad=0.18", "facecolor": "#F7F9FC", "edgecolor": "none"})
    _arrow(ax, (12.65, 5.71), (13.18, 4.72), "task status",
           color="#9099A8", dashed=True, label_offset=(0.48, 0.0))

    ax.text(0.45, 2.34, "同一数据流上的三次已观测结果", fontsize=13.0,
            fontweight="bold", color="#334155", ha="left", va="center")
    _result_card(
        ax, 0.45, "#2F9E66", "#E8F7EF", "R0 · 正常路径",
        "/risk/status R0  →  hold=false",
        f"CMD {rows[0]['command_sequence']}  →  {rows[0]['execution_decision']}",
    )
    _result_card(
        ax, 5.72, "#D18B00", "#FFF5D9", "R2 · 降级路径",
        "/risk/status R2  →  runtime_hold=true",
        f"CMD {rows[1]['command_sequence']}  →  {rows[1]['execution_decision']}",
    )
    _result_card(
        ax, 10.99, "#C33F4A", "#FDE8E8", "R3 · 急停路径",
        "/risk/status R3  →  TriggerEstop + latch",
        f"CMD {rows[2]['command_sequence']}  →  {rows[2]['execution_decision']}",
    )

    ax.text(
        0.45,
        0.08,
        f"PASS: DDS discovery · QoS contract · trace issues=0  |  scope: mock policy, no simulator/model/controller, not task success  |  {generated_at}",
        fontsize=8.5,
        color="#687386",
        ha="left",
        va="bottom",
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()

    smoke_path = args.evidence_dir / "m6_wiring_smoke.json"
    hoc_path = args.evidence_dir / "hoc_runtime_report.json"
    smoke = _load_json(smoke_path)
    hoc = _load_json(hoc_path)
    rows = _extract_rows(smoke, hoc)
    render(rows, args.output, str(smoke.get("generated_at_utc", "unknown")))

    if args.summary_output:
        summary = {
            "report_format": "m6_wiring_portfolio_evidence_v1",
            "generated_at_utc": smoke.get("generated_at_utc"),
            "status": smoke.get("status"),
            "scope": smoke.get("scope"),
            "contract_version": smoke.get("contract_version"),
            "contract_descriptor_sha256": smoke.get("contract_descriptor_sha256"),
            "source_sha256": {
                "m6_wiring_smoke.json": _sha256(smoke_path),
                "hoc_runtime_report.json": _sha256(hoc_path),
            },
            "checks": {
                "topic_discovery": smoke.get("checks", {}).get("topic_discovery"),
                "hoc_four_lanes_correlated": smoke.get("checks", {}).get("hoc_four_lanes_correlated"),
                "hoc_trace_bundle_exported": smoke.get("checks", {}).get("hoc_trace_bundle_exported"),
                "r2_actual_hold_observed": smoke.get("checks", {}).get("r2_actual_hold_observed"),
                "r3_actual_estop_observed": smoke.get("checks", {}).get("r3_actual_estop_observed"),
                "task_gt_remained_unavailable": smoke.get("checks", {}).get("task_gt_remained_unavailable"),
                "trace_issues": hoc.get("runtime_trace_report", {}).get("issues"),
            },
            "commands": rows,
        }
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
