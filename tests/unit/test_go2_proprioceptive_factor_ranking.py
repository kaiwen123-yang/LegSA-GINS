"""中文说明：单元测试覆盖 N7C5 Go2 本体候选因子排序。"""

from legsa_gins.go2_prior.go2_proprioceptive_factor_ranking import build_go2_proprioceptive_factor_ranking


def test_proprioceptive_factor_ranking_selects_ready_ekf_candidate():
    report = build_go2_proprioceptive_factor_ranking(
        inventory_report={"fields": {"rpy": {"available": True}, "quaternion": {"available": True}}},
        contact_report={"usable_as_weight": True},
        foot_report={"candidate_generated": True, "availability_ratio": 0.9, "rmse_to_receiver": 0.1, "rmse_to_raw": 0.2, "slip_risk_mean": 0.1, "activation_candidate": "ready_for_N7C6", "physical_plausibility": "plausible"},
        phase_report={"factor_gating_ready": True},
        yawrate_report={"row_count": 20, "stability_status": "stable"},
        relative_report={"window_count": 10, "relative_odometry_stability": "stable"},
        n7c4_decision={"recommended_default_policy": "fixed_1p0"},
    )
    assert report["recommended_EKF_next_factor"] in {"foot_kinematic_velocity_candidate", "go2_horizontal_velocity_fixed_1p0"}
    assert "yawrate_between_factor_candidate" in report["recommended_FGO_candidate_factors"]
    assert report["go2_not_truth"] is True
    assert report["paper_performance_claim"] is False
