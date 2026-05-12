"""中文说明：contact-conditioned velocity review 是 source consistency。"""

from legsa_gins.go2_prior.go2_contact_velocity_segment_review import review_contact_velocity_segments


def test_contact_velocity_segment_review_groups_by_contact_state():
    go2_rows = [
        {"aligned_time": i * 0.1, "go2_velocity_0": 0.5, "go2_velocity_1": 0.0, "go2_velocity_2": 0.0}
        for i in range(20)
    ]
    source_rows = [{"time": i * 0.1, "vn": 0.5, "ve": 0.0, "vd": 0.0} for i in range(20)]
    contact_rows = [{"time": i * 0.1, "contact_label_v2": "walking_contact"} for i in range(20)]
    report = review_contact_velocity_segments(
        go2_rows,
        receiver_velocity_rows=source_rows,
        raw_doppler_rows=source_rows,
        contact_v2_rows=contact_rows,
    )
    assert report["readiness_status"] == "acceptable"
    assert report["go2_velocity_truth_claim"] is False
    assert report["cross_source_velocity_truth_error_claim"] is False
    assert report["velocity_consistency_by_contact_state"]["walking_contact"]["count"] == 20
