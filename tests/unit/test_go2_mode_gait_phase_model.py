"""中文说明：单元测试覆盖 N7C5 mode/gait phase 分类。"""

from legsa_gins.go2_prior.go2_mode_gait_phase_model import build_go2_mode_gait_phase_model, classify_phase


def test_mode_gait_phase_classifies_basic_segments():
    assert classify_phase({"mode": "walk", "gait_type": "trot", "go2_velocity_0": 0.0, "go2_velocity_1": 0.0, "go2_velocity_2": 0.0, "yaw_speed_radps": 0.0}, {"support_probability": 0.8})[0] == "standing"
    assert classify_phase({"mode": "walk", "gait_type": "trot", "go2_velocity_0": 0.4, "go2_velocity_1": 0.0, "go2_velocity_2": 0.0, "yaw_speed_radps": 0.0}, {"support_probability": 0.8})[0] == "walking"
    assert classify_phase({"mode": "walk", "gait_type": "trot", "go2_velocity_0": 0.1, "go2_velocity_1": 0.0, "go2_velocity_2": 0.0, "yaw_speed_radps": 0.5}, {"support_probability": 0.8})[0] == "turning"


def test_mode_gait_phase_model_report_is_diagnostic_only():
    rows, report = build_go2_mode_gait_phase_model(
        [{"time": 0.0, "aligned_time": 0.0, "mode": "walk", "gait_type": "trot", "go2_velocity_0": 0.4, "go2_velocity_1": 0.0, "go2_velocity_2": 0.0, "yaw_speed_radps": 0.0, "body_height": 0.32}],
        [{"time": 0.0, "support_probability": 0.8}],
    )
    assert rows[0]["phase"] == "walking"
    assert report["factor_gating_ready"] is True
    assert report["not_truth"] is True
