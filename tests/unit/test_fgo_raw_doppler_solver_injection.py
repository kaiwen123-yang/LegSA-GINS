"""Tests for N8C3 Raw Doppler solver injection.

中文说明：验证 Raw Doppler 进入 residual vector 且 raw_off 会降低维度。
"""

from legsa_gins.fgo.fgo_factor_types import RawDopplerVelocityFactorRow
from legsa_gins.fgo.fgo_raw_doppler_solver_injection import build_solver_injection_report, run_raw_doppler_solver_variant


def _rows() -> list[dict]:
    return [
        {"index": index, "time": float(index), "lat_deg": 30.0, "lon_deg": 120.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": float(index), "vn_mps": 1.0, "ve_mps": 0.0, "vd_mps": 0.0}
        for index in range(4)
    ]


def _factors() -> list[RawDopplerVelocityFactorRow]:
    return [RawDopplerVelocityFactorRow(state_index=index, time=float(index), vn_mps=0.5, ve_mps=0.1, vd_mps=0.0) for index in range(4)]


def test_solver_injection_adds_raw_residual_rows() -> None:
    _, with_raw = run_raw_doppler_solver_variant(ekf_rows=_rows(), raw_factors=_factors(), variant="weak_yaw_smoothness_with_raw_fixed")
    _, without_raw = run_raw_doppler_solver_variant(ekf_rows=_rows(), raw_factors=_factors(), variant="raw_doppler_off_verified")
    report = build_solver_injection_report(with_raw_summary=with_raw, without_raw_summary=without_raw)
    assert report["appears_in_solver_residual_vector"]
    assert report["residual_row_count"] == 12
    assert report["jacobian_nonzero_count"] == 12
    assert report["dim_delta"] == 12
    assert not report["final_v23_weight_tuning"]
