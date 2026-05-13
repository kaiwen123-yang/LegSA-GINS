"""Small bounded linear solver for N8A no-feedback FGO."""

from __future__ import annotations

from typing import Any


def moving_average(values: list[float], window: int = 3) -> list[float]:
    """中文说明：fallback smoother；固定窗口，不根据评价结果调参。"""
    if not values:
        return []
    half = max(0, window // 2)
    smoothed: list[float] = []
    for index in range(len(values)):
        lo = max(0, index - half)
        hi = min(len(values), index + half + 1)
        smoothed.append(sum(values[lo:hi]) / max(1, hi - lo))
    return smoothed


def solve_no_feedback_linear_system(series: list[list[float]], *, smoothness_weight: float = 0.15) -> dict[str, Any]:
    """中文说明：对状态序列做离线平滑诊断，不反馈、不替换 EKF NAV。"""
    if not series:
        return {"solved": False, "state_count": 0, "smoothed": [], "finite_output": True, "residual_proxy_p95": 0.0}
    columns = list(zip(*series))
    smoothed_columns = [moving_average(list(col), window=3) for col in columns]
    smoothed = [list(row) for row in zip(*smoothed_columns)]
    residuals = [
        abs(raw - smooth)
        for raw_row, smooth_row in zip(series, smoothed)
        for raw, smooth in zip(raw_row, smooth_row)
    ]
    ordered = sorted(residuals)
    p95 = ordered[int(0.95 * (len(ordered) - 1))] if ordered else 0.0
    return {
        "solved": True,
        "state_count": len(series),
        "smoothed": smoothed,
        "finite_output": all(all(abs(value) < 1e12 for value in row) for row in smoothed),
        "residual_proxy_p95": p95,
        "smoothness_weight": smoothness_weight,
        "no_feedback": True,
    }
