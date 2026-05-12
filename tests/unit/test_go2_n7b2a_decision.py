"""中文说明：N7B2A decision 不启用 solver prior。"""

from legsa_gins.go2_prior.go2_n7b2a_decision import make_n7b2a_decision


def test_n7b2a_decision_blocks_low_physical_plausibility():
    decision = make_n7b2a_decision(
        attitude_std_report={"std_policy_status": "clear"},
        metric_namespace_report={"metric_namespace_missing": False},
        contact_physical_report={
            "physical_plausibility_status": "review_or_not_ready",
            "velocity_segment_readiness_status": "acceptable",
            "all_contact_suspect": True,
            "contact_too_permissive": True,
            "alternating_contact_ratio": 0.1,
        },
    )
    assert decision["status"] == "contact_v2_not_ready"
    assert decision["go2_velocity_prior_enabled"] is False
    assert decision["go2_yaw_prior_enabled"] is False
    assert decision["fgo"] is False


def test_n7b2a_decision_ready_path_is_future_review_only():
    decision = make_n7b2a_decision(
        attitude_std_report={"std_policy_status": "clear"},
        metric_namespace_report={"metric_namespace_missing": False},
        contact_physical_report={
            "physical_plausibility_status": "plausible",
            "velocity_segment_readiness_status": "acceptable",
        },
    )
    assert decision["status"] == "ready_for_go2_velocity_contact_weak_prior_activation"
    assert decision["go2_velocity_prior_enabled"] is False
