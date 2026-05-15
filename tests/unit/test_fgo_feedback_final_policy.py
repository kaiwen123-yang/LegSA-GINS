"""Unit tests for N8J selected feedback policy.

中文说明：N8J policy 必须固定为 N8I selected policy。
"""

from legsa_gins.fgo_feedback.fgo_feedback_final_policy import build_selected_policy_report


def test_selected_feedback_policy_is_locked():
    report = build_selected_policy_report()
    assert report["policy_name"] == "n8i_selected_conservative_feedback"
    assert report["gate_policy"] == "combined_conservative_gate"
    assert report["covariance_policy"] == "inflation_auto_from_residual_proxy"
    assert report["position_feedback_enabled"] is False
    assert report["paper_performance_claim"] is False
