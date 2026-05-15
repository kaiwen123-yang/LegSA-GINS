"""Unit tests for N8I window policy review.

中文说明：窗口策略必须保持 no-future-data，并优先保留 5s/1s 基线窗口。
"""

from types import SimpleNamespace

from legsa_gins.fgo_feedback.fgo_feedback_window_policy_review import build_window_policy_review


def test_window_policy_prefers_stable_5s_1s():
    bundle = SimpleNamespace(
        policy_summaries={
            "window_5s_stride_1s": {"feedback_accept_count": 6, "feedback_reject_count": 0, "eval_nav_generated": True},
            "window_3s_stride_1s": {"feedback_accept_count": 4, "feedback_reject_count": 0, "eval_nav_generated": True},
        },
        window_reports={
            "window_5s_stride_1s": {"window_count": 6, "no_future_data_verified": True, "overlap_stats": {"max_epoch_count": 5}},
            "window_3s_stride_1s": {"window_count": 4, "no_future_data_verified": True, "overlap_stats": {"max_epoch_count": 3}},
        },
        observation_reports={"window_5s_stride_1s": {"feedback_rows": 6}, "window_3s_stride_1s": {"feedback_rows": 4}},
        evaluation_by_policy={
            "window_5s_stride_1s": {"clean_gross_degradation": False},
            "window_3s_stride_1s": {"clean_gross_degradation": False},
        },
        trace_rows={"window_5s_stride_1s": [], "window_3s_stride_1s": []},
    )
    report = build_window_policy_review(bundle)
    assert report["selected_window_policy"] == "window_5s_stride_1s"
    assert report["no_future_data_feedback"] is True
    assert report["trace_solver_input"] is False
