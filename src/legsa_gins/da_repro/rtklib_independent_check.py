"""RTKLIB moving-base diagnostic parser for DA01R2B."""

from __future__ import annotations

import calendar
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from .common import percentile, read_csv_rows, wrap180, wrap360
from .orientation_audit import BaselineVector, compare_raw_to_status


def parse_rtklib_pos(path: str | Path, *, solution_id: str) -> list[dict[str, Any]]:
    pos_path = Path(path)
    rows: list[dict[str, Any]] = []
    if not pos_path.exists():
        return rows
    for line in pos_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("%"):
            continue
        parts = [part.strip() for part in stripped.split(",")]
        if len(parts) < 14:
            continue
        try:
            dt = datetime.strptime(parts[0], "%Y/%m/%d %H:%M:%S.%f")
            east = float(parts[1])
            north = float(parts[2])
            up = float(parts[3])
            q = int(parts[4])
            ns = int(parts[5])
            ratio = float(parts[-1])
        except (ValueError, IndexError):
            continue
        timestamp = float(calendar.timegm(dt.timetuple())) + dt.microsecond * 1.0e-6
        length = math.sqrt(east * east + north * north + up * up)
        heading = wrap360(math.degrees(math.atan2(east, north)))
        rows.append(
            {
                "solution_id": solution_id,
                "timestamp": timestamp,
                "gpst": parts[0],
                "east_m": east,
                "north_m": north,
                "up_m": up,
                "baseline_length_m": length,
                "heading_enu_deg": heading,
                "quality": q,
                "quality_label": {1: "fix", 2: "float", 5: "single"}.get(q, f"q{q}"),
                "satellite_count": ns,
                "ratio": ratio,
            }
        )
    return rows


def rtklib_vectors(rows: list[dict[str, Any]], *, source: str) -> list[BaselineVector]:
    return [
        BaselineVector(
            time=float(row["timestamp"]),
            east_m=float(row["east_m"]),
            north_m=float(row["north_m"]),
            up_m=float(row["up_m"]),
            source=source,
        )
        for row in rows
    ]


def summarize_rtklib_rows(rows: list[dict[str, Any]], status_vectors: list[BaselineVector] | None = None) -> dict[str, Any]:
    lengths = [float(row["baseline_length_m"]) for row in rows]
    ratios = [float(row["ratio"]) for row in rows if math.isfinite(float(row["ratio"]))]
    counts = {label: sum(1 for row in rows if row["quality_label"] == label) for label in ("fix", "float", "single")}
    headings = [float(row["heading_enu_deg"]) for row in rows]
    jumps = [abs(wrap180(headings[index] - headings[index - 1])) for index in range(1, len(headings))]
    status_summary: dict[str, Any] = {}
    if status_vectors:
        _, status_summary = compare_raw_to_status(rtklib_vectors(rows, source="rtklib_moving_base"), status_vectors, max_dt_sec=1.0)
    median_length = percentile(lengths, 0.50)
    p95_jump = percentile(jumps, 0.95)
    stable_direction = bool(rows) and median_length is not None and 0.20 <= median_length <= 0.60 and (p95_jump or 999.0) < 30.0
    if status_summary:
        stable_direction = stable_direction and bool(status_summary.get("direction_stable_against_status"))
    return {
        "usable_epochs": len(rows),
        "fix_count": counts["fix"],
        "float_count": counts["float"],
        "single_count": counts["single"],
        "median_baseline_length_m": median_length,
        "p05_baseline_length_m": percentile(lengths, 0.05),
        "p95_baseline_length_m": percentile(lengths, 0.95),
        "median_heading_jump_deg": percentile(jumps, 0.50),
        "p95_heading_jump_deg": p95_jump,
        "median_ratio": percentile(ratios, 0.50),
        "direction_stable_internal": bool(rows) and (p95_jump or 999.0) < 30.0,
        "direction_matches_status": status_summary.get("direction_stable_against_status") if status_summary else None,
        "median_vector_angle_diff_deg": status_summary.get("median_vector_angle_diff_deg") if status_summary else None,
        "p95_vector_angle_diff_deg": status_summary.get("p95_vector_angle_diff_deg") if status_summary else None,
        "baseline_direction_stable": stable_direction,
        "rtklib_also_fails_to_stabilize_heading": bool(rows) and not stable_direction,
        "used_as_solver_input": False,
        "trace_used": False,
        "final_v23_used": False,
        "legsa_used": False,
    }


def parse_status_vectors_from_csv(path: str | Path) -> list[BaselineVector]:
    vectors: list[BaselineVector] = []
    for row in read_csv_rows(path):
        if row.get("vector_order") not in ("", "GNSS2-GNSS1"):
            continue
        try:
            vectors.append(
                BaselineVector(
                    time=float(row["time"]),
                    east_m=float(row["east_m"]),
                    north_m=float(row["north_m"]),
                    up_m=float(row.get("up_m", 0.0)),
                    source="status_baseline_gnss2_minus_gnss1",
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(vectors, key=lambda vector: vector.time)
