"""N7B5 frame equivalence 单元测试：horizontal review 不使用 truth claim。"""

from legsa_gins.go2_prior.go2_frame_equivalence_review import review_frame_equivalence


def _rows():
    return [
        {
            "time": index * 0.1,
            "aligned_time": index * 0.1,
            "roll_rad": 0.002,
            "pitch_rad": -0.002,
            "yaw_rad": 0.02 * index,
            "yaw_speed_radps": 0.02,
            "go2_velocity_0": 1.0,
            "go2_velocity_1": 0.1,
            "go2_velocity_2": 0.0,
        }
        for index in range(20)
    ]


def test_frame_equivalence_marks_horizontal_diagnostic_only():
    rows = _rows()
    source = [{"time": row["time"], "vn": 1.0, "ve": 0.1, "vd": 0.0} for row in rows]
    timeseries, report = review_frame_equivalence(
        go2_rows=rows,
        frame_score_report={
            "best_candidate": "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
            "second_best": "yaw_only_rotation_diagnostic_only",
            "frame_status": "ambiguous_but_testable",
            "margin": 0.0004,
        },
        receiver_velocity_rows=source,
        raw_doppler_rows=source,
    )
    assert timeseries
    assert report["diagnostic_only"] is True
    assert report["go2_velocity_truth_claim"] is False
    assert report["formal_go2_velocity_prior"] is False
    assert report["trace_solver_input"] is False
    assert report["recommended_horizontal_policy"] in {
        "use_best_frame_horizontal_only",
        "use_yaw_only_horizontal_only",
        "do_not_use_go2_velocity",
    }
