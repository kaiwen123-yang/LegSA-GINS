"""Build DA01R1 double-difference design matrices from LOS epochs."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .common import percentile
from .dd_observation_model import baseline_design_row_ecef, double_difference_against_pivot
from .pivot_satellite_selector import select_pivot_satellite


def build_dd_design_epochs(los_epochs: list[dict[str, Any]], *, min_satellites: int = 4) -> list[dict[str, Any]]:
    design_epochs: list[dict[str, Any]] = []
    for epoch in los_epochs:
        satellites = [sat for sat in epoch.get("satellites", []) if sat.get("valid_flag", True)]
        if len(satellites) < min_satellites:
            continue
        pivot = select_pivot_satellite(satellites)
        if pivot is None:
            continue
        rows: list[dict[str, Any]] = []
        for sat in satellites:
            if sat["satellite_key"] == pivot["satellite_key"]:
                continue
            wavelength = float(sat.get("wavelength_m", math.nan))
            h = baseline_design_row_ecef(sat, pivot)
            dd = double_difference_against_pivot(sat, pivot)
            finite_h = all(math.isfinite(value) for value in h)
            if not finite_h or not math.isfinite(wavelength) or wavelength <= 0.0:
                continue
            rows.append(
                {
                    "rcv_tow": epoch["rcv_tow"],
                    "timestamp": epoch.get("timestamp"),
                    "pivot_satellite": pivot["sat_id"],
                    "satellite": sat["sat_id"],
                    "constellation": sat["constellation"],
                    "frequency": sat["frequency"],
                    "dd_code_m": dd["dd_code_m"],
                    "dd_carrier_m": dd["dd_carrier_m"],
                    "wavelength_m": wavelength,
                    "h_x": h[0],
                    "h_y": h[1],
                    "h_z": h[2],
                    "ambiguity_key": f"{sat['satellite_key']}-minus-{pivot['satellite_key']}",
                    "weight": max(1.0, min(float(sat.get("cno_avg_dbhz", 1.0)), float(pivot.get("cno_avg_dbhz", 1.0)))) / 45.0,
                }
            )
        if not rows:
            continue
        h_matrix = np.asarray([[row["h_x"], row["h_y"], row["h_z"]] for row in rows], dtype=float)
        rank = int(np.linalg.matrix_rank(h_matrix))
        condition = float(np.linalg.cond(h_matrix)) if rank >= 3 else math.inf
        design_epochs.append(
            {
                "rcv_tow": epoch["rcv_tow"],
                "timestamp": epoch.get("timestamp"),
                "pivot_satellite": pivot["sat_id"],
                "num_common_satellites": len(satellites),
                "num_dd": len(rows),
                "rank": rank,
                "condition_number": condition,
                "all_zero_h": bool(np.allclose(h_matrix, 0.0)),
                "rows": rows,
            }
        )
    return design_epochs


def dd_design_summary(design_epochs: list[dict[str, Any]]) -> dict[str, Any]:
    num_dd = [int(epoch["num_dd"]) for epoch in design_epochs]
    ranks = [int(epoch["rank"]) for epoch in design_epochs]
    conditions = [
        float(epoch["condition_number"])
        for epoch in design_epochs
        if math.isfinite(float(epoch.get("condition_number", math.inf)))
    ]
    rank3 = sum(1 for rank in ranks if rank >= 3)
    nonzero = sum(1 for epoch in design_epochs if not epoch.get("all_zero_h"))
    usable = [
        epoch
        for epoch in design_epochs
        if int(epoch["num_dd"]) >= 3
        and int(epoch["rank"]) >= 3
        and not epoch.get("all_zero_h")
        and math.isfinite(float(epoch.get("condition_number", math.inf)))
        and float(epoch.get("condition_number", math.inf)) < 1.0e6
    ]
    median_num_dd = percentile([float(value) for value in num_dd], 0.50)
    return {
        "design_epoch_count": len(design_epochs),
        "usable_dd_epochs": len(usable),
        "median_num_dd": median_num_dd,
        "rank3_epoch_count": rank3,
        "nonzero_h_epoch_count": nonzero,
        "median_condition_number": percentile(conditions, 0.50) if conditions else None,
        "max_condition_number": max(conditions) if conditions else None,
        "dd_design_matrix_pass": len(usable) >= 50 and (median_num_dd or 0.0) >= 3.0,
        "trace_solver_input": False,
        "status_yaw_used_as_design_input": False,
    }


def dd_design_sample_rows(design_epochs: list[dict[str, Any]], *, max_rows: int = 200) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for epoch in design_epochs:
        for row in epoch["rows"]:
            rows.append(
                {
                    **{key: value for key, value in epoch.items() if key != "rows"},
                    **row,
                }
            )
            if len(rows) >= max_rows:
                return rows
    return rows
