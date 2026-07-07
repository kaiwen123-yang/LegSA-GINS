"""Status-based short-baseline provider for diagnostic fallback and gates."""

from __future__ import annotations

import bisect
import math
from pathlib import Path
from typing import Any

from .common import as_bool, as_float, ecef_delta_to_enu, llh_to_ecef, percentile, read_csv_rows, status_time


def _valid_position_row(row: dict[str, Any]) -> bool:
    if "pos_valid" in row and not as_bool(row.get("pos_valid")):
        return False
    if "fix_ok" in row and not as_bool(row.get("fix_ok")):
        return False
    return all(as_float(row.get(name)) is not None for name in ("pos_lat", "pos_lon", "pos_height"))


def _position_rows(path: str | Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for row in read_csv_rows(path):
        if not _valid_position_row(row):
            continue
        t = status_time(row)
        if t is None:
            continue
        lat = as_float(row.get("pos_lat"))
        lon = as_float(row.get("pos_lon"))
        h = as_float(row.get("pos_height"))
        if lat is None or lon is None or h is None:
            continue
        x, y, z = llh_to_ecef(lat, lon, h)
        rows.append({"time": t, "lat": lat, "lon": lon, "height": h, "x": x, "y": y, "z": z})
    rows.sort(key=lambda item: item["time"])
    return rows


def _interp_position(rows: list[dict[str, float]], t: float) -> dict[str, float] | None:
    if not rows or t < rows[0]["time"] or t > rows[-1]["time"]:
        return None
    times = [row["time"] for row in rows]
    idx = bisect.bisect_left(times, t)
    if idx < len(rows) and abs(rows[idx]["time"] - t) < 1.0e-9:
        return rows[idx]
    left = rows[max(0, idx - 1)]
    right = rows[min(len(rows) - 1, idx)]
    if right["time"] == left["time"]:
        return left
    alpha = (t - left["time"]) / (right["time"] - left["time"])
    out = {"time": t}
    for key in ("lat", "lon", "height", "x", "y", "z"):
        out[key] = left[key] + alpha * (right[key] - left[key])
    return out


def build_status_baseline_series(gnss1_status: str | Path, gnss2_status: str | Path) -> tuple[list[dict[str, float]], dict[str, Any]]:
    rows1 = _position_rows(gnss1_status)
    rows2 = _position_rows(gnss2_status)
    series: list[dict[str, float]] = []
    outside = 0
    for row1 in rows1:
        row2 = _interp_position(rows2, row1["time"])
        if row2 is None:
            outside += 1
            continue
        dx = row2["x"] - row1["x"]
        dy = row2["y"] - row1["y"]
        dz = row2["z"] - row1["z"]
        east, north, up = ecef_delta_to_enu(dx, dy, dz, row1["lat"], row1["lon"])
        length = math.sqrt(east * east + north * north + up * up)
        heading = math.degrees(math.atan2(east, north)) % 360.0
        series.append(
            {
                "time": row1["time"],
                "east_m": east,
                "north_m": north,
                "up_m": up,
                "baseline_length_m": length,
                "baseline_heading_deg": heading,
                "gnss1_lat_deg": row1["lat"],
                "gnss1_lon_deg": row1["lon"],
                "gnss1_height_m": row1["height"],
                "gnss2_lat_deg": row2["lat"],
                "gnss2_lon_deg": row2["lon"],
                "gnss2_height_m": row2["height"],
            }
        )
    lengths = [row["baseline_length_m"] for row in series]
    physical = [value for value in lengths if 0.20 <= value <= 0.60]
    summary = {
        "gnss1_position_rows": len(rows1),
        "gnss2_position_rows": len(rows2),
        "aligned_baseline_rows": len(series),
        "interpolation_outside_range_count": outside,
        "median_baseline_length_m": percentile(lengths, 0.50),
        "p05_baseline_length_m": percentile(lengths, 0.05),
        "p95_baseline_length_m": percentile(lengths, 0.95),
        "physical_gate_min_m": 0.20,
        "physical_gate_max_m": 0.60,
        "physical_gate_pass": bool(series) and len(physical) / max(1, len(series)) >= 0.50,
        "baseline_vector_definition": "GNSS2 absolute position minus GNSS1 absolute position, converted to local ENU at GNSS1",
        "status_rel_pos_direct_use": False,
        "trace_solver_input": False,
    }
    return series, summary
