from __future__ import annotations

from training.scripts.audit_smolvla_s3_phaseaware_dataset import (
    _close_ramp_frames,
)


def test_close_ramp_excludes_fully_open_wait() -> None:
    grips = [1.0] * 200 + [0.95, 0.85, 0.7, 0.575, 0.5, 0.375, 0.2, 0.0]
    assert _close_ramp_frames(grips) == 4


def test_close_ramp_returns_none_without_departure_or_close() -> None:
    assert _close_ramp_frames([1.0] * 20) is None
    assert _close_ramp_frames([1.0, 0.9, 0.8, 0.7]) is None
