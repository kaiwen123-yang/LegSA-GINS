"""HX-02 GINav output adapter: official .pos -> coverage-aware standard CSV -> 11-column NAV.

Follows GINAV_OUTPUT_CONVERSION_CONTRACT.md (CLEAN4 coverage_aware_c00) and the
v3 precedent clean5_degradation/evaluation.ginav_nav:
  * time: unix = 315964800 + week*604800 + sow - 18; relative = unix - base_time;
  * position: official ECEF of the GINav INS/IMU point -> WGS84 LLH, no point shift;
  * velocity: official ECEF velocity rotated to local ENU at the emitted LLH, NED = [N, E, -U];
  * attitude: official pitch/roll/emitted yaw reordered to roll, pitch, yaw (FRD/NED);
  * rounding as printed in the coverage-aware record (LLH 12/12/6 decimals,
    velocity 9 decimals, time 3 decimals); 11-column NAV written with %.17g.
All finite native rows are kept in order; no row is inserted, removed or shifted.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ..horizontal_literature.ginav2021.outputs import (
    ecef_to_geodetic,
    ecef_velocity_to_enu,
    read_official_solution,
)

GPS_EPOCH_UNIX = 315964800.0
LEAP_SECONDS = 18.0
NAV11_COLUMNS = ("gps_week", "relative_time_s", "latitude_deg", "longitude_deg", "height_m",
                 "velocity_north_ned_mps", "velocity_east_ned_mps", "velocity_down_ned_mps",
                 "roll_frd_ned_deg", "pitch_frd_ned_deg", "yaw_frd_ned_deg")
STANDARD_COLUMNS = ("row_index", "gps_week", "gps_sow", "unix_time_s", "relative_time_s", "status_code",
                    "satellite_count", "ecef_x_m", "ecef_y_m", "ecef_z_m", "latitude_deg", "longitude_deg",
                    "height_m", "ecef_vx_mps", "ecef_vy_mps", "ecef_vz_mps", "velocity_east_enu_mps",
                    "velocity_north_enu_mps", "velocity_up_enu_mps", "velocity_north_ned_mps",
                    "velocity_east_ned_mps", "velocity_down_ned_mps", "roll_frd_ned_deg",
                    "pitch_frd_ned_deg", "yaw_frd_ned_deg", "lc_update", "ins_only", "state_finite")


def _fixed(value: float, decimals: int) -> str:
    text = f"{value:.{decimals}f}"
    return "0." + "0" * decimals if text.startswith("-") and float(text) == 0.0 else text


def standard_rows(pos_path: Path, base_time: float) -> list[dict[str, str]]:
    rows = []
    for index, row in enumerate(read_official_solution(pos_path)):
        week, sow = int(row["gps_week"]), float(row["gps_sow"])
        unix = GPS_EPOCH_UNIX + week * 604800.0 + sow - LEAP_SECONDS
        lat, lon, height = ecef_to_geodetic(row["ecef_x_m"], row["ecef_y_m"], row["ecef_z_m"])
        lat_t, lon_t, h_t = _fixed(lat, 12), _fixed(lon, 12), _fixed(height, 6)
        east, north, up = ecef_velocity_to_enu(float(lat_t), float(lon_t),
                                               (row["ecef_vx_mps"], row["ecef_vy_mps"], row["ecef_vz_mps"]))
        e_t, n_t, u_t = _fixed(east, 9), _fixed(north, 9), _fixed(up, 9)
        down_t = _fixed(-float(u_t), 9)
        rows.append({
            "row_index": str(index), "gps_week": str(week), "gps_sow": f"{sow:.3f}",
            "unix_time_s": f"{unix:.3f}", "relative_time_s": f"{unix - float(base_time):.3f}",
            "status_code": str(row.status), "satellite_count": str(row.satellite_count),
            "ecef_x_m": repr(row["ecef_x_m"]), "ecef_y_m": repr(row["ecef_y_m"]), "ecef_z_m": repr(row["ecef_z_m"]),
            "latitude_deg": lat_t, "longitude_deg": lon_t, "height_m": h_t,
            "ecef_vx_mps": repr(row["ecef_vx_mps"]), "ecef_vy_mps": repr(row["ecef_vy_mps"]),
            "ecef_vz_mps": repr(row["ecef_vz_mps"]),
            "velocity_east_enu_mps": e_t, "velocity_north_enu_mps": n_t, "velocity_up_enu_mps": u_t,
            "velocity_north_ned_mps": n_t, "velocity_east_ned_mps": e_t, "velocity_down_ned_mps": down_t,
            "roll_frd_ned_deg": repr(row["roll_deg"]), "pitch_frd_ned_deg": repr(row["pitch_deg"]),
            "yaw_frd_ned_deg": repr(row["yaw_deg"]),
            "lc_update": str(row.status == 5).lower(), "ins_only": str(row.status == 3).lower(),
            "state_finite": str(row.state_finite).lower(),
        })
    return rows


def write_standard_csv(rows: Sequence[Mapping[str, str]], path: Path) -> None:
    with Path(path).open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=STANDARD_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def nav11(rows: Sequence[Mapping[str, str]]) -> np.ndarray:
    nav = np.asarray([[float(row[name]) for name in NAV11_COLUMNS] for row in rows], dtype=float)
    if nav.ndim != 2 or nav.shape[1] != 11 or not np.isfinite(nav).all() or np.any(np.diff(nav[:, 1]) <= 0):
        raise ValueError("Invalid GINav standard NAV")
    return nav


def clip_window(nav: np.ndarray, window: Sequence[float]) -> np.ndarray:
    return nav[(nav[:, 1] >= float(window[0])) & (nav[:, 1] <= float(window[1]))]


def write_nav11(nav: np.ndarray, path: Path) -> None:
    with Path(path).open("xb") as handle:
        np.savetxt(handle, nav, fmt="%.17g")


def convert(pos_path: Path, *, base_time: float, window: Sequence[float], out_dir: Path) -> dict[str, Any]:
    """Write GINAV_STANDARD_NAV.csv, GINAV_NATIVE_NAV11.nav (all rows) and GINAV_WINDOW_NAV11.nav."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = standard_rows(pos_path, base_time)
    write_standard_csv(rows, out_dir / "GINAV_STANDARD_NAV.csv")
    finite = [row for row in rows if row["state_finite"] == "true"]
    # An official output without finite rows is recorded (empty NAV), never an adapter crash.
    full = nav11(finite) if finite else np.empty((0, 11))
    write_nav11(full, out_dir / "GINAV_NATIVE_NAV11.nav")
    clipped = clip_window(full, window)
    if clipped.shape[0]:
        write_nav11(clipped, out_dir / "GINAV_WINDOW_NAV11.nav")
    return {"native_rows": len(rows), "finite_rows": int(full.shape[0]), "window_rows": int(clipped.shape[0]),
            "nonfinite_rows": len(rows) - int(full.shape[0]),
            "first_rel_s": float(full[0, 1]) if full.shape[0] else None,
            "last_rel_s": float(full[-1, 1]) if full.shape[0] else None}
