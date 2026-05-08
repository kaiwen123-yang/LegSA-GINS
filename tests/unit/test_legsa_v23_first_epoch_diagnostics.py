"""中文说明：N4H4D1 first-epoch diagnostics 单元测试。"""

from legsa_gins.evaluation.legsa_v23_first_epoch_diagnostics import analyze_first_epoch


def test_first_epoch_detects_yaw_residual_jump_and_covariance_issue():
    report = analyze_first_epoch(
        {"init": "ok"},
        {"first_imu_time": 0.0, "first_gnss_time": 0.01, "last_imu_time": 1.0, "first_imu_dtheta_norm": 0.0},
        [
            {
                "yaw_residual_deg": 120.0,
                "position_residual_n": 0.0,
                "position_residual_e": 0.0,
                "position_residual_d": 0.0,
                "dx_phi_norm_deg": 30.0,
            }
        ],
        [{"roll_deg": 60.0, "pitch_deg": 0.0, "cov_min_diag": -1.0, "cov_trace": 1.0}],
    )
    assert report["first_epoch_update_residual_issue"] is True
    assert report["first_epoch_mechanization_jump_issue"] is True
    assert report["first_epoch_feedback_jump_issue"] is True
    assert report["first_epoch_covariance_issue"] is True

