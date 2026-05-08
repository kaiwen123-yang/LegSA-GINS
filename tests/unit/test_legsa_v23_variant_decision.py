"""中文说明：N4H4D2 decision 单元测试。"""

from legsa_gins.evaluation.legsa_v23_variant_decision import classify_d2_decision


def test_variant_decision_maps_candidate_to_d3_stage():
    decision = classify_d2_decision(
        {"formula_mismatch_candidates": []},
        {"immediate_gravity_or_frame_issue": False, "long_free_ins_drift_only": True},
        {
            "candidate_fix_detected": True,
            "candidate_fix_variant": "state_feedback_phi_negative",
            "improved_variants": ["state_feedback_phi_negative"],
            "multi_issue_or_coupled_issue": False,
        },
        {"yaw_reject_ratio": 0.8},
    )
    assert decision["recommended_next_stage"] == "N4H4D3_apply_guarded_fix_state_feedback_phi_negative"
    assert decision["no_performance_claim"] is True
    assert "yaw rejects remain high in D1 evidence" in decision["blocking_issues"]

