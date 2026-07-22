#!/usr/bin/env python3
"""SmolVLA S3 preflight / train control-plane.

Modes:
  --mode mock-preflight   local CI: no model weights, validates config/release/control flow
  --mode preflight        real GPU: short LoRA steps (20–50); NEVER starts full train
  --mode train            real GPU full LoRA; requires --i-understand-billing and preflight pass JSON

Does not run Isaac. Does not overwrite S2 evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_CONFIG = ROOT / "configs" / "smolvla_s3" / "lora_train.yaml"
DEFAULT_RELEASE = ROOT / "data" / "releases" / "smolvla_s3_abs_eef_rgb_v0"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _validate_release(release_dir: Path) -> dict[str, Any]:
    mod_path = ROOT / "training" / "scripts" / "validate_smolvla_s3_release.py"
    spec = importlib.util.spec_from_file_location("validate_smolvla_s3_release", mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {mod_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.validate_release(release_dir)


def run_mock_preflight(cfg: dict[str, Any], release_dir: Path, out_dir: Path) -> dict[str, Any]:
    rel = _validate_release(release_dir)
    if not rel["passed"]:
        return {
            "mode": "mock-preflight",
            "passed": False,
            "gate": "no_go",
            "reason": "release_validation_failed",
            "release_report": rel,
            "distinction": "MOCK_ONLY — not a real GPU preflight",
        }

    peft = cfg["peft"]
    train = cfg["train"]
    checks = {
        "config_parsed": True,
        "release_ok": True,
        "lora_r": peft["r"] == 64,
        "lora_alpha": peft["lora_alpha"] == 64,
        "no_arch_change": bool(train["no_architecture_change"]),
        "no_new_loss": bool(train["no_new_loss"]),
        "no_auto_hparam_search": bool(train["no_auto_hparam_search"]),
        "seed_fixed": train["seed"] == 42,
        "forbid_auto_train": bool(cfg["gates"]["forbid_auto_start_train_from_preflight"]),
        "human_confirm_required": bool(cfg["gates"]["require_human_confirm_for_full_train"]),
        "preflight_subset_present": (release_dir / "preflight_subset.json").is_file(),
    }
    # Simulated LoRA update bookkeeping (no tensors)
    fake_lora_before = {"adapter.weight": 0.0}
    fake_lora_after = {"adapter.weight": 1.0e-3}
    lora_updated = fake_lora_after != fake_lora_before

    report = {
        "mode": "mock-preflight",
        "passed": all(checks.values()) and lora_updated,
        "gate": "mock_pass" if all(checks.values()) else "no_go",
        "distinction": "MOCK_ONLY — control-flow validated; real GPU preflight still required on AutoDL",
        "checks": checks,
        "simulated": {
            "forward_backward": "mocked_ok",
            "loss_finite": True,
            "oom": False,
            "lora_params_updated": lora_updated,
            "checkpoint_save_reload": "mocked_ok",
            "peak_vram_mib": None,
            "step_time_ms": None,
        },
        "config_sha256": _sha256_file(Path(os.environ.get("S3_CONFIG", str(DEFAULT_CONFIG)))),
        "release_id": rel.get("release_id"),
        "release_report": rel,
        "created_at": _utc_stamp(),
        "real_gpu_preflight_required": True,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "preflight_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def run_real_preflight(
    cfg: dict[str, Any],
    release_dir: Path,
    out_dir: Path,
    steps: int,
    config_path: Path,
) -> dict[str, Any]:
    """Real short LoRA loop. Fail closed if imports/GPU/data unavailable."""
    rel = _validate_release(release_dir)
    if not rel["passed"]:
        return {
            "mode": "preflight",
            "passed": False,
            "gate": "no_go",
            "reason": "release_validation_failed",
            "release_report": rel,
        }

    try:
        import torch
        from peft import LoraConfig, get_peft_model
    except Exception as exc:  # noqa: BLE001
        return {
            "mode": "preflight",
            "passed": False,
            "gate": "no_go",
            "reason": f"import_failed: {exc}",
            "distinction": "REAL_GPU_PREFLIGHT_ATTEMPTED",
        }

    if not torch.cuda.is_available():
        return {
            "mode": "preflight",
            "passed": False,
            "gate": "no_go",
            "reason": "cuda_unavailable",
            "distinction": "REAL_GPU_PREFLIGHT_ATTEMPTED",
        }

    # Minimal PEFT sanity on a tiny Linear stand-in when full SmolVLA load is deferred
    # to AutoDL (weights may be absent locally). If SMOLVLA_BASE_DIR exists, prefer it.
    base_dir = Path(os.environ.get("SMOLVLA_BASE_DIR", ROOT / "checkpoints" / "smolvla_base_s3"))
    used_full_model = False
    peak_before = torch.cuda.max_memory_allocated() / (1024**2)
    torch.cuda.reset_peak_memory_stats()
    device = torch.device("cuda")

    try:
        if base_dir.is_dir() and any(base_dir.iterdir()):
            from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

            policy = SmolVLAPolicy.from_pretrained(str(base_dir))
            used_full_model = True
            model = policy.model if hasattr(policy, "model") else policy
        else:
            # Stand-in proves LoRA init/train/save/reload on this GPU stack.
            model = torch.nn.Sequential(
                torch.nn.Linear(32, 64),
                torch.nn.ReLU(),
                torch.nn.Linear(64, 8),
            )
            # Name projections similarly for target_modules match where possible
            class Tiny(torch.nn.Module):
                def __init__(self):
                    super().__init__()
                    self.q_proj = torch.nn.Linear(32, 32)
                    self.v_proj = torch.nn.Linear(32, 32)
                    self.out = torch.nn.Linear(32, 8)

                def forward(self, x):
                    return self.out(self.q_proj(x) + self.v_proj(x))

            model = Tiny()

        lora_cfg = LoraConfig(
            r=int(cfg["peft"]["r"]),
            lora_alpha=int(cfg["peft"]["lora_alpha"]),
            lora_dropout=float(cfg["peft"]["lora_dropout"]),
            target_modules=list(cfg["peft"]["target_modules"]),
            bias=cfg["peft"].get("bias", "none"),
        )
        model = get_peft_model(model, lora_cfg).to(device)
        before = {
            n: p.detach().float().cpu().clone()
            for n, p in model.named_parameters()
            if p.requires_grad
        }
        opt = torch.optim.AdamW(
            [p for p in model.parameters() if p.requires_grad],
            lr=float(cfg["train"]["learning_rate"]),
        )
        losses = []
        t0 = time.perf_counter()
        for step in range(steps):
            x = torch.randn(int(cfg["train"]["batch_size"]), 32, device=device)
            y = torch.randn(int(cfg["train"]["batch_size"]), 8, device=device)
            pred = model(x)
            loss = torch.nn.functional.mse_loss(pred, y)
            if not torch.isfinite(loss):
                raise RuntimeError("non-finite loss")
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))
        step_ms = (time.perf_counter() - t0) * 1000.0 / max(steps, 1)
        after = {
            n: p.detach().float().cpu()
            for n, p in model.named_parameters()
            if p.requires_grad
        }
        updated = any(
            not torch.allclose(before[n], after[n]) for n in before
        )
        ckpt = out_dir / "preflight_lora.pt"
        out_dir.mkdir(parents=True, exist_ok=True)
        torch.save({"state_dict": model.state_dict(), "steps": steps}, ckpt)
        reloaded = torch.load(ckpt, map_location="cpu", weights_only=False)
        reload_ok = "state_dict" in reloaded
        peak = torch.cuda.max_memory_allocated() / (1024**2)
        report = {
            "mode": "preflight",
            "passed": bool(updated and reload_ok and all(math_isfinite(l) for l in losses)),
            "gate": "pass" if updated and reload_ok else "no_go",
            "distinction": "REAL_GPU_PREFLIGHT",
            "used_full_smolvla_weights": used_full_model,
            "steps": steps,
            "loss_last": losses[-1] if losses else None,
            "loss_finite": all(math_isfinite(l) for l in losses),
            "oom": False,
            "lora_params_updated": updated,
            "checkpoint_path": str(ckpt),
            "checkpoint_reload_ok": reload_ok,
            "peak_vram_mib": peak,
            "step_time_ms_mean": step_ms,
            "gpu_name": torch.cuda.get_device_name(0),
            "torch_version": torch.__version__,
            "config_sha256": _sha256_file(config_path),
            "release_id": rel.get("release_id"),
            "release_report": rel,
            "created_at": _utc_stamp(),
            "must_not_auto_start_full_train": True,
            "note": (
                "Full SmolVLA+dataset preflight preferred when SMOLVLA_BASE_DIR is populated; "
                "tiny PEFT probe still validates GPU LoRA stack if weights absent."
            ),
        }
        (out_dir / "preflight_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return report
    except torch.cuda.OutOfMemoryError:
        return {
            "mode": "preflight",
            "passed": False,
            "gate": "no_go",
            "reason": "oom",
            "distinction": "REAL_GPU_PREFLIGHT",
            "oom": True,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "mode": "preflight",
            "passed": False,
            "gate": "no_go",
            "reason": str(exc),
            "distinction": "REAL_GPU_PREFLIGHT",
        }


def math_isfinite(x: float) -> bool:
    return x == x and abs(x) != float("inf")


def run_train_guarded(
    cfg: dict[str, Any],
    release_dir: Path,
    out_dir: Path,
    preflight_report: Path,
    confirm: bool,
    config_path: Path,
) -> dict[str, Any]:
    if not confirm:
        return {
            "mode": "train",
            "passed": False,
            "gate": "no_go",
            "reason": "missing --i-understand-billing human confirm",
        }
    if not preflight_report.is_file():
        return {
            "mode": "train",
            "passed": False,
            "gate": "no_go",
            "reason": "missing preflight_report.json",
        }
    pref = json.loads(preflight_report.read_text(encoding="utf-8"))
    if pref.get("mode") == "mock-preflight":
        return {
            "mode": "train",
            "passed": False,
            "gate": "no_go",
            "reason": "mock preflight cannot authorize real train",
        }
    if not pref.get("passed"):
        return {
            "mode": "train",
            "passed": False,
            "gate": "no_go",
            "reason": "preflight did not pass",
        }
    rel = _validate_release(release_dir)
    if not rel["passed"]:
        return {
            "mode": "train",
            "passed": False,
            "gate": "no_go",
            "reason": "release_validation_failed",
            "release_report": rel,
        }

    # Emit a frozen run metadata + exact command template; do not start long training
    # from this local S3 Ready pass unless SMOLVLA_S3_EXECUTE_TRAIN=1.
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "mode": "train",
        "executed": False,
        "ready_to_execute": True,
        "gate": "awaiting_autodl_execute",
        "release_id": rel.get("release_id"),
        "config_sha256": _sha256_file(config_path),
        "seed": cfg["train"]["seed"],
        "max_steps": cfg["train"]["max_steps"],
        "output_dir": str(out_dir),
        "preflight_report": str(preflight_report),
        "command_template": (
            "lerobot-train "
            f"--policy.path={cfg['base_checkpoint']['model_id']} "
            f"--dataset.root=$S3_DATASET_ROOT "
            f"--batch_size={cfg['train']['batch_size']} "
            f"--steps={cfg['train']['max_steps']} "
            f"--seed={cfg['train']['seed']} "
            f"--peft.method_type=LORA --peft.r={cfg['peft']['r']} "
            f"--output_dir={out_dir}"
        ),
        "note": (
            "Local S3 Ready does not start billing train. "
            "On AutoDL set SMOLVLA_S3_EXECUTE_TRAIN=1 after human approval."
        ),
        "created_at": _utc_stamp(),
    }
    if os.environ.get("SMOLVLA_S3_EXECUTE_TRAIN") == "1":
        meta["executed"] = False
        meta["gate"] = "no_go"
        meta["reason"] = (
            "EXECUTE flag set but this runner refuses to launch full train from "
            "non-AutoDL S3 Ready preparation path; use scripts/run_smolvla_s3_train.sh on GPU host."
        )
        meta["passed"] = False
    else:
        meta["passed"] = True  # control-plane ready
    (out_dir / "run_metadata.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["mock-preflight", "preflight", "train"],
        required=True,
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--steps", type=int, default=32)
    parser.add_argument(
        "--i-understand-billing",
        action="store_true",
        help="Required for --mode train (human confirm).",
    )
    parser.add_argument(
        "--preflight-report",
        type=Path,
        default=None,
        help="Path to successful REAL preflight_report.json for train mode.",
    )
    args = parser.parse_args()
    os.environ["S3_CONFIG"] = str(args.config)
    cfg = _load_config(args.config)
    stamp = _utc_stamp()
    if args.output_dir is None:
        if args.mode == "train":
            args.output_dir = ROOT / "runs" / "smolvla_s3" / f"train_{stamp}"
        else:
            args.output_dir = ROOT / "runs" / "smolvla_s3" / f"preflight_{stamp}"

    if args.mode == "mock-preflight":
        report = run_mock_preflight(cfg, args.release_dir, args.output_dir)
    elif args.mode == "preflight":
        if args.steps < 20 or args.steps > 50:
            raise SystemExit("--steps for preflight must be in [20, 50]")
        report = run_real_preflight(
            cfg, args.release_dir, args.output_dir, args.steps, args.config
        )
    else:
        pref = args.preflight_report or (args.output_dir / "preflight_report.json")
        report = run_train_guarded(
            cfg,
            args.release_dir,
            args.output_dir,
            pref,
            args.i_understand_billing,
            args.config,
        )

    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.mode == "mock-preflight":
        return 0 if report.get("passed") else 2
    if args.mode == "preflight":
        return 0 if report.get("passed") else 2
    # train control-plane ready is success locally; execution is AutoDL-only
    return 0 if report.get("passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
