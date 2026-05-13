"""中文说明：单元测试覆盖 N7C4 水平速度 prior 强度 CSV 构造。"""

from legsa_gins.go2_prior.go2_horizontal_velocity_strength_calibration import build_strength_prior_rows


def test_strength_calibration_fixed_and_adaptive_policies():
    source = [{"time": 0.0, "vn": 1.0, "ve": 0.0}, {"time": 0.1, "vn": 1.0, "ve": 0.0}]
    confidence = [
        {"time": 0.0, "confidence": 0.9, "confidence_level": "high"},
        {"time": 0.1, "confidence": 0.05, "confidence_level": "invalid"},
    ]
    fixed = build_strength_prior_rows(source_prior_rows=source, confidence_rows=confidence, policy_name="fixed_std_1p0")
    adaptive = build_strength_prior_rows(source_prior_rows=source, confidence_rows=confidence, policy_name="recalibrated_adaptive")
    assert {float(row["std_vn"]) for row in fixed} == {1.0}
    assert fixed[1]["update_flag"] == "true"
    assert float(adaptive[0]["std_vn"]) == 1.0
    assert adaptive[1]["update_flag"] == "false"
    assert float(adaptive[1]["std_vd"]) == 999.0
