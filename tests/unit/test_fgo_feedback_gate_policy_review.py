"""Unit tests for N8I gate policy review.

中文说明：default gate 全接受且 N8H 有 attitude spike 时，应推荐保守 gate。
"""

from types import SimpleNamespace

from legsa_gins.fgo_feedback.fgo_feedback_gate_policy_review import build_gate_policy_review


def test_gate_review_recommends_conservative_gate_for_spikes():
    bundle = SimpleNamespace(
        policy_summaries={
            "gate_default_primary": {"feedback_accept_count": 6, "feedback_reject_count": 0, "eval_nav_generated": True},
            "gate_combined_conservative": {"feedback_accept_count": 4, "feedback_reject_count": 2, "eval_nav_generated": True},
        },
        gate_reports={
            "gate_default_primary": {"feedback_count": 6, "accept_count": 6, "reject_count": 0, "gate_thresholds": {}},
            "gate_combined_conservative": {"feedback_count": 6, "accept_count": 4, "reject_count": 2, "gate_thresholds": {}},
        },
        evaluation_by_policy={
            "gate_default_primary": {"clean_gross_degradation": False},
            "gate_combined_conservative": {"clean_gross_degradation": False},
        },
        trace_rows={"gate_default_primary": [], "gate_combined_conservative": []},
        n8g_reports={"FGO_FEEDBACK_GATE_REPORT.json": {"accept_count": 6, "reject_count": 0, "correction_norm_stats": {}}},
        n8h_reports={"FGO_FEEDBACK_CORRECTION_REVIEW_REPORT.json": {"attitude_correction_spike_count_primary": 2}},
    )
    report = build_gate_policy_review(bundle)
    assert report["classification"] == "conservative_gate_recommended"
    assert report["selected_gate_policy"] == "combined_conservative_gate"
    assert report["trace_solver_input"] is False
