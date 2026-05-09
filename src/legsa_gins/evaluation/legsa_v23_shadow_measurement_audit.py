"""Shadow measurement audit for N4H4D4.

中文说明：用 external clean NAV 状态离线计算 LegSA measurement residual。
external NAV 绝不作为 solver input，只用于 shadow/evaluation 诊断。
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from .legsa_v23_external_trace_parity import align_by_time, parse_nav


def _read_gnss(path: str | Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    p = Path(path)
    if not p.exists():
        return rows
    with p.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) < 15:
                continue
            try:
                values = [float(part) for part in parts[:15]]
            except ValueError:
                continue
            rows.append(
                {
                    "time": values[0],
                    "lat_deg": values[1],
                    "lon_deg": values[2],
                    "height_m": values[3],
                    "vn": values[7],
                    "ve": values[8],
                    "vd": values[9],
                    "yaw_deg": values[13],
                    "yaw_std_deg": values[14],
                }
            )
    return rows


def _wrap_deg(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def _horizontal_residual(nav: dict[str, float], gnss: dict[str, float]) -> float:
    lat_mean = math.radians(0.5 * (nav.get("lat_deg", 0.0) + gnss.get("lat_deg", 0.0)))
    north = (nav.get("lat_deg", 0.0) - gnss.get("lat_deg", 0.0)) * 111_319.49079327358
    east = (nav.get("lon_deg", 0.0) - gnss.get("lon_deg", 0.0)) * 111_319.49079327358 * math.cos(lat_mean)
    down = -(nav.get("height_m", 0.0) - gnss.get("height_m", 0.0))
    return math.sqrt(north * north + east * east + down * down)


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[index]


def _stats(values: list[float]) -> dict[str, float | None]:
    return {
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "max": max(values) if values else None,
        "mean": sum(values) / len(values) if values else None,
    }


def _read_internal_updates(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"position": [], "velocity": [], "yaw_modes": []}
    position: list[float] = []
    velocity: list[float] = []
    yaw_modes: list[str] = []
    with p.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                position.append(float(row.get("position_residual_norm", "nan")))
                velocity.append(float(row.get("velocity_residual_norm", "nan")))
            except ValueError:
                pass
            yaw_modes.append(row.get("yaw_scheme_mode", "NONE"))
    return {"position": position, "velocity": velocity, "yaw_modes": yaw_modes}


def build_shadow_measurement_residuals(
    external_nav: str | Path | list[dict[str, float]],
    clean_gnss: str | Path,
    all_updates_csv: str | Path | None = None,
    tolerance: float = 0.005,
) -> dict[str, Any]:
    """中文说明：用 external 状态重算 position/velocity/yaw residual，和内部 residual 对照。"""

    nav_rows = parse_nav(external_nav) if not isinstance(external_nav, list) else external_nav
    gnss_rows = _read_gnss(clean_gnss)
    pairs = align_by_time(nav_rows, gnss_rows, tolerance=tolerance)
    position = [_horizontal_residual(nav, gnss) for nav, gnss in pairs]
    velocity = [
        math.sqrt(
            (nav.get("vn", 0.0) - gnss.get("vn", 0.0)) ** 2
            + (nav.get("ve", 0.0) - gnss.get("ve", 0.0)) ** 2
            + (nav.get("vd", 0.0) - gnss.get("vd", 0.0)) ** 2
        )
        for nav, gnss in pairs
    ]
    yaw = [abs(_wrap_deg(gnss.get("yaw_deg", 0.0) - nav.get("yaw_deg", 0.0))) for nav, gnss in pairs]
    yaw_reject_ratio = (sum(1 for value in yaw if value > 15.0) / len(yaw)) if yaw else None
    internal = _read_internal_updates(all_updates_csv) if all_updates_csv else {"position": [], "velocity": [], "yaw_modes": []}
    internal_yaw_modes = internal["yaw_modes"]
    internal_yaw_reject_ratio = (
        sum(1 for mode in internal_yaw_modes if mode in {"REJECT", "YAW-REJECT"}) / len(internal_yaw_modes)
        if internal_yaw_modes
        else None
    )
    external_position = _stats(position)
    external_velocity = _stats(velocity)
    external_yaw = _stats(yaw)
    internal_position = _stats([value for value in internal["position"] if math.isfinite(value)])
    internal_velocity = _stats([value for value in internal["velocity"] if math.isfinite(value)])
    external_small = (
        (external_position["p95"] is not None and external_position["p95"] < 5.0)
        and (external_velocity["p95"] is not None and external_velocity["p95"] < 3.0)
        and (yaw_reject_ratio is not None and yaw_reject_ratio < 0.5)
    )
    internal_large = (
        (internal_position["p95"] is not None and internal_position["p95"] > 10.0)
        or (internal_velocity["p95"] is not None and internal_velocity["p95"] > 5.0)
        or (internal_yaw_reject_ratio is not None and internal_yaw_reject_ratio > 0.5)
    )
    external_large = (
        (external_position["p95"] is not None and external_position["p95"] > 10.0)
        or (external_velocity["p95"] is not None and external_velocity["p95"] > 5.0)
        or (yaw_reject_ratio is not None and yaw_reject_ratio > 0.5)
    )
    return {
        "aligned_count": len(pairs),
        "external_state_position_residual": external_position,
        "external_state_velocity_residual": external_velocity,
        "external_state_yaw_residual": external_yaw,
        "external_state_yaw_reject_ratio": yaw_reject_ratio,
        "compared_to_internal_residuals_from_ALL_UPDATES": {
            "internal_position_residual": internal_position,
            "internal_velocity_residual": internal_velocity,
            "internal_yaw_reject_ratio": internal_yaw_reject_ratio,
        },
        "measurement_model_likely_ok_state_diverges": bool(external_small and internal_large),
        "measurement_model_or_convention_issue": bool(external_large),
        "yaw_issue_caused_by_internal_state_divergence": bool(
            yaw_reject_ratio is not None
            and yaw_reject_ratio < 0.5
            and internal_yaw_reject_ratio is not None
            and internal_yaw_reject_ratio > 0.5
        ),
        "shadow_external_nav_solver_input": False,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "numerical_performance_claim": False,
    }
