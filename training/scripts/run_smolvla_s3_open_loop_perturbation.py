#!/usr/bin/env python3
"""SmolVLA open-loop nuisance perturbation diagnostic (P1-0A / P1-0B).

LoRA-only. canonical_first_action (H=1) with reset every observation.
Does NOT call decide_gate. gate_eligible=false. claims_task_success=false.
Does NOT modify clean canonical Pass reports or eval_gate_v3 thresholds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

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
    expert_absolute_action8,
    frame_errors,
    load_video_frame_bgr,
    write_json,
)
from training.scripts import run_smolvla_s3_open_loop as ol  # noqa: E402
from training.smolvla_s3.nuisance_perturbations import (  # noqa: E402
    apply_nuisance_bgr,
    condition_seed,
)
from training.smolvla_s3.stage_anchors import (  # noqa: E402
    STAGE_NAMES,
    build_episode_plan,
    first_close_frame,
)

DEFAULT_CFG = ROOT / "configs" / "smolvla_s3" / "openloop_perturbation.yaml"
DEFAULT_RELEASE = (
    ROOT
    / "data"
    / "releases"
    / "smolvla_s3_recovery_v3_prospective_eval10_gate_v3_20260724b"
)
DEFAULT_TRAIN_CFG = (
    ROOT / "configs" / "smolvla_s3" / "lora_train_recovery_v3_phaseaware50.yaml"
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_full_episode_series(parquet: Path) -> tuple[list[float], list[float], int]:
    import pyarrow.parquet as pq

    table = pq.read_table(parquet)
    n = table.num_rows
    ee = table.column("observation.ee_pose")
    act = table.column("action")
    z: list[float] = []
    g: list[float] = []
    for i in range(n):
        pose = np.asarray(ee[i].as_py(), dtype=np.float64).reshape(-1)
        action = np.asarray(act[i].as_py(), dtype=np.float64).reshape(-1)
        z.append(float(pose[2]) if pose.shape[0] >= 3 else 0.0)
        g.append(float(action[7]) if action.shape[0] >= 8 else 1.0)
    return z, g, n


def _resolve_episodes(release_dir: Path, data_root: Path, slices: list[str]) -> list[dict]:
    splits = json.loads((release_dir / "splits.json").read_text(encoding="utf-8"))
    episodes: list[dict[str, Any]] = []
    for slice_name in slices:
        for ref in splits.get(slice_name, []):
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
                raise FileNotFoundError(f"missing data for {ref} under {root}")
            episodes.append(
                {
                    "ref": ref,
                    "slice": slice_name,
                    "parquet": str(parquet),
                    "video": str(video),
                }
            )
    return episodes


def _infer_one(
    *,
    policy,
    preprocess,
    postprocess,
    row: Mapping[str, Any],
    bgr: np.ndarray,
    state_contract: Mapping[str, Any] | None,
) -> dict[str, Any]:
    import torch

    expert8 = expert_absolute_action8(row)
    task = str(row.get("language_instruction") or row.get("task") or "")
    if task and not task.endswith("\n"):
        task = task + "\n"
    img = ol._bgr_to_chw_hw(bgr, 240, 320)
    batch_in = {
        "observation.state": torch.from_numpy(
            ol._native_policy_state(row, state_contract)
        ).unsqueeze(0),
        "observation.ee_pose": torch.from_numpy(
            ol._as_f32(row, "observation.ee_pose", 7)
        ).unsqueeze(0),
        "observation.object_pose": torch.from_numpy(
            ol._as_f32(row, "observation.object_pose", 7)
        ).unsqueeze(0),
        "observation.ft": torch.from_numpy(ol._as_f32(row, "observation.ft", 6)).unsqueeze(
            0
        ),
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
        pred = policy.select_action(batch)
        if postprocess is not None:
            pred = postprocess(pred)
        torch.cuda.synchronize()
        latency_ms = (time.perf_counter() - t0) * 1000.0
    pred_np = pred.detach().float().cpu().numpy().reshape(-1)
    mapped = ol._map_native8(pred_np)
    errs = frame_errors(mapped, expert8)
    return {
        "latency_ms": latency_ms,
        "expert_gripper_cmd": float(expert8[7]),
        "pred_gripper_cmd": float(mapped["gripper_cmd"]),
        "raw_pred8": mapped["raw_pred8"],
        "ee_position_l2_m": float(errs["ee_position_l2_m"]),
        "quaternion_angular_error_rad": float(errs["quaternion_angular_error_rad"]),
        "gripper_correct": bool(errs["gripper_correct"]),
        "expert_closed": float(expert8[7]) <= 0.5,
        "pred_closed": float(mapped["gripper_cmd"]) <= 0.5,
        "raw_gripper": float(mapped["raw_pred8"][7]),
        "near_static_ee": float(errs["ee_position_l2_m"]) < 0.005,
    }


def _aggregate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "n": 0,
            "ee_rmse_m": None,
            "quat_error_mean_rad": None,
            "gripper_balanced_accuracy": None,
            "wrong_close_rate": None,
            "near_static_rate": None,
            "raw_gripper_oob_rate": None,
            "latency_ms_p50": None,
        }
    ee = np.asarray([r["ee_position_l2_m"] for r in records], dtype=np.float64)
    quat = np.asarray(
        [r["quaternion_angular_error_rad"] for r in records], dtype=np.float64
    )
    expert_closed = np.asarray([r["expert_closed"] for r in records], dtype=bool)
    pred_closed = np.asarray([r["pred_closed"] for r in records], dtype=bool)
    tp = int(np.sum(expert_closed & pred_closed))
    tn = int(np.sum(~expert_closed & ~pred_closed))
    fp = int(np.sum(~expert_closed & pred_closed))
    fn = int(np.sum(expert_closed & ~pred_closed))
    recall = tp / (tp + fn) if (tp + fn) else None
    specificity = tn / (tn + fp) if (tn + fp) else None
    bal = (
        float((recall + specificity) / 2.0)
        if recall is not None and specificity is not None
        else None
    )
    raw = np.asarray([r["raw_gripper"] for r in records], dtype=np.float64)
    oob = float(np.mean((raw < 0.0) | (raw > 1.0)))
    lat = np.asarray([r["latency_ms"] for r in records], dtype=np.float64)
    wrong_close = float(np.mean(~expert_closed & pred_closed))
    near_static = float(np.mean([r["near_static_ee"] for r in records]))
    return {
        "n": len(records),
        "ee_rmse_m": float(np.sqrt(np.mean(ee**2))),
        "ee_l2_mean_m": float(np.mean(ee)),
        "quat_error_mean_rad": float(np.mean(quat)),
        "gripper_balanced_accuracy": bal,
        "gripper_confusion": {
            "tp_closed": tp,
            "tn_open": tn,
            "fp_close": fp,
            "fn_open": fn,
        },
        "wrong_close_rate": wrong_close,
        "near_static_rate": near_static,
        "raw_gripper_oob_rate": oob,
        "latency_ms_p50": float(np.percentile(lat, 50)),
        "latency_ms_p95": float(np.percentile(lat, 95)),
    }


def _degradation(clean: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("ee_rmse_m", "quat_error_mean_rad", "wrong_close_rate", "near_static_rate"):
        c = clean.get(key)
        o = other.get(key)
        if c is None or o is None:
            out[key] = None
            continue
        out[key] = {
            "clean": c,
            "perturbed": o,
            "abs_delta": float(o - c),
            "rel_delta": float((o - c) / c) if abs(c) > 1e-12 else None,
        }
    c_ba = clean.get("gripper_balanced_accuracy")
    o_ba = other.get("gripper_balanced_accuracy")
    if c_ba is not None and o_ba is not None:
        out["gripper_balanced_accuracy"] = {
            "clean": c_ba,
            "perturbed": o_ba,
            "abs_delta": float(o_ba - c_ba),
        }
    else:
        out["gripper_balanced_accuracy"] = None
    return out


def _close_timing_summary(
    window_records_by_ep: dict[str, list[dict[str, Any]]],
    *,
    debounce: int,
) -> dict[str, Any]:
    offsets: list[int] = []
    missed = 0
    for _ref, recs in window_records_by_ep.items():
        recs = sorted(recs, key=lambda r: int(r["frame_index"]))
        expert_g = [float(r["expert_gripper_cmd"]) for r in recs]
        pred_g = [float(r["pred_gripper_cmd"]) for r in recs]
        e_close = first_close_frame(expert_g, debounce=debounce)
        p_close = first_close_frame(pred_g, debounce=debounce)
        if e_close is None:
            continue
        if p_close is None:
            missed += 1
            continue
        # Convert window-local index to absolute frame via record frame_index.
        e_fi = int(recs[e_close]["frame_index"])
        p_fi = int(recs[p_close]["frame_index"])
        offsets.append(p_fi - e_fi)
    return {
        "n_episodes_with_expert_close": len(offsets) + missed,
        "missed_close_episodes": missed,
        "close_offset_frames_signed_mean": (
            float(np.mean(offsets)) if offsets else None
        ),
        "close_offset_frames_signed_median": (
            float(np.median(offsets)) if offsets else None
        ),
        "early_close_episodes": int(sum(1 for o in offsets if o < 0)),
        "late_close_episodes": int(sum(1 for o in offsets if o > 0)),
        "on_time_episodes": int(sum(1 for o in offsets if o == 0)),
        "debounce_frames": debounce,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-dir", type=Path, required=True)
    p.add_argument("--vlm-dir", type=Path, required=True)
    p.add_argument("--lora-dir", type=Path, required=True)
    p.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE)
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--train-config", type=Path, default=DEFAULT_TRAIN_CFG)
    p.add_argument("--perturbation-config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--slices", type=str, default="benchmark")
    p.add_argument(
        "--layers",
        type=str,
        default="stage_anchors,close_window",
        help="Comma list: stage_anchors and/or close_window",
    )
    p.add_argument(
        "--i-understand-diagnostic-only",
        action="store_true",
        help="Required acknowledge: not a Gate rerun",
    )
    args = p.parse_args(argv)

    if not args.i_understand_diagnostic_only:
        print(
            "[perturb] FATAL: pass --i-understand-diagnostic-only "
            "(this run cannot Pass Gate / claim task success)",
            file=sys.stderr,
        )
        return 2

    cfg = yaml.safe_load(args.perturbation_config.read_text(encoding="utf-8"))
    train_cfg = yaml.safe_load(args.train_config.read_text(encoding="utf-8"))
    state_contract = train_cfg.get("state_contract")
    nuisance = cfg["nuisance_conditions"]
    close_debounce = int(cfg.get("close_debounce_frames", 3))
    grip_thr = float(cfg.get("gripper_threshold", 0.5))
    layers = {s.strip() for s in args.layers.split(",") if s.strip()}

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    episodes = _resolve_episodes(
        args.release_dir,
        args.data_root,
        [s.strip() for s in args.slices.split(",") if s.strip()],
    )
    plans: list[dict[str, Any]] = []
    for ep in episodes:
        z, g, _n = _load_full_episode_series(Path(ep["parquet"]))
        plan = build_episode_plan(
            ep,
            ee_z=z,
            gripper_cmds=g,
            close_debounce=close_debounce,
            gripper_threshold=grip_thr,
            window_before=int(cfg["layers"]["close_window"]["frames_before"]),
            window_after=int(cfg["layers"]["close_window"]["frames_after"]),
        )
        plans.append(plan)
    write_json(out_dir / "anchor_table.json", {"episodes": plans})

    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("open-loop perturbation requires CUDA")
    device = torch.device("cuda")
    workdir = ol._prepare_lora_workdir(args.base_dir, args.lora_dir, args.vlm_dir)
    try:
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        policy, preprocess, postprocess = ol._load_policy(
            workdir=workdir, lora_dir=args.lora_dir, device=device
        )

        all_records: list[dict[str, Any]] = []
        t_run = time.perf_counter()

        # ---- Layer 1: stage anchors ----
        if "stage_anchors" in layers:
            conds = list(cfg["layers"]["stage_anchors"]["conditions"])
            for plan in plans:
                rows_needed = sorted(set(plan["stage_anchors"].values()))
                rows = {
                    int(r["frame_index"]): r
                    for r in ol._load_parquet_rows(Path(plan["parquet"]), rows_needed)
                }
                video = Path(plan["video"])
                for stage in STAGE_NAMES:
                    fi = int(plan["stage_anchors"][stage])
                    row = rows[fi]
                    clean_bgr = load_video_frame_bgr(video, fi)
                    for cond in conds:
                        spec = nuisance[cond]
                        rng = np.random.default_rng(
                            condition_seed(str(plan["ref"]), fi, cond)
                        )
                        bgr = (
                            clean_bgr
                            if cond == "clean"
                            else apply_nuisance_bgr(clean_bgr, spec, rng=rng)
                        )
                        result = _infer_one(
                            policy=policy,
                            preprocess=preprocess,
                            postprocess=postprocess,
                            row=row,
                            bgr=bgr,
                            state_contract=state_contract,
                        )
                        rec = {
                            "layer": "stage_anchors",
                            "episode_ref": plan["ref"],
                            "stage": stage,
                            "condition": cond,
                            "frame_index": fi,
                            "close_idx": plan["close_idx"],
                            **result,
                        }
                        all_records.append(rec)
                print(
                    f"[perturb] stage_anchors done ep={plan['ref']} "
                    f"total_records={len(all_records)}",
                    flush=True,
                )

        # ---- Layer 2: close window ----
        if "close_window" in layers:
            conds = list(cfg["layers"]["close_window"]["conditions"])
            for plan in plans:
                idxs = list(plan["close_window_indices"])
                rows = {
                    int(r["frame_index"]): r
                    for r in ol._load_parquet_rows(Path(plan["parquet"]), idxs)
                }
                video = Path(plan["video"])
                for fi in idxs:
                    row = rows[fi]
                    clean_bgr = load_video_frame_bgr(video, fi)
                    for cond in conds:
                        spec = nuisance[cond]
                        rng = np.random.default_rng(
                            condition_seed(str(plan["ref"]), fi, cond)
                        )
                        bgr = (
                            clean_bgr
                            if cond == "clean"
                            else apply_nuisance_bgr(clean_bgr, spec, rng=rng)
                        )
                        result = _infer_one(
                            policy=policy,
                            preprocess=preprocess,
                            postprocess=postprocess,
                            row=row,
                            bgr=bgr,
                            state_contract=state_contract,
                        )
                        rec = {
                            "layer": "close_window",
                            "episode_ref": plan["ref"],
                            "stage": "close_window",
                            "condition": cond,
                            "frame_index": fi,
                            "close_idx": plan["close_idx"],
                            **result,
                        }
                        all_records.append(rec)
                print(
                    f"[perturb] close_window done ep={plan['ref']} "
                    f"total_records={len(all_records)}",
                    flush=True,
                )

        peak_mib = int(torch.cuda.max_memory_allocated() / (1024**2))
        wall_s = time.perf_counter() - t_run
        del policy, preprocess, postprocess
        torch.cuda.empty_cache()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    # Aggregate
    by_layer_cond: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    by_stage_cond: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in all_records:
        by_layer_cond[r["layer"]][r["condition"]].append(r)
        if r["layer"] == "stage_anchors":
            by_stage_cond[r["stage"]][r["condition"]].append(r)

    layer_metrics: dict[str, Any] = {}
    for layer, cond_map in by_layer_cond.items():
        layer_metrics[layer] = {
            cond: _aggregate_records(recs) for cond, recs in sorted(cond_map.items())
        }
        clean = layer_metrics[layer].get("clean")
        if clean:
            layer_metrics[layer]["degradation_vs_clean"] = {
                cond: _degradation(clean, m)
                for cond, m in layer_metrics[layer].items()
                if cond not in {"clean", "degradation_vs_clean"}
                and isinstance(m, dict)
                and "n" in m
            }

    stage_metrics: dict[str, Any] = {}
    for stage, cond_map in by_stage_cond.items():
        stage_metrics[stage] = {
            cond: _aggregate_records(recs) for cond, recs in sorted(cond_map.items())
        }
        clean = stage_metrics[stage].get("clean")
        if clean:
            stage_metrics[stage]["degradation_vs_clean"] = {
                cond: _degradation(clean, m)
                for cond, m in stage_metrics[stage].items()
                if cond not in {"clean", "degradation_vs_clean"}
                and isinstance(m, dict)
                and "n" in m
            }

    close_timing: dict[str, Any] = {}
    if "close_window" in layers:
        for cond in cfg["layers"]["close_window"]["conditions"]:
            by_ep: dict[str, list] = defaultdict(list)
            for r in all_records:
                if r["layer"] == "close_window" and r["condition"] == cond:
                    by_ep[r["episode_ref"]].append(r)
            close_timing[cond] = _close_timing_summary(by_ep, debounce=close_debounce)

    report = {
        "contract_version": cfg.get("contract_version"),
        "gate_eligible": False,
        "claims_task_success": False,
        "claims_sim2real": False,
        "claims_online_autonomous_grasp": False,
        "inference_mode": "canonical_first_action",
        "horizon": 1,
        "policy_reset": "every_observation",
        "gt_policy": "expert_action_at_t_nuisance_only",
        "excluded_from_main_table": cfg.get("excluded_from_main_table"),
        "perturbation_config": str(args.perturbation_config),
        "perturbation_config_sha256": _sha256_file(args.perturbation_config),
        "train_config": str(args.train_config),
        "train_config_sha256": _sha256_file(args.train_config),
        "release_dir": str(args.release_dir),
        "release_splits_sha256": _sha256_file(args.release_dir / "splits.json"),
        "lora_dir": str(args.lora_dir),
        "base_dir": str(args.base_dir),
        "vlm_dir": str(args.vlm_dir),
        "data_root": str(args.data_root),
        "gpu_name": torch.cuda.get_device_name(0),
        "infer_peak_vram_mib": peak_mib,
        "wall_seconds": round(wall_s, 3),
        "n_episodes": len(plans),
        "n_records": len(all_records),
        "layers_run": sorted(layers),
        "nuisance_conditions": nuisance,
        "layer_metrics": layer_metrics,
        "stage_metrics": stage_metrics,
        "close_timing": close_timing,
        "notes": [
            "Diagnostic only; does not replace clean canonical Gate Pass.",
            "Main degradation table uses image nuisance only; state noise excluded.",
            "No H=5/H=10 open-loop multi-step metrics.",
        ],
        "created_utc": _utc_stamp(),
    }
    write_json(out_dir / "perturbation_report.json", report)
    write_json(
        out_dir / "perturbation_summary.json",
        {
            "gate_eligible": False,
            "claims_task_success": False,
            "n_records": len(all_records),
            "layers_run": sorted(layers),
            "layer_metrics": layer_metrics,
            "stage_metrics": {
                s: {c: m for c, m in mets.items() if c != "degradation_vs_clean"}
                for s, mets in stage_metrics.items()
            },
            "close_timing": close_timing,
            "infer_peak_vram_mib": peak_mib,
            "wall_seconds": round(wall_s, 3),
        },
    )
    # Frame-level logs (may be large but <2k rows).
    write_json(out_dir / "perturbation_records.json", {"records": all_records})

    print(json.dumps(report["layer_metrics"], indent=2, ensure_ascii=False))
    print(
        f"[perturb] wrote {out_dir} records={len(all_records)} "
        f"peak_vram_mib={peak_mib} wall_s={wall_s:.1f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
