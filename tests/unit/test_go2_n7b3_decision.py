"""中文说明：N7B3 decision keeps diagnostic-only claim boundary."""

from legsa_gins.go2_prior.go2_n7b3_decision import make_n7b3_decision


def test_n7b3_decision_ready_for_n7c_only_when_stable_contact_and_frame():
    decision = make_n7b3_decision(
        velocity_frame_report={
            "recommended_frame_for_diagnostic_prior": "go2_velocity_as_world_enu_or_ned_direct",
            "frame_ambiguity_status": "resolved_for_diagnostic_prior",
        },
        contact_model_report={"contact_model_ready": True, "selected_diagnostic_contact_model": "v3"},
        velocity_prior_report={"prior_csv_generated": True, "contact_gated_epoch_count": 10},
        yaw_rate_prior_report={"prior_epoch_count": 2, "activation_status": "yaw_rate_prior_not_activated_due_to_state_model"},
        activation_report={"diagnostic_degradation_detected": False, "stable_with_updates": ["go2_velocity_contact_gated_diagnostic"]},
    )
    assert decision["status"] == "ready_for_N7C_go2_velocity_contact_weak_prior_activation"
    assert decision["paper_performance_claim"] is False
    assert decision["go2_velocity_truth_claim"] is False
