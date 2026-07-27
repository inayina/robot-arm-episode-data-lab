"""Tests for Wilson CI portfolio count notes."""

from __future__ import annotations

from evaluation.stats_interpretation import (
    PORTFOLIO_COUNT_NOTES,
    interpret_count,
    wilson_interval,
)


def test_wilson_0_of_5() -> None:
    rate, lo, hi = wilson_interval(0, 5)
    assert rate == 0.0
    assert lo == 0.0
    assert hi is not None and 0.40 < hi < 0.45


def test_wilson_5_of_5() -> None:
    rate, lo, hi = wilson_interval(5, 5)
    assert rate == 1.0
    assert hi == 1.0
    assert lo is not None and 0.55 < lo < 0.60


def test_portfolio_notes_cover_anchors() -> None:
    assert "smolvla_s4_relight_lift_0_of_5" in PORTFOLIO_COUNT_NOTES
    assert "scripted_oracle_lift_5_of_5" in PORTFOLIO_COUNT_NOTES
    note = interpret_count(0, 5, label="demo")
    assert "do not extrapolate" in note["interpretation"]
    assert "claims_task_success" in note["non_extrapolation"]
