"""Small bounded linear solver for N8A no-feedback FGO."""

from __future__ import annotations

from typing import Any

from legsa_gins.fgo.fgo_angle_utils import normalize_deg_0_360, safe_angle_diff_deg, unwrap_series_deg


DEFAULT_SMOOTHNESS_WEIGHT = 0.15


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


def _blend(raw: list[float], averaged: list[float], alpha: float) -> list[float]:
    return [left + alpha * (right - left) for left, right in zip(raw, averaged)]


def solve_no_feedback_linear_system(
    series: list[list[float]],
    *,
    smoothness_weight: float = DEFAULT_SMOOTHNESS_WEIGHT,
    column_smoothness_weights: dict[int, float] | None = None,
    angle_column_indices: tuple[int, ...] = tuple(),
    window: int = 3,
) -> dict[str, Any]:
    """中文说明：对状态序列做离线平滑诊断；yaw 列使用 shortest-angle 约定。"""
    if not series:
        return {"solved": False, "state_count": 0, "smoothed": [], "finite_output": True, "residual_proxy_p95": 0.0}

    def _alpha(weight: float) -> float:
        return 0.0 if weight <= 0.0 else min(1.0, weight / DEFAULT_SMOOTHNESS_WEIGHT)

    alpha = _alpha(smoothness_weight)
    column_weights = column_smoothness_weights or {}
    angle_columns = set(angle_column_indices)
    columns = list(zip(*series))
    smoothed_columns: list[list[float]] = []
    for index, col in enumerate(columns):
        values = [float(value) for value in col]
        column_alpha = _alpha(float(column_weights.get(index, smoothness_weight)))
        if index in angle_columns:
            unwrapped = unwrap_series_deg(values)
            averaged = moving_average(unwrapped, window=window)
            smoothed_columns.append([normalize_deg_0_360(value) for value in _blend(unwrapped, averaged, column_alpha)])
        else:
            averaged = moving_average(values, window=window)
            smoothed_columns.append(_blend(values, averaged, column_alpha))
    smoothed = [list(row) for row in zip(*smoothed_columns)]
    residuals: list[float] = []
    for raw_row, smooth_row in zip(series, smoothed):
        for column_index, (raw, smooth) in enumerate(zip(raw_row, smooth_row)):
            if column_index in angle_columns:
                residuals.append(abs(safe_angle_diff_deg(float(raw), float(smooth))))
            else:
                residuals.append(abs(float(raw) - float(smooth)))
    ordered = sorted(residuals)
    p95 = ordered[int(0.95 * (len(ordered) - 1))] if ordered else 0.0
    final_cost = sum(value * value for value in residuals)
    return {
        "solved": True,
        "state_count": len(series),
        "smoothed": smoothed,
        "finite_output": all(all(abs(value) < 1e12 for value in row) for row in smoothed),
        "residual_proxy_p95": p95,
        "iteration_count": 1,
        "final_cost": final_cost,
        "smoothness_weight": smoothness_weight,
        "smoothness_alpha": alpha,
        "column_smoothness_weights": {str(key): value for key, value in sorted(column_weights.items())},
        "angle_column_indices": sorted(angle_columns),
        "yaw_wrap_residuals_enabled": 5 in angle_columns,
        "no_feedback": True,
    }
