"""Unit tests for N8I decision rules.

中文说明：决策必须输出保守 gate/cov/window 选择，并保留无论文宣称边界。
"""

from legsa_gins.fgo_feedback.fgo_feedback_n8i_decision import build_n8i_decision_report


def test_n8i_decision_selects_conservative_gate():
    report = build_n8i_decision_report(
        policy_grid={"runtime_curated_policy_count": 9},
        gate_review={"classification": "conservative_gate_recommended", "selected_gate_policy": "combined_conservative_gate"},
        covariance_review={"selected_covariance_policy": "inflation_auto_from_residual_proxy"},
        window_review={"selected_window_policy": "window_5s_stride_1s"},
        mode_summaries={"reject_all_sanity_passed": True, "variants": [{"policy_id": "primary_hv_att_conservative_gate", "feedback_mode": "horizontal_velocity_attitude_feedback", "gross_degradation": False}]},
        mode_comparison={"gross_degradation_status": "absent"},
        attitude_spike_review={"default_attitude_spike_count": 2, "conservative_gate_reject_count_for_attitude_or_yaw": 2},
        figure_manifest={"all_required_figures_nonempty": True, "figure_count_total": 12},
    )
    assert report["status"] == "conservative_feedback_gate_ready"
    assert report["selected_feedback_policy"] == "primary_hv_att_conservative_gate"
    assert report["paper_performance_claim"] is False
