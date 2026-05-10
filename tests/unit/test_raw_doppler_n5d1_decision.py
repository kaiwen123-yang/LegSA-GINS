from legsa_gins.raw_gnss.raw_doppler_n5d1_decision import make_n5d1_decision


def test_n5d1_decision_maps_empty_figures_to_n5d2():
    # 中文说明：mandatory 图为空时必须回到 N5D2，不允许 visual validation 通过。
    decision = make_n5d1_decision(
        coverage_report={"mandatory_coverage_passed": False, "required_figures_nonempty": False, "required_figures_generated": False},
        spike_report={"spike_count": 2, "recommended_action": "source_aware_candidate"},
        semantics_report={"velocity_3sigma_semantics_fixed": True},
    )
    assert decision["status"] == "visual_validation_not_ready"
    assert decision["recommended_next_stage"] == "N5D2_clean_ablation_timeseries_recovery"


def test_n5d1_decision_maps_repaired_spike_audit_to_n6a():
    # 中文说明：覆盖与 spike audit 均完成时，只给出下一阶段准入建议，不实现 N6A。
    decision = make_n5d1_decision(
        coverage_report={"mandatory_coverage_passed": True, "required_figures_nonempty": True, "required_figures_generated": True},
        spike_report={"spike_count": 2, "recommended_action": "source_aware_candidate", "spike_impact_on_EKF": "medium"},
        semantics_report={"velocity_3sigma_semantics_fixed": True},
    )
    assert decision["status"] == "visual_validation_repaired_ready"
    assert decision["recommended_next_stage"] == "N6A_source_aware_LSIM_OIM_weighting_foundation"
    assert decision["paper_performance_claim"] is False


def test_n5d1_decision_maps_high_impact_spike_to_policy_needed():
    # 中文说明：高影响 spike 需要后续策略处理，N5D1 不调 gate。
    decision = make_n5d1_decision(
        coverage_report={"mandatory_coverage_passed": True, "required_figures_nonempty": True, "required_figures_generated": True},
        spike_report={"spike_count": 2, "recommended_action": "gating_needed", "spike_impact_on_EKF": "high"},
        semantics_report={"velocity_3sigma_semantics_fixed": True},
    )
    assert decision["status"] == "visual_repaired_but_spike_policy_needed"
    assert decision["recommended_next_stage"] == "N5E_raw_doppler_gating_if_high_impact"
