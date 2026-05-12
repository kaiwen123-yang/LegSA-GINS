"""中文说明：Go2 velocity 是 cross-source consistency，不是真值误差。"""

from legsa_gins.go2_prior.go2_velocity_quality import analyze_velocity_quality


def test_go2_velocity_quality_reports_not_truth():
    go2_rows = [
        {"aligned_time": float(i), "go2_velocity_0": 0.5, "go2_velocity_1": 0.0, "go2_velocity_2": 0.0}
        for i in range(12)
    ]
    receiver = [{"time": float(i), "vn": 0.5, "ve": 0.0, "vd": 0.0} for i in range(12)]
    raw = [{"time": float(i), "vn": 0.5, "ve": 0.0, "vd": 0.0} for i in range(12)]
    contact = [{"time": float(i), "contact_label": "walking_contact"} for i in range(12)]
    _, report = analyze_velocity_quality(go2_rows, receiver_velocity_rows=receiver, raw_doppler_rows=raw, contact_rows=contact)
    assert report["aligned_count_to_receiver_velocity"] == 12
    assert report["aligned_count_to_raw_doppler"] == 12
    assert report["velocity_diff_rmse_to_receiver"] == 0.0
    assert report["not_truth"] is True
    assert report["go2_velocity_truth_claim"] is False
    assert report["go2_velocity_prior_enabled"] is False
