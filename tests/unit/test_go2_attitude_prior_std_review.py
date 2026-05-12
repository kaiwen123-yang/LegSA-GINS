"""中文说明：N7B2A review 说明 5 deg 是 measurement std，不是 gate。"""

from legsa_gins.go2_prior.go2_attitude_prior_std_review import review_go2_attitude_prior_std_policy


def test_attitude_prior_std_review_marks_5deg_as_measurement_uncertainty():
    report = review_go2_attitude_prior_std_policy(
        {
            "weak_prior_build": {"std_policy": {"std_roll_deg": 5.0, "std_pitch_deg": 5.0}},
            "quaternion_rpy": {"rpy_consistency_status": "passed", "activation_allowed_for_attitude_prior": True},
            "comparison": {"std_screen_summaries": [{"std_deg": 5.0, "summary": {"roll_rmse_deg": 0.04}}]},
        }
    )
    assert report["current_roll_pitch_std_deg"] == 5.0
    assert report["is_gate_or_threshold"] is False
    assert report["is_measurement_std"] is True
    assert report["go2_attitude_not_truth"] is True
    assert report["suggested_future_std_screen"] == [1.0, 1.6, 3.0, 5.0]
