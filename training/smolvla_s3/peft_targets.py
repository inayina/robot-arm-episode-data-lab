"""Normalize SmolVLA Recovery PEFT target_modules (regex string or list)."""

from __future__ import annotations

from typing import Any


OFFICIAL_SMOLVLA_PEFT_REGEX = (
    r"(model\.vlm_with_expert\.lm_expert\..*\.(q|v)_proj|"
    r"model\.(state_proj|action_in_proj|action_out_proj|"
    r"action_time_mlp_in|action_time_mlp_out))"
)


def normalize_target_modules(raw: Any) -> str | list[str]:
    """Preserve a single regex string; wrap / copy module-name lists.

    YAML may load the official PEFT regex as a folded string. Callers that do
    ``for x in target_modules`` must NOT iterate characters.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        return text
    if isinstance(raw, (list, tuple)):
        return [str(x) for x in raw]
    raise TypeError(f"peft.target_modules must be str or list, got {type(raw)!r}")


def target_modules_for_cli(raw: Any) -> str:
    """Serialize for ``--peft.target_modules=...`` (JSON string always)."""
    import json

    normalized = normalize_target_modules(raw)
    return json.dumps(normalized)


def target_modules_fingerprint(raw: Any) -> list[str]:
    """Stable fingerprint for checkpoint audit (one element if regex)."""
    normalized = normalize_target_modules(raw)
    if isinstance(normalized, str):
        return [normalized]
    return sorted(normalized)


def normalize_full_training_modules(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        return [text] if text else []
    if isinstance(raw, (list, tuple)):
        return [str(x) for x in raw]
    raise TypeError(
        f"peft.full_training_modules must be list or str, got {type(raw)!r}"
    )


def peft_contract_from_cfg(peft: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_modules": normalize_target_modules(peft.get("target_modules")),
        "target_modules_fingerprint": target_modules_fingerprint(
            peft.get("target_modules")
        ),
        "full_training_modules": normalize_full_training_modules(
            peft.get("full_training_modules")
        ),
    }
