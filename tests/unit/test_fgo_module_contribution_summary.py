"""Tests for N8E module contribution summary.

中文说明：验证 Raw Doppler 低边际贡献 caveat 不被写成失败。
"""

from legsa_gins.fgo.fgo_module_contribution_summary import build_module_contribution_summary


def test_module_summary_preserves_raw_doppler_caveat_not_failure() -> None:
    report = build_module_contribution_summary(
        stage_reports={
            "n5b_decision": {"status": "raw_doppler_frontend_active"},
            "n8c3_decision": {"status": "raw_doppler_active_consistent_or_dominated"},
            "n8d_decision": {"raw_doppler_remains_low_marginal_value": True},
            "n8d_raw_receiver": {"raw_doppler_remains_low_marginal_value": True},
        },
        matrix_report={"matrix_complete": True},
    )
    modules = {row["module"]: row for row in report["modules"]}
    assert report["module_count"] == 8
    assert modules["Raw Doppler EKF"]["status"] == "active_effective_frontend_factor"
    assert modules["Raw Doppler FGO"]["status"] == "active_solver_factor_low_marginal_value"
    assert modules["Raw Doppler FGO"]["low_marginal_value_is_failure"] is False
    assert report["candidate_factors_diagnostic_only"]
