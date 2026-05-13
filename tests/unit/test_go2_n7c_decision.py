"""N7C decision unit tests.

中文说明：单测验证 N7C 决策状态机，不声明 paper performance。
"""

from legsa_gins.go2_prior.go2_n7c_decision import make_n7c_decision


def _variant(update_count: int) -> dict:
    return {
        "variant_id": "go2_horizontal_velocity_weak_prior_main",
        "returncode": 0,
        "manifest": {
            "go2_horizontal_velocity_prior_update_count": update_count,
            "go2_velocity_prior_reject_count": 0,
        },
    }


def test_n7c_decision_activation_failed_without_updates():
    decision = make_n7c_decision(
        prior_build_report={"epoch_count": 10},
        matrix={"required_variants_present": True},
        variant_summaries={"variants": [_variant(0)]},
        comparison_report={"comparisons": {}},
    )
    assert decision["status"] == "activation_failed"
    assert decision["recommended_next_stage"] == "N7C2_activation_debug"


def test_n7c_decision_ready_with_updates_and_weak_stress():
    decision = make_n7c_decision(
        prior_build_report={"epoch_count": 10},
        matrix={"required_variants_present": True},
        variant_summaries={"variants": [_variant(4)]},
        comparison_report={"comparisons": {}},
    )
    assert decision["status"] == "ready_with_weak_stress_evidence"
    assert decision["paper_performance_claim"] is False
    assert decision["go2_velocity_truth_claim"] is False
