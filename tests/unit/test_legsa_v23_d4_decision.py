from legsa_gins.evaluation.legsa_v23_d4_decision import classify_d4


"""中文说明：N4H4D4 决策测试只验证证据到 next-stage 的映射。"""


def test_d4_decision_maps_runtime_update_issue():
    decision = classify_d4(
        {"full_diff": {"horizontal_rmse_m": 100.0}},
        {},
        {"update_count_low": True},
        {},
        {},
    )
    assert decision["most_likely_issue"] == "runtime_loop_update_timing"
    assert decision["recommended_next_stage"] == "N4H4D5_update_timeline_fix"
    assert decision["numerical_performance_claim"] is False
