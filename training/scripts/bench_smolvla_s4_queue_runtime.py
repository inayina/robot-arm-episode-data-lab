#!/usr/bin/env python3
"""P1-1: measure sync vs async-double-buffer S4 queue timing on real LoRA.

Uses frozen Recovery v3 LoRA + one prospective episode as observation stream.
Does NOT start Isaac, does NOT change Gate thresholds, claims_task_success=false.

Online Isaac node today still calls select_action synchronously each timer;
this bench isolates the chunk/K schedule question with ActionChunkQueue.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.vla_contract.smolvla_panda_s2 import (  # noqa: E402
    load_video_frame_bgr,
    write_json,
)
from training.scripts import run_smolvla_s3_open_loop as ol  # noqa: E402
from training.smolvla_s3.async_queue_runtime import (  # noqa: E402
    AsyncDoubleBufferScheduler,
    SyncQueueScheduler,
    run_scheduler,
)
from training.smolvla_s3.runtime_s4 import DEFAULT_CONTRACT  # noqa: E402

DEFAULT_RELEASE = (
    ROOT
    / "data"
    / "releases"
    / "smolvla_s3_recovery_v3_prospective_eval10_gate_v3_20260724b"
)
DEFAULT_TRAIN_CFG = (
    ROOT / "configs" / "smolvla_s3" / "lora_train_recovery_v3_phaseaware50.yaml"
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _bgr_to_rgb_uint8(bgr: np.ndarray) -> np.ndarray:
    import cv2

    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _load_obs_stream(
    *,
    release_dir: Path,
    data_root: Path,
    episode_ref: str | None,
    max_frames: int,
    state_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    splits = json.loads((release_dir / "splits.json").read_text(encoding="utf-8"))
    refs = splits.get("benchmark", [])
    if not refs:
        raise RuntimeError("release has no benchmark episodes")
    ref = episode_ref or refs[0]
    ds, ep_i = ol._parse_episode_ref(ref)
    root = data_root / ds
    parquet = root / "data" / "chunk-000" / f"episode_{ep_i:06d}.parquet"
    video = (
        root
        / "videos"
        / "chunk-000"
        / "observation.images.scene"
        / f"episode_{ep_i:06d}.mp4"
    )
    if not parquet.is_file() or not video.is_file():
        raise FileNotFoundError(f"missing {ref} under {root}")
    import pyarrow.parquet as pq

    n = pq.read_table(parquet).num_rows
    indices = list(range(min(n, max_frames)))
    rows = ol._load_parquet_rows(parquet, indices)
    stream: list[dict[str, Any]] = []
    for row in rows:
        fi = int(row["frame_index"])
        bgr = load_video_frame_bgr(video, fi)
        stream.append(
            {
                "ref": ref,
                "frame_index": fi,
                "row": row,
                "rgb": _bgr_to_rgb_uint8(bgr),
                "state": ol._native_policy_state(row, state_contract),
            }
        )
    return stream


def _make_infer_chunk_fn(policy, preprocess, postprocess, stream, state_lock):
    import torch

    cursor = {"i": 0}

    def _infer():
        with state_lock:
            item = stream[cursor["i"] % len(stream)]
            cursor["i"] += 1
        row = item["row"]
        task = str(row.get("language_instruction") or row.get("task") or "")
        if task and not task.endswith("\n"):
            task = task + "\n"
        # Use scene key expected by Recovery processors.
        img = ol._bgr_to_chw_hw(
            # reconstruct BGR from RGB for the shared helper
            item["rgb"][:, :, ::-1].copy(),
            240,
            320,
        )
        batch_in = {
            "observation.state": torch.from_numpy(item["state"]).unsqueeze(0),
            "observation.ee_pose": torch.from_numpy(
                ol._as_f32(row, "observation.ee_pose", 7)
            ).unsqueeze(0),
            "observation.object_pose": torch.from_numpy(
                ol._as_f32(row, "observation.object_pose", 7)
            ).unsqueeze(0),
            "observation.ft": torch.from_numpy(
                ol._as_f32(row, "observation.ft", 6)
            ).unsqueeze(0),
            "observation.gripper": torch.from_numpy(
                ol._as_f32(row, "observation.gripper", 1)
            ).unsqueeze(0),
            "observation.images.scene": torch.from_numpy(img).unsqueeze(0),
            "task": [task],
        }
        batch = preprocess(batch_in)
        with torch.inference_mode():
            if hasattr(policy, "reset"):
                policy.reset()
            elif hasattr(policy, "base_model") and hasattr(policy.base_model, "reset"):
                policy.base_model.reset()
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            # Full chunk (B, chunk, action_dim); queue keeps first K.
            if hasattr(policy, "predict_action_chunk"):
                chunk = policy.predict_action_chunk(batch)
            elif hasattr(policy, "base_model") and hasattr(
                policy.base_model, "predict_action_chunk"
            ):
                chunk = policy.base_model.predict_action_chunk(batch)
            else:
                raise RuntimeError("policy lacks predict_action_chunk")
            if postprocess is not None:
                # postprocess may expect single-step; apply per-step if needed
                try:
                    chunk = postprocess(chunk)
                except Exception:
                    steps = []
                    for k in range(chunk.shape[1]):
                        steps.append(postprocess(chunk[:, k, :]))
                    import torch as _torch

                    chunk = _torch.stack(steps, dim=1)
            torch.cuda.synchronize()
            lat_ms = (time.perf_counter() - t0) * 1000.0
        arr = chunk.detach().float().cpu().numpy()
        if arr.ndim == 3:
            arr = arr[0]
        if arr.shape[0] < DEFAULT_CONTRACT.chunk_size:
            raise RuntimeError(
                f"expected chunk>={DEFAULT_CONTRACT.chunk_size}, got {arr.shape}"
            )
        actions = [arr[i, :8].tolist() for i in range(DEFAULT_CONTRACT.chunk_size)]
        return actions, float(lat_ms)

    return _infer


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-dir", type=Path, required=True)
    p.add_argument("--vlm-dir", type=Path, required=True)
    p.add_argument("--lora-dir", type=Path, required=True)
    p.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE)
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--train-config", type=Path, default=DEFAULT_TRAIN_CFG)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--n-ticks", type=int, default=150)
    p.add_argument("--max-source-frames", type=int, default=120)
    p.add_argument("--episode-ref", type=str, default="")
    p.add_argument(
        "--i-understand-diagnostic-only",
        action="store_true",
    )
    args = p.parse_args(argv)
    if not args.i_understand_diagnostic_only:
        print(
            "[queue-bench] FATAL: pass --i-understand-diagnostic-only",
            file=sys.stderr,
        )
        return 2

    train_cfg = yaml.safe_load(args.train_config.read_text(encoding="utf-8"))
    state_contract = train_cfg.get("state_contract")
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    stream = _load_obs_stream(
        release_dir=args.release_dir,
        data_root=args.data_root,
        episode_ref=args.episode_ref or None,
        max_frames=args.max_source_frames,
        state_contract=state_contract,
    )
    write_json(
        out / "obs_stream_meta.json",
        {
            "episode_ref": stream[0]["ref"],
            "n_frames": len(stream),
            "n_ticks": args.n_ticks,
        },
    )

    import threading

    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("queue runtime bench requires CUDA")

    workdir = ol._prepare_lora_workdir(args.base_dir, args.lora_dir, args.vlm_dir)
    try:
        device = torch.device("cuda")
        policy, preprocess, postprocess = ol._load_policy(
            workdir=workdir, lora_dir=args.lora_dir, device=device
        )
        # Align chunk config with contract.
        cfg = policy.config if hasattr(policy, "config") else policy.base_model.config
        cfg.n_action_steps = DEFAULT_CONTRACT.n_action_steps
        lock = threading.Lock()
        infer_fn = _make_infer_chunk_fn(
            policy, preprocess, postprocess, stream, lock
        )

        # Warmup one chunk (excluded from report).
        _ = infer_fn()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()

        summaries: dict[str, Any] = {}
        for mode in ("sync", "async_double_buffer"):
            print(f"[queue-bench] running mode={mode} ticks={args.n_ticks}", flush=True)
            if mode == "sync":
                sched = SyncQueueScheduler(infer_chunk_fn=infer_fn)
            else:
                sched = AsyncDoubleBufferScheduler(infer_chunk_fn=infer_fn)
            t0 = time.perf_counter()
            report, ticks = run_scheduler(
                sched, n_ticks=args.n_ticks, mode=mode, pace_realtime=True
            )
            wall = time.perf_counter() - t0
            if mode == "async_double_buffer":
                sched.close()
            summary = report.summary()
            summary["wall_seconds"] = round(wall, 3)
            summary["peak_vram_mib"] = int(
                torch.cuda.max_memory_allocated() / (1024**2)
            )
            summaries[mode] = summary
            write_json(out / f"ticks_{mode}.json", {
                "mode": mode,
                "ticks": [
                    {
                        "tick": t.tick,
                        "underrun": t.underrun,
                        "deadline_miss": t.deadline_miss,
                        "infer_started": t.infer_started,
                        "infer_completed": t.infer_completed,
                        "pending_before": t.pending_before,
                    }
                    for t in ticks
                ],
            })
            print(json.dumps(summary, indent=2), flush=True)

        del policy, preprocess, postprocess
        torch.cuda.empty_cache()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    bundle = {
        "contract_version": "smolvla_s4_queue_runtime_bench_v0",
        "gate_eligible": False,
        "claims_task_success": False,
        "claims_sim2real": False,
        "ran_isaac": False,
        "async_double_buffer_runtime_implemented_online": False,
        "async_double_buffer_runtime_measured_offline": True,
        "s4_contract": DEFAULT_CONTRACT.to_dict(),
        "lora_dir": str(args.lora_dir),
        "base_dir": str(args.base_dir),
        "vlm_dir": str(args.vlm_dir),
        "data_root": str(args.data_root),
        "release_dir": str(args.release_dir),
        "episode_ref": stream[0]["ref"],
        "n_ticks": args.n_ticks,
        "gpu_name": torch.cuda.get_device_name(0),
        "modes": summaries,
        "comparison": {
            "sync_underrun_rate": summaries["sync"]["underrun_rate"],
            "async_underrun_rate": summaries["async_double_buffer"]["underrun_rate"],
            "sync_deadline_miss_rate": summaries["sync"]["deadline_miss_rate"],
            "async_deadline_miss_rate": summaries["async_double_buffer"][
                "deadline_miss_rate"
            ],
            "sync_infer_p50_ms": summaries["sync"]["inference_latency_ms_p50"],
            "async_infer_p50_ms": summaries["async_double_buffer"][
                "inference_latency_ms_p50"
            ],
            "replan_budget_ms": 1000.0 * DEFAULT_CONTRACT.replan_period_s,
            "control_period_ms": 1000.0 / DEFAULT_CONTRACT.control_rate_hz,
            "notes": [
                "If inference_latency_p95 < replan_budget (500 ms) async can hide GPU cost across K=5.",
                "If sync tick_wall > control_period (100 ms) the 10 Hz loop cannot hold without async or rate cut.",
                "Online Isaac node still uses sync select_action; this bench does not flip that flag.",
            ],
        },
        "created_utc": _utc(),
    }
    write_json(out / "queue_runtime_report.json", bundle)
    write_json(out / "queue_runtime_summary.json", {
        "gate_eligible": False,
        "claims_task_success": False,
        "ran_isaac": False,
        "comparison": bundle["comparison"],
        "modes": {
            k: {
                "underrun_rate": v["underrun_rate"],
                "deadline_miss_rate": v["deadline_miss_rate"],
                "inference_latency_ms_p50": v["inference_latency_ms_p50"],
                "inference_latency_ms_p95": v["inference_latency_ms_p95"],
                "fits_replan_budget": v["fits_replan_budget"],
                "infer_calls": v["infer_calls"],
            }
            for k, v in summaries.items()
        },
    })
    print(f"[queue-bench] wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
