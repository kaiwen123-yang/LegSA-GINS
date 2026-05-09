from legsa_gins.evaluation.legsa_v23_d5_decision import classify_d5


"""中文说明：D5 decision 单测确认证据映射到 D6 next stage。"""


def test_d5_decision_prefers_one_step_mechanization_suspect():
    decision = classify_d5(
        {"one_step_mechanization_suspect": True},
        {},
        {},
        {},
        {},
    )
    assert decision["recommended_next_stage"] == "N4H4D6_mechanization_step_fix"
    assert decision["diagnostic_only"] is True


def test_d5_decision_maps_gain_or_r_scaling():
    decision = classify_d5(
        {"one_step_mechanization_suspect": False},
        {"feedback_applies_large_phi": True},
        {"gain_spike_drives_feedback": True},
        {},
        {},
    )
    assert decision["most_likely_issue"] == "covariance_or_measurement_noise_scaling"
    assert "feedback_applies_large_phi" in decision["blocking_issues"]


def test_d5_decision_maps_shadow_state_divergence():
    decision = classify_d5(
        {"one_step_mechanization_suspect": False},
        {},
        {},
        {},
        {"large_dx_caused_by_state_divergence": True},
    )
    assert decision["recommended_next_stage"] == "N4H4D6_mechanization_feedback_coupled_fix"
