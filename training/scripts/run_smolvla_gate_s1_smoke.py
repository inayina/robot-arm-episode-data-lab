#!/usr/bin/env python3
"""SmolVLA Gate S1 smoke: official base load + one select_action; record VRAM/latency/LICENSE.

Uses official non-Panda sample (lerobot/libero) when available.
Does NOT train, does NOT launch Isaac, does NOT use Panda episodes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def _sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_license_files(root: Path) -> list[dict]:
    hits: list[dict] = []
    if not root.exists():
        return hits
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "NOTICE"):
        for path in root.rglob(name):
            if not path.is_file() or path.stat().st_size >= 200_000:
                continue
            # Skip huge trees under .git
            if ".git" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            hits.append(
                {
                    "path": str(path),
                    "sha256": _sha256_file(path),
                    "head": text[:500],
                    "mentions_apache": ("Apache" in text) or ("apache" in text),
                }
            )
            if len(hits) >= 20:
                return hits
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", default="lerobot/smolvla_base")
    parser.add_argument("--dataset-id", default="lerobot/libero")
    parser.add_argument("--local-dir", type=Path, required=True)
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--report-md", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--timed-runs", type=int, default=3)
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Skip Hub download; require local_dir/model.safetensors already present.",
    )
    parser.add_argument(
        "--vlm-local-dir",
        type=Path,
        default=None,
        help="Optional local HuggingFaceTB/SmolVLM2-500M-Video-Instruct checkout "
        "(rewrites config.vlm_model_name to avoid Hub fetch).",
    )
    args = parser.parse_args()

    # Broken/partial mirrors break transformers Hub HEAD checks.
    import os

    for key in ("HF_ENDPOINT", "HUGGINGFACE_HUB_ENDPOINT"):
        if os.environ.get(key):
            os.environ.pop(key, None)

    import torch
    from huggingface_hub import snapshot_download
    from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

    if not torch.cuda.is_available():
        raise RuntimeError("Gate S1 requires CUDA; torch.cuda.is_available() is False")

    device = torch.device("cuda")
    torch.cuda.reset_peak_memory_stats()
    gpu_name = torch.cuda.get_device_name(0)
    vram_total_mib = int(torch.cuda.get_device_properties(0).total_memory / (1024**2))

    args.local_dir.mkdir(parents=True, exist_ok=True)
    weight_path = args.local_dir / "model.safetensors"
    use_local_only = bool(args.local_files_only or weight_path.is_file())
    t0 = time.perf_counter()
    if use_local_only:
        if not weight_path.is_file():
            raise FileNotFoundError(f"--local-files-only set but missing {weight_path}")
        local_path = args.local_dir
        download_s = 0.0
    else:
        local_path = Path(
            snapshot_download(
                repo_id=args.model_id,
                local_dir=str(args.local_dir),
                local_dir_use_symlinks=False,
            )
        )
        download_s = time.perf_counter() - t0

    if args.vlm_local_dir is not None:
        vlm_dir = args.vlm_local_dir.resolve()
        if not (vlm_dir / "config.json").is_file():
            raise FileNotFoundError(f"--vlm-local-dir missing config.json: {vlm_dir}")
        cfg_path = local_path / "config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["vlm_model_name"] = str(vlm_dir)
        # Hub config.input_features uses camera* keys; preprocessor stats use image*.
        # Align to preprocessor names so select_action sees the same keys as batch.
        cfg["input_features"] = {
            "observation.state": {"type": "STATE", "shape": [6]},
            "observation.image": {"type": "VISUAL", "shape": [3, 256, 256]},
            "observation.image2": {"type": "VISUAL", "shape": [3, 256, 256]},
            "observation.image3": {"type": "VISUAL", "shape": [3, 256, 256]},
        }
        cfg_path.write_text(json.dumps(cfg, indent=4) + "\n", encoding="utf-8")
        # Processor JSON also hardcodes Hub tokenizer id.
        pre_json = local_path / "policy_preprocessor.json"
        if pre_json.is_file():
            pre_cfg = json.loads(pre_json.read_text(encoding="utf-8"))
            for step in pre_cfg.get("steps", []):
                step_cfg = step.get("config") or {}
                if step_cfg.get("tokenizer_name"):
                    step_cfg["tokenizer_name"] = str(vlm_dir)
            pre_json.write_text(json.dumps(pre_cfg, indent=2) + "\n", encoding="utf-8")

    t1 = time.perf_counter()
    policy = SmolVLAPolicy.from_pretrained(str(local_path)).to(device).eval()
    load_s = time.perf_counter() - t1
    load_peak_mib = int(torch.cuda.max_memory_allocated() / (1024**2))

    preprocess = None
    postprocess = None
    preprocess_error = None
    try:
        from lerobot.policies.factory import make_pre_post_processors

        preprocess, postprocess = make_pre_post_processors(
            policy.config,
            str(local_path),
            preprocessor_overrides={"device_processor": {"device": str(device)}},
        )
    except Exception as exc:
        preprocess_error = repr(exc)

    dataset_error = None
    frame = None
    frame_source = None
    try:
        from lerobot.datasets.lerobot_dataset import LeRobotDataset

        dataset = LeRobotDataset(args.dataset_id)
        episode_index = 0
        from_idx = int(dataset.meta.episodes["dataset_from_index"][episode_index])
        frame = dict(dataset[from_idx])
        frame_source = f"dataset:{args.dataset_id}"
    except Exception as exc:
        dataset_error = repr(exc)
        # Offline fallback matching smolvla_base preprocessor feature names.
        # Provide explicit batch dim; some processor paths skip ToBatch for tensors.
        frame = {
            "observation.state": torch.zeros(1, 6, dtype=torch.float32),
            "observation.image": torch.zeros(1, 3, 256, 256, dtype=torch.float32),
            "observation.image2": torch.zeros(1, 3, 256, 256, dtype=torch.float32),
            "observation.image3": torch.zeros(1, 3, 256, 256, dtype=torch.float32),
            "task": ["pick up the object\n"],
        }
        frame_source = "synthetic_smolvla_base_schema"

    latencies_ms: list[float] = []
    action_shape = None
    infer_mode = "unknown"
    infer_error = None

    def run_once() -> None:
        nonlocal action_shape, infer_mode
        if frame is None or preprocess is None:
            raise RuntimeError(
                f"cannot infer without dataset frame + preprocessor "
                f"(dataset_error={dataset_error}, preprocess_error={preprocess_error})"
            )
        batch = preprocess(frame)
        with torch.inference_mode():
            if hasattr(policy, "reset"):
                policy.reset()
            t_a = time.perf_counter()
            pred = policy.select_action(batch)
            if postprocess is not None:
                pred = postprocess(pred)
            torch.cuda.synchronize()
            latencies_ms.append((time.perf_counter() - t_a) * 1000.0)
        action_shape = list(pred.shape) if hasattr(pred, "shape") else None
        infer_mode = (
            "official_libero_frame_select_action"
            if frame_source and frame_source.startswith("dataset:")
            else "synthetic_frame_select_action"
        )

    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    try:
        for _ in range(max(0, args.warmup)):
            run_once()
        latencies_ms.clear()
        torch.cuda.reset_peak_memory_stats()
        for _ in range(max(1, args.timed_runs)):
            run_once()
    except Exception as exc:
        infer_error = repr(exc)
        infer_mode = "load_ok_infer_failed"

    infer_peak_mib = int(torch.cuda.max_memory_allocated() / (1024**2))

    rev = None
    card_license = None
    hub_info_error = None
    try:
        from huggingface_hub import HfApi

        info = HfApi().model_info(args.model_id)
        rev = info.sha
        card_license = getattr(info, "license", None)
        if card_license is None and getattr(info, "cardData", None):
            card_license = (info.cardData or {}).get("license")
    except Exception as exc:
        hub_info_error = repr(exc)

    licenses = _find_license_files(local_path)
    try:
        import lerobot

        lerobot_root = Path(lerobot.__file__).resolve().parents[1]
        licenses.extend(_find_license_files(lerobot_root))
        # Also repo root if editable
        maybe_repo = Path("/home/ina/dev/lerobot")
        if maybe_repo.exists():
            licenses.extend(_find_license_files(maybe_repo))
        lerobot_version = getattr(lerobot, "__version__", "unknown")
    except Exception:
        lerobot_version = "unknown"

    # Deduplicate license paths
    seen: set[str] = set()
    uniq_licenses = []
    for item in licenses:
        if item["path"] in seen:
            continue
        seen.add(item["path"])
        uniq_licenses.append(item)

    freeze = subprocess.check_output(
        ["python", "-m", "pip", "freeze"], text=True, errors="replace"
    )
    interesting = [
        line
        for line in freeze.splitlines()
        if any(
            key in line.lower()
            for key in ("lerobot", "torch", "transformers", "peft", "smol", "accelerate")
        )
    ]

    status = "pass" if infer_error is None and latencies_ms else "partial_load_ok"
    if load_peak_mib <= 0:
        status = "fail"

    report = {
        "contract_version": "smolvla_gate_s1_report_v0",
        "artifact_type": "smolvla_gate_s1_official_repro",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "claims_task_success": False,
        "uses_panda_data": False,
        "dataset_id_for_smoke": args.dataset_id,
        "trained": False,
        "ran_isaac": False,
        "model_id": args.model_id,
        "local_dir": str(local_path),
        "hub_revision_sha": rev,
        "hub_license_field": card_license,
        "hub_info_error": hub_info_error,
        "license_files": uniq_licenses,
        "gpu_name": gpu_name,
        "vram_total_mib": vram_total_mib,
        "download_seconds": round(download_s, 3),
        "load_seconds": round(load_s, 3),
        "load_peak_vram_mib": load_peak_mib,
        "infer_peak_vram_mib": infer_peak_mib,
        "infer_mode": infer_mode,
        "frame_source": frame_source,
        "infer_error": infer_error,
        "preprocess_error": preprocess_error,
        "dataset_error": dataset_error,
        "action_shape": action_shape,
        "latency_ms": {
            "runs": [round(x, 3) for x in latencies_ms],
            "p50": round(sorted(latencies_ms)[len(latencies_ms) // 2], 3)
            if latencies_ms
            else None,
            "mean": round(sum(latencies_ms) / len(latencies_ms), 3)
            if latencies_ms
            else None,
        },
        "policy_config": {
            "n_obs_steps": getattr(policy.config, "n_obs_steps", None),
            "chunk_size": getattr(policy.config, "chunk_size", None),
            "n_action_steps": getattr(policy.config, "n_action_steps", None),
            "max_state_dim": getattr(policy.config, "max_state_dim", None),
            "max_action_dim": getattr(policy.config, "max_action_dim", None),
            "resize_imgs_with_padding": list(
                getattr(policy.config, "resize_imgs_with_padding", []) or []
            ),
        },
        "software": {
            "lerobot_version": lerobot_version,
            "torch_version": torch.__version__,
            "cuda_version": torch.version.cuda,
            "pip_interesting": interesting,
        },
        "go_no_go": {
            "gate": "S1",
            "status": status,
            "notes": [
                "Official smoke only; not Panda open-loop.",
                f"Sample frame source: {frame_source}.",
            ],
        },
    }

    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    md_lines = [
        "# SmolVLA Gate S1：官方环境与资源复现",
        "",
        f"**日期**：{report['created_at']}  ",
        f"**状态**：`{status}`  ",
        "**约束**：未用 Panda 数据；未训练；未跑 Isaac；`claims_task_success=false`。",
        "",
        "## 硬件",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| GPU | {gpu_name} |",
        f"| VRAM total | {vram_total_mib} MiB |",
        f"| Load peak | {load_peak_mib} MiB |",
        f"| Infer peak | {infer_peak_mib} MiB |",
        "",
        "## 模型",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| model_id | `{args.model_id}` |",
        f"| hub revision | `{rev}` |",
        f"| hub license field | `{card_license}` |",
        f"| infer_mode | `{infer_mode}` |",
        f"| latency mean ms | {report['latency_ms']['mean']} |",
        f"| action_shape | `{action_shape}` |",
        "",
        f"LICENSE 文件命中：{len(uniq_licenses)}（见 JSON）。",
        "",
        "## 错误（如有）",
        "",
        f"- preprocess_error: `{preprocess_error}`",
        f"- dataset_error: `{dataset_error}`",
        f"- infer_error: `{infer_error}`",
        f"- hub_info_error: `{hub_info_error}`",
        "",
        f"机器可读：`{args.report_json}`",
        "",
    ]
    args.report_md.parent.mkdir(parents=True, exist_ok=True)
    args.report_md.write_text("\n".join(md_lines), encoding="utf-8")
    print(
        json.dumps(
            {"report_json": str(args.report_json), "status": status},
            indent=2,
        )
    )
    return 0 if status in ("pass", "partial_load_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
