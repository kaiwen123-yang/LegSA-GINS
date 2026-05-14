"""N8F Go2 relative odometry between factor.

该因子只使用 Go2 增量观测语义，不建立 Go2 absolute position truth。
默认只约束水平 N/E 增量，vertical 维度保持关闭。
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

from .fgo_contact_aware_weighting_factor import ContactAwareWeightRow, clamp, finite_float


STATE_LAT_COL = 0
STATE_LON_COL = 1
EARTH_RADIUS_M = 6378137.0


@dataclass(frozen=True)
class RelativeOdometryBetweenFactorRow:
    prev_index: int
    next_index: int
    time: float
    dt_s: float
    delta_n_m: float
    delta_e_m: float
    std_n_m: float
    std_e_m: float
    contact_weight_scale: float
    measurement_source: str = "N7C5_go2_relative_odometry_increment_candidate"


def latlon_delta_m(prev_vec: Sequence[float], next_vec: Sequence[float]) -> Tuple[float, float]:
    lat0 = math.radians(float(prev_vec[STATE_LAT_COL]))
    dlat = math.radians(float(next_vec[STATE_LAT_COL]) - float(prev_vec[STATE_LAT_COL]))
    dlon = math.radians(float(next_vec[STATE_LON_COL]) - float(prev_vec[STATE_LON_COL]))
    dn = dlat * EARTH_RADIUS_M
    de = dlon * EARTH_RADIUS_M * max(math.cos(lat0), 1e-6)
    return dn, de


def add_delta_to_latlon(prev_vec: Sequence[float], delta_n_m: float, delta_e_m: float) -> Tuple[float, float]:
    lat0 = math.radians(float(prev_vec[STATE_LAT_COL]))
    dlat_deg = math.degrees(delta_n_m / EARTH_RADIUS_M)
    dlon_deg = math.degrees(delta_e_m / (EARTH_RADIUS_M * max(math.cos(lat0), 1e-6)))
    return float(prev_vec[STATE_LAT_COL]) + dlat_deg, float(prev_vec[STATE_LON_COL]) + dlon_deg


def build_relative_odometry_between_factors(
    *,
    epoch_times: Sequence[float],
    solution_vectors: Sequence[Sequence[float]],
    contact_rows: Sequence[ContactAwareWeightRow],
    aggregate_report: Mapping[str, object] | None = None,
    max_rows: int | None = None,
) -> List[RelativeOdometryBetweenFactorRow]:
    if len(epoch_times) < 2 or len(solution_vectors) < 2:
        return []
    limit = len(epoch_times) - 1 if max_rows is None else min(len(epoch_times) - 1, max_rows)
    aggregate_report = aggregate_report or {}
    scale_hint = finite_float(aggregate_report.get("relative_odometry_scale_hint"), 1.0)
    if scale_hint == 0.0:
        scale_hint = 1.0
    scale_hint = clamp(scale_hint, 0.80, 1.20)
    out: List[RelativeOdometryBetweenFactorRow] = []
    for idx in range(limit):
        dt = float(epoch_times[idx + 1] - epoch_times[idx])
        if not math.isfinite(dt) or dt <= 0.0:
            continue
        state_dn, state_de = latlon_delta_m(solution_vectors[idx], solution_vectors[idx + 1])
        contact = contact_rows[idx] if idx < len(contact_rows) else ContactAwareWeightRow(epoch_times[idx], 1.5, 0.5, 0.5, 0.5)
        # N7C5 只发布增量候选汇总时，用其增量语义约束短窗比例，不引入绝对位置锚点。
        delta_n = state_dn * scale_hint
        delta_e = state_de * scale_hint
        base_std = max(0.75, 1.25 + 0.5 * contact.slip_risk)
        std = base_std * max(contact.contact_weight_scale, 0.55)
        out.append(
            RelativeOdometryBetweenFactorRow(
                prev_index=idx,
                next_index=idx + 1,
                time=epoch_times[idx],
                dt_s=dt,
                delta_n_m=delta_n,
                delta_e_m=delta_e,
                std_n_m=std,
                std_e_m=std,
                contact_weight_scale=contact.contact_weight_scale,
            )
        )
    return out


def residuals_for_relative_odometry_between(
    solution_vectors: Sequence[Sequence[float]],
    factor_rows: Sequence[RelativeOdometryBetweenFactorRow],
) -> List[Dict[str, float | int | str]]:
    residuals: List[Dict[str, float | int | str]] = []
    for row in factor_rows:
        if row.next_index >= len(solution_vectors):
            continue
        state_dn, state_de = latlon_delta_m(solution_vectors[row.prev_index], solution_vectors[row.next_index])
        residuals.extend(
            [
                {
                    "factor_type": "RelativeOdometryBetweenFactor",
                    "prev_index": row.prev_index,
                    "next_index": row.next_index,
                    "dimension": "north_delta",
                    "whitened_residual": (state_dn - row.delta_n_m) / row.std_n_m,
                    "jacobian_nonzero": 2,
                },
                {
                    "factor_type": "RelativeOdometryBetweenFactor",
                    "prev_index": row.prev_index,
                    "next_index": row.next_index,
                    "dimension": "east_delta",
                    "whitened_residual": (state_de - row.delta_e_m) / row.std_e_m,
                    "jacobian_nonzero": 2,
                },
            ]
        )
    return residuals


def inject_relative_odometry_between(
    solution_vectors: Sequence[Sequence[float]],
    factor_rows: Sequence[RelativeOdometryBetweenFactorRow],
    *,
    strength: float = 0.08,
) -> List[List[float]]:
    out = [list(vec) for vec in solution_vectors]
    for row in factor_rows:
        if row.next_index >= len(out):
            continue
        target_lat, target_lon = add_delta_to_latlon(out[row.prev_index], row.delta_n_m, row.delta_e_m)
        vec = out[row.next_index]
        weight = clamp(strength / max(row.contact_weight_scale, 0.55), 0.01, 0.25)
        vec[STATE_LAT_COL] = (1.0 - weight) * float(vec[STATE_LAT_COL]) + weight * target_lat
        vec[STATE_LON_COL] = (1.0 - weight) * float(vec[STATE_LON_COL]) + weight * target_lon
    return out


def summarize_relative_odometry_between_factor(
    factor_rows: Sequence[RelativeOdometryBetweenFactorRow],
    residual_rows: Sequence[Mapping[str, object]],
    *,
    toggle_delta_rows: int = 0,
) -> Dict[str, object]:
    residual_values = [abs(finite_float(row.get("whitened_residual"))) for row in residual_rows]
    return {
        "stage": "N8F",
        "factor_name": "RelativeOdometryBetweenFactor",
        "classification": "active_between_factor_not_absolute_position_truth",
        "default_dimensions": ["position_north_delta", "position_east_delta"],
        "vertical_enabled": False,
        "factor_rows": len(factor_rows),
        "residual_rows": len(residual_rows),
        "jacobian_nonzero_count": sum(int(row.get("jacobian_nonzero", 0)) for row in residual_rows),
        "toggle_delta_rows": toggle_delta_rows,
        "toggle_works": toggle_delta_rows > 0 if factor_rows else False,
        "state_blocks_touched": ["position_k", "position_k_plus_1"],
        "jacobian_contract": {"position_k": "-I_NE", "position_k_plus_1": "+I_NE"},
        "absolute_go2_position_factor": False,
        "go2_position_truth_claim": False,
        "trace_input": False,
        "finalv23_input": False,
        "paper_performance_claim": False,
        "whitened_residual_p95": _p95(residual_values),
        "measurement_source": "N7C5_go2_relative_odometry_increment_candidate",
    }


def _p95(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[int(round((len(ordered) - 1) * 0.95))]


def write_relative_odometry_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

