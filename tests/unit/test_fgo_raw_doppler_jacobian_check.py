"""Tests for N8C3 Raw Doppler Jacobian check.

中文说明：验证真实 assembly Jacobian 非零且只触碰速度块。
"""

from legsa_gins.fgo.fgo_factor_types import RawDopplerVelocityFactorRow
from legsa_gins.fgo.fgo_raw_doppler_jacobian_check import build_raw_doppler_jacobian_check_report


def test_raw_doppler_jacobian_check_passes() -> None:
    vectors = [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.2, 0.0]]
    factors = [RawDopplerVelocityFactorRow(state_index=0, time=0.0, vn_mps=0.5, ve_mps=0.0, vd_mps=0.1)]
    report = build_raw_doppler_jacobian_check_report(solution_vectors=vectors, raw_factors=factors)
    assert report["jacobian_contract_passed"]
    assert report["real_jacobian_nonzero_count"] == 3
    assert report["touches_velocity_only"]
