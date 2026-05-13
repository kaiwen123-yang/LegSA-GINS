"""N7C1 visual decision unit tests.

中文说明：单测验证 N7C1 只产生 visual gate 决策，不产生 paper performance claim。
"""

from legsa_gins.go2_prior.go2_n7c_visual_decision import make_n7c1_visual_decision


def test_n7c1_visual_decision_fails_empty_figures():
    decision = make_n7c1_visual_decision(
        coverage_report={"required_figures_nonempty": False},
        sanity_report={"vertical_velocity_disabled_confirmed": True},
        n7c_decision_report={"status": "ready_with_weak_stress_evidence"},
    )
    assert decision["status"] == "visual_validation_failed_empty_figures"
    assert decision["recommended_next_stage"] == "N7C2_timeseries_recovery"


def test_n7c1_visual_decision_passes_with_weak_stress_evidence():
    decision = make_n7c1_visual_decision(
        coverage_report={"required_figures_nonempty": True},
        sanity_report={
            "vertical_velocity_disabled_confirmed": True,
            "clean_no_gross_degradation_visual": True,
            "stress_variants_visual_stable": True,
            "visual_sanity_passed": True,
        },
        n7c_decision_report={"status": "ready_with_weak_stress_evidence"},
    )
    assert decision["status"] == "visual_validation_passed_with_weak_stress_evidence"
    assert decision["paper_performance_claim"] is False
    assert decision["go2_velocity_truth_claim"] is False
