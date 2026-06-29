"""Wrap-safe validation for yaw provider tables."""

from __future__ import annotations

import math
from typing import Any

from legsa_gins.degradation.lateral_baseline_yaw_conversion import circular_diff_deg


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def validate_yaw_wrap(rows: list[dict[str, Any]]) -> dict[str, Any]:
    yaw_values = [_float(row.get("yaw_deg")) for row in rows if str(row.get("status", "")).lower() != "outage"]
    finite = [v for v in yaw_values if math.isfinite(v)]
    # Provider files may store yaw either as [0, 360) or solver-friendly
    # signed wrapped degrees [-180, 180). Both are valid as long as circular
    # differences are used for residual/effect checks.
    range_fail = [v for v in finite if v < -180.0 or v >= 360.0]
    diffs = [abs(circular_diff_deg(b, a)) for a, b in zip(finite, finite[1:])]
    diff_fail = [d for d in diffs if d > 180.0 + 1.0e-9]
    return {
        "row_count": len(rows),
        "finite_yaw_count": len(finite),
        "nonfinite_yaw_count": len(yaw_values) - len(finite),
        "yaw_range_fail_count": len(range_fail),
        "wrap_diff_fail_count": len(diff_fail),
        "max_wrap_step_deg": max(diffs) if diffs else 0.0,
        "wrap_policy": "atan2(sin(diff),cos(diff)) circular difference equivalent",
        "yaw_wrap_validation_status": "PASS" if len(finite) == len(yaw_values) and not range_fail and not diff_fail else "FAIL",
    }
