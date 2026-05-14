"""Tests for N8C3 Raw Doppler toggle regression.

中文说明：验证 toy/real toggle 都移除 Raw Doppler residual rows。
"""

from legsa_gins.fgo.fgo_factor_types import RawDopplerVelocityFactorRow
from legsa_gins.fgo.fgo_raw_doppler_solver_injection import run_raw_doppler_solver_variant
from legsa_gins.fgo.fgo_raw_doppler_toggle_regression import build_raw_doppler_toggle_regression_report


def test_raw_doppler_toggle_regression_passes() -> None:
    rows = [
        {"index": index, "time": float(index), "lat_deg": 30.0, "lon_deg": 120.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": float(index), "vn_mps": 1.0, "ve_mps": 0.0, "vd_mps": 0.0}
        for index in range(4)
    ]
    factors = [RawDopplerVelocityFactorRow(state_index=index, time=float(index), vn_mps=0.5, ve_mps=0.0, vd_mps=0.0) for index in range(4)]
    _, with_raw = run_raw_doppler_solver_variant(ekf_rows=rows, raw_factors=factors, variant="weak_yaw_smoothness_with_raw_fixed")
    _, without_raw = run_raw_doppler_solver_variant(ekf_rows=rows, raw_factors=factors, variant="raw_doppler_off_verified")
    report = build_raw_doppler_toggle_regression_report(ekf_rows=rows, raw_factors=factors, with_raw_summary=with_raw, without_raw_summary=without_raw)
    assert report["toggle_regression_passed"]
    assert report["real"]["raw_factor_residual_summary_present_only_with_raw"]
