#!/usr/bin/env python3
"""SmolVLA S3 paired open-loop: base (S2 protocol) vs LoRA (native abs-EEF).

- Base: Gate S2 libero6d diagnostic mapping (same as S2 open-loop).
- LoRA: native Panda training I/O (action[8], observation.images.scene, …)
  matching the formal LoRA checkpoint feature schema.

Applies the selected frozen gate to LoRA metrics vs S2 baseline thresholds.
Eval-gate-v2 additionally requires evaluator-v3 gripper severity metrics and a
prospective manifest before Pass. Does not train, does not launch Isaac, and
claims_task_success=false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

# AutoDL / air-gapped hosts: force hub offline before any transformers import.
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
    MAPPING_HYPOTHESIS,
    aggregate_open_loop_metrics,
    bgr_to_chw_float01,
    build_open_loop_report,
    expert_absolute_action8,
    frame_errors,
    load_video_frame_bgr,
    map_libero6_to_abs_channels,
    panda_state6_from_row,
    write_json,
)
from training.scripts.run_smolvla_s3_control import (  # noqa: E402
    audit_trained_checkpoint,
)
from training.smolvla_s3.eval_gate_v3 import (  # noqa: E402
    EVALUATOR_CONTRACT_VERSION,
    GATE_CONTRACT_VERSION as EVAL_GATE_V2_CONTRACT_VERSION,
    SEVERITY_GATE_CONTRACT_VERSIONS,
    compute_gripper_severity_metrics,
    decide_gate_v3,
    validate_prospective_context,
)
from training.smolvla_s3.state15 import observation_state_for_policy  # noqa: E402

DEFAULT_GATE = ROOT / "configs" / "smolvla_s3" / "eval_gate_v2.yaml"
DEFAULT_RELEASE = (
    ROOT / "data" / "releases" / "smolvla_s3_abs_eef_rgb_v1_griptiming"
)
DEFAULT_CONFIG = ROOT / "configs" / "smolvla_s3" / "lora_train.yaml"
GRIPPER_THRESHOLD = 0.5
GRIPPER_TOLERANCE = 0.25
DEFAULT_CLOSE_DEBOUNCE_FRAMES = 3
INFERENCE_MODE_CANONICAL = "canonical_first_action"
INFERENCE_MODE_QUEUED = "queued_diagnostic"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


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


def _native_policy_state(
    row: Mapping[str, Any], state_contract: Mapping[str, Any] | None
) -> np.ndarray:
    name = str((state_contract or {}).get("name") or "")
    dim = (state_contract or {}).get("dim")
    if name == "observation.state[15]" or dim == 15:
        return observation_state_for_policy(row)
    return _as_f32(row, "observation.state", 7)


def _parse_episode_ref(ref: str) -> tuple[str, int]:
    ds, ep = ref.split("/", 1)
    if not ep.startswith("episode_"):
        raise ValueError(f"bad episode ref: {ref}")
    return ds, int(ep.split("_", 1)[1])


def _resolve_data_root(release_dir: Path, data_root: Path | None) -> Path:
    if data_root is not None:
        return data_root
    manifest = json.loads((release_dir / "manifest.json").read_text(encoding="utf-8"))
    roots = manifest.get("source_dataset_roots") or []
    if not roots:
        raise RuntimeError("manifest missing source_dataset_roots; pass --data-root")
    first = Path(roots[0])
    if first.is_dir():
        return first.parent
    autodl = Path("/root/autodl-tmp/data")
    if autodl.is_dir():
        return autodl
    raise RuntimeError(
        f"cannot resolve data root from {first}; pass --data-root explicitly"
    )


def _patch_vlm_tokenizer(pre: dict[str, Any], vlm_dir: Path) -> dict[str, Any]:
    for step in pre.get("steps", []):
        step_cfg = step.get("config") or {}
        if step_cfg.get("tokenizer_name"):
            step_cfg["tokenizer_name"] = str(vlm_dir.resolve())
    return pre


def _prepare_base_workdir(base_dir: Path, vlm_dir: Path) -> Path:
    """S2-style workdir: 6-D state + triple 256² images."""
    tmp = Path(tempfile.mkdtemp(prefix="smolvla_s3_ol_base_"))
    for name in (
        "model.safetensors",
        "policy_postprocessor.json",
        "policy_preprocessor_step_5_normalizer_processor.safetensors",
        "policy_postprocessor_step_0_unnormalizer_processor.safetensors",
    ):
        src = base_dir / name
        if src.is_file():
            os.symlink(src.resolve(), tmp / name)
    cfg = json.loads((base_dir / "config.json").read_text(encoding="utf-8"))
    cfg["vlm_model_name"] = str(vlm_dir.resolve())
    cfg["input_features"] = {
        "observation.state": {"type": "STATE", "shape": [6]},
        "observation.image": {"type": "VISUAL", "shape": [3, 256, 256]},
        "observation.image2": {"type": "VISUAL", "shape": [3, 256, 256]},
        "observation.image3": {"type": "VISUAL", "shape": [3, 256, 256]},
    }
    (tmp / "config.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    pre = json.loads((base_dir / "policy_preprocessor.json").read_text(encoding="utf-8"))
    pre = _patch_vlm_tokenizer(pre, vlm_dir)
    (tmp / "policy_preprocessor.json").write_text(
        json.dumps(pre, indent=2) + "\n", encoding="utf-8"
    )
    return tmp


def _prepare_lora_workdir(base_dir: Path, lora_dir: Path, vlm_dir: Path) -> Path:
    """Native S3 workdir: base weights + LoRA feature config + LoRA normalizers."""
    tmp = Path(tempfile.mkdtemp(prefix="smolvla_s3_ol_lora_"))
    os.symlink((base_dir / "model.safetensors").resolve(), tmp / "model.safetensors")
    for name in (
        "policy_preprocessor.json",
        "policy_postprocessor.json",
        "policy_preprocessor_step_5_normalizer_processor.safetensors",
        "policy_postprocessor_step_0_unnormalizer_processor.safetensors",
    ):
        src = lora_dir / name
        if not src.is_file():
            raise FileNotFoundError(f"LoRA missing processor asset: {src}")
        os.symlink(src.resolve(), tmp / name)
    cfg = json.loads((lora_dir / "config.json").read_text(encoding="utf-8"))
    cfg["vlm_model_name"] = str(vlm_dir.resolve())
    (tmp / "config.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    pre = json.loads((tmp / "policy_preprocessor.json").read_text(encoding="utf-8"))
    # rewrite via unlink+write (symlink target is read-only intent)
    (tmp / "policy_preprocessor.json").unlink()
    pre = _patch_vlm_tokenizer(pre, vlm_dir)
    (tmp / "policy_preprocessor.json").write_text(
        json.dumps(pre, indent=2) + "\n", encoding="utf-8"
    )
    return tmp


def _load_policy(*, workdir: Path, lora_dir: Path | None, device):
    from lerobot.policies.factory import make_pre_post_processors
    from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

    print(f"[s3-openloop] load policy workdir={workdir} lora={lora_dir}", flush=True)
    t0 = time.perf_counter()
    policy = SmolVLAPolicy.from_pretrained(str(workdir), local_files_only=True)
    print(f"[s3-openloop] from_pretrained done ({time.perf_counter() - t0:.1f}s)", flush=True)
    policy = policy.to(device).eval()
    if lora_dir is not None:
        from peft import PeftModel

        t1 = time.perf_counter()
        policy = PeftModel.from_pretrained(policy, str(lora_dir))
        policy.eval()
        print(f"[s3-openloop] peft attach done ({time.perf_counter() - t1:.1f}s)", flush=True)
    cfg_obj = policy.config if hasattr(policy, "config") else policy.base_model.config
    t2 = time.perf_counter()
    preprocess, postprocess = make_pre_post_processors(
        cfg_obj,
        str(workdir),
        preprocessor_overrides={"device_processor": {"device": str(device)}},
    )
    print(
        f"[s3-openloop] processors ready ({time.perf_counter() - t2:.1f}s; "
        f"total {time.perf_counter() - t0:.1f}s)",
        flush=True,
    )
    return policy, preprocess, postprocess


def _as_f32(row: Mapping[str, Any], key: str, dim: int, default: float = 0.0) -> np.ndarray:
    if key not in row or row[key] is None:
        return np.full((dim,), default, dtype=np.float32)
    arr = np.asarray(row[key], dtype=np.float32).reshape(-1)
    out = np.full((dim,), default, dtype=np.float32)
    n = min(dim, int(arr.shape[0]))
    out[:n] = arr[:n]
    return out


def _bgr_to_chw_hw(frame_bgr: np.ndarray, height: int, width: int) -> np.ndarray:
    import cv2

    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (width, height), interpolation=cv2.INTER_AREA)
    return np.transpose(resized.astype(np.float32) / 255.0, (2, 0, 1))


def _map_native8(pred8: Sequence[float]) -> dict[str, Any]:
    p = np.asarray(pred8, dtype=np.float64).reshape(-1)
    if p.shape[0] < 8:
        raise ValueError(f"expected pred[8], got {p.shape[0]}")
    grip = float(np.clip(p[7], 0.0, 1.0))
    return {
        "ee_target_xyz": p[:3].tolist(),
        "ee_target_xyzw": p[3:7].tolist(),
        "gripper_cmd": grip,
        "raw_pred8": p[:8].tolist(),
        "mapping_hypothesis": "native_absolute_eef_gripper_v0",
    }


def _first_close_frame(
    cmds: Sequence[float],
    thr: float = GRIPPER_THRESHOLD,
    *,
    debounce: int = 1,
) -> int | None:
    """Return first sustained close sample under Panda 0=closed, 1=open."""
    if debounce < 1:
        raise ValueError("debounce must be >= 1")
    closed = [float(c) <= thr for c in cmds]
    for i in range(0, len(closed) - debounce + 1):
        if all(closed[i : i + debounce]):
            return i
    return None


def _safe_ratio(num: int, den: int) -> float | None:
    return float(num / den) if den else None


def _binary_gripper_metrics(
    expert: Sequence[float],
    predicted: Sequence[float],
    *,
    threshold: float = GRIPPER_THRESHOLD,
) -> dict[str, Any]:
    expert_closed = np.asarray(expert, dtype=np.float64) <= threshold
    pred_closed = np.asarray(predicted, dtype=np.float64) <= threshold
    if expert_closed.shape != pred_closed.shape:
        raise ValueError("expert and predicted gripper arrays must have the same shape")
    tp = int(np.sum(expert_closed & pred_closed))
    tn = int(np.sum(~expert_closed & ~pred_closed))
    fp = int(np.sum(~expert_closed & pred_closed))
    fn = int(np.sum(expert_closed & ~pred_closed))
    recall = _safe_ratio(tp, tp + fn)
    specificity = _safe_ratio(tn, tn + fp)
    precision = _safe_ratio(tp, tp + fp)
    balanced = (
        float((recall + specificity) / 2.0)
        if recall is not None and specificity is not None
        else None
    )
    f1 = (
        float(2.0 * precision * recall / (precision + recall))
        if precision is not None and recall is not None and precision + recall > 0
        else 0.0
    )
    return {
        "gripper_confusion": {"tp_closed": tp, "tn_open": tn, "fp_close": fp, "fn_open": fn},
        "gripper_binary_accuracy": _safe_ratio(tp + tn, len(expert_closed)),
        "gripper_balanced_accuracy": balanced,
        "gripper_closed_precision": precision,
        "gripper_closed_recall": recall,
        "gripper_closed_f1": f1,
        "expert_closed_fraction": (
            float(np.mean(expert_closed)) if len(expert_closed) else None
        ),
        "predicted_closed_fraction": (
            float(np.mean(pred_closed)) if len(pred_closed) else None
        ),
    }


def _episode_extra_metrics(
    frame_logs: list[dict[str, Any]],
    *,
    grip_idx: int,
    close_debounce: int = DEFAULT_CLOSE_DEBOUNCE_FRAMES,
) -> dict[str, Any]:
    if not frame_logs:
        return {
            "gripper_close_timing_error_frames": None,
            "gripper_close_timing_offset_frames_signed": None,
            "gripper_close_timing_offset_seconds_signed": None,
            "action_smoothness_ee_step_l2_p90": None,
            "expert_smoothness_ee_step_l2_p90": None,
            "saturation_or_clip_ratio": None,
            "raw_gripper_oob_ratio": None,
            "home_no_close_detected": True,
        }
    expert_g = [float(f["expert_gripper_cmd"]) for f in frame_logs]
    pred_g = [float(f["pred_gripper_cmd"]) for f in frame_logs]
    raw = [f.get("raw_pred") for f in frame_logs]
    frame_indices = [int(f.get("frame_index", i)) for i, f in enumerate(frame_logs)]
    timestamps = [f.get("timestamp") for f in frame_logs]
    e_close = _first_close_frame(expert_g, debounce=close_debounce)
    p_close = _first_close_frame(pred_g, debounce=close_debounce)
    if e_close is not None and p_close is None:
        timing_sample_steps_abs: int | None = 999
        timing_frames_signed: int | None = None
        timing_seconds_signed: float | None = None
        timing_status = "predicted_close_missing"
    elif e_close is None and p_close is not None:
        timing_sample_steps_abs = 999
        timing_frames_signed = None
        timing_seconds_signed = None
        timing_status = "expert_close_missing"
    elif e_close is None and p_close is None:
        timing_sample_steps_abs = None
        timing_frames_signed = None
        timing_seconds_signed = None
        timing_status = "no_close_in_either"
    else:
        sample_offset = int(p_close) - int(e_close)
        timing_sample_steps_abs = abs(sample_offset)
        timing_frames_signed = frame_indices[int(p_close)] - frame_indices[int(e_close)]
        if timestamps[int(p_close)] is not None and timestamps[int(e_close)] is not None:
            timing_seconds_signed = float(timestamps[int(p_close)]) - float(
                timestamps[int(e_close)]
            )
        else:
            timing_seconds_signed = None
        timing_status = "matched"

    xyz = np.asarray([f["pred_xyz"] for f in frame_logs], dtype=np.float64)
    expert_xyz = np.asarray(
        [f.get("expert_xyz", f["pred_xyz"]) for f in frame_logs], dtype=np.float64
    )
    smooth_p90 = (
        float(np.percentile(np.linalg.norm(np.diff(xyz, axis=0), axis=1), 90))
        if len(xyz) >= 2
        else 0.0
    )
    expert_smooth_p90 = (
        float(np.percentile(np.linalg.norm(np.diff(expert_xyz, axis=0), axis=1), 90))
        if len(expert_xyz) >= 2
        else 0.0
    )

    sat = 0.0
    if raw and raw[0] is not None:
        outs = []
        for r in raw:
            g = float(np.asarray(r, dtype=np.float64).reshape(-1)[grip_idx])
            outs.append(1.0 if (g < 0.0 or g > 1.0) else 0.0)
        sat = float(np.mean(outs))

    expert_has_close = any(g <= 0.5 for g in expert_g)
    prediction_has_close = any(g <= 0.5 for g in pred_g)
    home_no_close = bool(expert_has_close and not prediction_has_close)
    pred_closed = np.asarray(pred_g, dtype=np.float64) <= GRIPPER_THRESHOLD
    transitions = int(np.sum(pred_closed[1:] != pred_closed[:-1]))
    binary = _binary_gripper_metrics(expert_g, pred_g)
    tolerance_accuracy = float(
        np.mean(
            np.abs(np.asarray(pred_g, dtype=np.float64) - np.asarray(expert_g, dtype=np.float64))
            <= GRIPPER_TOLERANCE
        )
    )
    return {
        **binary,
        "gripper_tolerance_accuracy": tolerance_accuracy,
        "gripper_close_debounce_frames": close_debounce,
        "gripper_close_timing_status": timing_status,
        "expert_first_close_sample": e_close,
        "predicted_first_close_sample": p_close,
        "gripper_close_timing_error_sample_steps_abs": timing_sample_steps_abs,
        "gripper_close_timing_error_frames": (
            abs(timing_frames_signed)
            if timing_frames_signed is not None
            else (999 if timing_sample_steps_abs == 999 else None)
        ),
        "gripper_close_timing_offset_frames_signed": timing_frames_signed,
        "gripper_close_timing_offset_seconds_signed": timing_seconds_signed,
        "gripper_binary_transition_count": transitions,
        "action_smoothness_ee_step_l2_p90": smooth_p90,
        "expert_smoothness_ee_step_l2_p90": expert_smooth_p90,
        "saturation_or_clip_ratio": sat,
        "raw_gripper_oob_ratio": sat,
        "home_no_close_detected": home_no_close,
    }


def _run_policy_on_episodes(
    *,
    policy,
    preprocess,
    postprocess,
    device,
    episodes: list[dict[str, Any]],
    stride: int,
    max_frames: int,
    protocol: str,
    inference_mode: str = INFERENCE_MODE_CANONICAL,
    state_contract: Mapping[str, Any] | None = None,
    gripper_severity_epsilon: float = 0.05,
) -> dict[str, Any]:
    import torch

    all_errs: list[dict] = []
    all_lat: list[float] = []
    per_episode: list[dict] = []
    interface_error = None
    grip_idx = 5 if protocol == "s2_libero6" else 7
    total_source_frames = 0
    if inference_mode not in {
        INFERENCE_MODE_CANONICAL,
        INFERENCE_MODE_QUEUED,
    }:
        raise ValueError(f"unknown inference mode: {inference_mode}")

    try:
        n_eps = len(episodes)
        for ep_i, ep_meta in enumerate(episodes, start=1):
            parquet = Path(ep_meta["parquet"])
            video = Path(ep_meta["video"])
            import pyarrow.parquet as pq

            n_rows = pq.read_table(parquet).num_rows
            total_source_frames += n_rows
            indices = list(range(0, n_rows, max(1, stride)))
            if max_frames > 0:
                indices = indices[:max_frames]
            print(
                f"[s3-openloop] {protocol} episode {ep_i}/{n_eps} "
                f"ref={ep_meta.get('ref')} frames={len(indices)}/{n_rows}",
                flush=True,
            )
            rows = _load_parquet_rows(parquet, indices)
            frame_logs: list[dict] = []
            ep_errs: list[dict] = []
            ep_lat: list[float] = []
            t_ep = time.perf_counter()
            if inference_mode == INFERENCE_MODE_QUEUED:
                if hasattr(policy, "reset"):
                    policy.reset()
                elif hasattr(policy, "base_model") and hasattr(
                    policy.base_model, "reset"
                ):
                    policy.base_model.reset()

            for row in rows:
                fi = int(row.get("frame_index", 0))
                bgr = load_video_frame_bgr(video, fi)
                expert8 = expert_absolute_action8(row)
                task = str(row.get("language_instruction") or row.get("task") or "")
                if task and not task.endswith("\n"):
                    task = task + "\n"

                if protocol == "s2_libero6":
                    img = bgr_to_chw_float01(bgr, 256)
                    state6 = panda_state6_from_row(row)
                    batch_in = {
                        "observation.state": torch.from_numpy(state6).unsqueeze(0),
                        "observation.image": torch.from_numpy(img).unsqueeze(0),
                        "observation.image2": torch.from_numpy(img).unsqueeze(0),
                        "observation.image3": torch.from_numpy(img).unsqueeze(0),
                        "task": [task],
                    }
                else:
                    img = _bgr_to_chw_hw(bgr, 240, 320)
                    batch_in = {
                        "observation.state": torch.from_numpy(
                            _native_policy_state(row, state_contract)
                        ).unsqueeze(0),
                        "observation.ee_pose": torch.from_numpy(
                            _as_f32(row, "observation.ee_pose", 7)
                        ).unsqueeze(0),
                        "observation.object_pose": torch.from_numpy(
                            _as_f32(row, "observation.object_pose", 7)
                        ).unsqueeze(0),
                        "observation.ft": torch.from_numpy(
                            _as_f32(row, "observation.ft", 6)
                        ).unsqueeze(0),
                        "observation.gripper": torch.from_numpy(
                            _as_f32(row, "observation.gripper", 1)
                        ).unsqueeze(0),
                        "observation.images.scene": torch.from_numpy(img).unsqueeze(0),
                        "task": [task],
                    }

                batch = preprocess(batch_in)
                with torch.inference_mode():
                    if inference_mode == INFERENCE_MODE_CANONICAL:
                        if hasattr(policy, "reset"):
                            policy.reset()
                        elif hasattr(policy, "base_model") and hasattr(
                            policy.base_model, "reset"
                        ):
                            policy.base_model.reset()
                    torch.cuda.synchronize()
                    t0 = time.perf_counter()
                    pred = policy.select_action(batch)
                    if postprocess is not None:
                        pred = postprocess(pred)
                    torch.cuda.synchronize()
                    latency_ms = (time.perf_counter() - t0) * 1000.0
                    ep_lat.append(latency_ms)

                pred_np = pred.detach().float().cpu().numpy().reshape(-1)
                if protocol == "s2_libero6":
                    mapped = map_libero6_to_abs_channels(pred_np)
                    raw = mapped["raw_pred6"]
                else:
                    mapped = _map_native8(pred_np)
                    raw = mapped["raw_pred8"]
                errs = frame_errors(mapped, expert8)
                errs["pred_xyz"] = mapped["ee_target_xyz"]
                ep_errs.append(errs)
                frame_logs.append(
                    {
                        "frame_index": fi,
                        "timestamp": (
                            float(row["timestamp"])
                            if row.get("timestamp") is not None
                            else None
                        ),
                        "expert_xyz": expert8[:3].tolist(),
                        "pred_xyz": mapped["ee_target_xyz"],
                        "expert_gripper_cmd": float(expert8[7]),
                        "pred_gripper_cmd": mapped["gripper_cmd"],
                        "raw_pred": raw,
                        "inference_latency_ms": latency_ms,
                        "ee_position_l2_m": errs["ee_position_l2_m"],
                        "quaternion_angular_error_rad": errs["quaternion_angular_error_rad"],
                        "gripper_correct": errs["gripper_correct"],
                    }
                )

            extra = _episode_extra_metrics(frame_logs, grip_idx=grip_idx)
            metrics = aggregate_open_loop_metrics(ep_errs, ep_lat) if ep_errs else None
            if metrics is not None:
                metrics["gripper_tolerance_accuracy"] = metrics["gripper_accuracy"]
                metrics["gripper_accuracy_legacy_tolerance"] = metrics["gripper_accuracy"]
                metrics.update(
                    {
                        key: value
                        for key, value in extra.items()
                        if key.startswith("gripper_")
                        or key
                        in {
                            "expert_closed_fraction",
                            "predicted_closed_fraction",
                            "raw_gripper_oob_ratio",
                        }
                    }
                )
                metrics["gripper_accuracy"] = extra["gripper_balanced_accuracy"]
            # Prefer mean quat from frame logs when native
            if metrics is not None and protocol == "native_abs_eef":
                qvals = [
                    f["quaternion_angular_error_rad"]
                    for f in frame_logs
                    if f.get("quaternion_angular_error_rad") is not None
                ]
                metrics["quaternion_angular_error_rad"] = (
                    float(np.mean(qvals)) if qvals else None
                )
            per_episode.append(
                {
                    "episode_ref": ep_meta["ref"],
                    "slice": ep_meta["slice"],
                    "protocol": protocol,
                    "frame_indices": indices,
                    "source_num_frames": n_rows,
                    "evaluated_num_frames": len(indices),
                    "full_episode_coverage": stride == 1 and len(indices) == n_rows,
                    "metrics": metrics,
                    "extra": extra,
                    "frame_logs": frame_logs,
                }
            )
            all_errs.extend(ep_errs)
            all_lat.extend(ep_lat)
            mean_lat = float(np.mean(ep_lat)) if ep_lat else None
            print(
                f"[s3-openloop] {protocol} episode {ep_i}/{n_eps} done "
                f"in {time.perf_counter() - t_ep:.1f}s"
                + (f" latency_ms_mean={mean_lat:.1f}" if mean_lat is not None else ""),
                flush=True,
            )
    except Exception as exc:  # noqa: BLE001
        interface_error = repr(exc)

    overall = None
    open_loop = None
    if all_errs:
        overall = aggregate_open_loop_metrics(all_errs, all_lat)
        overall["gripper_tolerance_accuracy"] = overall["gripper_accuracy"]
        overall["gripper_accuracy_legacy_tolerance"] = overall["gripper_accuracy"]
        timings = [
            e["extra"]["gripper_close_timing_error_frames"]
            for e in per_episode
            if e["extra"]["gripper_close_timing_error_frames"] is not None
        ]
        smooth = [
            e["extra"]["action_smoothness_ee_step_l2_p90"]
            for e in per_episode
            if e["extra"]["action_smoothness_ee_step_l2_p90"] is not None
        ]
        hnc = [1.0 if e["extra"]["home_no_close_detected"] else 0.0 for e in per_episode]
        timing_missing_count = sum(
            e["extra"].get("gripper_close_timing_status") != "matched"
            for e in per_episode
        )
        confusion = {
            key: sum(
                int(e["extra"]["gripper_confusion"][key])
                for e in per_episode
                if e["extra"].get("gripper_confusion")
            )
            for key in ("tp_closed", "tn_open", "fp_close", "fn_open")
        }
        tp = confusion["tp_closed"]
        tn = confusion["tn_open"]
        fp = confusion["fp_close"]
        fn = confusion["fn_open"]
        recall = _safe_ratio(tp, tp + fn)
        specificity = _safe_ratio(tn, tn + fp)
        precision = _safe_ratio(tp, tp + fp)
        balanced = (
            float((recall + specificity) / 2.0)
            if recall is not None and specificity is not None
            else None
        )
        f1 = (
            float(2.0 * precision * recall / (precision + recall))
            if precision is not None
            and recall is not None
            and precision + recall > 0
            else 0.0
        )
        overall.update(
            {
                "gripper_confusion": confusion,
                "gripper_binary_accuracy": _safe_ratio(tp + tn, tp + tn + fp + fn),
                "gripper_balanced_accuracy": balanced,
                "gripper_closed_precision": precision,
                "gripper_closed_recall": recall,
                "gripper_closed_f1": f1,
                "expert_closed_fraction": _safe_ratio(tp + fn, tp + tn + fp + fn),
                "predicted_closed_fraction": _safe_ratio(tp + fp, tp + tn + fp + fn),
                # The v1 evaluator gates on threshold-classification balanced accuracy.
                "gripper_accuracy": balanced,
            }
        )
        overall["gripper_close_missing_count"] = timing_missing_count
        overall["gripper_close_timing_error_frames"] = (
            999.0
            if timing_missing_count
            else (float(np.mean(timings)) if timings else None)
        )
        for key in (
            "gripper_close_timing_offset_frames_signed",
            "gripper_close_timing_offset_seconds_signed",
            "gripper_binary_transition_count",
            "expert_smoothness_ee_step_l2_p90",
        ):
            values = [
                e["extra"][key]
                for e in per_episode
                if e["extra"].get(key) is not None
            ]
            overall[key] = float(np.mean(values)) if values else None
        overall["action_smoothness_ee_step_l2_p90"] = (
            float(np.mean(smooth)) if smooth else None
        )
        raw_gripper_values = [
            float(np.asarray(frame["raw_pred"], dtype=np.float64).reshape(-1)[grip_idx])
            for episode in per_episode
            for frame in episode["frame_logs"]
            if frame.get("raw_pred") is not None
        ]
        overall["saturation_or_clip_ratio"] = (
            float(
                np.mean(
                    [
                        1.0 if value < 0.0 or value > 1.0 else 0.0
                        for value in raw_gripper_values
                    ]
                )
            )
            if raw_gripper_values
            else None
        )
        overall["raw_gripper_oob_ratio"] = overall["saturation_or_clip_ratio"]
        overall.update(
            compute_gripper_severity_metrics(
                per_episode,
                grip_idx=grip_idx,
                epsilon=gripper_severity_epsilon,
                threshold=GRIPPER_THRESHOLD,
                debounce=DEFAULT_CLOSE_DEBOUNCE_FRAMES,
            )
        )
        overall["home_no_close_detected_rate"] = float(np.mean(hnc)) if hnc else None
        overall["source_num_frames"] = total_source_frames
        overall["evaluated_num_frames"] = len(all_errs)
        overall["coverage_ratio"] = (
            float(len(all_errs) / total_source_frames) if total_source_frames else 0.0
        )
        overall["full_episode_coverage"] = bool(
            per_episode and all(e["full_episode_coverage"] for e in per_episode)
        )
        overall["sampling_stride_frames"] = stride
        overall["temporal_metrics_gate_eligible"] = bool(
            overall["full_episode_coverage"]
            and stride == 1
            and inference_mode == INFERENCE_MODE_CANONICAL
        )
        overall["inference_mode"] = inference_mode
        overall["executes_action_chunk_queue"] = (
            inference_mode == INFERENCE_MODE_QUEUED
        )
        if protocol == "native_abs_eef":
            qvals = [
                f["quaternion_angular_error_rad"]
                for e in per_episode
                for f in e["frame_logs"]
                if f.get("quaternion_angular_error_rad") is not None
            ]
            overall["quaternion_angular_error_rad"] = (
                float(np.mean(qvals)) if qvals else None
            )
        open_loop = build_open_loop_report(
            overall,
            notes=(
                f"SmolVLA S3 open-loop protocol={protocol}. "
                f"mapping={MAPPING_HYPOTHESIS if protocol == 's2_libero6' else 'native_absolute_eef_gripper_v0'}. "
                f"inference_mode={inference_mode}. "
                "Not task success. Not Isaac."
            ),
        )

    slices: dict[str, Any] = {}
    for slice_name in ("id_validation", "ood_position"):
        key = "validation" if slice_name == "id_validation" else "benchmark"
        subset = [e for e in per_episode if e["slice"] == key and e["metrics"]]
        if not subset:
            slices[slice_name] = None
            continue
        gripper_balanced_values = [
            float(e["metrics"]["gripper_accuracy"])
            for e in subset
            if e["metrics"].get("gripper_accuracy") is not None
        ]
        slices[slice_name] = {
            "ee_position_rmse_m": float(
                np.mean([float(e["metrics"]["ee_position_rmse_m"]) for e in subset])
            ),
            "gripper_accuracy": (
                float(np.mean(gripper_balanced_values))
                if gripper_balanced_values
                else None
            ),
            "gripper_tolerance_accuracy": float(
                np.mean(
                    [float(e["metrics"]["gripper_tolerance_accuracy"]) for e in subset]
                )
            ),
            "n_episodes": len(subset),
        }

    return {
        "protocol": protocol,
        "interface_ok": interface_error is None and bool(all_errs),
        "interface_error": interface_error,
        "metrics": overall,
        "open_loop_report": open_loop,
        "per_episode_raw_results": per_episode,
        "slices": slices,
        "n_frames": len(all_errs),
        "source_num_frames": total_source_frames,
        "coverage_ratio": (
            float(len(all_errs) / total_source_frames) if total_source_frames else 0.0
        ),
        "latency_ms_mean": float(np.mean(all_lat)) if all_lat else None,
        "latency_ms_p50": float(np.percentile(all_lat, 50)) if all_lat else None,
        "latency_ms_p95": float(np.percentile(all_lat, 95)) if all_lat else None,
        "latency_ms_max": float(np.max(all_lat)) if all_lat else None,
    }


def _finite(x: Any) -> bool:
    if x is None:
        return True
    try:
        v = float(x)
    except (TypeError, ValueError):
        return False
    return math.isfinite(v)


def decide_gate(
    gate: Mapping[str, Any],
    lora_metrics: Mapping[str, Any] | None,
    *,
    s2_ee: float,
    prospective_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if gate.get("contract_version") in SEVERITY_GATE_CONTRACT_VERSIONS:
        return decide_gate_v3(
            gate,
            lora_metrics,
            s2_ee=s2_ee,
            prospective_context=prospective_context,
        )
    reasons: list[str] = []
    if not lora_metrics:
        return {
            "gate_decision": "no_go",
            "reasons": ["missing_lora_metrics"],
            "relative_ee_improvement_vs_s2": None,
        }

    ee = lora_metrics.get("ee_position_rmse_m")
    grip = lora_metrics.get(
        "gripper_balanced_accuracy", lora_metrics.get("gripper_accuracy")
    )
    quat = lora_metrics.get("quaternion_angular_error_rad")
    timing = lora_metrics.get("gripper_close_timing_error_frames")
    smooth = lora_metrics.get("action_smoothness_ee_step_l2_p90")
    sat = lora_metrics.get(
        "raw_gripper_oob_ratio", lora_metrics.get("saturation_or_clip_ratio")
    )
    hnc = lora_metrics.get("home_no_close_detected_rate")
    temporal_eligible = bool(lora_metrics.get("temporal_metrics_gate_eligible", False))

    for name, val in (
        ("ee", ee),
        ("grip", grip),
        ("timing", timing),
        ("smooth", smooth),
        ("sat", sat),
        ("hnc", hnc),
        ("quat", quat),
    ):
        if val is not None and not _finite(val):
            return {
                "gate_decision": "no_go",
                "reasons": [f"nan_or_inf:{name}"],
                "relative_ee_improvement_vs_s2": None,
            }

    rel = None
    if ee is not None and s2_ee > 0:
        rel = (float(s2_ee) - float(ee)) / float(s2_ee)

    thr = gate["thresholds"]
    no_go = thr["no_go"]
    hold = thr["hold"]
    pas = thr["pass"]

    if ee is not None and float(ee) >= float(no_go["ee_position_rmse_m_min"]):
        reasons.append(f"ee_rmse>={no_go['ee_position_rmse_m_min']}")
    no_go_grip = no_go.get(
        "gripper_balanced_accuracy_max", no_go.get("gripper_accuracy_max")
    )
    if grip is not None and no_go_grip is not None and float(grip) <= float(no_go_grip):
        reasons.append(f"grip_balanced_acc<={no_go_grip}")
    if hnc is not None and float(hnc) >= float(no_go["home_no_close_detected_min_rate"]):
        reasons.append(f"home_no_close>={no_go['home_no_close_detected_min_rate']}")
    if smooth is not None and float(smooth) <= float(no_go["near_static_ee_step_l2_p90_max"]):
        reasons.append("near_static_ee")
    no_go_sat = no_go.get(
        "raw_gripper_oob_ratio_min", no_go.get("saturation_or_clip_ratio_min")
    )
    if sat is not None and no_go_sat is not None and float(sat) >= float(no_go_sat):
        reasons.append("high_saturation")

    if reasons:
        return {
            "gate_decision": "no_go",
            "reasons": reasons,
            "relative_ee_improvement_vs_s2": rel,
        }

    def _pass_ok() -> tuple[bool, list[str]]:
        checks: list[str] = []
        if ee is None or float(ee) > float(pas["ee_position_rmse_m_max"]):
            checks.append("ee")
        if rel is None or float(rel) < float(pas["relative_ee_improvement_vs_s2_min"]):
            checks.append("rel_improve")
        if quat is None or float(quat) > float(pas["quaternion_angular_error_rad_max"]):
            checks.append("quat")
        pass_grip = pas.get(
            "gripper_balanced_accuracy_min", pas.get("gripper_accuracy_min")
        )
        if grip is None or pass_grip is None or float(grip) < float(pass_grip):
            checks.append("grip")
        if timing is None or float(timing) > float(
            pas["gripper_close_timing_error_frames_max"]
        ):
            checks.append("timing")
        if smooth is None or float(smooth) > float(pas["action_smoothness_ee_step_l2_p90_max"]):
            checks.append("smooth")
        pass_sat = pas.get(
            "raw_gripper_oob_ratio_max", pas.get("saturation_or_clip_ratio_max")
        )
        if sat is None or pass_sat is None or float(sat) > float(pass_sat):
            checks.append("sat")
        if hnc is None or float(hnc) > float(pas["home_no_close_detected_max_rate"]):
            checks.append("hnc")
        if not temporal_eligible:
            checks.append("temporal_coverage")
        return (not checks), checks

    ok, fail = _pass_ok()
    if ok:
        return {
            "gate_decision": "pass",
            "reasons": ["all_pass_thresholds"],
            "relative_ee_improvement_vs_s2": rel,
        }

    hold_ok = True
    hold_fail: list[str] = []
    if ee is None or float(ee) > float(hold["ee_position_rmse_m_max"]):
        hold_ok = False
        hold_fail.append("ee")
    if rel is None or float(rel) < float(hold["relative_ee_improvement_vs_s2_min"]):
        hold_ok = False
        hold_fail.append("rel_improve")
    if quat is not None and float(quat) > float(hold["quaternion_angular_error_rad_max"]):
        hold_ok = False
        hold_fail.append("quat")
    hold_grip = hold.get(
        "gripper_balanced_accuracy_min", hold.get("gripper_accuracy_min")
    )
    if grip is None or hold_grip is None or float(grip) < float(hold_grip):
        hold_ok = False
        hold_fail.append("grip")
    if hnc is None or float(hnc) > float(hold["home_no_close_detected_max_rate"]):
        hold_ok = False
        hold_fail.append("hnc")

    if hold_ok:
        return {
            "gate_decision": "hold",
            "reasons": [f"pass_failed:{','.join(fail)}", "within_hold_band"],
            "relative_ee_improvement_vs_s2": rel,
            "pass_failures": fail,
        }

    return {
        "gate_decision": "no_go",
        "reasons": [f"below_hold:{','.join(hold_fail)}", f"pass_failed:{','.join(fail)}"],
        "relative_ee_improvement_vs_s2": rel,
        "pass_failures": fail,
        "hold_failures": hold_fail,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", type=Path, required=True)
    parser.add_argument("--vlm-dir", type=Path, required=True)
    parser.add_argument("--lora-dir", type=Path, required=True)
    parser.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument("--eval-gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument(
        "--prospective-eval-manifest",
        type=Path,
        default=None,
        help=(
            "Run-specific v1 manifest required for an eval-gate-v2 Pass. "
            "Missing/invalid manifests fail closed to Hold/No-Go."
        ),
    )
    parser.add_argument("--train-config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--stride",
        type=int,
        default=1,
        help="Source-frame stride. Canonical Pass requires stride=1.",
    )
    parser.add_argument(
        "--max-frames-per-episode",
        type=int,
        default=0,
        help="0 evaluates the complete episode. Canonical Pass requires 0.",
    )
    parser.add_argument("--slices", default="validation,benchmark")
    parser.add_argument(
        "--inference-mode",
        choices=[INFERENCE_MODE_CANONICAL, INFERENCE_MODE_QUEUED],
        default=INFERENCE_MODE_CANONICAL,
        help=(
            "canonical_first_action resets on every observation and is gate-eligible; "
            "queued_diagnostic resets only at episode boundaries and consumes the "
            "policy action queue, but can never Pass the canonical gate."
        ),
    )
    args = parser.parse_args()
    if args.stride < 1:
        raise SystemExit("--stride must be >= 1")
    if args.max_frames_per_episode < 0:
        raise SystemExit("--max-frames-per-episode must be >= 0")

    for key in ("HF_ENDPOINT", "HUGGINGFACE_HUB_ENDPOINT"):
        os.environ.pop(key, None)

    stamp = _utc_stamp()
    out_dir = args.output_dir or (ROOT / "runs" / "smolvla_s3" / f"openloop_{stamp}")
    out_dir.mkdir(parents=True, exist_ok=True)
    train_cfg = yaml.safe_load(args.train_config.read_text(encoding="utf-8"))
    checkpoint_audit = audit_trained_checkpoint(train_cfg, args.lora_dir)
    write_json(out_dir / "checkpoint_config_audit.json", checkpoint_audit)
    if not checkpoint_audit["passed"]:
        summary = {
            "gate_decision": "no_go",
            "reasons": ["checkpoint_config_drift"],
            "checkpoint_config_verified": False,
            "checkpoint_audit_json": str(out_dir / "checkpoint_config_audit.json"),
            "failures": checkpoint_audit.get("failures") or checkpoint_audit.get("missing"),
            "ran_isaac": False,
            "claims_task_success": False,
        }
        write_json(out_dir / "s3_open_loop_summary.json", summary)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 2

    gate = yaml.safe_load(args.eval_gate.read_text(encoding="utf-8"))
    splits = json.loads((args.release_dir / "splits.json").read_text(encoding="utf-8"))
    splits_sha256 = _sha256_file(args.release_dir / "splits.json")
    prospective_manifest = None
    if args.prospective_eval_manifest is not None:
        if not args.prospective_eval_manifest.is_file():
            raise FileNotFoundError(
                f"missing prospective manifest: {args.prospective_eval_manifest}"
            )
        prospective_manifest = yaml.safe_load(
            args.prospective_eval_manifest.read_text(encoding="utf-8")
        )
    data_root = _resolve_data_root(args.release_dir, args.data_root)
    wanted = [s.strip() for s in args.slices.split(",") if s.strip()]
    episodes: list[dict[str, Any]] = []
    for slice_name in wanted:
        for ref in splits.get(slice_name, []):
            ds, ep_i = _parse_episode_ref(ref)
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

    prospective_context: dict[str, Any] | None = None
    if gate.get("contract_version") in SEVERITY_GATE_CONTRACT_VERSIONS:
        prospective_context = validate_prospective_context(
            gate,
            prospective_manifest,
            gate_sha256=_sha256_file(args.eval_gate),
            release_splits_sha256=splits_sha256,
            evaluation_episode_refs=[episode["ref"] for episode in episodes],
            train_episode_refs=splits.get("train", []),
            stride=args.stride,
            max_frames_per_episode=args.max_frames_per_episode,
            inference_mode=args.inference_mode,
        )
        # Canonical v2 is prospective-only. Reject a missing/invalid manifest
        # before loading the policy or spending GPU inference. Queued mode may
        # still run without a manifest because it is diagnostic and cannot Pass.
        canonical_manifest_required = (
            args.inference_mode == INFERENCE_MODE_CANONICAL
        )
        supplied_manifest_invalid = (
            args.prospective_eval_manifest is not None
            and not prospective_context["eligible"]
        )
        if (
            canonical_manifest_required and not prospective_context["eligible"]
        ) or supplied_manifest_invalid:
            summary = {
                "gate_decision": "no_go",
                "reasons": ["missing_or_invalid_prospective_eval_manifest"],
                "prospective_evaluation": prospective_context,
                "checkpoint_config_verified": checkpoint_audit["passed"],
                "ran_policy_inference": False,
                "ran_isaac": False,
                "claims_task_success": False,
            }
            write_json(out_dir / "s3_open_loop_summary.json", summary)
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 2

    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("S3 open-loop requires CUDA")

    device = torch.device("cuda")
    gpu_name = torch.cuda.get_device_name(0)
    results: dict[str, Any] = {}
    workdirs: list[Path] = []
    try:
        # Base: S2 diagnostic protocol
        base_wd = _prepare_base_workdir(args.base_dir, args.vlm_dir)
        workdirs.append(base_wd)
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        t_load = time.perf_counter()
        policy, preprocess, postprocess = _load_policy(
            workdir=base_wd, lora_dir=None, device=device
        )
        load_s = time.perf_counter() - t_load
        run = _run_policy_on_episodes(
            policy=policy,
            preprocess=preprocess,
            postprocess=postprocess,
            device=device,
            episodes=episodes,
            stride=args.stride,
            max_frames=args.max_frames_per_episode,
            protocol="s2_libero6",
            inference_mode=args.inference_mode,
            gripper_severity_epsilon=float(
                gate.get("gripper_range_severity_contract", {}).get(
                    "epsilon", 0.05
                )
            ),
        )
        run["load_seconds"] = round(load_s, 3)
        run["infer_peak_vram_mib"] = int(torch.cuda.max_memory_allocated() / (1024**2))
        results["base"] = run
        del policy, preprocess, postprocess
        torch.cuda.empty_cache()

        # LoRA: native abs-EEF protocol matching train schema
        lora_wd = _prepare_lora_workdir(args.base_dir, args.lora_dir, args.vlm_dir)
        workdirs.append(lora_wd)
        torch.cuda.reset_peak_memory_stats()
        t_load = time.perf_counter()
        policy, preprocess, postprocess = _load_policy(
            workdir=lora_wd, lora_dir=args.lora_dir, device=device
        )
        load_s = time.perf_counter() - t_load
        run = _run_policy_on_episodes(
            policy=policy,
            preprocess=preprocess,
            postprocess=postprocess,
            device=device,
            episodes=episodes,
            stride=args.stride,
            max_frames=args.max_frames_per_episode,
            protocol="native_abs_eef",
            inference_mode=args.inference_mode,
            state_contract=train_cfg.get("state_contract"),
            gripper_severity_epsilon=float(
                gate.get("gripper_range_severity_contract", {}).get(
                    "epsilon", 0.05
                )
            ),
        )
        run["load_seconds"] = round(load_s, 3)
        run["infer_peak_vram_mib"] = int(torch.cuda.max_memory_allocated() / (1024**2))
        results["lora"] = run
        del policy, preprocess, postprocess
        torch.cuda.empty_cache()
    finally:
        for wd in workdirs:
            shutil.rmtree(wd, ignore_errors=True)

    s2_ee = float(gate["baselines"]["s2_ee_rmse_m"])
    lora_metrics = (results.get("lora") or {}).get("metrics")
    if gate.get("contract_version") in SEVERITY_GATE_CONTRACT_VERSIONS:
        if lora_metrics is not None:
            lora_metrics["prospective_eval_eligible"] = bool(
                prospective_context["eligible"]
            )
    decision = decide_gate(
        gate,
        lora_metrics,
        s2_ee=s2_ee,
        prospective_context=prospective_context,
    )

    base_m = (results.get("base") or {}).get("metrics") or {}
    lora_m = lora_metrics or {}
    paired_delta = {}
    for k in (
        "ee_position_rmse_m",
        "gripper_accuracy",
        "gripper_tolerance_accuracy",
        "action_smoothness_ee_step_l2_p90",
        "home_no_close_detected_rate",
        "raw_gripper_oob_ratio",
        "quaternion_angular_error_rad",
    ):
        if k in base_m and k in lora_m and base_m[k] is not None and lora_m[k] is not None:
            paired_delta[k] = float(lora_m[k]) - float(base_m[k])

    report = {
        "contract_version": gate.get("contract_version", "smolvla_s3_eval_gate_v0"),
        "evaluator_contract_version": EVALUATOR_CONTRACT_VERSION,
        "artifact_type": "smolvla_s3_open_loop_paired",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "claims_task_success": False,
        "ran_isaac": False,
        "paired_eval": True,
        "protocol_note": {
            "base": "s2_libero6 diagnostic mapping (Gate S2)",
            "lora": "native_absolute_eef_gripper_v0 matching LoRA train features",
            "gate_applied_to": "lora",
        },
        "mapping_hypothesis_base": MAPPING_HYPOTHESIS,
        "release_id": json.loads(
            (args.release_dir / "manifest.json").read_text(encoding="utf-8")
        ).get("release_id"),
        "config_sha256": _sha256_file(args.train_config)
        if args.train_config.is_file()
        else None,
        "checkpoint_config_audit": checkpoint_audit,
        "eval_gate_sha256": _sha256_file(args.eval_gate),
        "eval_gate_status": gate.get("status"),
        "thresholds_frozen": gate.get("thresholds_frozen"),
        "prospective_evaluation": prospective_context,
        "prospective_eval_manifest": (
            str(args.prospective_eval_manifest)
            if args.prospective_eval_manifest is not None
            else None
        ),
        "base_checkpoint_path": str(args.base_dir),
        "vlm_path": str(args.vlm_dir),
        "lora_checkpoint_path": str(args.lora_dir),
        "data_root": str(data_root),
        "stride": args.stride,
        "max_frames_per_episode": args.max_frames_per_episode,
        "sampling_contract": {
            "canonical_pass_requires_stride": 1,
            "canonical_pass_requires_full_episode": True,
            "temporal_metrics_gate_eligible": bool(
                (lora_m or {}).get("temporal_metrics_gate_eligible")
            ),
            "inference_mode": args.inference_mode,
            "executes_action_chunk_queue": (
                args.inference_mode == INFERENCE_MODE_QUEUED
            ),
        },
        "episodes": [e["ref"] for e in episodes],
        "gpu_name": gpu_name,
        "peak_vram_mib": max(
            int((results.get("base") or {}).get("infer_peak_vram_mib") or 0),
            int((results.get("lora") or {}).get("infer_peak_vram_mib") or 0),
        ),
        "base": {
            "protocol": results["base"]["protocol"],
            "interface_ok": results["base"]["interface_ok"],
            "interface_error": results["base"]["interface_error"],
            "metrics": results["base"]["metrics"],
            "slices": results["base"]["slices"],
            "latency_ms_mean": results["base"]["latency_ms_mean"],
            "latency_ms_p50": results["base"]["latency_ms_p50"],
            "latency_ms_p95": results["base"]["latency_ms_p95"],
            "latency_ms_max": results["base"]["latency_ms_max"],
            "n_frames": results["base"]["n_frames"],
            "source_num_frames": results["base"]["source_num_frames"],
            "coverage_ratio": results["base"]["coverage_ratio"],
            "load_seconds": results["base"]["load_seconds"],
            "infer_peak_vram_mib": results["base"]["infer_peak_vram_mib"],
        },
        "lora": {
            "protocol": results["lora"]["protocol"],
            "interface_ok": results["lora"]["interface_ok"],
            "interface_error": results["lora"]["interface_error"],
            "metrics": results["lora"]["metrics"],
            "slices": results["lora"]["slices"],
            "latency_ms_mean": results["lora"]["latency_ms_mean"],
            "latency_ms_p50": results["lora"]["latency_ms_p50"],
            "latency_ms_p95": results["lora"]["latency_ms_p95"],
            "latency_ms_max": results["lora"]["latency_ms_max"],
            "n_frames": results["lora"]["n_frames"],
            "source_num_frames": results["lora"]["source_num_frames"],
            "coverage_ratio": results["lora"]["coverage_ratio"],
            "load_seconds": results["lora"]["load_seconds"],
            "infer_peak_vram_mib": results["lora"]["infer_peak_vram_mib"],
        },
        "paired_delta_lora_minus_base": paired_delta,
        "per_episode_raw_results": {
            "base": results["base"]["per_episode_raw_results"],
            "lora": results["lora"]["per_episode_raw_results"],
        },
        "open_loop_report": {
            "base": results["base"]["open_loop_report"],
            "lora": results["lora"]["open_loop_report"],
        },
        "gate_decision": decision["gate_decision"],
        "gate_decision_detail": decision,
        "notes": [
            "Open-loop offline metrics only; not task success.",
            "Gripper gate uses threshold-classification balanced accuracy; continuous tolerance is reported separately.",
            "Temporal Pass requires stride=1 and full-episode coverage.",
            (
                "Canonical mode resets per observation for teacher-forced first-action "
                "evaluation."
                if args.inference_mode == INFERENCE_MODE_CANONICAL
                else "Queued diagnostic resets only at episode boundaries, consumes the "
                "policy queue, and is not canonical-gate eligible."
            ),
            "Do not enter S4 Isaac unless gate_decision=pass and human asks.",
            (
                "Severity-gate (v2/v3) Pass requires a frozen-gate prospective manifest "
                "with zero train/design overlap."
                if gate.get("contract_version") in SEVERITY_GATE_CONTRACT_VERSIONS
                else "Eval-gate-v1 is evaluated with evaluator-v3 backward-compatible logic."
            ),
            f"S2 baseline EE RMSE={s2_ee}",
            "First misconfigured run (LoRA under S2 I/O) invalidated; this report uses native LoRA I/O.",
        ],
    }

    report_path = out_dir / "s3_open_loop_report.json"
    write_json(report_path, report)
    summary = {
        "gate_decision": report["gate_decision"],
        "base_ee_rmse": (base_m or {}).get("ee_position_rmse_m"),
        "lora_ee_rmse": (lora_m or {}).get("ee_position_rmse_m"),
        "base_grip_acc": (base_m or {}).get("gripper_accuracy"),
        "lora_grip_acc": (lora_m or {}).get("gripper_accuracy"),
        "lora_grip_tolerance_acc": (lora_m or {}).get("gripper_tolerance_accuracy"),
        "lora_grip_binary_acc": (lora_m or {}).get("gripper_binary_accuracy"),
        "lora_grip_balanced_acc": (lora_m or {}).get("gripper_balanced_accuracy"),
        "lora_grip_closed_f1": (lora_m or {}).get("gripper_closed_f1"),
        "lora_close_offset_frames_signed": (lora_m or {}).get(
            "gripper_close_timing_offset_frames_signed"
        ),
        "lora_close_offset_seconds_signed": (lora_m or {}).get(
            "gripper_close_timing_offset_seconds_signed"
        ),
        "lora_raw_gripper_oob_ratio": (lora_m or {}).get("raw_gripper_oob_ratio"),
        "lora_raw_gripper_oob_beyond_epsilon_ratio": (lora_m or {}).get(
            "raw_gripper_oob_beyond_epsilon_ratio"
        ),
        "lora_gripper_clip_adjustment_mae": (lora_m or {}).get(
            "gripper_clip_adjustment_mae"
        ),
        "lora_gripper_clip_adjustment_max_abs": (lora_m or {}).get(
            "gripper_clip_adjustment_max_abs"
        ),
        "prospective_eval_eligible": (
            prospective_context.get("eligible") if prospective_context else False
        ),
        "prospective_eval_errors": (
            prospective_context.get("errors") if prospective_context else []
        ),
        "full_episode_coverage": (lora_m or {}).get("full_episode_coverage"),
        "temporal_metrics_gate_eligible": (lora_m or {}).get(
            "temporal_metrics_gate_eligible"
        ),
        "lora_quat_err_rad": (lora_m or {}).get("quaternion_angular_error_rad"),
        "lora_latency_ms_p50": results["lora"]["latency_ms_p50"],
        "lora_latency_ms_p95": results["lora"]["latency_ms_p95"],
        "relative_ee_improvement_vs_s2": decision.get("relative_ee_improvement_vs_s2"),
        "report_json": str(report_path),
        "reasons": decision.get("reasons"),
        "pass_failures": decision.get("pass_failures"),
        "hold_failures": decision.get("hold_failures"),
        "checkpoint_config_verified": checkpoint_audit["passed"],
    }
    write_json(out_dir / "s3_open_loop_summary.json", summary)
    (out_dir / "open_loop_log.txt").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if not results["base"]["interface_ok"] or not results["lora"]["interface_ok"]:
        return 2
    # Fail closed so a shell/CI pipeline cannot treat Hold or No-Go as Isaac-ready.
    return 0 if report["gate_decision"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
