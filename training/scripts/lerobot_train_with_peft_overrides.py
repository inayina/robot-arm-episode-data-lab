#!/usr/bin/env python3
"""Wrap ``lerobot-train`` so LoRA alpha/dropout/bias reach PEFT on LeRobot 0.5.x.

LeRobot 0.5.1 ``PeftConfig`` only exposes ``method_type`` / ``r`` / ``target_modules`` /
``init_type`` / ``full_training_modules``. Passing ``--peft.lora_alpha`` (etc.) is
rejected by the CLI, so training silently used PEFT defaults (alpha=8, dropout=0.0).

Official ``PreTrainedPolicy._build_peft_config`` already forwards extra keys into
``LoraConfig(**config_dict)``. This entry injects the frozen S3 values before
delegating to ``lerobot.scripts.lerobot_train:main``.

Also enforces Recovery policy feature **replace** (not draccus deep-merge):
``--policy.input_features`` alone leaves base SmolVLA ``camera2``/``camera3`` in
the saved config. Pass ``--s3-policy-input-features`` /
``--s3-policy-output-features`` JSON to replace the feature maps after
``from_pretrained``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def install_peft_overrides(alpha: int, dropout: float, bias: str) -> None:
    """Patch ``_build_peft_config`` so LoraConfig gets alpha/dropout/bias."""
    from lerobot.policies.pretrained import PreTrainedPolicy

    original = PreTrainedPolicy._build_peft_config

    def _build_peft_config(self, cli_overrides: dict):
        overrides = dict(cli_overrides or {})
        overrides["lora_alpha"] = int(alpha)
        overrides["lora_dropout"] = float(dropout)
        overrides["bias"] = str(bias)
        return original(self, overrides)

    PreTrainedPolicy._build_peft_config = _build_peft_config  # type: ignore[method-assign]


def install_local_tokenizer_override(vlm_dir: str) -> None:
    """Force SmolVLM tokenizer loads onto a local directory (AutoDL offline).

    LeRobot's preprocessor ships ``tokenizer_name=HuggingFaceTB/SmolVLM2-...``.
    When huggingface.co is unreachable, ``AutoTokenizer.from_pretrained`` fails
    even if the VLM snapshot is already on disk. Open-loop scripts rewrite the
    processor step config; formal train needs the same redirect here.
    """
    from pathlib import Path

    from transformers import AutoTokenizer

    local = Path(vlm_dir).resolve()
    if not (local / "tokenizer_config.json").is_file():
        raise FileNotFoundError(
            f"SMOLVLA_VLM_DIR missing tokenizer_config.json: {local}"
        )
    hub_id = "HuggingFaceTB/SmolVLM2-500M-Video-Instruct"
    original = AutoTokenizer.from_pretrained

    def from_pretrained(pretrained_model_name_or_path, *args, **kwargs):
        name = str(pretrained_model_name_or_path)
        if name == hub_id:
            pretrained_model_name_or_path = str(local)
            kwargs.setdefault("local_files_only", True)
        return original(pretrained_model_name_or_path, *args, **kwargs)

    AutoTokenizer.from_pretrained = staticmethod(from_pretrained)  # type: ignore[method-assign]


def _coerce_policy_features(raw: dict[str, Any]) -> dict[str, Any]:
    from lerobot.configs.types import FeatureType, PolicyFeature

    out: dict[str, Any] = {}
    for key, spec in raw.items():
        type_name = spec["type"]
        ftype = (
            type_name
            if isinstance(type_name, FeatureType)
            else FeatureType(str(type_name))
        )
        shape = tuple(int(x) for x in spec["shape"])
        out[str(key)] = PolicyFeature(type=ftype, shape=shape)
    return out


def install_policy_feature_replace(
    input_features: dict[str, Any] | None,
    output_features: dict[str, Any] | None,
) -> None:
    """Replace (not merge) policy input/output features after from_pretrained."""
    if input_features is None and output_features is None:
        return

    from lerobot.configs.policies import PreTrainedConfig

    from training.smolvla_s3.policy_features import image_feature_keys

    original = PreTrainedConfig.from_pretrained
    expected_input = (
        _coerce_policy_features(input_features) if input_features is not None else None
    )
    expected_output = (
        _coerce_policy_features(output_features)
        if output_features is not None
        else None
    )

    @classmethod  # type: ignore[misc]
    def from_pretrained(cls, *args, **kwargs):
        cfg = original(*args, **kwargs)
        if expected_input is not None:
            cfg.input_features = dict(expected_input)
            actual_cams = image_feature_keys(
                {k: True for k in (cfg.input_features or {})}
            )
            expected_cams = image_feature_keys(
                {k: True for k in expected_input}
            )
            if actual_cams != expected_cams:
                raise RuntimeError(
                    "S3 policy input_features replace failed: "
                    f"actual={actual_cams} expected={expected_cams}"
                )
        if expected_output is not None:
            cfg.output_features = dict(expected_output)
        return cfg

    PreTrainedConfig.from_pretrained = from_pretrained  # type: ignore[method-assign]


def _parse_json_obj(raw: str | None, flag: str) -> dict[str, Any] | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{flag} must be a JSON object: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{flag} must be a JSON object")
    return value


def _resolve_overrides(
    argv: list[str],
) -> tuple[int, float, str, dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--s3-lora-alpha", type=int, default=None)
    parser.add_argument("--s3-lora-dropout", type=float, default=None)
    parser.add_argument("--s3-lora-bias", type=str, default=None)
    parser.add_argument("--s3-policy-input-features", type=str, default=None)
    parser.add_argument("--s3-policy-output-features", type=str, default=None)
    known, rest = parser.parse_known_args(argv)

    alpha = known.s3_lora_alpha
    if alpha is None:
        alpha = int(os.environ.get("S3_LORA_ALPHA", "64"))
    dropout = known.s3_lora_dropout
    if dropout is None:
        dropout = float(os.environ.get("S3_LORA_DROPOUT", "0.05"))
    bias = known.s3_lora_bias
    if bias is None:
        bias = os.environ.get("S3_LORA_BIAS", "none")

    input_features = _parse_json_obj(
        known.s3_policy_input_features
        or os.environ.get("S3_POLICY_INPUT_FEATURES"),
        "--s3-policy-input-features",
    )
    output_features = _parse_json_obj(
        known.s3_policy_output_features
        or os.environ.get("S3_POLICY_OUTPUT_FEATURES"),
        "--s3-policy-output-features",
    )
    return alpha, dropout, bias, input_features, output_features, rest


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    alpha, dropout, bias, input_features, output_features, rest = _resolve_overrides(
        argv
    )
    install_peft_overrides(alpha, dropout, bias)
    install_policy_feature_replace(input_features, output_features)
    vlm_dir = os.environ.get("SMOLVLA_VLM_DIR", "").strip()
    if vlm_dir:
        install_local_tokenizer_override(vlm_dir)
    # lerobot's @parser.wrap reads sys.argv
    sys.argv = [sys.argv[0], *rest]
    from lerobot.scripts.lerobot_train import main as lerobot_main

    lerobot_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
