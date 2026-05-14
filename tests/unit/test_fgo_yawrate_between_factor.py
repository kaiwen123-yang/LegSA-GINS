"""Unit tests for N8F yaw-rate between factor.

中文说明：检查 yaw-rate between wrap 和非绝对 yaw 真值边界。
"""

from legsa_gins.fgo.fgo_yawrate_between_factor import (
    build_yawrate_between_factors,
    residuals_for_yawrate_between,
    summarize_yawrate_between_factor,
    yawrate_between_residual_deg,
)


def test_yawrate_wrap_contract() -> None:
    assert yawrate_between_residual_deg(359.0, 1.0, 2.0, 1.0) == 0.0


def test_yawrate_factor_report_is_between_only() -> None:
    solution = [
        [30.0, 120.0, 10.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
        [30.0, 120.0, 10.0, 0.0, 0.0, 2.0, 1.0, 0.0, 0.0],
    ]
    factors = build_yawrate_between_factors(epoch_times=[0.0, 1.0], yaw_speed_rows=[{"yaw_speed_abs": "0.034906585"}], solution_vectors=solution)
    residuals = residuals_for_yawrate_between(solution, factors)
    report = summarize_yawrate_between_factor(factors, residuals, toggle_delta_rows=len(residuals))
    assert report["factor_rows"] == 1
    assert report["residual_rows"] == 1
    assert report["absolute_yaw_truth_claim"] is False
