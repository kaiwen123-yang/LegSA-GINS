"""Unit tests for N8F relative odometry between factor.

中文说明：检查相对位置增量 residual，不建立 Go2 绝对位置真值。
"""

from legsa_gins.fgo.fgo_contact_aware_weighting_factor import ContactAwareWeightRow
from legsa_gins.fgo.fgo_relative_odometry_between_factor import (
    build_relative_odometry_between_factors,
    inject_relative_odometry_between,
    residuals_for_relative_odometry_between,
    summarize_relative_odometry_between_factor,
)


def test_relative_odometry_between_factor_has_increment_residual() -> None:
    solution = [
        [30.0, 120.0, 10.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
        [30.00001, 120.00001, 10.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
    ]
    contact = [ContactAwareWeightRow(0.0, 1.0, 0.8, 0.2, 0.2)]
    factors = build_relative_odometry_between_factors(epoch_times=[0.0, 1.0], solution_vectors=solution, contact_rows=contact)
    residuals = residuals_for_relative_odometry_between(solution, factors)
    report = summarize_relative_odometry_between_factor(factors, residuals, toggle_delta_rows=len(residuals))
    assert report["factor_rows"] == 1
    assert report["residual_rows"] == 2
    assert report["absolute_go2_position_factor"] is False


def test_relative_odometry_injection_updates_next_position() -> None:
    solution = [
        [30.0, 120.0, 10.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
        [30.00001, 120.00001, 10.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
    ]
    contact = [ContactAwareWeightRow(0.0, 1.0, 0.8, 0.2, 0.2)]
    factors = build_relative_odometry_between_factors(
        epoch_times=[0.0, 1.0],
        solution_vectors=solution,
        contact_rows=contact,
        aggregate_report={"relative_odometry_scale_hint": 0.9},
    )
    updated = inject_relative_odometry_between(solution, factors, strength=0.2)
    assert updated[1][0] != solution[1][0] or updated[1][1] != solution[1][1]
