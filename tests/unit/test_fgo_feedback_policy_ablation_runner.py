"""Unit tests for N8I policy-ablation runner helpers.

中文说明：runner 汇总 helper 必须保留 correction stats 和 no-claim 边界。
"""

from types import SimpleNamespace

from legsa_gins.fgo_feedback.fgo_feedback_policy_ablation_runner import build_mode_ablation_reports, policy_trace_stats


def test_policy_trace_stats_counts_attitude_spikes():
    bundle = SimpleNamespace(
        trace_rows={
            "policy": [
                {"update_time": 1.0, "attitude_norm_deg": 4.5, "velocity_norm_mps": 0.2, "position_norm_m": 0.0, "yaw_residual_deg": 0.1, "accepted": 1}
            ]
        }
    )
    report = policy_trace_stats(bundle, "policy")
    assert report["attitude_spike_count_over_4deg"] == 1
    assert report["attitude_deg"]["max"] == 4.5


def test_mode_ablation_report_boundary_flags():
    bundle = SimpleNamespace(
        policy_summaries={
            "baseline_no_feedback": {"feedback_accept_count": 0, "feedback_reject_count": 0, "eval_nav_generated": True},
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
            "reject_all_sanity": {
                "clean_gross_degradation": False,
                "feedback_vs_baseline_delta": {
                    "horizontal_m": {"p50": 0.0, "p95": 0.0, "max": 0.0},
                    "yaw_deg": {"p50": 0.0, "p95": 0.0, "max": 0.0},
                },
            }
        },
        trace_rows={"baseline_no_feedback": [], "reject_all_sanity": []},
    )
    summaries, comparison = build_mode_ablation_reports(bundle)
    assert summaries["reject_all_sanity_passed"] is True
    assert comparison["trace_solver_input"] is False
