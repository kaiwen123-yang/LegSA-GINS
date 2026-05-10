"""Parse RTKLIB Doppler helper velocity outputs for N5B.

中文说明：本模块只解析 RTKLIB helper 输出的速度字段；rnx2rtkp 的最终定位解
不能作为 LegSA solver input，也不能在这里被转换成位置观测。
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


VELOCITY_FACTOR_FIELDS = [
    "time",
    "vn",
    "ve",
    "vd",
    "std_vn",
    "std_ve",
    "std_vd",
    "sat_count",
    "doppler_obs_count",
    "gdop_like",
    "provider_status",
    "source_epoch_time",
    "quality_flag",
]


def _float(value: Any, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _int(value: Any, fallback: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def parse_helper_velocity_csv(path: str | Path) -> list[dict[str, Any]]:
    """Read the runtime-only helper CSV.

    中文说明：helper CSV 是 RTKLIB pntpos/estvel Doppler velocity 输出，不含位置
    解作为 LegSA measurement。
    """

    source = Path(path)
    if not source.exists():
        return []
    rows: list[dict[str, Any]] = []
    with source.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "source_epoch_time": _float(row.get("source_epoch_time", row.get("time"))),
                    "time": _float(row.get("time", row.get("source_epoch_time"))),
                    "vecef_x": _float(row.get("vecef_x")),
                    "vecef_y": _float(row.get("vecef_y")),
                    "vecef_z": _float(row.get("vecef_z")),
                    "std_vx": max(_float(row.get("std_vx"), 0.2), 1.0e-6),
                    "std_vy": max(_float(row.get("std_vy"), 0.2), 1.0e-6),
                    "std_vz": max(_float(row.get("std_vz"), 0.2), 1.0e-6),
                    "sat_count": _int(row.get("sat_count")),
                    "doppler_obs_count": _int(row.get("doppler_obs_count")),
                    "provider_status": row.get("provider_status", "provider_missing"),
                    "quality_flag": row.get("quality_flag", ""),
                }
            )
    return rows


def ecef_velocity_to_ned(vx: float, vy: float, vz: float, lat_deg: float, lon_deg: float) -> tuple[float, float, float]:
    """Convert ECEF velocity to local NED.

    中文说明：只转换 RTKLIB Doppler-derived velocity，不读取 .gnss vn/ve/vd。
    """

    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    sin_lon, cos_lon = math.sin(lon), math.cos(lon)
    vn = -sin_lat * cos_lon * vx - sin_lat * sin_lon * vy + cos_lat * vz
    ve = -sin_lon * vx + cos_lon * vy
    vd = -cos_lat * cos_lon * vx - cos_lat * sin_lon * vy - sin_lat * vz
    return vn, ve, vd


def read_clean_gnss_position_and_times(path: str | Path) -> dict[str, Any]:
    """Read only time and approximate position from a 15-column clean GNSS file.

    中文说明：这里不读取或使用 clean .gnss 的速度列，避免把 baseline receiver-native
    velocity 冒充 raw Doppler。
    """

    gnss = Path(path)
    times: list[float] = []
    position: dict[str, float] | None = None
    if not gnss.exists():
        return {"exists": False, "times": [], "position": None}
    for line in gnss.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cells = line.split()
        if len(cells) < 4:
            continue
        time = _float(cells[0], math.nan)
        if math.isfinite(time):
            times.append(time)
        if position is None:
            position = {"lat_deg": _float(cells[1]), "lon_deg": _float(cells[2]), "height_m": _float(cells[3])}
    return {"exists": True, "times": times, "position": position}


def reject_position_solution_as_factor(path: str | Path) -> dict[str, Any]:
    """Return an explicit boundary report for RTKLIB position solutions.

    中文说明：RTKLIB position solution 可作为诊断日志，但不能被当作 LegSA raw
    Doppler factor 输入。
    """

    return {
        "path": str(path),
        "accepted_as_factor_input": False,
        "reason": "rtklib_position_solution_not_legsa_solver_input",
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }
