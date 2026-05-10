"""中文说明：测试 N5D 决策映射，确保 source/time/blocker 不被写成 ready claim。"""

from legsa_gins.raw_gnss.raw_doppler_n5d_decision import make_n5d_decision


BASE_SANITY = {
    "raw_velocity_not_pvt_copy": True,
    "raw_velocity_not_gnss_15col_copy": True,
    "time_alignment_ok": True,
    "clean_variant_no_gross_divergence": True,
    "visual_stress_candidate_passed": True,
}


def test_maps_source_issue_to_n5e():
    sanity = dict(BASE_SANITY, time_alignment_ok=False)
    report = make_n5d_decision(sanity, {"stress_help_pair_count": 3})
    assert report["status"] == "not_ready_source_or_alignment_issue"
    assert report["recommended_next_stage"] == "N5E_source_or_time_alignment_fix"


def test_maps_ready_weak_and_degraded():
    ready = make_n5d_decision(BASE_SANITY, {"stress_help_pair_count": 2, "stress_degrade_pair_count": 0})
    assert ready["status"] == "ready_for_source_aware_weighting"
    weak = make_n5d_decision(BASE_SANITY, {"stress_help_pair_count": 1, "stress_degrade_pair_count": 0})
    assert weak["status"] == "ready_with_weak_stress_evidence"
    degraded = make_n5d_decision(dict(BASE_SANITY, clean_variant_no_gross_divergence=False), {"stress_help_pair_count": 3})
    assert degraded["status"] == "not_ready_clean_degradation"
    assert ready["paper_performance_claim"] is False
