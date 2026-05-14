"""Unit tests for N8F legged candidate factor contracts.

中文说明：检查合同报告保留 no-truth 和 no-trace 边界。
"""

from legsa_gins.fgo.fgo_legged_candidate_factor_contracts import build_legged_candidate_factor_contracts
from legsa_gins.fgo.fgo_legged_factor_jacobian_check import run_legged_factor_jacobian_checks


def test_contracts_are_no_truth_and_no_trace() -> None:
    jac = run_legged_factor_jacobian_checks()
    report = build_legged_candidate_factor_contracts(
        contact_report={"rows": 3},
        foot_report={"factor_rows": 3, "go2_truth_claim": False},
        yawrate_report={"factor_rows": 2, "absolute_yaw_truth_claim": False},
        relative_report={"factor_rows": 2, "go2_position_truth_claim": False},
        jacobian_report=jac,
    )
    assert report["all_jacobian_checks_passed"] is True
    assert report["all_no_truth_claim"] is True
    assert report["all_trace_input_false"] is True
