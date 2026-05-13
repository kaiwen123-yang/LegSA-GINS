"""中文说明：N7B3 velocity frame review 只做 cross-source consistency，不做 truth claim。"""

from legsa_gins.go2_prior.go2_velocity_frame_review import review_go2_velocity_frame


def test_velocity_frame_review_selects_direct_without_truth_claim():
    go2_rows = []
    receiver_rows = []
    raw_rows = []
    for index in range(12):
        time = index * 0.1
        velocity = [1.0 + 0.05 * index, 0.25, 0.12]
        go2_rows.append(
            {
                "time": time,
                "aligned_time": time,
                "go2_velocity_0": velocity[0],
                "go2_velocity_1": velocity[1],
                "go2_velocity_2": velocity[2],
                "roll_rad": 0.01,
                "pitch_rad": -0.02,
                "yaw_rad": 0.40,
            }
        )
        receiver_rows.append({"time": time, "vn": velocity[0], "ve": velocity[1], "vd": velocity[2]})
        raw_rows.append({"time": time, "vn": velocity[0], "ve": velocity[1], "vd": velocity[2]})
    report = review_go2_velocity_frame(
        go2_rows=go2_rows,
        receiver_velocity_rows=receiver_rows,
        raw_doppler_rows=raw_rows,
    )
    assert report["best_candidate_by_cross_source_consistency"] == "go2_velocity_as_world_enu_or_ned_direct"
    assert report["no_truth_claim"] is True
    assert report["go2_velocity_truth_claim"] is False
