"""Ambiguity evidence helpers for DA3R2 raw-carrier backends."""

from __future__ import annotations

from .dd_los_provider import BaselineEpoch


def ambiguity_summary(epochs: list[BaselineEpoch]) -> dict[str, object]:
    fixed = [row for row in epochs if row.q == 1]
    float_rows = [row for row in epochs if row.q == 2]
    ratio_ready = [row for row in epochs if row.ratio > 0.0]
    return {
        "ambiguity_ready": bool(fixed or ratio_ready),
        "fixed_epoch_count": len(fixed),
        "float_epoch_count": len(float_rows),
        "ratio_epoch_count": len(ratio_ready),
        "rtklib_q1_is_fixed_integer_solution": True,
        "rtklib_q2_is_float_solution": True,
        "status_yaw_fallback_counted_as_ambiguity": False,
    }
