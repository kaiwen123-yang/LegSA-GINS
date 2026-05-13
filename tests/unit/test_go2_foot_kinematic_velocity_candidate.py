"""中文说明：单元测试覆盖 N7C5 stance-weighted foot kinematic velocity 候选。"""

import math

from legsa_gins.go2_prior.go2_foot_kinematic_velocity_candidate import build_go2_foot_kinematic_velocity_candidate


def _go2_row(time: float):
    row = {
        "time": time,
        "aligned_time": time,
        "gyro_x": 0.0,
        "gyro_y": 0.0,
        "gyro_z": 0.0,
        "roll_rad": 0.0,
        "pitch_rad": 0.0,
        "yaw_rad": 0.0,
    }
    for foot in range(4):
        row[f"foot_position_body_{3 * foot + 0}"] = 0.2
        row[f"foot_position_body_{3 * foot + 1}"] = 0.1
        row[f"foot_position_body_{3 * foot + 2}"] = -0.3
        row[f"foot_speed_body_{3 * foot + 0}"] = -1.0
        row[f"foot_speed_body_{3 * foot + 1}"] = -0.2
        row[f"foot_speed_body_{3 * foot + 2}"] = 0.0
    return row


def test_foot_kinematic_velocity_candidate_matches_stance_formula():
    go2 = [_go2_row(0.0), _go2_row(0.1), _go2_row(0.2)]
    contact = [{"time": row["time"], **{f"foot_{foot}_contact_probability": 0.9 for foot in range(4)}} for row in go2]
    velocity = [{"time": row["time"], "vn": 1.0, "ve": 0.2, "vd": 0.0} for row in go2]
    rows, report = build_go2_foot_kinematic_velocity_candidate(
        go2_rows=go2,
        contact_rows=contact,
        go2_velocity_rows=velocity,
        receiver_velocity_rows=velocity,
        raw_doppler_rows=velocity,
    )
    assert len(rows) == 3
    assert math.isclose(float(rows[0]["candidate_vn"]), 1.0, abs_tol=1.0e-9)
    assert math.isclose(float(rows[0]["candidate_ve"]), 0.2, abs_tol=1.0e-9)
    assert report["activation_candidate"] == "ready_for_N7C6"
    assert report["not_truth"] is True
    assert report["trace_solver_input"] is False
