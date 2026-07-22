#!/usr/bin/env python3
"""SmolVLA Gate S2: Panda absolute-EEF offline open-loop (no Isaac, no train).

Loads local smolvla_base + SmolVLM, reads upstream LeRobot v2.1 parquet+mp4,
runs select_action, compares to expert action[8] under a declared 6→abs mapping
hypothesis. Writes open-loop report (claims_task_success=false).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.vla_contract.absolute_eef import export_frame  # noqa: E402
from evaluation.vla_contract.smolvla_panda_s2 import (  # noqa: E402
    MAPPING_HYPOTHESIS,
    S2_REPORT_VERSION,
    aggregate_open_loop_metrics,
    bgr_to_chw_float01,
    build_open_loop_report,
    expert_absolute_action8,
    frame_errors,
    h3_semantic_status,
    load_video_frame_bgr,
    map_libero6_to_abs_channels,
    panda_state6_from_row,
    write_json,
)


def _load_parquet_rows(path: Path, indices: list[int]) -> list[dict]:
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    rows: list[dict] = []
    for i in indices:
        row = {"source_path": str(path)}
        for name in table.column_names:
            row[name] = table.column(name)[i].as_py()
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--episode-root",
        type=Path,
        default=Path(
            "/home/ina/dev/ros2-arm-teleoperation-suite/data/"
            "e2_red_500hz_seed52_closelift5_20260720"
        ),
    )
    parser.add_argument("--episode-index", type=int, default=0)
    parser.add_argument("--max-frames", type=int, default=8)
    parser.add_argument("--stride", type=int, default=20)
    parser.add_argument(
        "--local-dir",
        type=Path,
        default=ROOT / "checkpoints" / "smolvla_base_gate_s1",
    )
    parser.add_argument(
        "--vlm-local-dir",
        type=Path,
        default=ROOT / "checkpoints" / "SmolVLM2-500M-Video-Instruct",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=ROOT / "evaluation" / "examples" / "smolvla_gate_s2_report.json",
    )
    parser.add_argument(
        "--open-loop-json",
        type=Path,
        default=ROOT / "evaluation" / "examples" / "smolvla_gate_s2_open_loop_report.json",
    )
    parser.add_argument(
        "--report-md",
        type=Path,
        default=ROOT / "docs" / "SMOLVLA_GATE_S2_OPEN_LOOP.md",
    )
    parser.add_argument(
        "--schema-yaml",
        type=Path,
        default=ROOT / "configs" / "robot_schemas" / "smolvla_panda_s2.yaml",
    )
    args = parser.parse_args()

    import os

    for key in ("HF_ENDPOINT", "HUGGINGFACE_HUB_ENDPOINT"):
        os.environ.pop(key, None)

    if not torch.cuda.is_available():
        raise RuntimeError("Gate S2 open-loop requires CUDA")

    device = torch.device("cuda")
    gpu_name = torch.cuda.get_device_name(0)
    vram_total = int(torch.cuda.get_device_properties(0).total_memory / (1024**2))

    ep = int(args.episode_index)
    parquet = (
        args.episode_root
        / "data"
        / "chunk-000"
        / f"episode_{ep:06d}.parquet"
    )
    video = (
        args.episode_root
        / "videos"
        / "chunk-000"
        / "observation.images.scene"
        / f"episode_{ep:06d}.mp4"
    )
    info_path = args.episode_root / "meta" / "info.json"
    info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.is_file() else {}

    h4 = "pass"
    h4_notes: list[str] = []
    if info.get("codebase_version") != "v2.1":
        h4 = "no_go"
        h4_notes.append(f"codebase_version={info.get('codebase_version')!r} expected v2.1")
    if not parquet.is_file():
        h4 = "no_go"
        h4_notes.append(f"missing parquet {parquet}")
    if not video.is_file():
        h4 = "no_go"
        h4_notes.append(f"missing video {video}")

    import pyarrow.parquet as pq

    n_rows = pq.read_table(parquet).num_rows
    indices = list(range(0, n_rows, max(1, args.stride)))[: max(1, args.max_frames)]
    rows = _load_parquet_rows(parquet, indices)

    # Rewrite local SmolVLA config for offline VLM + image key alignment (same as S1).
    cfg_path = args.local_dir / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["vlm_model_name"] = str(args.vlm_local_dir.resolve())
    cfg["input_features"] = {
        "observation.state": {"type": "STATE", "shape": [6]},
        "observation.image": {"type": "VISUAL", "shape": [3, 256, 256]},
        "observation.image2": {"type": "VISUAL", "shape": [3, 256, 256]},
        "observation.image3": {"type": "VISUAL", "shape": [3, 256, 256]},
    }
    cfg_path.write_text(json.dumps(cfg, indent=4) + "\n", encoding="utf-8")
    pre_json = args.local_dir / "policy_preprocessor.json"
    if pre_json.is_file():
        pre_cfg = json.loads(pre_json.read_text(encoding="utf-8"))
        for step in pre_cfg.get("steps", []):
            step_cfg = step.get("config") or {}
            if step_cfg.get("tokenizer_name"):
                step_cfg["tokenizer_name"] = str(args.vlm_local_dir.resolve())
        pre_json.write_text(json.dumps(pre_cfg, indent=2) + "\n", encoding="utf-8")

    from lerobot.policies.factory import make_pre_post_processors
    from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

    torch.cuda.reset_peak_memory_stats()
    t_load0 = time.perf_counter()
    policy = SmolVLAPolicy.from_pretrained(str(args.local_dir)).to(device).eval()
    load_s = time.perf_counter() - t_load0
    preprocess, postprocess = make_pre_post_processors(
        policy.config,
        str(args.local_dir),
        preprocessor_overrides={"device_processor": {"device": str(device)}},
    )
    load_peak = int(torch.cuda.max_memory_allocated() / (1024**2))

    latencies: list[float] = []
    per_frame_errs: list[dict] = []
    frame_logs: list[dict] = []
    interface_ok = True
    interface_error = None

    try:
        for row in rows:
            fi = int(row.get("frame_index", 0))
            bgr = load_video_frame_bgr(video, fi)
            img = bgr_to_chw_float01(bgr, 256)
            state6 = panda_state6_from_row(row)
            expert8 = expert_absolute_action8(row)
            abs_frame = export_frame(
                {
                    **row,
                    "observation.state": list(
                        np.concatenate(
                            [
                                np.asarray(row["observation.state"], dtype=np.float64).reshape(-1)[:7],
                                np.asarray(row["observation.gripper"], dtype=np.float64).reshape(-1)[:1],
                            ]
                        )
                    ),
                    "action": expert8.tolist(),
                }
            )
            task = str(row.get("language_instruction") or row.get("task") or "")
            if task and not task.endswith("\n"):
                task = task + "\n"

            batch_in = {
                "observation.state": torch.from_numpy(state6).unsqueeze(0),
                "observation.image": torch.from_numpy(img).unsqueeze(0),
                "observation.image2": torch.from_numpy(img).unsqueeze(0),
                "observation.image3": torch.from_numpy(img).unsqueeze(0),
                "task": [task],
            }
            batch = preprocess(batch_in)
            with torch.inference_mode():
                if hasattr(policy, "reset"):
                    policy.reset()
                t0 = time.perf_counter()
                pred = policy.select_action(batch)
                if postprocess is not None:
                    pred = postprocess(pred)
                torch.cuda.synchronize()
                latencies.append((time.perf_counter() - t0) * 1000.0)

            pred_np = pred.detach().float().cpu().numpy().reshape(-1)
            mapped = map_libero6_to_abs_channels(pred_np)
            errs = frame_errors(mapped, expert8)
            errs["pred_xyz"] = mapped["ee_target_xyz"]
            per_frame_errs.append(errs)
            frame_logs.append(
                {
                    "frame_index": fi,
                    "expert_xyz": expert8[:3].tolist(),
                    "pred_xyz": mapped["ee_target_xyz"],
                    "expert_gripper_cmd": float(expert8[7]),
                    "pred_gripper_cmd": mapped["gripper_cmd"],
                    "ee_position_l2_m": errs["ee_position_l2_m"],
                    "gripper_correct": errs["gripper_correct"],
                    "absolute_eef_frame_index": abs_frame.get("frame_index"),
                }
            )
    except Exception as exc:
        interface_ok = False
        interface_error = repr(exc)

    infer_peak = int(torch.cuda.max_memory_allocated() / (1024**2))
    s2_interface = "pass" if interface_ok and per_frame_errs else "no_go"

    metrics = None
    open_loop = None
    h3 = "no_go"
    if per_frame_errs:
        metrics = aggregate_open_loop_metrics(per_frame_errs, latencies)
        notes = (
            f"SmolVLA Gate S2 offline open-loop. mapping={MAPPING_HYPOTHESIS}. "
            f"schema={args.schema_yaml.name}. quat unmapped under 6-D hypothesis. "
            "Not task success."
        )
        open_loop = build_open_loop_report(metrics, notes=notes)
        h3 = h3_semantic_status(metrics)

    report = {
        "contract_version": S2_REPORT_VERSION,
        "artifact_type": "smolvla_gate_s2_open_loop",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "claims_task_success": False,
        "trained": False,
        "ran_isaac": False,
        "uses_panda_data": True,
        "model_id": "lerobot/smolvla_base",
        "mapping_hypothesis": MAPPING_HYPOTHESIS,
        "schema_yaml": str(args.schema_yaml),
        "episode_root": str(args.episode_root),
        "episode_index": ep,
        "frame_indices": indices,
        "upstream_codebase_version": info.get("codebase_version"),
        "s2_interface_status": s2_interface,
        "h3_pretrained_vs_absolute_eef": h3,
        "h4_upstream_v21_loader": h4,
        "h4_notes": h4_notes,
        "interface_error": interface_error,
        "gpu_name": gpu_name,
        "vram_total_mib": vram_total,
        "load_seconds": round(load_s, 3),
        "load_peak_vram_mib": load_peak,
        "infer_peak_vram_mib": infer_peak,
        "latency_ms_mean": round(float(np.mean(latencies)), 3) if latencies else None,
        "frame_logs": frame_logs,
        "open_loop_report": open_loop,
        "go_no_go": {
            "gate": "S2",
            "interface": s2_interface,
            "semantic_h3": h3,
            "loader_h4": h4,
            "notes": [
                "S2 pass requires interface=pass and loader_h4=pass.",
                "H-3 semantic Go is separate; pretrained base expected No-Go.",
                "Do not enter S3/S4 without new approval.",
            ],
        },
    }

    write_json(args.report_json, report)
    if open_loop is not None:
        write_json(args.open_loop_json, open_loop)

    # Markdown summary
    md = [
        "# SmolVLA Gate S2：Panda absolute-EEF open-loop",
        "",
        f"**日期**：{report['created_at']}  ",
        f"**Interface**：`{s2_interface}`  ",
        f"**H-3 pretrained vs absolute EEF**：`{h3}`  ",
        f"**H-4 upstream v2.1 loader**：`{h4}`  ",
        "**约束**：未训练；未跑 Isaac；`claims_task_success=false`。",
        "",
        "## 结论",
        "",
        f"- 映射假设：`{MAPPING_HYPOTHESIS}`（**诊断用**；非原生语义等价声明）。",
        f"- EE xyz RMSE：`{(metrics or {}).get('ee_position_rmse_m')}` m",
        f"- Gripper accuracy：`{(metrics or {}).get('gripper_accuracy')}`",
        f"- Quat error：`{(metrics or {}).get('quaternion_angular_error_rad')}`（6-D 假设下通常为 null）",
        f"- Latency mean：`{report['latency_ms_mean']}` ms；Infer VRAM：`{infer_peak}` MiB",
        "",
        "## 证据",
        "",
        f"- Report：`{args.report_json}`",
        f"- Open-loop schema payload：`{args.open_loop_json}`",
        f"- Feature map：`{args.schema_yaml}`",
        f"- Episode：`{args.episode_root}` ep{ep} frames {indices}",
        "",
        "## No-Go 提醒",
        "",
        "- 禁止把 SmolVLA 6-D 输出直接当 `ee_delta_gripper[7]`。",
        "- 禁止把本报告 EE RMSE 与 ACT delta 指标同表混比。",
        "- H-3=`no_go` 表示**预训练先验未对齐 Panda absolute EEF**；需 S3 LoRA（另批 / ≥16GB），不是再盲扫 ACT。",
        "",
    ]
    if interface_error:
        md.extend(["## Interface error", "", f"```\n{interface_error}\n```", ""])
    args.report_md.parent.mkdir(parents=True, exist_ok=True)
    args.report_md.write_text("\n".join(md), encoding="utf-8")

    print(
        json.dumps(
            {
                "report_json": str(args.report_json),
                "s2_interface": s2_interface,
                "h3": h3,
                "h4": h4,
                "ee_rmse": (metrics or {}).get("ee_position_rmse_m"),
                "grip_acc": (metrics or {}).get("gripper_accuracy"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if s2_interface == "pass" and h4 == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
