from legsa_gins.source_aware.source_aware_decision import make_source_aware_decision


def test_source_aware_decision_not_activated_without_trace():
    # 中文说明：没有 trace 或 R scale 变化时必须判定未激活。
    decision = make_source_aware_decision({"main_variant_stats": {}}, {"comparisons": {}}, {})
    assert decision["status"] == "not_activated"
    assert decision["paper_performance_claim"] is False


def test_source_aware_decision_ready_with_spike_response():
    # 中文说明：clean/stress/spike 同时满足时才允许进入后续 Go2 准备。
    weight_stats = {
        "main_variant_stats": {
            "source_aware_trace_generated": True,
            "stats_by_source": {"raw_doppler_velocity": {"R_scale_changed_count": 2}},
        }
    }
    comparison = {
        "comparisons": {
            "baseline_plus_raw_lsim_oim_minus_no_sourceaware": {"diagnostic_label": "diagnostic_neutral"},
            "receiver_velocity_disabled_sourceaware_minus_no_sourceaware": {"diagnostic_label": "diagnostic_improvement"},
        }
    }
    spike = {"raw_doppler_R_scale_increased_near_spikes": True}
    decision = make_source_aware_decision(weight_stats, comparison, spike)
    assert decision["status"] == "ready_for_go2_weak_prior_or_extended_source_weighting"
