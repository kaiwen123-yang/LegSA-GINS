"""中文说明：N7B2 smoother 固定诊断参数，不从 trace 调参。"""

from legsa_gins.go2_prior.go2_contact_window_smoother import smooth_contact_state_rows


def test_contact_window_smoother_reduces_single_row_noise():
    labels = ["walking_contact", "walking_contact", "uncertain", "walking_contact", "walking_contact"]
    rows = [
        {"time": index * 0.1, "contact_label_v2": label, **{f"foot_{foot}_contact_v2": int(label != "uncertain") for foot in range(4)}}
        for index, label in enumerate(labels)
    ]
    smoothed, report = smooth_contact_state_rows(rows, window_size=3, min_duration=1)
    assert smoothed[2]["contact_label_v2"] == "walking_contact"
    assert report["uncertain_ratio_after"] < report["uncertain_ratio_before"]
    assert report["go2_velocity_prior_enabled"] is False
