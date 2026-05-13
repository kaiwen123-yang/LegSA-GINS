"""N7B4 decision 单元测试：不得升级正式 Go2 prior。"""

from legsa_gins.go2_prior.go2_n7b4_decision import make_n7b4_decision


def test_n7b4_decision_keeps_formal_prior_disabled():
    decision = make_n7b4_decision(
        contact_probability_report={"contact_probability_model_ready": True, "selected_contact_probability_model": "ensemble_probability"},
        frame_score_report={"frame_status": "ambiguous_but_testable", "selected_frame_for_diagnostic": "body"},
        prior_build_report={"csv_generated": True, "epoch_count": 10},
        activation_report={"stable_with_updates": ["probability_weighted_go2_velocity_diagnostic"], "diagnostic_degradation_detected": False},
    )
    assert decision["status"] == "contact_ready_frame_ambiguous"
    assert decision["formal_go2_velocity_prior"] is False
    assert decision["paper_performance_claim"] is False
