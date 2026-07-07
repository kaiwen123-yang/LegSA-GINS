"""DA03 Liu constrained wrapped least-squares method boundary."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .common import ecef_delta_to_enu, wrap360
from .method_teunissen_clambda import CLASSIC_CASES, ClassicCase
from .receiver_position import ReceiverApproxPosition
from .wrapped_ls_solver import solve_cwls_baseline
from .yaw_frame_contract import body_yaw_from_lateral_baseline


METHOD_ID = "DA03_LIU_CWLS"
METHOD_NAME = "Liu constrained wrapped least-squares GNSS attitude determination"
FULL_REPRODUCTION_LEVEL = "FAITHFUL_NON_OFFICIAL_ALGORITHM"
DIAGNOSTIC_REPRODUCTION_LEVEL = "DIAGNOSTIC_STATUS_FALLBACK"
PROVIDER_LAYER = "raw_carrier_dd_los"
DA03_CLASSIC_CASES: tuple[ClassicCase, ...] = CLASSIC_CASES


PAPER_TO_CODE_MAPPING_ROWS: tuple[dict[str, Any], ...] = (
    {
        "paper_item": "DD carrier/code observation model",
        "paper_equation": "Eq. (5), Eq. (7), Eq. (9)",
        "code_mapping": "dd_design_matrix rows: dd_carrier_m, dd_code_m, h_x/h_y/h_z",
        "implementation_scope": "single_baseline_by2",
    },
    {
        "paper_item": "wrapped residual",
        "paper_equation": "Eq. (24)-(28)",
        "code_mapping": "wrapped_ls_solver.wrap_cycles((carrier - H b) / wavelength)",
        "implementation_scope": "carrier_phase_cycles",
    },
    {
        "paper_item": "C-WLS objective with code",
        "paper_equation": "Eq. (46), Eq. (52)",
        "code_mapping": "phase wrapped residual plus weak code residual in solve_cwls_baseline",
        "implementation_scope": "known_single_baseline_length",
    },
    {
        "paper_item": "single-baseline constraint",
        "paper_equation": "Eq. (54)-(55)",
        "code_mapping": "baseline vector constrained to nominal BY2 antenna length",
        "implementation_scope": "GNSS2-GNSS1 baseline",
    },
    {
        "paper_item": "integer ambiguity treatment",
        "paper_equation": "Eq. (24), Eq. (75)",
        "code_mapping": "integer ambiguity recovered by special half-down rounding after baseline estimate",
        "implementation_scope": "implicit_integer_ambiguity",
    },
)


def method_contract() -> dict[str, Any]:
    return {
        "method_id": METHOD_ID,
        "method_name": METHOD_NAME,
        "method_mode": "full_backend",
        "provider_layer_used": PROVIDER_LAYER,
        "reproduction_level": FULL_REPRODUCTION_LEVEL,
        "paper": "Liu et al., Constrained Wrapped Least Squares: A Tool for High Accuracy GNSS Attitude Determination",
        "single_baseline_scope": True,
        "wrapped_residual": True,
        "implicit_integer_ambiguity": True,
        "baseline_length_constraint": True,
        "status_yaw_as_full_backend": False,
        "trace_used_for_sign_or_offset": False,
        "per_case_offset": False,
        "old_aggregate_imported": False,
    }


def solve_cwls_design_epochs(
    design_epochs: list[dict[str, Any]],
    *,
    receiver1_position: ReceiverApproxPosition,
    nominal_length_m: float,
    yaw_offset_deg: float = 90.0,
    grid_count: int = 384,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    output_rows: list[dict[str, Any]] = []
    ambiguity_rows: list[dict[str, Any]] = []
    for epoch in design_epochs:
        if int(epoch.get("rank", 0)) < 3 or int(epoch.get("num_dd", 0)) < 3:
            continue
        rows = list(epoch.get("rows", []))
        h = [[float(row["h_x"]), float(row["h_y"]), float(row["h_z"])] for row in rows]
        carrier = [float(row["dd_carrier_m"]) for row in rows]
        code = [float(row["dd_code_m"]) for row in rows]
        wavelengths = [float(row["wavelength_m"]) for row in rows]
        weights = [float(row.get("weight", 1.0)) for row in rows]
        solution = solve_cwls_baseline(
            h_rows=h,
            carrier_m=carrier,
            code_m=code,
            wavelengths_m=wavelengths,
            weights=weights,
            baseline_length_m=nominal_length_m,
            grid_count=grid_count,
            code_sigma_m=1.0,
        )
        if solution is None:
            continue
        bx, by, bz = solution.baseline_vector_m
        east, north, up = ecef_delta_to_enu(bx, by, bz, receiver1_position.lat_deg, receiver1_position.lon_deg)
        length = math.sqrt(east * east + north * north + up * up)
        heading = wrap360(math.degrees(math.atan2(east, north)))
        body_yaw = body_yaw_from_lateral_baseline(heading, offset_deg=yaw_offset_deg)
        output_rows.append(
            {
                "timestamp": epoch.get("timestamp"),
                "rcv_tow": epoch.get("rcv_tow"),
                "method_id": METHOD_ID,
                "method_mode": "full_backend",
                "case_id": "C00_clean_normal",
                "baseline_ecef_x_m": bx,
                "baseline_ecef_y_m": by,
                "baseline_ecef_z_m": bz,
                "baseline_east_m": east,
                "baseline_north_m": north,
                "baseline_up_m": up,
                "baseline_length_m": length,
                "baseline_heading_deg": heading,
                "body_yaw_deg": body_yaw,
                "num_dd": epoch.get("num_dd"),
                "design_rank": epoch.get("rank"),
                "design_condition_number": epoch.get("condition_number"),
                "cwls_objective": solution.objective,
                "wrapped_phase_rms_cycles": solution.wrapped_phase_rms_cycles,
                "code_residual_rms_m": solution.code_residual_rms_m,
                "ambiguity_count": len(solution.integer_ambiguities),
                "ambiguity_fixed_status": "implicit_wrapped_integer_recovered",
                "ambiguity_ratio": "",
                "candidate_count": solution.candidate_count,
                "refinement_steps": solution.refinement_steps,
                "provider_layer_used": PROVIDER_LAYER,
                "reproduction_level": FULL_REPRODUCTION_LEVEL,
                "trace_used_online": False,
                "status_diagnostic_used_as_full_backend": False,
            }
        )
        ambiguity_rows.append(
            {
                "timestamp": epoch.get("timestamp"),
                "rcv_tow": epoch.get("rcv_tow"),
                "ambiguity_count": len(solution.integer_ambiguities),
                "fixed_status": "implicit_wrapped_integer_recovered",
                "wrapped_phase_rms_cycles": solution.wrapped_phase_rms_cycles,
                "trace_solver_input": False,
                "status_yaw_used_as_ambiguity": False,
            }
        )
    return output_rows, ambiguity_rows
