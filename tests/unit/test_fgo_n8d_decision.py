"""Tests for N8D decision.

中文说明：N8D 决策保持 no feedback / no paper claim 边界。
"""

from legsa_gins.fgo.fgo_n8d_decision import make_n8d_decision


def test_n8d_decision_reports_process_redesign_when_smoothness_dominates() -> None:
    decision = make_n8d_decision(
        balance_report={"smoothness_dominance_detected": True},
        smoothness_report={"smoothness_still_dominant": True},
        raw_receiver_report={"raw_doppler_remains_low_marginal_value": False},
        go2_report={"go2_joint_stable_low_marginal_value": False},
        formal_matrix_report={"all_required_variants_run": True, "all_variants_real_solver_rerun": True},
        figure_manifest={"figure_count_total": 12, "required_figures_nonempty": True},
    )
    assert decision["status"] == "process_factor_redesign_needed"
    assert decision["recommended_next_stage"] == "N8D2_process_factor_redesign"
    assert not decision["paper_performance_claim"]
