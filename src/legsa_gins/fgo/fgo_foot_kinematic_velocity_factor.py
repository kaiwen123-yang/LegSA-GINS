"""N8F foot kinematic velocity factor for no-feedback FGO.

该因子把 N7C5 足端运动学速度候选正式转成 FGO velocity residual。
默认只约束水平速度 vN/vE，不使用 Go2 速度或接触作为真值。
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence

from .fgo_contact_aware_weighting_factor import ContactAwareWeightRow, clamp, finite_float


STATE_VN_COL = 6
STATE_VE_COL = 7
STATE_VD_COL = 8


@dataclass(frozen=True)
class FootKinematicVelocityFactorRow:
    state_index: int
    time: float
    vn_mps: float
    ve_mps: float
    std_vn_mps: float
    std_ve_mps: float
    slip_risk: float
    contact_weight_scale: float
    measurement_source: str = "N7C5_foot_kinematic_velocity_candidate"


def _nearest_index(rows: Sequence[Mapping[str, str]], time_value: float) -> int:
    if not rows:
        return -1
    return min(range(len(rows)), key=lambda idx: abs(finite_float(rows[idx].get("time"), time_value) - time_value))


def build_foot_kinematic_velocity_factors(
    *,
    epoch_times: Sequence[float],
    foot_rows: Sequence[Mapping[str, str]],
    contact_rows: Sequence[ContactAwareWeightRow],
    max_rows: int | None = None,
) -> List[FootKinematicVelocityFactorRow]:
    """Align N7C5 foot-kinematic velocity rows to FGO epochs."""

    if not epoch_times or not foot_rows:
        return []
    limit = len(epoch_times) if max_rows is None else min(len(epoch_times), max_rows)
    out: List[FootKinematicVelocityFactorRow] = []
    for idx in range(limit):
        time_value = epoch_times[idx]
        foot_idx = _nearest_index(foot_rows, time_value)
        if foot_idx < 0:
            foot_idx = min(idx, len(foot_rows) - 1)
        foot_row = foot_rows[foot_idx]
        vn = finite_float(foot_row.get("candidate_vn"), math.nan)
        ve = finite_float(foot_row.get("candidate_ve"), math.nan)
        if not (math.isfinite(vn) and math.isfinite(ve)):
            continue
        contact = contact_rows[idx] if idx < len(contact_rows) else ContactAwareWeightRow(time_value, 1.5, 0.5, 0.5, 0.5)
        slip = finite_float(foot_row.get("slip_risk"), contact.slip_risk)
        base_std = 0.85 + 0.65 * clamp(slip, 0.0, 1.0)
        scale = max(0.55, contact.contact_weight_scale)
        out.append(
            FootKinematicVelocityFactorRow(
                state_index=idx,
                time=time_value,
                vn_mps=vn,
                ve_mps=ve,
                std_vn_mps=max(0.35, base_std * scale),
                std_ve_mps=max(0.35, base_std * scale),
                slip_risk=clamp(slip, 0.0, 1.0),
                contact_weight_scale=scale,
            )
        )
    return out


def residuals_for_foot_kinematic_velocity(
    solution_vectors: Sequence[Sequence[float]],
    factor_rows: Sequence[FootKinematicVelocityFactorRow],
) -> List[Dict[str, float | int | str]]:
    residuals: List[Dict[str, float | int | str]] = []
    for row in factor_rows:
        if row.state_index >= len(solution_vectors):
            continue
        vec = solution_vectors[row.state_index]
        rvn = (float(vec[STATE_VN_COL]) - row.vn_mps) / row.std_vn_mps
        rve = (float(vec[STATE_VE_COL]) - row.ve_mps) / row.std_ve_mps
        residuals.extend(
            [
                {
                    "factor_type": "FootKinematicVelocityFactor",
                    "state_index": row.state_index,
                    "dimension": "vn",
                    "whitened_residual": rvn,
                    "jacobian_nonzero": 1,
                },
                {
                    "factor_type": "FootKinematicVelocityFactor",
                    "state_index": row.state_index,
                    "dimension": "ve",
                    "whitened_residual": rve,
                    "jacobian_nonzero": 1,
                },
            ]
        )
    return residuals


def inject_foot_kinematic_velocity(
    solution_vectors: Sequence[Sequence[float]],
    factor_rows: Sequence[FootKinematicVelocityFactorRow],
    *,
    strength: float = 0.18,
) -> List[List[float]]:
    """Apply a conservative linearized velocity update for N8F reruns."""

    out = [list(vec) for vec in solution_vectors]
    for row in factor_rows:
        if row.state_index >= len(out):
            continue
        vec = out[row.state_index]
        weight = clamp(strength / max(row.contact_weight_scale, 0.55), 0.02, 0.45)
        vec[STATE_VN_COL] = (1.0 - weight) * float(vec[STATE_VN_COL]) + weight * row.vn_mps
        vec[STATE_VE_COL] = (1.0 - weight) * float(vec[STATE_VE_COL]) + weight * row.ve_mps
    return out


def summarize_foot_kinematic_velocity_factor(
    factor_rows: Sequence[FootKinematicVelocityFactorRow],
    residual_rows: Sequence[Mapping[str, object]],
    *,
    toggle_delta_rows: int = 0,
) -> Dict[str, object]:
    residual_values = [abs(finite_float(row.get("whitened_residual"))) for row in residual_rows]
    slip_values = [row.slip_risk for row in factor_rows]
    return {
        "stage": "N8F",
        "factor_name": "FootKinematicVelocityFactor",
        "classification": "active_proprioceptive_velocity_factor_not_truth",
        "default_dimensions": ["velocity_north", "velocity_east"],
        "vertical_velocity_enabled": False,
        "factor_rows": len(factor_rows),
        "residual_rows": len(residual_rows),
        "jacobian_nonzero_count": sum(int(row.get("jacobian_nonzero", 0)) for row in residual_rows),
        "toggle_delta_rows": toggle_delta_rows,
        "toggle_works": toggle_delta_rows > 0 if factor_rows else False,
        "state_blocks_touched": ["velocity_north", "velocity_east"],
        "no_position_block": True,
        "no_yaw_absolute_factor": True,
        "no_vertical_velocity_factor": True,
        "go2_truth_claim": False,
        "trace_input": False,
        "finalv23_input": False,
        "paper_performance_claim": False,
        "slip_risk_mean": statistics.fmean(slip_values) if slip_values else 0.0,
        "whitened_residual_p95": _p95(residual_values),
        "measurement_source": "N7C5_foot_kinematic_velocity_candidate",
    }


def _p95(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[int(round((len(ordered) - 1) * 0.95))]


def write_foot_factor_table(path: Path, factor_rows: Sequence[FootKinematicVelocityFactorRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "factor_type",
                "state_index",
                "time",
                "vn_mps",
                "ve_mps",
                "std_vn_mps",
                "std_ve_mps",
                "slip_risk",
                "contact_weight_scale",
                "measurement_source",
            ],
        )
        writer.writeheader()
        for row in factor_rows:
            writer.writerow(
                {
                    "factor_type": "FootKinematicVelocityFactor",
                    "state_index": row.state_index,
                    "time": f"{row.time:.9f}",
                    "vn_mps": f"{row.vn_mps:.9f}",
                    "ve_mps": f"{row.ve_mps:.9f}",
                    "std_vn_mps": f"{row.std_vn_mps:.9f}",
                    "std_ve_mps": f"{row.std_ve_mps:.9f}",
                    "slip_risk": f"{row.slip_risk:.9f}",
                    "contact_weight_scale": f"{row.contact_weight_scale:.9f}",
                    "measurement_source": row.measurement_source,
                }
            )


def write_factor_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

