"""中文说明：单测 N8G decision 只给工程阶段建议，不给性能 claim。"""

from legsa_gins.fgo_feedback.fgo_feedback_decision import build_n8g_decision_report


def test_n8g_decision_ready_when_feedback_enters_ekf():
    decision = build_n8g_decision_report(
        observation_report={"feedback_rows": 2},
        variant_report={"feedback_update_count_total": 2, "feedback_accept_count_total": 2, "feedback_reject_count_total": 0},
        evaluation_report={"gross_degradation_status": "absent"},
    )
    assert decision["status"] == "fgo_feedback_ekf_foundation_ready"
    assert decision["fgo_feedback_output_substitution"] is False
