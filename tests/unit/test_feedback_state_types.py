"""中文说明：单测 feedback state type、角度 wrap 和 CSV 行合同。"""

from legsa_gins.fgo_feedback.feedback_state_types import (
    FeedbackGateThresholds,
    FeedbackObservation,
    angle_delta_deg,
    wrap_degrees,
)


def test_angle_wrap_and_observation_row():
    assert wrap_degrees(181.0) == -179.0
    assert angle_delta_deg(1.0, 359.0) == 2.0
    obs = FeedbackObservation(
        time=1.0,
        pN=0.0,
        pE=0.0,
        pD=0.0,
        vN=1.0,
        vE=0.0,
        vD=0.0,
        roll=0.0,
        pitch=0.0,
        yaw=1.0,
        std_pN=3.0,
        std_pE=3.0,
        std_pD=4.0,
        std_vN=0.5,
        std_vE=0.5,
        std_vD=0.8,
        std_roll=2.0,
        std_pitch=2.0,
        std_yaw=3.0,
        source_window_start=0.0,
        source_window_end=1.0,
        feedback_valid=True,
        window_epoch_count=5,
        feedback_mode="velocity_attitude_feedback",
    )
    assert obs.to_csv_row()["feedback_valid"] == "1"
    assert FeedbackGateThresholds().max_velocity_correction_mps > 0
