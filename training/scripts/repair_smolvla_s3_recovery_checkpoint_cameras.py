#!/usr/bin/env python3
"""Repair Recovery checkpoint camera metadata and re-run checkpoint audit.

Strips base SmolVLA ``camera2``/``camera3`` leftovers left by draccus deep-merge
of ``--policy.input_features``. Does not retrain and does not touch adapter
weights. Prefer this over a full AutoDL retrain when only
``nonempty_camera_keys`` / ``preprocessor_nonempty_camera_keys`` failed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.smolvla_s3.control_plane import (  # noqa: E402
    _load_config,
    audit_trained_checkpoint,
    finalize_train_run,
    repair_checkpoint_camera_contract,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT
        / "configs"
        / "smolvla_s3"
        / "lora_train_recovery_v3_phaseaware50.yaml",
    )
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="If set, rewrite run_metadata via finalize-train after a successful repair.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan strip without writing JSON backups/edits.",
    )
    args = parser.parse_args(argv)

    cfg = _load_config(args.config)
    repair = repair_checkpoint_camera_contract(
        cfg, args.checkpoint_dir, write=not args.dry_run
    )
    audit = None
    meta = None
    if repair.get("passed") and not args.dry_run and repair.get("wrote"):
        audit = audit_trained_checkpoint(cfg, args.checkpoint_dir)
        if args.output_dir is not None and audit.get("passed"):
            meta = finalize_train_run(
                cfg, args.output_dir, args.checkpoint_dir, args.config
            )
            (args.output_dir / "checkpoint_config_audit.json").write_text(
                json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (args.output_dir / "checkpoint_camera_repair.json").write_text(
                json.dumps(repair, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    report = {
        "passed": bool(repair.get("passed"))
        and (args.dry_run or (audit is not None and audit.get("passed"))),
        "gate": (
            "checkpoint_config_verified"
            if audit and audit.get("passed")
            else (
                "repair_planned"
                if args.dry_run and repair.get("passed")
                else "no_go"
            )
        ),
        "repair": repair,
        "checkpoint_audit": audit,
        "run_metadata": meta,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
