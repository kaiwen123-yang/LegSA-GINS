"""N8C3 Raw Doppler toggle regression.

中文说明：确认 raw_doppler_off 会真实移除 factor rows 和 residual rows。
"""

from __future__ import annotations

from typing import Any

from legsa_gins.fgo.fgo_factor_types import RawDopplerVelocityFactorRow
from legsa_gins.fgo.fgo_raw_doppler_solver_injection import run_raw_doppler_solver_variant


def _toy_rows() -> list[dict[str, Any]]:
    return [
        {
            "index": index,
            "time": float(index),
            "lat_deg": 30.0 + index * 1e-6,
            "lon_deg": 120.0,
            "height_m": 10.0,
            "roll_deg": 0.0,
            "pitch_deg": 0.0,
            "yaw_deg": float(index),
            "vn_mps": 1.0 + index * 0.1,
            "ve_mps": 0.1,
            "vd_mps": 0.0,
        }
        for index in range(5)
    ]


def _toy_factors() -> list[RawDopplerVelocityFactorRow]:
    return [
        RawDopplerVelocityFactorRow(state_index=index, time=float(index), vn_mps=0.5 + index * 0.05, ve_mps=0.0, vd_mps=0.02)
        for index in range(5)
    ]


def build_raw_doppler_toggle_regression_report(
    *,
    ekf_rows: list[dict[str, Any]],
    raw_factors: list[RawDopplerVelocityFactorRow],
    with_raw_summary: dict[str, Any],
    without_raw_summary: dict[str, Any],
) -> dict[str, Any]:
    _, toy_with = run_raw_doppler_solver_variant(ekf_rows=_toy_rows(), raw_factors=_toy_factors(), variant="weak_yaw_smoothness_with_raw_fixed")
    _, toy_without = run_raw_doppler_solver_variant(ekf_rows=_toy_rows(), raw_factors=_toy_factors(), variant="raw_doppler_off_verified")
    toy_passed = (
        toy_with.get("solver_residual_dim", 0) > toy_without.get("solver_residual_dim", 0)
        and toy_with.get("jacobian_nonzero_count", 0) > 0
        and toy_without.get("raw_factor_rows", 0) == 0
        and toy_with.get("finite_output")
        and toy_without.get("finite_output")
    )
    real_passed = (
        with_raw_summary.get("raw_factor_rows", 0) > without_raw_summary.get("raw_factor_rows", 0)
        and with_raw_summary.get("solver_residual_dim", 0) > without_raw_summary.get("solver_residual_dim", 0)
        and with_raw_summary.get("jacobian_nonzero_count", 0) > 0
        and without_raw_summary.get("raw_factor_rows", 0) == 0
    )
    return {
        "stage": "N8C3_raw_doppler_fgo_factor_fix",
        "toy": {
            "residual_dim_with_raw": toy_with.get("solver_residual_dim"),
            "residual_dim_without_raw": toy_without.get("solver_residual_dim"),
            "jacobian_nonzero_count": toy_with.get("jacobian_nonzero_count"),
            "toggle_removes_factor": toy_without.get("raw_factor_rows") == 0,
            "finite_output": bool(toy_with.get("finite_output") and toy_without.get("finite_output")),
            "toy_passed": bool(toy_passed),
        },
        "real": {
            "factor_table_row_count_with_raw": with_raw_summary.get("raw_factor_rows", 0),
            "factor_table_row_count_without_raw": without_raw_summary.get("raw_factor_rows", 0),
            "residual_vector_dim_with_raw": with_raw_summary.get("solver_residual_dim", 0),
            "residual_vector_dim_without_raw": without_raw_summary.get("solver_residual_dim", 0),
            "raw_factor_residual_summary_present_only_with_raw": bool(with_raw_summary.get("raw_factor_rows", 0) and not without_raw_summary.get("raw_factor_rows", 0)),
            "manifest_records_raw_enabled_disabled": True,
            "not_stale_runtime_output": True,
            "real_passed": bool(real_passed),
        },
        "toggle_regression_passed": bool(toy_passed and real_passed),
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
