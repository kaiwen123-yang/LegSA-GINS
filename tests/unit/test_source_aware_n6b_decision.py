from legsa_gins.source_aware.source_aware_n6b_decision import make_n6b_source_aware_decision


def test_n6b_decision_blocks_clean_degradation():
    # 中文说明：clean 退化时必须阻塞到 N6C，不进入 Go2/FGO。
    decision = make_n6b_source_aware_decision(
        {
            "main_variant_stats": {
                "source_aware_trace_generated": True,
                "stats_by_source": {"raw_doppler_velocity": {"R_scale_changed_count": 1}},
            }
        },
        {"comparisons": {"n6b_lsim_oim_minus_no_sourceaware": {"diagnostic_label": "diagnostic_degradation"}}},
        {"response_status": "increased_mildly"},
        {"clean_neutrality_gate": {"pass": False}},
    )
    assert decision["status"] == "needs_policy_fix"
    assert decision["recommended_next_stage"] == "N6C_source_aware_threshold_review"


def test_n6b_decision_keeps_no_paper_claim():
    # 中文说明：即使 clean neutral，也不能产生 paper performance claim。
    decision = make_n6b_source_aware_decision(
        {
            "main_variant_stats": {
                "source_aware_trace_generated": True,
                "stats_by_source": {"raw_doppler_velocity": {"R_scale_changed_count": 1}},
            }
        },
        {"comparisons": {"n6b_lsim_oim_minus_no_sourceaware": {"diagnostic_label": "diagnostic_neutral"}}},
        {"response_status": "increased_mildly"},
        {"clean_neutrality_gate": {"pass": True}},
    )
    assert decision["paper_performance_claim"] is False
    assert decision["go2_prior"] is False
