"""First-epoch diagnostics for N4H4D1.

中文说明：根据 CONFIG/INPUT/FIRST_UPDATES/FIRST_PROPAGATIONS 判断首 epoch 是否已经异常；
这里只分类问题，不修 solver、不调参、不删 epoch。
"""

from __future__ import annotations

import math
from typing import Any


def _number(value: Any, default: float = math.nan) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def analyze_first_epoch(
    config_snapshot: dict[str, Any],
    input_snapshot: dict[str, Any],
    first_updates: list[dict[str, Any]],
    first_propagations: list[dict[str, Any]],
) -> dict[str, Any]:
    """中文说明：输出 first-epoch 分类；所有阈值只用于诊断，不是评价门限。"""

    first_update = first_updates[0] if first_updates else {}
    first_prop = first_propagations[0] if first_propagations else {}
    first_imu_dt = _number(input_snapshot.get("first_imu_dt"), default=_number(first_prop.get("dt"), default=math.nan))
    first_dtheta_norm = _number(input_snapshot.get("first_imu_dtheta_norm"), 0.0)
    first_dvel_norm = _number(input_snapshot.get("first_imu_dvel_norm"), 0.0)
    first_imu_time = _number(input_snapshot.get("first_imu_time"))
    first_gnss_time = _number(input_snapshot.get("first_gnss_time"))
    last_imu_time = _number(input_snapshot.get("last_imu_time"))
    yaw_residual = _number(first_update.get("yaw_residual_deg"))
    pos_residual = _norm(
        [
            _number(first_update.get("position_residual_n"), 0.0),
            _number(first_update.get("position_residual_e"), 0.0),
            _number(first_update.get("position_residual_d"), 0.0),
        ]
    )
    vel_residual = _norm(
        [
            _number(first_update.get("velocity_residual_n"), 0.0),
            _number(first_update.get("velocity_residual_e"), 0.0),
            _number(first_update.get("velocity_residual_d"), 0.0),
        ]
    )
    dx_phi_norm_deg = _number(first_update.get("dx_phi_norm_deg"), 0.0)
    dx_norm = _number(first_update.get("dx_norm_before_feedback"), 0.0)
    roll = abs(_number(first_prop.get("roll_deg"), 0.0))
    pitch = abs(_number(first_prop.get("pitch_deg"), 0.0))
    yaw = abs(_number(first_prop.get("yaw_deg"), 0.0))
    cov_min_diag = _number(first_prop.get("cov_min_diag"), 1.0)
    cov_max_diag = _number(first_prop.get("cov_max_diag"), 1.0)
    cov_trace = _number(first_prop.get("cov_trace"), 1.0)

    first_epoch_config_issue = bool(config_snapshot.get("evidence_status") == "evidence_missing")
    first_epoch_time_alignment_issue = bool(
        not math.isfinite(first_imu_time)
        or not math.isfinite(first_gnss_time)
        or not math.isfinite(last_imu_time)
        or first_gnss_time < first_imu_time - 1.0
        or first_gnss_time > last_imu_time + 1.0
    )
    first_epoch_update_residual_issue = bool(abs(yaw_residual) > 15.0 or pos_residual > 10.0 or vel_residual > 5.0)
    first_epoch_mechanization_jump_issue = bool(
        first_dtheta_norm > 1.0 or first_dvel_norm > 20.0 or roll > 45.0 or pitch > 45.0 or yaw > 360.0
    )
    first_epoch_feedback_jump_issue = bool(dx_phi_norm_deg > 20.0 or dx_norm > 100.0)
    first_epoch_covariance_issue = bool(
        not math.isfinite(cov_min_diag)
        or cov_min_diag < -1.0e-12
        or not math.isfinite(cov_trace)
        or cov_trace > 1.0e12
        or cov_max_diag <= 0.0
    )

    return {
        "phase": "N4H4D1",
        "first_imu_dt": first_imu_dt,
        "first_imu_dtheta_norm": first_dtheta_norm,
        "first_imu_dvel_norm": first_dvel_norm,
        "first_yaw_residual_deg": yaw_residual,
        "first_position_residual_norm_m": pos_residual,
        "first_velocity_residual_norm_mps": vel_residual,
        "first_dx_phi_norm_deg": dx_phi_norm_deg,
        "first_dx_norm_before_feedback": dx_norm,
        "first_epoch_config_issue": first_epoch_config_issue,
        "first_epoch_time_alignment_issue": first_epoch_time_alignment_issue,
        "first_epoch_update_residual_issue": first_epoch_update_residual_issue,
        "first_epoch_mechanization_jump_issue": first_epoch_mechanization_jump_issue,
        "first_epoch_feedback_jump_issue": first_epoch_feedback_jump_issue,
        "first_epoch_covariance_issue": first_epoch_covariance_issue,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
