"""中文说明：N7B contact state 只产生 readiness label，不启用 prior。"""

from legsa_gins.go2_prior.go2_contact_state import build_contact_state


def test_go2_contact_state_labels_standing_and_walking():
    rows = [
        {
            "aligned_time": 0.0,
            "mode": "stand",
            "gait_type": 0,
            **{f"foot_force_{i}": 30.0 for i in range(4)},
            **{f"foot_speed_body_{i}": 0.01 for i in range(12)},
        },
        {
            "aligned_time": 0.1,
            "mode": "walk",
            "gait_type": 1,
            "foot_force_0": 30.0,
            "foot_force_1": 2.0,
            "foot_force_2": 30.0,
            "foot_force_3": 2.0,
            **{f"foot_speed_body_{i}": 0.05 for i in range(12)},
        },
    ]
    timeseries, report = build_contact_state(rows)
    assert timeseries[0]["contact_label"] == "standing_contact"
    assert timeseries[1]["contact_label"] == "walking_contact"
    assert report["contact_rows"] == 2
    assert report["go2_contact_prior_enabled"] is False
    assert report["trace_solver_input"] is False
