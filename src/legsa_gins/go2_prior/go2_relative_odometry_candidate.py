"""N7C5 Go2 relative odometry candidate review.

中文说明：Go2 position 只检查短窗增量一致性，不作为 EKF absolute position
prior；若稳定，也只是后续 FGO between-factor 候选。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _read_csv(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _norm3(vec: tuple[float, float, float]) -> float:
    return math.sqrt(sum(value * value for value in vec))


def _rmse(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return math.sqrt(sum(value * value for value in finite) / len(finite)) if finite else math.nan


def _eval_nav_displacements(rows: list[dict[str, Any]], step: int) -> list[float]:
    out: list[float] = []
    if len(rows) <= step:
        return out
    lat0 = math.radians(_f(rows[0].get("lat_deg"), 0.0))
    cos_lat = math.cos(lat0)
    for i in range(0, len(rows) - step, step):
        north = (math.radians(_f(rows[i + step].get("lat_deg"), 0.0)) - math.radians(_f(rows[i].get("lat_deg"), 0.0))) * 6378137.0
        east = (math.radians(_f(rows[i + step].get("lon_deg"), 0.0)) - math.radians(_f(rows[i].get("lon_deg"), 0.0))) * 6378137.0 * cos_lat
        up = _f(rows[i + step].get("height_m"), 0.0) - _f(rows[i].get("height_m"), 0.0)
        out.append(math.sqrt(north * north + east * east + up * up))
    return out


def build_go2_relative_odometry_candidate(go2_rows: list[dict[str, Any]], eval_nav_path: str | Path | None = None, step: int = 50) -> dict[str, Any]:
    rows = sorted(go2_rows, key=lambda row: _f(row.get("aligned_time", row.get("time")), 0.0))
    position_deltas: list[float] = []
    velocity_integral_deltas: list[float] = []
    consistency_errors: list[float] = []
    for i in range(0, max(0, len(rows) - step), step):
        a, b = rows[i], rows[i + step]
        dt = _f(b.get("aligned_time", b.get("time")), 0.0) - _f(a.get("aligned_time", a.get("time")), 0.0)
        if dt <= 0:
            continue
        dp = tuple(_f(b.get(f"go2_position_{axis}"), 0.0) - _f(a.get(f"go2_position_{axis}"), 0.0) for axis in range(3))
        vel = tuple(0.5 * (_f(a.get(f"go2_velocity_{axis}"), 0.0) + _f(b.get(f"go2_velocity_{axis}"), 0.0)) * dt for axis in range(3))
        pn = _norm3(dp)
        vn = _norm3(vel)
        position_deltas.append(pn)
        velocity_integral_deltas.append(vn)
        consistency_errors.append(abs(pn - vn))
    eval_rows = _read_csv(eval_nav_path) if eval_nav_path else []
    eval_deltas = _eval_nav_displacements(eval_rows, step)
    stable = len(consistency_errors) > 3 and _rmse(consistency_errors) < 1.0
    return {
        "stage": "N7C5_go2_full_proprioceptive_factor_mining",
        "window_count": len(consistency_errors),
        "go2_position_delta_rmse_m": _rmse(position_deltas),
        "integrated_go2_velocity_delta_rmse_m": _rmse(velocity_integral_deltas),
        "position_vs_integrated_velocity_error_rmse_m": _rmse(consistency_errors),
        "ekf_displacement_delta_rmse_m": _rmse(eval_deltas),
        "relative_odometry_stability": "stable" if stable else "diagnostic_only",
        "recommendation": "go2_relative_odometry_between_factor" if stable else "not_ekf_absolute_position",
        "ekf_absolute_position_prior_allowed": False,
        "go2_position_prior_enabled": False,
        "go2_position_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "paper_performance_claim": False,
        "fgo": False,
    }


def write_go2_relative_odometry_candidate(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
