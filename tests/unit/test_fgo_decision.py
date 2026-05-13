from legsa_gins.fgo.fgo_decision import make_n8a_decision


def test_n8a_ready_decision() -> None:
    """中文说明：N8A ready 只表示 foundation 可运行。"""
    decision = make_n8a_decision(
        backend={"selected_backend": "numpy"},
        registry={"no_feedback": True},
        dataset={"state_count": 2, "active_factor_count_estimate": 10, "diagnostic_candidate_factor_count_estimate": 8},
        smoother={"solve_status": "solved", "fgo_output_feedback_to_ekf": False},
        evaluation={"metric_namespace": "FGO_vs_EKF_delta"},
        figures={"required_figures_generated": True, "required_figures_nonempty": True},
    )
    assert decision["status"] == "n8a_no_feedback_fgo_foundation_ready"
    assert decision["paper_performance_claim"] is False
