from legsa_gins.source_aware.source_aware_n6b_visual_decision import make_n6b1_visual_decision


def test_n6b1_decision_empty_figures_blocks():
    # 中文说明：mandatory 图为空时必须进入 recovery，而不是继续下一阶段。
    decision = make_n6b1_visual_decision(coverage_report={"required_figures_nonempty": False}, sanity_report={})
    assert decision["status"] == "visual_validation_failed_empty_figures"


def test_n6b1_decision_weight_policy_failure():
    # 中文说明：R scale 卡在 cap 时应转入 N6C threshold review。
    decision = make_n6b1_visual_decision(
        coverage_report={"required_figures_nonempty": True, "visual_validation_passed": True},
        sanity_report={"receiver_position_not_slammed_to_cap": False, "receiver_velocity_not_slammed_to_cap": True},
    )
    assert decision["status"] == "visual_validation_failed_weight_policy"


def test_n6b1_decision_passes_nominal():
    # 中文说明：图像、coverage、sanity 全通过时才允许给出 visual pass。
    decision = make_n6b1_visual_decision(
        coverage_report={"required_figures_nonempty": True, "visual_validation_passed": True},
        sanity_report={
            "receiver_position_not_slammed_to_cap": True,
            "receiver_velocity_not_slammed_to_cap": True,
            "clean_no_gross_degradation_visual": True,
            "raw_doppler_spike_response_visible": True,
            "visual_sanity_passed": True,
        },
    )
    assert decision["status"] == "visual_validation_passed"
    assert decision["paper_performance_claim"] is False
