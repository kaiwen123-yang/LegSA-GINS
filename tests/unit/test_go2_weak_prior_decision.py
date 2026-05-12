"""中文说明：N7A decision 不产生 paper performance claim。"""

from legsa_gins.go2_state.go2_weak_prior_decision import make_go2_weak_prior_decision


def test_go2_weak_prior_decision_not_activated():
    decision = make_go2_weak_prior_decision(
        build_report={"activation_allowed": True},
        frame_report={"activation_allowed": True},
        comparison_report={"go2_attitude_weak_prior_manifest": {"go2_attitude_weak_prior_update_count": 0}},
        source_aware_stats={},
    )
    assert decision["status"] == "not_activated"
    assert decision["paper_performance_claim"] is False
