"""N8C2 factor activation audit helpers.

The current N8 FGO path is a bounded no-feedback diagnostic smoother.  Some
factor-like policies are represented by solver weights and residual proxies
rather than a production factor table, so this audit keeps direct residual
evidence separate from proxy evidence.

中文说明：本模块只审查 FGO factor 激活证据，不把代理残差包装成正式因子。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_angle_utils import safe_angle_diff_deg, shortest_angle_residual_deg
from legsa_gins.fgo.fgo_factor_registry import build_default_factor_registry
from legsa_gins.fgo.fgo_yaw_convention_fix import _f


ACTIVE_FACTOR_NAMES = [
    "ReceiverPositionFactor",
    "ReceiverVelocityFactor",
    "DualYawFactor",
    "RawDopplerVelocityFactor",
    "Go2ProprioceptiveJointFactor",
    "SmoothnessFactor",
]

FACTOR_OFF_VARIANTS = {
    "RawDopplerVelocityFactor": "raw_doppler_off",
    "Go2ProprioceptiveJointFactor": "go2_joint_off",
    "SmoothnessFactor": "no_smoothness_diagnostic",
}

FACTOR_STD_PROXY = {
    "ReceiverPositionFactor": 1.0,
    "ReceiverVelocityFactor": 1.0,
    "DualYawFactor": 1.0,
    "RawDopplerVelocityFactor": 1.0,
    "Go2ProprioceptiveJointFactor": 1.0,
    "SmoothnessFactor": 1.0,
}


def write_json_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def percentile(values: list[float], pct: float) -> float:
    finite = sorted(abs(value) for value in values if math.isfinite(value))
    if not finite:
        return 0.0
    if len(finite) == 1:
        return finite[0]
    position = (len(finite) - 1) * pct / 100.0
    lo = int(math.floor(position))
    hi = int(math.ceil(position))
    if lo == hi:
        return finite[lo]
    frac = position - lo
    return finite[lo] * (1.0 - frac) + finite[hi] * frac


def residual_stats(values: list[float]) -> dict[str, float]:
    finite = [abs(value) for value in values if math.isfinite(value)]
    return {
        "p50": percentile(finite, 50),
        "p95": percentile(finite, 95),
        "max": max(finite) if finite else 0.0,
        "rmse": math.sqrt(sum(value * value for value in finite) / len(finite)) if finite else 0.0,
        "sum_sq": sum(value * value for value in finite),
    }


def select_current_rows(rows_by_variant: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return rows_by_variant.get("weak_yaw_smoothness") or rows_by_variant.get("default_active_stack_n8a2") or []


def factor_contracts_by_name(registry_report: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    registry = registry_report or build_default_factor_registry()
    return {str(row.get("factor_name")): row for row in registry.get("factors", [])}


def _position_delta_m(left: dict[str, Any], right: dict[str, Any]) -> float:
    lat0 = math.radians(_f(left.get("lat_deg")))
    north = (_f(right.get("lat_deg")) - _f(left.get("lat_deg"))) * 111_320.0
    east = (_f(right.get("lon_deg")) - _f(left.get("lon_deg"))) * 111_320.0 * math.cos(lat0)
    up = _f(right.get("height_m")) - _f(left.get("height_m"))
    return math.sqrt(north * north + east * east + up * up)


def _velocity_delta(left: dict[str, Any], right: dict[str, Any], columns: tuple[str, ...] = ("vn_mps", "ve_mps", "vd_mps")) -> float:
    return math.sqrt(sum((_f(right.get(column)) - _f(left.get(column))) ** 2 for column in columns))


def _go2_joint_delta(left: dict[str, Any], right: dict[str, Any]) -> float:
    roll = safe_angle_diff_deg(_f(right.get("roll_deg")), _f(left.get("roll_deg")))
    pitch = safe_angle_diff_deg(_f(right.get("pitch_deg")), _f(left.get("pitch_deg")))
    vn = _f(right.get("vn_mps")) - _f(left.get("vn_mps"))
    ve = _f(right.get("ve_mps")) - _f(left.get("ve_mps"))
    return math.sqrt(roll * roll + pitch * pitch + vn * vn + ve * ve)


def _smoothness_delta(left: dict[str, Any], right: dict[str, Any]) -> float:
    position = _position_delta_m(left, right)
    roll = safe_angle_diff_deg(_f(right.get("roll_deg")), _f(left.get("roll_deg")))
    pitch = safe_angle_diff_deg(_f(right.get("pitch_deg")), _f(left.get("pitch_deg")))
    yaw = shortest_angle_residual_deg(_f(right.get("yaw_deg")), _f(left.get("yaw_deg")))
    velocity = _velocity_delta(left, right)
    return math.sqrt(position * position + roll * roll + pitch * pitch + yaw * yaw + velocity * velocity)


def build_factor_residual_series(
    *,
    factor_name: str,
    ekf_rows: list[dict[str, Any]],
    fgo_rows: list[dict[str, Any]],
) -> tuple[list[float], list[float]]:
    count = min(len(ekf_rows), len(fgo_rows))
    ekf = ekf_rows[:count]
    fgo = fgo_rows[:count]
    times = [_f(row.get("time", row.get("timestamp")), float(index)) for index, row in enumerate(ekf)]
    if factor_name == "ReceiverPositionFactor":
        return times, [_position_delta_m(left, right) for left, right in zip(ekf, fgo)]
    if factor_name == "ReceiverVelocityFactor":
        return times, [_velocity_delta(left, right) for left, right in zip(ekf, fgo)]
    if factor_name == "DualYawFactor":
        return times, [abs(shortest_angle_residual_deg(_f(right.get("yaw_deg")), _f(left.get("yaw_deg")))) for left, right in zip(ekf, fgo)]
    if factor_name == "RawDopplerVelocityFactor":
        return times, [_velocity_delta(left, right) for left, right in zip(ekf, fgo)]
    if factor_name == "Go2ProprioceptiveJointFactor":
        return times, [_go2_joint_delta(left, right) for left, right in zip(ekf, fgo)]
    if factor_name == "SmoothnessFactor":
        smooth_times = times[1:]
        return smooth_times, [_smoothness_delta(left, right) for left, right in zip(fgo, fgo[1:])]
    return times, []


def _variant(ablation_summary: dict[str, Any], name: str) -> dict[str, Any]:
    return next((row for row in ablation_summary.get("variants", []) if row.get("variant") == name), {})


def _variant_delta(default: dict[str, Any], off: dict[str, Any]) -> dict[str, float]:
    keys = [
        "yaw_delta_wrapped_rmse_deg",
        "horizontal_delta_rmse_m",
        "up_delta_rmse_m",
        "roll_delta_rmse_deg",
        "pitch_delta_rmse_deg",
        "final_cost",
    ]
    deltas = {
        key: float(off.get(key, 0.0) or 0.0) - float(default.get(key, 0.0) or 0.0)
        for key in keys
        if key in default or key in off
    }
    deltas["combined_abs_delta"] = sum(abs(value) for value in deltas.values())
    return deltas


def _covariance_stats(factor_name: str, dimension: int) -> dict[str, float]:
    std = float(FACTOR_STD_PROXY.get(factor_name, 1.0) or 1.0)
    variance = std * std
    return {
        "std_min": std,
        "std_p50": std,
        "std_max": std,
        "covariance_min": variance,
        "covariance_p50": variance,
        "covariance_max": variance,
        "dimension": float(dimension),
    }


def _classify_factor(
    *,
    factor_name: str,
    registered: bool,
    included_in_solver_residual: bool,
    residual_row_count: int,
    whitened_p95: float,
    normalized_p95: float,
    contribution_share: float,
    on_off_delta: float,
) -> str:
    if not registered:
        return "activation_missing"
    if not included_in_solver_residual:
        if residual_row_count > 0:
            return "suspicious_no_effect" if factor_name == "RawDopplerVelocityFactor" else "activation_missing"
        return "activation_missing"
    if factor_name == "SmoothnessFactor" and (contribution_share >= 0.45 or on_off_delta > 0.5):
        return "influential"
    if contribution_share >= 0.35 or on_off_delta > 0.25:
        return "influential"
    if factor_name == "RawDopplerVelocityFactor" and normalized_p95 > 0.0 and contribution_share < 0.05:
        return "active_but_dominated"
    if whitened_p95 > 0.0 and on_off_delta <= 0.05:
        return "consistent_no_large_delta"
    if whitened_p95 > 0.0:
        return "weak_but_active"
    return "suspicious_no_effect"


def build_factor_activation_audit(
    *,
    ekf_rows: list[dict[str, Any]],
    rows_by_variant: dict[str, list[dict[str, Any]]],
    ablation_summary: dict[str, Any],
    factor_weight_review: dict[str, Any],
    registry_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = registry_report or build_default_factor_registry()
    contracts = factor_contracts_by_name(registry)
    active = set(registry.get("active_default_factors", []))
    current_rows = select_current_rows(rows_by_variant)
    direct_p95 = dict(factor_weight_review.get("per_factor_residual_p95", {}))
    default_variant = _variant(ablation_summary, "default_active_stack_n8a2")

    intermediate: list[dict[str, Any]] = []
    total_whitened_sq = 0.0
    for factor_name in ACTIVE_FACTOR_NAMES:
        contract = contracts.get(factor_name, {})
        dimension = int(contract.get("residual_dimension", 1) or 1)
        times, raw_values = build_factor_residual_series(factor_name=factor_name, ekf_rows=ekf_rows, fgo_rows=current_rows)
        std = max(float(FACTOR_STD_PROXY.get(factor_name, 1.0) or 1.0), 1e-9)
        whitened = [value / std for value in raw_values]
        normalized = [value / math.sqrt(max(1, dimension)) for value in whitened]
        raw_stats = residual_stats(raw_values)
        whitened_stats = residual_stats(whitened)
        normalized_stats = residual_stats(normalized)
        total_whitened_sq += whitened_stats["sum_sq"]
        off_name = FACTOR_OFF_VARIANTS.get(factor_name, "")
        off_variant = _variant(ablation_summary, off_name) if off_name else {}
        variant_delta = _variant_delta(default_variant, off_variant) if off_variant else {}
        included_direct = factor_name in direct_p95 and float(direct_p95.get(factor_name, 0.0) or 0.0) > 0.0
        if factor_name == "SmoothnessFactor" and factor_name in direct_p95:
            included_direct = True
        row = {
            "factor_type": factor_name,
            "registered": bool(contract),
            "active_default": factor_name in active,
            "included_in_dataset": factor_name in active and bool(raw_values),
            "included_in_solver_residual": bool(included_direct),
            "direct_solver_residual_evidence": bool(included_direct),
            "proxy_residual_evidence": bool(raw_values),
            "proxy_residual_source": "state_delta_proxy" if factor_name != "RawDopplerVelocityFactor" else "receiver_velocity_delta_proxy_no_direct_raw_doppler_factor_table",
            "residual_row_count": len(raw_values),
            "residual_dimension": dimension,
            "jacobian_nonzero_count": len(raw_values) * dimension if included_direct else 0,
            "touched_state_blocks": list(contract.get("state_blocks_touched", [])),
            "covariance_policy": contract.get("covariance_policy", ""),
            "r_covariance_stats": _covariance_stats(factor_name, dimension),
            "raw_residual_stats": raw_stats,
            "whitened_residual_stats": whitened_stats,
            "dimension_normalized_residual_stats": normalized_stats,
            "raw_residual_p50": raw_stats["p50"],
            "raw_residual_p95": raw_stats["p95"],
            "raw_residual_max": raw_stats["max"],
            "whitened_residual_p50": whitened_stats["p50"],
            "whitened_residual_p95": whitened_stats["p95"],
            "whitened_residual_max": whitened_stats["max"],
            "dimension_normalized_residual_p50": normalized_stats["p50"],
            "dimension_normalized_residual_p95": normalized_stats["p95"],
            "dimension_normalized_residual_max": normalized_stats["max"],
            "factor_count": len(raw_values) if factor_name in active else 0,
            "contribution_norm": math.sqrt(whitened_stats["sum_sq"]),
            "total_whitened_sq": whitened_stats["sum_sq"],
            "on_off_variant": off_name,
            "on_off_variant_exists": bool(off_variant),
            "on_off_delta": variant_delta,
            "on_off_delta_combined_abs": variant_delta.get("combined_abs_delta", 0.0),
            "residual_time_span": {
                "start": times[0] if times else None,
                "end": times[-1] if times else None,
                "count": len(times),
            },
        }
        intermediate.append(row)

    rows = []
    for row in intermediate:
        share = float(row["total_whitened_sq"]) / total_whitened_sq if total_whitened_sq > 0.0 else 0.0
        status = _classify_factor(
            factor_name=str(row["factor_type"]),
            registered=bool(row["registered"]),
            included_in_solver_residual=bool(row["included_in_solver_residual"]),
            residual_row_count=int(row["residual_row_count"]),
            whitened_p95=float(row["whitened_residual_p95"]),
            normalized_p95=float(row["dimension_normalized_residual_p95"]),
            contribution_share=share,
            on_off_delta=float(row["on_off_delta_combined_abs"]),
        )
        row["contribution_share"] = share
        row["contribution_status"] = status
        rows.append(row)

    return {
        "stage": "N8C2_fgo_factor_activation_review",
        "factor_activation_rows": rows,
        "active_factor_count": len(ACTIVE_FACTOR_NAMES),
        "total_whitened_sq": total_whitened_sq,
        "classification_counts": {status: sum(1 for row in rows if row["contribution_status"] == status) for status in sorted({row["contribution_status"] for row in rows})},
        "raw_doppler_activation_status": next((row["contribution_status"] for row in rows if row["factor_type"] == "RawDopplerVelocityFactor"), "activation_missing"),
        "all_registered_active_factors_reviewed": all(row["registered"] for row in rows),
        "direct_factor_table_available": False,
        "proxy_residuals_kept_separate": True,
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "output_substitution": False,
        "fgo_output_replaces_ekf_nav": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }
