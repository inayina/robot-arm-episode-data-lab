"""Policy feature contract helpers for SmolVLA S3 Recovery.

LeRobot 0.5.x ``PreTrainedConfig.from_pretrained`` applies CLI overrides via
``draccus.parse``, which **deep-merges** dict fields. Passing
``--policy.input_features`` with only ``camera1`` therefore leaves base
SmolVLA ``camera2`` / ``camera3`` (256x256) in the live config and in the
saved checkpoint metadata.

Recovery training with ``empty_cameras=0`` still only forwards present batch
cameras (scene→camera1), so those leftover keys are metadata drift — but they
fail ``checkpoint_config_verified``. These helpers enforce a replace (not
merge) contract and support auditable metadata repair.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping


def image_feature_keys(features: Mapping[str, Any] | None) -> list[str]:
    return sorted(
        key
        for key in (features or {})
        if str(key).startswith("observation.images.")
        and "empty_camera_" not in str(key)
    )


def apply_feature_contract(
    features: Mapping[str, Any] | None,
    contract: Mapping[str, Any],
    *,
    drop_unlisted_images: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    """Return features with ``contract`` applied; optionally drop extra images.

    Non-image keys outside the contract are preserved. Contract keys always
    overwrite. Extra ``observation.images.*`` keys (except empty_camera pads)
    are removed when ``drop_unlisted_images`` is true.
    """
    out: dict[str, Any] = dict(features or {})
    removed: list[str] = []
    if drop_unlisted_images:
        allowed_images = {
            key
            for key in contract
            if str(key).startswith("observation.images.")
        }
        for key in list(out):
            if (
                str(key).startswith("observation.images.")
                and "empty_camera_" not in str(key)
                and key not in allowed_images
            ):
                removed.append(str(key))
                del out[key]
    for key, spec in contract.items():
        out[str(key)] = dict(spec)
    return out, removed


def simulate_draccus_feature_merge(
    base: Mapping[str, Any],
    override: Mapping[str, Any],
) -> dict[str, Any]:
    """Reproduce LeRobot/draccus deep-merge for feature dicts (test helper)."""
    merged = dict(base)
    for key, spec in override.items():
        if isinstance(spec, Mapping) and isinstance(merged.get(key), Mapping):
            nested = dict(merged[key])
            nested.update(dict(spec))
            merged[key] = nested
        else:
            merged[key] = dict(spec) if isinstance(spec, Mapping) else spec
    return merged


def replace_feature_mapping(
    current: MutableMapping[str, Any] | None,
    replacement: Mapping[str, Any],
) -> dict[str, Any]:
    """Full replace used at train-time after from_pretrained merge."""
    return {str(key): dict(spec) for key, spec in replacement.items()}
