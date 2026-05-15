"""Unit tests for N8I mode ablation report.

中文说明：reject-all sanity 必须匹配 baseline，且 report 不能声明 output substitution。
"""

from types import SimpleNamespace

from legsa_gins.fgo_feedback.fgo_feedback_mode_ablation import build_feedback_mode_ablation


def test_mode_ablation_keeps_reject_all_sanity():
    bundle = SimpleNamespace(
        policy_summaries={
            "baseline_no_feedback": {"feedback_accept_count": 0, "feedback_reject_count": 0, "eval_nav_generated": True},
            "primary_horizontal_velocity_attitude_default": {
                "feedback_accept_count": 6,
                "feedback_reject_count": 0,
                "eval_nav_generated": True,
                "no_output_substitution": True,
                "no_direct_nav_override": True,
            },
            "reject_all_sanity": {
                "feedback_accept_count": 0,
                "feedback_reject_count": 0,
                "eval_nav_generated": True,
                "reject_all": True,
                "no_output_substitution": True,
                "no_direct_nav_override": True,
            },
        },
        gate_reports={},
        evaluation_by_policy={
            "primary_horizontal_velocity_attitude_default": {"clean_gross_degradation": False},
            "reject_all_sanity": {
                "clean_gross_degradation": False,
                "feedback_vs_baseline_delta": {
                    "horizontal_m": {"p50": 0.0, "p95": 0.0, "max": 0.0},
                    "yaw_deg": {"p50": 0.0, "p95": 0.0, "max": 0.0},
                },
            },
        },
        trace_rows={"baseline_no_feedback": [], "primary_horizontal_velocity_attitude_default": [], "reject_all_sanity": []},
    )
    summaries, comparison = build_feedback_mode_ablation(bundle)
    assert summaries["reject_all_sanity_passed"] is True
    assert summaries["no_output_substitution"] is True
    assert comparison["paper_performance_claim"] is False
