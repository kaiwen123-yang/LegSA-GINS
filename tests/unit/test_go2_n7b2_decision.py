"""中文说明：N7B2 decision 只决定 future stage，不启用 solver。"""

from legsa_gins.go2_prior.go2_n7b2_decision import make_n7b2_decision


def test_n7b2_decision_ready_path_keeps_priors_disabled():
    decision = make_n7b2_decision(
        distribution_report={"field_quality_status": "usable"},
        contact_v2_report={"contact_quality_status": "ready"},
        smoothing_report={"uncertain_ratio_after": 0.2},
        velocity_segment_report={"readiness_status": "acceptable"},
    )
    assert decision["status"] == "ready_for_go2_velocity_contact_weak_prior_activation"
    assert decision["recommended_next_stage"] == "N7C_go2_velocity_contact_weak_prior_activation"
    assert decision["go2_velocity_prior_enabled"] is False
    assert decision["go2_yaw_prior_enabled"] is False
    assert decision["paper_performance_claim"] is False


def test_n7b2_decision_uncertain_path_blocks_n7c():
    decision = make_n7b2_decision(
        distribution_report={"field_quality_status": "usable"},
        contact_v2_report={"contact_quality_status": "not_ready"},
        smoothing_report={"uncertain_ratio_after": 0.7},
        velocity_segment_report={"readiness_status": "acceptable"},
    )
    assert decision["status"] == "contact_still_not_ready"
