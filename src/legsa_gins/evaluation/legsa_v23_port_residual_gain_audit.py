"""Residual/gain audit for N4H4R3B over-close screening.

中文说明：读取 runtime-only residual/gain trace，筛查 R/K/dx 是否表现为过强更新；
如果 C++ trace 尚无 K/dx 精确值，则保留 evidence_missing，不伪造数值。
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


def _float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _p(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def _max(values: list[float]) -> float | None:
    return max(values) if values else None


def _stats(values: list[float]) -> dict[str, float | None]:
    return {"p50": _p(values, 0.50), "p95": _p(values, 0.95), "max": _max(values)}


def _collect(rows: list[dict[str, str]], key: str, *, absolute: bool = False) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = _float(row.get(key))
        if value is None:
            continue
        values.append(abs(value) if absolute else value)
    return values


def analyze_residual_gain(trace_csv: str | Path) -> dict[str, Any]:
    path = Path(trace_csv)
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))

    pos = _collect(rows, "pos_residual_norm", absolute=True)
    vel = _collect(rows, "vel_residual_norm", absolute=True)
    yaw = _collect(rows, "yaw_residual_deg", absolute=True)
    r_pos = _collect(rows, "R_pos_trace", absolute=True)
    r_vel = _collect(rows, "R_vel_trace", absolute=True)
    r_yaw = _collect(rows, "R_yaw", absolute=True)
    k_pos = _collect(rows, "K_pos_norm", absolute=True)
    k_vel = _collect(rows, "K_vel_norm", absolute=True)
    k_yaw = _collect(rows, "K_yaw_norm", absolute=True)
    dx_pos = _collect(rows, "dx_pos_norm", absolute=True)
    dx_vel = _collect(rows, "dx_vel_norm", absolute=True)
    dx_phi = _collect(rows, "dx_phi_norm_deg", absolute=True)
    cov_before = _collect(rows, "cov_trace_before", absolute=True)
    cov_after = _collect(rows, "cov_trace_after", absolute=True)

    yaw_modes: dict[str, int] = {}
    for row in rows:
        mode = row.get("yaw_mode") or "UNKNOWN"
        yaw_modes[mode] = yaw_modes.get(mode, 0) + 1

    k_evidence_missing = not (k_pos or k_vel or k_yaw)
    residuals_small = bool(pos and _p(pos, 0.95) is not None and _p(pos, 0.95) < 0.10 and yaw and _p(yaw, 0.95) < 0.5)
    r_too_small = bool(
        (r_pos and _p(r_pos, 0.50) is not None and _p(r_pos, 0.50) < 1.0e-4)
        or (r_vel and _p(r_vel, 0.50) is not None and _p(r_vel, 0.50) < 1.0e-5)
        or (r_yaw and _p(r_yaw, 0.50) is not None and _p(r_yaw, 0.50) < 1.0e-8)
    )
    k_too_large = bool(
        (k_pos and _max(k_pos) is not None and _max(k_pos) > 10.0)
        or (k_vel and _max(k_vel) is not None and _max(k_vel) > 10.0)
        or (k_yaw and _max(k_yaw) is not None and _max(k_yaw) > 10.0)
    )
    over_tight = bool((r_too_small or k_too_large) and residuals_small)
    return {
        "phase": "N4H4R3B",
        "update_count": len(rows),
        "pos_residual_stats": _stats(pos),
        "vel_residual_stats": _stats(vel),
        "yaw_residual_stats": _stats(yaw),
        "R_pos_trace_stats": _stats(r_pos),
        "R_vel_trace_stats": _stats(r_vel),
        "R_yaw_stats": _stats(r_yaw),
        "K_pos_stats": _stats(k_pos),
        "K_vel_stats": _stats(k_vel),
        "K_yaw_stats": _stats(k_yaw),
        "dx_pos_stats": _stats(dx_pos),
        "dx_vel_stats": _stats(dx_vel),
        "dx_phi_stats": _stats(dx_phi),
        "cov_trace_before_stats": _stats(cov_before),
        "cov_trace_after_stats": _stats(cov_after),
        "yaw_mode_counts": yaw_modes,
        "over_tight_measurement_update_suspect": over_tight,
        "R_too_small_suspect": r_too_small,
        "K_too_large_suspect": k_too_large,
        "K_evidence_missing": k_evidence_missing,
        "residuals_unusually_small": residuals_small,
        "nav_hugs_measurement_suspect": residuals_small,
        "covariance_reasonable": not bool(cov_before and any(value <= 0 for value in cov_before)),
        "engineering_backbone_parity_only": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
