from legsa_gins.evaluation.legsa_v23_d6_decision import classify_d6


# 中文说明：D6 decision 按证据映射下一阶段，不能在本阶段直接修 solver。
def test_maps_bias_scale_and_unit_evidence_to_d7():
    decision = classify_d6(
        {"bias_feedback_overcorrection": True},
        {"compensation_timing_ok": True},
        {"covariance_unit_mismatch_suspect": True},
        {"bias_scale_feedback_primary_suspect": True},
        {},
    )
    assert decision["recommended_next_stage"] == "N4H4D7_fix_bias_scale_covariance_units"
    assert "bias_feedback_overcorrection" in decision["blocking_issues"]
