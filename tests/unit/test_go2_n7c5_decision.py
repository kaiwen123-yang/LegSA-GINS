"""中文说明：单元测试覆盖 N7C5 decision gate。"""

from legsa_gins.go2_prior.go2_n7c5_decision import make_n7c5_decision


def test_n7c5_decision_routes_ready_foot_candidate_to_n7c6():
    decision = make_n7c5_decision(
        foot_report={"activation_candidate": "ready_for_N7C6", "physical_plausibility": "plausible"},
        yawrate_report={"stability_status": "stable"},
        relative_report={"relative_odometry_stability": "stable"},
        ranking_report={"recommended_EKF_next_factor": "foot_kinematic_velocity_candidate", "recommended_FGO_candidate_factors": ["yawrate_between_factor_candidate"]},
        n7c4_decision={"recommended_default_policy": "fixed_1p0"},
        figure_manifest={"figure_count_total": 10, "required_figures_generated": True, "required_figures_nonempty": True},
    )
    assert decision["status"] == "ready_for_N7C6_foot_kinematic_velocity_factor"
    assert decision["recommended_next_stage"] == "N7C6_foot_kinematic_velocity_factor_activation"
    assert decision["formal_activation_in_n7c5"] is False
    assert decision["go2_not_truth"] is True


def test_n7c5_decision_falls_back_to_n8a_when_only_existing_factor_stable():
    decision = make_n7c5_decision(
        foot_report={"activation_candidate": "diagnostic_only", "physical_plausibility": "needs_more_evidence"},
        yawrate_report={"stability_status": "diagnostic_only"},
        relative_report={"relative_odometry_stability": "diagnostic_only"},
        ranking_report={"recommended_EKF_next_factor": "go2_horizontal_velocity_fixed_1p0", "recommended_FGO_candidate_factors": []},
        n7c4_decision={"recommended_default_policy": "fixed_1p0"},
        figure_manifest={"figure_count_total": 10, "required_figures_generated": True, "required_figures_nonempty": True},
    )
    assert decision["status"] == "go2_horizontal_velocity_and_attitude_factor_sufficient"
    assert decision["go2_position_prior_enabled"] is False
    assert decision["go2_yaw_prior_enabled"] is False
    assert decision["go2_vertical_velocity_prior_enabled"] is False
