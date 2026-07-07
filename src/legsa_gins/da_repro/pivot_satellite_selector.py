"""Pivot satellite selection for DA01R1 double-difference epochs."""

from __future__ import annotations

from typing import Any


def select_pivot_satellite(satellites: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [sat for sat in satellites if sat.get("valid_flag", True)]
    if not valid:
        return None
    return max(
        valid,
        key=lambda sat: (
            float(sat.get("elevation_deg", -90.0)),
            float(sat.get("cno_avg_dbhz", 0.0)),
            str(sat.get("sat_id", "")),
        ),
    )


def build_pivot_selection_rows(los_epochs: list[dict[str, Any]], *, min_satellites: int = 4) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for epoch in los_epochs:
        sats = list(epoch.get("satellites", []))
        pivot = select_pivot_satellite(sats) if len(sats) >= min_satellites else None
        rows.append(
            {
                "rcv_tow": epoch.get("rcv_tow"),
                "timestamp": epoch.get("timestamp"),
                "common_satellite_count": len(sats),
                "min_satellite_requirement": min_satellites,
                "pivot_selected": pivot is not None,
                "pivot_satellite": pivot.get("sat_id") if pivot else "",
                "pivot_elevation_deg": pivot.get("elevation_deg") if pivot else "",
                "pivot_cno_avg_dbhz": pivot.get("cno_avg_dbhz") if pivot else "",
                "selection_policy": "highest_elevation_then_average_cno_then_sat_id",
                "trace_used_for_selection": False,
            }
        )
    return rows


def pivot_selection_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [row for row in rows if row.get("pivot_selected")]
    counts = [int(row["common_satellite_count"]) for row in rows]
    return {
        "epoch_count": len(rows),
        "pivot_selected_epoch_count": len(usable),
        "min_common_satellite_count": min(counts) if counts else 0,
        "max_common_satellite_count": max(counts) if counts else 0,
        "pivot_selection_pass": bool(usable),
        "selection_policy": "highest_elevation_then_average_cno_then_sat_id",
        "trace_used_for_selection": False,
    }
