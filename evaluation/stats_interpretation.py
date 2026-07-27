"""Binomial rate helpers with Wilson 95% CI for small-N portfolio metrics.

Use for interpreting counts like 0/5 or 5/5. These intervals describe
uncertainty of a Bernoulli rate under the observed sample size; they do
**not** authorize extrapolation to larger seed budgets, OOD shifts, or
task success beyond the measured protocol.
"""

from __future__ import annotations

import math
from typing import Any


def wilson_interval(
    successes: int,
    n: int,
    *,
    z: float = 1.96,
) -> tuple[float | None, float | None, float | None]:
    """Return (rate, ci95_low, ci95_high). None triple when n <= 0."""
    if n <= 0:
        return None, None, None
    if successes < 0 or successes > n:
        raise ValueError(f"successes={successes} outside [0, {n}]")
    p = successes / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return p, max(0.0, center - margin), min(1.0, center + margin)


def interpret_count(
    successes: int,
    n: int,
    *,
    label: str,
) -> dict[str, Any]:
    """Short statistical note for portfolio / resume use."""
    rate, lo, hi = wilson_interval(successes, n)
    return {
        "label": label,
        "successes": successes,
        "n": n,
        "rate": rate,
        "ci_method": "wilson" if n > 0 else "not_computed",
        "ci95_low": lo,
        "ci95_high": hi,
        "interpretation": (
            f"{successes}/{n} → point rate "
            f"{(rate if rate is not None else float('nan')):.3f}, "
            f"Wilson 95% CI "
            f"[{(lo if lo is not None else float('nan')):.3f}, "
            f"{(hi if hi is not None else float('nan')):.3f}]. "
            "Interval is for this protocol and sample size only; "
            "do not extrapolate to larger N, OOD, Sim2Real, or task success."
        ),
        "non_extrapolation": (
            "Not a power analysis; not a license to expand seeds; "
            "not Sim2Real; claims_task_success remains false."
        ),
    }


# Frozen portfolio anchors (authoritative counts; CI for communication only).
PORTFOLIO_COUNT_NOTES: dict[str, dict[str, Any]] = {
    "smolvla_s4_relight_lift_0_of_5": interpret_count(0, 5, label="S4 lift (relight)"),
    "scripted_oracle_lift_5_of_5": interpret_count(5, 5, label="oracle lift v2b"),
    "act_e3_overall_0_of_20": interpret_count(0, 20, label="ACT E3 overall"),
}
