"""中文说明：N7B2A metric namespace guard 防止 parity 误读为 absolute accuracy。"""

from legsa_gins.go2_prior.go2_metric_namespace_guard import build_metric_namespace_guard_report


def test_metric_namespace_guard_clarifies_parity_and_cross_source():
    report = build_metric_namespace_guard_report(
        n7a_reports={"comparison": {"go2_attitude_weak_prior_minus_no_go2": {"delta": {"roll_rmse_deg": 0.043, "pitch_rmse_deg": 0.031}}}},
        n7b_reports={"velocity": {"velocity_diff_rmse_to_receiver": 1.2, "bias_n": 0.1}},
        n7b2_reports={"contact_v2": {"walking_contact_ratio": 1.0, "uncertain_ratio": 0.0}},
    )
    assert report["metric_namespace_missing"] is False
    assert report["parity_metrics_clarified"] is True
    assert report["absolute_metrics_clarified"] is True
    assert report["velocity_metric_context"]["go2_velocity_comparison_truth_error"] is False
    assert any(item["namespace"] == "parity_to_final_v23" for item in report["metrics"])
