"""N7B5 decision 单元测试：ready 也不能变成 formal prior claim。"""

from legsa_gins.go2_prior.go2_n7b5_decision import make_n7b5_decision


def test_n7b5_decision_ready_for_n7c_horizontal_review():
    decision = make_n7b5_decision(
        frame_equivalence_report={
            "frame_equivalent_for_horizontal_only": True,
            "recommended_horizontal_policy": "use_best_frame_horizontal_only",
        },
        prior_build_report={"csv_generated": True, "epoch_count": 10, "vertical_velocity_disabled": True},
        activation_report={
            "stable_horizontal_variants": ["best_frame_horizontal_only_diagnostic"],
            "total_go2_velocity_prior_update_count": 10,
            "diagnostic_degradation_detected": False,
        },
    )
    assert decision["status"] == "ready_for_N7C_horizontal_go2_velocity_weak_prior"
    assert decision["formal_go2_velocity_prior"] is False
    assert decision["paper_performance_claim"] is False
    assert decision["go2_velocity_truth_claim"] is False


def test_n7b5_decision_degradation_blocks_recommendation():
    decision = make_n7b5_decision(
        frame_equivalence_report={"frame_equivalent_for_horizontal_only": True},
        prior_build_report={"csv_generated": True, "epoch_count": 10},
        activation_report={
            "stable_horizontal_variants": [],
            "total_go2_velocity_prior_update_count": 10,
            "diagnostic_degradation_detected": True,
        },
    )
    assert decision["status"] == "go2_velocity_prior_not_recommended"
    assert decision["recommended_next_stage"] == "N8A_no_feedback_FGO_foundation"
