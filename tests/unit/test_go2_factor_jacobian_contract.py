"""Unit tests for N7C2 factor Jacobian contracts.

中文说明：验证 Go2 horizontal velocity 只触碰 vn/ve，vd 导数为零。
"""

from legsa_gins.go2_prior.go2_factor_jacobian_contract import (
    build_go2_factor_jacobian_contract_report,
    toy_go2_horizontal_velocity_check,
)


def test_go2_horizontal_velocity_toy_jacobian_is_horizontal_only():
    result = toy_go2_horizontal_velocity_check()
    assert result["status"] == "toy_passed"
    assert abs(result["dv_n_derivative"][0] - 1.0) < 1.0e-9
    assert abs(result["dv_n_derivative"][1]) < 1.0e-9
    assert abs(result["dv_e_derivative"][0]) < 1.0e-9
    assert abs(result["dv_e_derivative"][1] - 1.0) < 1.0e-9
    assert result["vertical_derivative_zero"] is True


def test_factor_contract_report_keeps_go2_boundaries():
    report = build_go2_factor_jacobian_contract_report()
    assert report["all_active_factor_contracts_present"] is True
    assert report["toy_finite_difference_status"] == "toy_passed"
    assert report["go2_horizontal_H_nonzero_blocks"] == ["velocity_north", "velocity_east"]
    assert report["go2_horizontal_touches_only_horizontal_velocity"] is True
    assert report["go2_horizontal_vertical_derivative_zero"] is True
    assert report["go2_vertical_velocity_prior_enabled"] is False
    assert report["paper_performance_claim"] is False
