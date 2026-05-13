"""中文说明：N7B3 contact comparison 只选择 diagnostic contact model。"""

from legsa_gins.go2_prior.go2_contact_model_candidates import build_contact_model_candidates
from legsa_gins.go2_prior.go2_contact_model_comparison import compare_contact_models


def _rows():
    out = []
    for index in range(24):
        time = index * 0.1
        row = {
            "time": time,
            "aligned_time": time,
            "mode": "walk",
            "gait_type": "trot",
            "go2_velocity_0": 1.0,
            "go2_velocity_1": 0.25,
            "go2_velocity_2": 0.1,
            "roll_rad": 0.0,
            "pitch_rad": 0.0,
            "yaw_rad": 0.3,
        }
        pair = (0, 3) if index % 2 == 0 else (1, 2)
        for foot in range(4):
            row[f"foot_force_{foot}"] = 35.0 if foot in pair else 1.0
            for axis in range(3):
                row[f"foot_speed_body_{3 * foot + axis}"] = 0.05 if foot in pair and axis == 0 else (1.0 if axis == 0 else 0.0)
        out.append(row)
    return out


def test_contact_model_comparison_selects_diagnostic_model():
    go2 = _rows()
    timeseries, candidate_report = build_contact_model_candidates(go2)
    receiver = [{"time": row["time"], "vn": 1.0, "ve": 0.25, "vd": 0.1} for row in go2]
    raw = list(receiver)
    report = compare_contact_models(
        candidate_timeseries=timeseries,
        candidate_report=candidate_report,
        go2_rows=go2,
        receiver_velocity_rows=receiver,
        raw_doppler_rows=raw,
        velocity_frame_report={"recommended_frame_for_diagnostic_prior": "go2_velocity_as_world_enu_or_ned_direct"},
    )
    assert report["contact_model_ready"] is True
    assert report["selected_diagnostic_contact_model"]
    assert report["diagnostic_only"] is True
