"""中文说明：gap screen 测试不产生 numerical performance claim。"""

from legsa_gins.evaluation.gap_screen import make_gap_screen


def test_gap_screen_recommends_n4h_for_severe_errors():
    report = make_gap_screen(
        summary={"horizontal_rmse_m": 100.0, "up_rmse_m": 20.0, "yaw_rmse_deg": 30.0},
        gate_report={"target_gate_pass": False, "ready_for_factor_stacking": False},
        event_report={"go2_time_domain": "UNIX_EPOCH_LIKE", "gnss_time_domain": "UNIX_EPOCH_LIKE", "evidence_status": "common_window_ready"},
        imu_report={"accel_contains_gravity": True, "quaternion_rpy_consistency_status": "passed"},
        imu_propagation_mode="gyro_only_zero_dvel",
        heading_offset_mode="plus90",
    )

    assert report["clock_sync_claim"] is False
    assert report["physical_time_offset_claim"] is False
    assert report["severe_horizontal_error"] is True
    assert report["recommended_next_stage"] == "N4H_full_kf_gins_style_ekf_reconstruction"

