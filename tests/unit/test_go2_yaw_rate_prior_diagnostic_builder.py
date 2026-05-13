"""中文说明：yaw-rate diagnostic builder 不允许 formal activation。"""

from legsa_gins.go2_prior.go2_yaw_rate_prior_diagnostic_builder import build_go2_yaw_rate_diagnostic_prior


def test_yaw_rate_builder_marks_state_model_blocker(tmp_path):
    rows = [
        {"time": 0.0, "aligned_time": 0.0, "yaw_rad": 0.0, "yaw_speed_radps": 0.1},
        {"time": 0.1, "aligned_time": 0.1, "yaw_rad": 0.01, "yaw_speed_radps": 0.1},
    ]
    path, report = build_go2_yaw_rate_diagnostic_prior(go2_rows=rows, output_dir=tmp_path)
    assert path.exists()
    assert report["activation_status"] == "yaw_rate_prior_not_activated_due_to_state_model"
    assert report["formal_activation_allowed"] is False
