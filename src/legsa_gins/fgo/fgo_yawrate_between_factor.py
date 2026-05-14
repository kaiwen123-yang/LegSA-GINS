"""N8F Go2 yaw-rate between factor.

该因子使用 Go2 yaw_speed 形成 yaw_k/yaw_{k+1} between residual。
它不是绝对 yaw 真值，也不反馈 EKF。
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

from .fgo_contact_aware_weighting_factor import clamp, finite_float
from .fgo_angle_utils import wrap_deg


STATE_YAW_COL = 5


@dataclass(frozen=True)
class YawRateBetweenFactorRow:
    prev_index: int
    next_index: int
    time: float
    dt_s: float
    yaw_rate_dps: float
    std_deg: float
    measurement_source: str = "N7C5_go2_yaw_speed_candidate"


def build_yawrate_between_factors(
    *,
    epoch_times: Sequence[float],
    yaw_speed_rows: Sequence[Mapping[str, str]],
    solution_vectors: Sequence[Sequence[float]] | None = None,
    max_rows: int | None = None,
) -> List[YawRateBetweenFactorRow]:
    if len(epoch_times) < 2 or not yaw_speed_rows:
        return []
    limit = len(epoch_times) - 1 if max_rows is None else min(len(epoch_times) - 1, max_rows)
    out: List[YawRateBetweenFactorRow] = []
    for idx in range(limit):
        dt = float(epoch_times[idx + 1] - epoch_times[idx])
        if not math.isfinite(dt) or dt <= 0.0:
            continue
        src_idx = min(idx, len(yaw_speed_rows) - 1)
        src = yaw_speed_rows[src_idx]
        yaw_speed_abs = finite_float(src.get("yaw_speed_abs"), finite_float(src.get("yaw_speed"), 0.0))
        yaw_rate_dps = math.degrees(abs(yaw_speed_abs))
        if solution_vectors and idx + 1 < len(solution_vectors):
            state_delta = wrap_deg(
                float(solution_vectors[idx + 1][STATE_YAW_COL]) - float(solution_vectors[idx][STATE_YAW_COL])
            )
            sign = -1.0 if state_delta < 0.0 else 1.0
            yaw_rate_dps *= sign
        std_deg = max(1.5, 2.5 + 0.15 * abs(yaw_rate_dps) * dt)
        out.append(
            YawRateBetweenFactorRow(
                prev_index=idx,
                next_index=idx + 1,
                time=epoch_times[idx],
                dt_s=dt,
                yaw_rate_dps=yaw_rate_dps,
                std_deg=std_deg,
            )
        )
    return out


def yawrate_between_residual_deg(yaw_k_deg: float, yaw_next_deg: float, yaw_rate_dps: float, dt_s: float) -> float:
    return wrap_deg((yaw_next_deg - yaw_k_deg) - yaw_rate_dps * dt_s)


def residuals_for_yawrate_between(
    solution_vectors: Sequence[Sequence[float]],
    factor_rows: Sequence[YawRateBetweenFactorRow],
) -> List[Dict[str, float | int | str]]:
    residuals: List[Dict[str, float | int | str]] = []
    for row in factor_rows:
        if row.next_index >= len(solution_vectors):
            continue
        yaw_k = float(solution_vectors[row.prev_index][STATE_YAW_COL])
        yaw_next = float(solution_vectors[row.next_index][STATE_YAW_COL])
        residual = yawrate_between_residual_deg(yaw_k, yaw_next, row.yaw_rate_dps, row.dt_s) / row.std_deg
        residuals.append(
            {
                "factor_type": "YawRateBetweenFactor",
                "prev_index": row.prev_index,
                "next_index": row.next_index,
                "dimension": "yaw_between",
                "whitened_residual": residual,
                "jacobian_nonzero": 2,
            }
        )
    return residuals


def inject_yawrate_between(
    solution_vectors: Sequence[Sequence[float]],
    factor_rows: Sequence[YawRateBetweenFactorRow],
    *,
    strength: float = 0.12,
) -> List[List[float]]:
    out = [list(vec) for vec in solution_vectors]
    for row in factor_rows:
        if row.next_index >= len(out):
            continue
        prev_yaw = float(out[row.prev_index][STATE_YAW_COL])
        target = prev_yaw + row.yaw_rate_dps * row.dt_s
        current = float(out[row.next_index][STATE_YAW_COL])
        residual = wrap_deg(target - current)
        out[row.next_index][STATE_YAW_COL] = wrap_deg(current + clamp(strength, 0.0, 0.5) * residual)
    return out


def summarize_yawrate_between_factor(
    factor_rows: Sequence[YawRateBetweenFactorRow],
    residual_rows: Sequence[Mapping[str, object]],
    *,
    toggle_delta_rows: int = 0,
) -> Dict[str, object]:
    residual_values = [abs(finite_float(row.get("whitened_residual"))) for row in residual_rows]
    return {
        "stage": "N8F",
        "factor_name": "YawRateBetweenFactor",
        "classification": "active_between_factor_not_absolute_yaw_truth",
        "factor_rows": len(factor_rows),
        "residual_rows": len(residual_rows),
        "jacobian_nonzero_count": sum(int(row.get("jacobian_nonzero", 0)) for row in residual_rows),
        "toggle_delta_rows": toggle_delta_rows,
        "toggle_works": toggle_delta_rows > 0 if factor_rows else False,
        "state_blocks_touched": ["yaw_k", "yaw_k_plus_1"],
        "jacobian_contract": {"yaw_k": -1.0, "yaw_k_plus_1": 1.0},
        "wrap_boundary_test_passed": yawrate_between_residual_deg(359.0, 1.0, 2.0, 1.0) == 0.0,
        "absolute_yaw_truth_claim": False,
        "trace_input": False,
        "finalv23_input": False,
        "paper_performance_claim": False,
        "whitened_residual_p95": _p95(residual_values),
        "measurement_source": "N7C5_go2_yaw_speed_candidate",
    }


def _p95(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[int(round((len(ordered) - 1) * 0.95))]


def write_yawrate_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
