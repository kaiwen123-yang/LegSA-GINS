"""中文说明：N7B decision 只推荐未来阶段，不启用 N7B prior。"""

from legsa_gins.go2_prior.go2_n7b_decision import make_n7b_decision


def test_go2_n7b_decision_ready_for_future_velocity_activation():
    decision = make_n7b_decision(
        contact_report={"recommended_contact_quality_status": "ready", "uncertain_ratio": 0.1},
        velocity_report={"consistency_status": "acceptable_for_future_review"},
        yaw_rate_report={"consistency_status": "review_required", "yaw_rate_prior_recommended": "false"},
        motion_report={},
        n7a_weak_prior_report={"activation_allowed": True},
    )
    assert decision["status"] == "ready_for_go2_velocity_weak_prior_activation"
    assert decision["recommended_next_stage"] == "N7C_go2_velocity_contact_weak_prior_activation"
    assert decision["go2_velocity_prior_enabled"] is False
    assert decision["paper_performance_claim"] is False
