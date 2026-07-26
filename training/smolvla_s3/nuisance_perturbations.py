"""Image nuisance perturbations for open-loop diagnostics.

Applied on BGR uint8 frames before CHW float conversion.
Does not alter expert GT actions (nuisance contract).
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np


def apply_nuisance_bgr(
    frame_bgr: np.ndarray,
    spec: Mapping[str, Any],
    *,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Return a perturbed BGR copy. `clean` / identity leaves values unchanged."""
    if frame_bgr is None:
        raise ValueError("frame_bgr is required")
    out = np.asarray(frame_bgr, dtype=np.uint8).copy()
    scale = float(spec.get("brightness_scale", 1.0))
    if abs(scale - 1.0) > 1e-9:
        out = np.clip(out.astype(np.float32) * scale, 0, 255).astype(np.uint8)

    ksize = int(spec.get("gaussian_blur_ksize", 0) or 0)
    if ksize >= 3:
        import cv2

        if ksize % 2 == 0:
            ksize += 1
        out = cv2.GaussianBlur(out, (ksize, ksize), 0)

    noise_std = float(spec.get("gaussian_noise_std", 0.0) or 0.0)
    if noise_std > 0.0:
        gen = rng if rng is not None else np.random.default_rng(0)
        noise = gen.normal(0.0, noise_std, size=out.shape)
        out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    return out


def condition_seed(episode_ref: str, frame_index: int, condition: str) -> int:
    """Stable seed so noise draws are reproducible across reruns."""
    raw = f"{episode_ref}|{frame_index}|{condition}".encode("utf-8")
    return int.from_bytes(raw[:8].ljust(8, b"\0"), "little", signed=False) % (2**31 - 1)
