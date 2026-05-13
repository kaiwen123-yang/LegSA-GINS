"""中文说明：单元测试覆盖 Go2 水平速度置信度的保守组合策略。"""

from legsa_gins.go2_prior.go2_horizontal_velocity_confidence import build_go2_horizontal_velocity_confidence


def test_confidence_uses_conservative_components_without_truth_claims():
    prior = [{"time": 0.0, "vn": 1.0, "ve": 0.2, "vd": 0.0}]
    contact = [{
        "time": 0.0,
        "model_id": "ensemble_probability",
        "support_probability": 0.9,
        "confidence_score": 0.9,
        "uncertainty_probability": 0.1,
        "mode": "walk",
        "gait_type": "trot",
    }]
    frame = [{"time": 0.0, "horizontal_difference_mps": 0.05, "horizontal_angle_difference_deg": 2.0}]
    receiver = [{"time": 0.0, "vn": 1.0, "ve": 0.2, "vd": 0.0}]
    raw = [{"time": 0.0, "vn": 1.0, "ve": 0.2, "vd": 0.0}]
    rows, report = build_go2_horizontal_velocity_confidence(
        prior_rows=prior,
        contact_probability_rows=contact,
        contact_probability_report={"selected_contact_probability_model": "ensemble_probability"},
        frame_equivalence_rows=frame,
        frame_equivalence_report={"frame_equivalent_for_horizontal_only": True},
        receiver_velocity_rows=receiver,
        raw_doppler_rows=raw,
    )
    assert len(rows) == 1
    assert 0.0 <= rows[0]["confidence"] <= 1.0
    assert rows[0]["confidence_level"] in {"high", "medium", "low", "invalid"}
    assert rows[0]["no_truth_claim"] is True
    assert report["no_trace_tuning"] is True
    assert report["navigation_metric_feedback_tuning"] is False
