"""Build raw-carrier ambiguity candidates from common RAWX carrier phases."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from legsa_gins.raw_gnss.ubx_rawx_parser import parse_rawx_from_csv

from .common_epoch_satellite_matcher import group_by_epoch_sat


def build_ambiguity_candidate_summary(gnss1_raw: str | Path, gnss2_raw: str | Path, *, max_epochs: int = 200) -> dict[str, Any]:
    grouped1 = group_by_epoch_sat(parse_rawx_from_csv(gnss1_raw))
    grouped2 = group_by_epoch_sat(parse_rawx_from_csv(gnss2_raw))
    candidate_rows: list[dict[str, Any]] = []
    for epoch in sorted(set(grouped1) & set(grouped2)):
        common = sorted(set(grouped1[epoch]) & set(grouped2[epoch]))
        common = [sat for sat in common if math.isfinite(grouped1[epoch][sat].cp_mes) and math.isfinite(grouped2[epoch][sat].cp_mes)]
        if len(common) < 2:
            continue
        ref = common[0]
        ref_sd = grouped2[epoch][ref].cp_mes - grouped1[epoch][ref].cp_mes
        for sat in common[1:]:
            sd = grouped2[epoch][sat].cp_mes - grouped1[epoch][sat].cp_mes
            dd_cycles = sd - ref_sd
            candidate_rows.append(
                {
                    "rcv_tow": epoch,
                    "reference_satellite": ref,
                    "satellite": sat,
                    "dd_phase_cycles": dd_cycles,
                    "nearest_integer": round(dd_cycles),
                    "fractional_residual_cycles": dd_cycles - round(dd_cycles),
                }
            )
        if len({row["rcv_tow"] for row in candidate_rows}) >= max_epochs:
            break
    residuals = [abs(float(row["fractional_residual_cycles"])) for row in candidate_rows]
    return {
        "ambiguity_candidate_vector_available": bool(candidate_rows),
        "candidate_count": len(candidate_rows),
        "sample_candidates": candidate_rows[:20],
        "fractional_residual_abs_median_cycles": sorted(residuals)[len(residuals) // 2] if residuals else None,
        "integer_rounding_policy": "nearest_integer_for_candidate_diagnostics_only",
        "full_backend_ambiguity_solution": False,
        "blocker_reasons": [] if candidate_rows else ["no_common_carrier_phase_dd_candidates"],
        "trace_solver_input": False,
        "status_yaw_used_as_ambiguity": False,
    }
