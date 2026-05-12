"""中文说明：N7B2 contact-state v2 只产生 diagnostic labels。"""

from legsa_gins.go2_prior.go2_contact_state_v2 import build_contact_state_v2


def _threshold_report() -> dict:
    candidate = {
        "force_threshold_by_foot": {f"foot_{foot}": 10.0 for foot in range(4)},
        "low_force_threshold_by_foot": {f"foot_{foot}": 5.0 for foot in range(4)},
        "speed_support_threshold_by_foot": {f"foot_{foot}": 0.3 for foot in range(4)},
    }
    return {"recommended_candidate": "mode_gait_assisted_contact", "candidate_thresholds": {"mode_gait_assisted_contact": candidate}}


def test_contact_state_v2_labels_standing_walking_and_invalid():
    rows = [
        {
            "aligned_time": 0.0,
            "mode": "stand",
            "gait_type": 0,
            "go2_velocity_0": 0.01,
            **{f"foot_force_{foot}": 30.0 for foot in range(4)},
            **{f"foot_speed_body_{axis}": 0.01 for axis in range(12)},
        },
        {
            "aligned_time": 0.1,
            "mode": "walk",
            "gait_type": 1,
            "go2_velocity_0": 0.4,
            "foot_force_0": 30.0,
            "foot_force_1": 3.0,
            "foot_force_2": 30.0,
            "foot_force_3": 3.0,
            **{f"foot_speed_body_{axis}": 0.04 for axis in range(12)},
        },
        {"aligned_time": 0.2, "mode": "walk", "gait_type": 1},
    ]
    timeseries, report = build_contact_state_v2(rows, _threshold_report())
    assert timeseries[0]["contact_label_v2"] == "standing_contact"
    assert timeseries[1]["contact_label_v2"] == "walking_contact"
    assert timeseries[2]["contact_label_v2"] == "invalid"
    assert report["go2_velocity_prior_enabled"] is False
    assert report["trace_solver_input"] is False
