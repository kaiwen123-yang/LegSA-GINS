"""Unit tests for N8F Jacobian checks.

中文说明：检查 toy 有限差分 Jacobian 合同通过。
"""

from legsa_gins.fgo.fgo_legged_factor_jacobian_check import run_legged_factor_jacobian_checks


def test_jacobian_checks_pass() -> None:
    report = run_legged_factor_jacobian_checks()
    assert report["all_passed"] is True
    assert report["checks"]["ContactAwareWeightingLayer"]["state_jacobian_nonzero_count"] == 0
