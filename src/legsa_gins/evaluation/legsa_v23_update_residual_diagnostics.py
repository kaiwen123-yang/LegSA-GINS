"""Update residual diagnostics for N4H4D1.

中文说明：分析 FIRST_UPDATES.csv 的 position/velocity/yaw residual 和 dx；
它只用于定位 update/feedback 问题，不形成性能 claim。
"""

from __future__ import annotations

import math
from statistics import mean
from typing import Any


def _number(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(math.ceil(ratio * len(ordered))) - 1))
    return ordered[index]


def _norm(row: dict[str, Any], keys: tuple[str, str, str]) -> float:
    return math.sqrt(sum(_number(row, key) ** 2 for key in keys))


def analyze_update_residuals(first_updates: list[dict[str, Any]]) -> dict[str, Any]:
    """中文说明：输出 residual 统计和初步异常分类；不调量测权重。"""

    yaw_abs = [abs(_number(row, "yaw_residual_deg")) for row in first_updates]
    pos_norms = [
        _norm(row, ("position_residual_n", "position_residual_e", "position_residual_d")) for row in first_updates
    ]
    vel_norms = [
        _norm(row, ("velocity_residual_n", "velocity_residual_e", "velocity_residual_d")) for row in first_updates
    ]
    dx_phi = [abs(_number(row, "dx_phi_norm_deg")) for row in first_updates]
    dx_pos = [abs(_number(row, "dx_pos_norm")) for row in first_updates]
    dx_vel = [abs(_number(row, "dx_vel_norm")) for row in first_updates]
    modes = [str(row.get("yaw_scheme_mode", "")) for row in first_updates]
    total = len(first_updates)
    reject_count = sum(1 for mode in modes if "REJECT" in mode)
    normal_count = sum(1 for mode in modes if "NORMAL" in mode)
    downweight_count = sum(1 for mode in modes if "DOWNWEIGHT" in mode)
    reject_ratio = reject_count / total if total else 0.0

    classifications: list[str] = []
    if yaw_abs and (yaw_abs[0] > 90.0 or reject_ratio > 0.5):
        classifications.append("yaw_convention_or_init_issue")
    if pos_norms and max(pos_norms) > 10.0:
        classifications.append("position_residual_sign_or_lever_issue")
    if vel_norms and max(vel_norms) > 5.0:
        classifications.append("velocity_residual_issue")
    if dx_phi and max(dx_phi) > 20.0:
        classifications.append("feedback_jump_issue")
    if not classifications:
        classifications.append("evidence_missing" if not first_updates else "residuals_not_primary_issue")

    return {
        "phase": "N4H4D1",
        "update_count_analyzed": total,
        "yaw_residual_mean_deg": mean(yaw_abs) if yaw_abs else 0.0,
        "yaw_residual_p95_deg": _percentile(yaw_abs, 0.95),
        "yaw_residual_max_deg": max(yaw_abs) if yaw_abs else 0.0,
        "position_residual_norm_mean_m": mean(pos_norms) if pos_norms else 0.0,
        "position_residual_norm_p95_m": _percentile(pos_norms, 0.95),
        "position_residual_norm_max_m": max(pos_norms) if pos_norms else 0.0,
        "velocity_residual_norm_mean_mps": mean(vel_norms) if vel_norms else 0.0,
        "velocity_residual_norm_p95_mps": _percentile(vel_norms, 0.95),
        "velocity_residual_norm_max_mps": max(vel_norms) if vel_norms else 0.0,
        "yaw_normal_count": normal_count,
        "yaw_downweight_count": downweight_count,
        "yaw_reject_count": reject_count,
        "yaw_reject_ratio": reject_ratio,
        "dx_phi_norm_deg_p95": _percentile(dx_phi, 0.95),
        "dx_phi_norm_deg_max": max(dx_phi) if dx_phi else 0.0,
        "dx_pos_norm_p95": _percentile(dx_pos, 0.95),
        "dx_pos_norm_max": max(dx_pos) if dx_pos else 0.0,
        "dx_vel_norm_p95": _percentile(dx_vel, 0.95),
        "dx_vel_norm_max": max(dx_vel) if dx_vel else 0.0,
        "reject_reason_classification": classifications,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }

