"""N7B4 velocity frame scoring 单元测试：只验证 consistency，不声明 truth。"""

from legsa_gins.go2_prior.go2_velocity_frame_internal_external_score import score_velocity_frames


def _go2_rows():
    rows = []
    x = 0.0
    for index in range(12):
        t = index * 0.1
        vx = 1.0
        x += vx * 0.1
        rows.append(
            {
                "time": t,
                "aligned_time": t,
                "roll_rad": 0.0,
                "pitch_rad": 0.0,
                "yaw_rad": 0.0,
                "yaw_speed_radps": 0.0,
                "go2_position_0": x,
                "go2_position_1": 0.0,
                "go2_position_2": 0.0,
                "go2_velocity_0": vx,
                "go2_velocity_1": 0.0,
                "go2_velocity_2": 0.0,
            }
        )
    return rows


def test_velocity_frame_score_has_testable_frame():
    source = [{"time": row["time"], "vn": 1.0, "ve": 0.0, "vd": 0.0} for row in _go2_rows()]
    report = score_velocity_frames(go2_rows=_go2_rows(), receiver_velocity_rows=source, raw_doppler_rows=source)
    assert report["best_candidate"]
    assert report["frame_status"] in {"resolved_for_diagnostic", "ambiguous_but_testable"}
    assert report["no_truth_claim"] is True
