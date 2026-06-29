"""A1 dual-difference yaw construction for BY2 degraded providers."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from legsa_gins.input_generation.status_yaw_builder import apply_yaw_install_and_ned, build_a1_dual_diff_yaw_rows


def build_source_lineage_yaw_series(
    gnss1_status_path: str | Path,
    gnss2_status_path: str | Path,
    *,
    base_time: float | None = None,
) -> tuple[list[dict[str, float]], dict[str, Any]]:
    if base_time is None:
        # The status-yaw builder uses aligned GNSS1 header times; the historical
        # BY2 chain floors the first status epoch to the nearest 100 s block.
        import csv

        with Path(gnss1_status_path).open("r", encoding="utf-8-sig", newline="") as handle:
            first = next(csv.DictReader(handle))
        first_time = float(first.get("header.stamp.secs") or first.get("Time") or first.get("time"))
        base_time = math.floor(first_time / 100.0) * 100.0
    rows, audit = build_a1_dual_diff_yaw_rows(gnss1_status_path, gnss2_status_path, base_time=float(base_time))
    rows = apply_yaw_install_and_ned(rows, sign=1.0, offset_deg=0.0)
    series = [
        {"time": float(row["aligned_time"]), "yaw_deg": float(row["yaw_ned_deg"])}
        for row in rows
    ]
    audit = dict(audit)
    audit.update(
        {
            "gnss_order": "GNSS2-GNSS1",
            "lateral_conversion_formula": "yaw_ned=90-yaw_body",
            "yaw_std_policy": "fixed_1p5_deg unless case spec explicitly changes yaw std",
            "trace_used_for_generation": False,
            "final_v23_output_used_for_generation": False,
            "legsa_output_used_for_generation": False,
            "rmse_selected_sign": False,
        }
    )
    return series, audit

