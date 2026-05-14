"""N8F1 factor signal review.

中文说明：检查新激活因子是否有非空、有限、可视化的工程信号；不生成性能宣称。
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence


def _f(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _stats(values: Sequence[float]) -> Dict[str, float]:
    finite = [abs(float(value)) for value in values if math.isfinite(float(value))]
    if not finite:
        return {"rows": 0, "finite_ratio": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    ordered = sorted(finite)
    return {
        "rows": len(values),
        "finite_ratio": len(finite) / max(1, len(values)),
        "p50": statistics.median(ordered),
        "p95": ordered[int(round((len(ordered) - 1) * 0.95))],
        "max": max(ordered),
    }


def _signal_status(rows: int, finite_ratio: float, p95: float, toggle_effect: bool) -> str:
    if rows <= 0 or finite_ratio < 0.95 or not toggle_effect:
        return "inactive"
    if p95 > 25.0:
        return "unstable"
    if p95 < 1e-9:
        return "weak_but_active"
    return "informative"


def build_n8f_factor_signal_review(
    *,
    reports: Mapping[str, Any],
    contact_timeseries: Sequence[Mapping[str, Any]],
    foot_series: Sequence[Mapping[str, Any]],
    yawrate_series: Sequence[Mapping[str, Any]],
    relative_series: Sequence[Mapping[str, Any]],
    variants: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    contact_scales = [_f(row.get("contact_weight_scale")) for row in contact_timeseries]
    contact_stats = _stats(contact_scales)
    contact_varies = (max(contact_scales) - min(contact_scales)) > 1e-9 if contact_scales else False
    foot_stats = _stats([_f(row.get("residual_proxy")) for row in foot_series])
    foot_whitened = _stats([_f(row.get("whitened_residual_proxy")) for row in foot_series])
    yaw_stats = _stats([_f(row.get("residual_proxy")) for row in yawrate_series])
    relative_stats = _stats([_f(row.get("residual_proxy")) for row in relative_series])
    comparison = reports.get("comparison", {})
    gross = list(comparison.get("gross_degradation_variants", [])) if isinstance(comparison, Mapping) else []
    foot_toggle = any(row.get("foot_kinematic_velocity_enabled") and int(row.get("candidate_solver_residual_dim", 0) or 0) > 0 for row in variants)
    yaw_toggle = any(row.get("yawrate_between_enabled") and int(row.get("candidate_solver_residual_dim", 0) or 0) > 0 for row in variants)
    rel_toggle = any(row.get("relative_odometry_between_enabled") and int(row.get("candidate_solver_residual_dim", 0) or 0) > 0 for row in variants)
    contact_review = {
        "scale_varies_over_time": contact_varies,
        "not_all_constant": contact_varies,
        "p50": contact_stats["p50"],
        "p95": contact_stats["p95"],
        "max": contact_stats["max"],
        "affects_intended_factors": list(reports.get("contact_weighting", {}).get("used_by_factor", [])),
        "signal_status": "informative" if contact_varies and contact_stats["rows"] > 0 else "inactive",
    }
    foot_review = {
        "residual_rows": int(reports.get("foot_kinematic", {}).get("residual_rows", 0) or 0),
        "residual_stats": foot_stats,
        "whitened_residual_stats": foot_whitened,
        "toggle_effect": foot_toggle,
        "signal_status": _signal_status(int(reports.get("foot_kinematic", {}).get("residual_rows", 0) or 0), foot_stats["finite_ratio"], foot_whitened["p95"], foot_toggle),
    }
    yaw_review = {
        "residual_rows": int(reports.get("yawrate", {}).get("residual_rows", 0) or 0),
        "wrap_sanity": bool(reports.get("yawrate", {}).get("wrap_boundary_test_passed", False)),
        "residual_stats": yaw_stats,
        "toggle_effect": yaw_toggle,
        "signal_status": _signal_status(int(reports.get("yawrate", {}).get("residual_rows", 0) or 0), yaw_stats["finite_ratio"], yaw_stats["p95"], yaw_toggle),
    }
    relative_review = {
        "residual_rows": int(reports.get("relative_odometry", {}).get("residual_rows", 0) or 0),
        "delta_consistency": not bool(reports.get("relative_odometry", {}).get("absolute_go2_position_factor", True)),
        "residual_stats": relative_stats,
        "toggle_effect": rel_toggle,
        "signal_status": _signal_status(int(reports.get("relative_odometry", {}).get("residual_rows", 0) or 0), relative_stats["finite_ratio"], relative_stats["p95"], rel_toggle),
    }
    statuses = [
        contact_review["signal_status"],
        foot_review["signal_status"],
        yaw_review["signal_status"],
        relative_review["signal_status"],
    ]
    return {
        "stage": "N8F1",
        "contact_aware_weighting": contact_review,
        "foot_kinematic_velocity": foot_review,
        "yawrate_between": yaw_review,
        "relative_odometry_between": relative_review,
        "candidate_stack": {
            "gross_degradation_flag": bool(gross),
            "gross_degradation_variants": gross,
            "factor_contribution_summary": {
                "variant_count": len(variants),
                "candidate_solver_injection_passed": bool(comparison.get("candidate_solver_injection_passed", False)) if isinstance(comparison, Mapping) else False,
            },
            "no_feedback": True,
            "output_substitution": False,
        },
        "all_new_factors_have_real_signal": all(status != "inactive" for status in statuses),
        "inactive_factors": [
            name
            for name, status in zip(
                ["contact_aware_weighting", "foot_kinematic_velocity", "yawrate_between", "relative_odometry_between"],
                statuses,
            )
            if status == "inactive"
        ],
        "paper_performance_claim": False,
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "go2_truth_claim": False,
    }


def write_factor_signal_review(path: str | Path, report: Mapping[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output

