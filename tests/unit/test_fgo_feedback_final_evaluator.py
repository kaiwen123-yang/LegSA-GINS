"""Unit tests for N8J final evaluator.

中文说明：final evaluator 必须保留 metric namespace 和 no-claim 边界。
"""

from types import SimpleNamespace

from legsa_gins.fgo_feedback.fgo_feedback_final_evaluator import build_final_evaluation_report


def test_final_evaluator_reports_selected_delta_namespace():
    bundle = SimpleNamespace(
        evaluation_by_policy={
            "n8j_selected_conservative_feedback": {"feedback_vs_baseline_delta": {"horizontal_m": {"p95": 0.1}}},
            "default_gate_feedback_for_reference": {},
            "reject_all_sanity": {},
        },
        policy_summaries={"n8j_selected_conservative_feedback": {"feedback_accept_count": 4, "feedback_reject_count": 2}},
        observation_reports={"n8j_selected_conservative_feedback": {"feedback_rows": 6}},
        trace_rows={"n8j_selected_conservative_feedback": []},
    )
    report = build_final_evaluation_report(bundle)
    assert "feedback_vs_baseline_delta" in report["metric_namespaces"]
    assert report["feedback_counts"]["accepted"] == 4
    assert report["paper_performance_claim"] is False
