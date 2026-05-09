"""Kalman gain and feedback diagnostics for N4H4D4."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


def _float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def _stats(values: list[float]) -> dict[str, float | None]:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return {"count": 0, "mean": None, "max": None, "min": None, "p95": None}
    ordered = sorted(clean)
    p95_index = min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95)))
    return {
        "count": len(clean),
        "mean": sum(clean) / len(clean),
        "max": max(clean),
        "min": min(clean),
        "p95": ordered[p95_index],
    }


def analyze_gain_feedback(all_updates_csv: str | Path) -> dict[str, Any]:
    """中文说明：分析 D4 debug 的 K/dx/cov 统计，只定位问题，不调参。"""

    path = Path(all_updates_csv)
    if not path.exists():
        return {
            "status": "all_updates_missing",
            "feedback_not_applied": True,
            "trace_solver_input": False,
            "numerical_performance_claim": False,
        }
    k_pos: list[float] = []
    k_vel: list[float] = []
    k_yaw: list[float] = []
    dx_phi: list[float] = []
    dx_pos: list[float] = []
    dx_vel: list[float] = []
    cov_after: list[float] = []
    cov_min_after: list[float] = []
    feedback_applied = 0
    rows = 0
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        for row in csv.DictReader(handle):
            rows += 1
            k_pos.append(_float(row, "K_norm_pos"))
            k_vel.append(_float(row, "K_norm_vel"))
            k_yaw.append(_float(row, "K_norm_yaw"))
            dx_phi.append(_float(row, "dx_phi_norm_deg"))
            dx_pos.append(_float(row, "dx_pos_norm"))
            dx_vel.append(_float(row, "dx_vel_norm"))
            cov_after.append(_float(row, "cov_trace_after"))
            cov_min_after.append(_float(row, "cov_min_diag_after"))
            if row.get("state_feedback_applied", "").lower() == "true":
                feedback_applied += 1
    k_all = k_pos + k_vel + k_yaw
    dx_phi_over_1 = sum(1 for value in dx_phi if value > 1.0)
    dx_phi_over_5 = sum(1 for value in dx_phi if value > 5.0)
    dx_phi_over_10 = sum(1 for value in dx_phi if value > 10.0)
    k_stats = _stats(k_all)
    dx_phi_stats = _stats(dx_phi)
    cov_min_stats = _stats(cov_min_after)
    return {
        "status": "analyzed",
        "row_count": rows,
        "K_norm_stats": k_stats,
        "K_norm_pos_stats": _stats(k_pos),
        "K_norm_vel_stats": _stats(k_vel),
        "K_norm_yaw_stats": _stats(k_yaw),
        "dx_phi_norm_deg_stats": dx_phi_stats,
        "dx_phi_over_1deg_count": dx_phi_over_1,
        "dx_phi_over_5deg_count": dx_phi_over_5,
        "dx_phi_over_10deg_count": dx_phi_over_10,
        "dx_pos_norm_stats": _stats(dx_pos),
        "dx_vel_norm_stats": _stats(dx_vel),
        "cov_trace_after_stats": _stats(cov_after),
        "cov_min_diag_after_stats": cov_min_stats,
        "feedback_applied_count": feedback_applied,
        "kalman_gain_too_large": bool(k_stats["max"] is not None and k_stats["max"] > 100.0),
        "covariance_collapse": bool(cov_min_stats["min"] is not None and cov_min_stats["min"] < 1.0e-18),
        "feedback_overcorrection": bool(dx_phi_stats["max"] is not None and dx_phi_stats["max"] > 10.0),
        "dx_phi_spike": bool(dx_phi_over_5 > 0),
        "dx_pos_vel_spike": bool(max(dx_pos or [0.0]) > 10.0 or max(dx_vel or [0.0]) > 10.0),
        "covariance_invalid": bool(any(value < -1.0e-12 for value in cov_min_after)),
        "feedback_not_applied": bool(rows and feedback_applied == 0),
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
