"""Unit tests for N8F foot kinematic velocity factor.

中文说明：检查 foot residual、水平速度注入和非真值边界。
"""

from legsa_gins.fgo.fgo_contact_aware_weighting_factor import ContactAwareWeightRow
from legsa_gins.fgo.fgo_foot_kinematic_velocity_factor import (
    build_foot_kinematic_velocity_factors,
    inject_foot_kinematic_velocity,
    residuals_for_foot_kinematic_velocity,
    summarize_foot_kinematic_velocity_factor,
)


def test_foot_factor_residual_and_jacobian_are_active() -> None:
    contact = [ContactAwareWeightRow(0.0, 1.0, 0.8, 0.2, 0.2)]
    factors = build_foot_kinematic_velocity_factors(
        epoch_times=[0.0],
        foot_rows=[{"time": "0.0", "candidate_vn": "0.8", "candidate_ve": "0.1", "slip_risk": "0.2"}],
        contact_rows=contact,
    )
    solution = [[30.0, 120.0, 10.0, 0.0, 0.0, 0.0, 1.0, 0.2, 0.0]]
    residuals = residuals_for_foot_kinematic_velocity(solution, factors)
    report = summarize_foot_kinematic_velocity_factor(factors, residuals, toggle_delta_rows=len(residuals))
    assert report["factor_rows"] == 1
    assert report["residual_rows"] == 2
    assert report["jacobian_nonzero_count"] == 2
    assert report["go2_truth_claim"] is False


def test_foot_injection_moves_horizontal_velocity_only() -> None:
    contact = [ContactAwareWeightRow(0.0, 1.0, 0.8, 0.2, 0.2)]
    factors = build_foot_kinematic_velocity_factors(
        epoch_times=[0.0],
        foot_rows=[{"time": "0.0", "candidate_vn": "0.0", "candidate_ve": "0.0", "slip_risk": "0.2"}],
        contact_rows=contact,
    )
    solution = [[30.0, 120.0, 10.0, 0.0, 0.0, 0.0, 1.0, 0.2, -0.3]]
    updated = inject_foot_kinematic_velocity(solution, factors, strength=0.2)
    assert updated[0][6] < solution[0][6]
    assert updated[0][7] < solution[0][7]
    assert updated[0][8] == solution[0][8]
