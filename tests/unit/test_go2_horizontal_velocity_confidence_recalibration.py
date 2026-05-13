"""中文说明：单元测试覆盖 N7C4 Go2 水平速度 confidence 重新校准策略。"""

from legsa_gins.go2_prior.go2_horizontal_velocity_confidence_recalibration import (
    build_go2_horizontal_velocity_recalibrated_confidence,
)


def test_recalibrated_confidence_can_promote_locally_consistent_rows():
    prior = [{"time": 0.0, "vn": 1.0, "ve": 0.2, "vd": 0.0}]
    contact = [{"time": 0.0, "model_id": "ensemble_probability", "support_probability": 0.8, "confidence_score": 0.8, "uncertainty_probability": 0.1, "mode": "walk", "gait_type": "trot"}]
    frame = [{"time": 0.0, "horizontal_difference_mps": 0.05, "horizontal_angle_difference_deg": 2.0}]
    receiver = [{"time": 0.0, "vn": 1.05, "ve": 0.2}]
    raw = [{"time": 0.0, "vn": 1.0, "ve": 0.25}]
    rows, report = build_go2_horizontal_velocity_recalibrated_confidence(
        prior_rows=prior,
        contact_probability_rows=contact,
        contact_probability_report={"selected_contact_probability_model": "ensemble_probability"},
        frame_equivalence_rows=frame,
        frame_equivalence_report={"frame_equivalent_for_horizontal_only": True},
        receiver_velocity_rows=receiver,
        raw_doppler_rows=raw,
        residual_rows=[{"time": 0.0, "residual_norm": 0.2, "normalized_innovation": 0.5}],
    )
    assert rows[0]["confidence_level"] == "high"
    assert report["confidence_counts"]["high"] == 1
    assert report["no_artificial_balancing"] is True
