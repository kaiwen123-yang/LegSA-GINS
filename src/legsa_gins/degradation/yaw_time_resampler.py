"""Wrap-safe yaw resampling for provider time axes."""

from __future__ import annotations

import bisect
import math
from typing import Any

from legsa_gins.degradation.lateral_baseline_yaw_conversion import circular_diff_deg, wrap360


def _as_float(value: Any, default: float = math.nan) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def interpolate_yaw_deg(
    rows: list[dict[str, Any]],
    target_time: float,
    *,
    time_key: str = "time",
    yaw_key: str = "yaw_deg",
    tolerance_sec: float = 2.0,
) -> float | None:
    if not rows:
        return None
    times = [_as_float(row.get(time_key)) for row in rows]
    if any(not math.isfinite(t) for t in times):
        return None
    target = float(target_time)
    if target < times[0] - tolerance_sec or target > times[-1] + tolerance_sec:
        return None
    index = bisect.bisect_left(times, target)
    if index == 0:
        return wrap360(_as_float(rows[0].get(yaw_key))) if abs(times[0] - target) <= tolerance_sec else None
    if index >= len(times):
        return wrap360(_as_float(rows[-1].get(yaw_key))) if abs(times[-1] - target) <= tolerance_sec else None
    left = rows[index - 1]
    right = rows[index]
    lt = times[index - 1]
    rt = times[index]
    if min(abs(target - lt), abs(target - rt)) > tolerance_sec:
        return None
    ly = _as_float(left.get(yaw_key))
    ry = _as_float(right.get(yaw_key))
    if not math.isfinite(ly) or not math.isfinite(ry):
        return None
    if rt <= lt:
        return wrap360(ly)
    frac = (target - lt) / (rt - lt)
    return wrap360(ly + circular_diff_deg(ry, ly) * frac)


def resample_yaw_series(
    source_rows: list[dict[str, Any]],
    provider_times: list[float],
    *,
    provider_to_source_time_offset_sec: float,
    time_key: str = "time",
    yaw_key: str = "yaw_deg",
) -> list[float | None]:
    return [
        interpolate_yaw_deg(
            source_rows,
            float(t) + float(provider_to_source_time_offset_sec),
            time_key=time_key,
            yaw_key=yaw_key,
        )
        for t in provider_times
    ]

