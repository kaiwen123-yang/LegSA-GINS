from legsa_gins.source_aware.source_aware_policy_diagnostics import clean_neutrality_gate, r_scale_gate


def test_clean_neutrality_gate_passes_within_limits():
    # 中文说明：clean neutrality gate 只判断报告 delta，不修改算法。
    report = clean_neutrality_gate(
        {
            "horizontal_rmse_m": 0.01,
            "up_rmse_m": 0.02,
            "yaw_rmse_deg": 0.03,
            "roll_rmse_deg": 0.01,
            "pitch_rmse_deg": 0.01,
        }
    )
    assert report["pass"] is True


def test_r_scale_gate_rejects_cap_slam():
    report = r_scale_gate(
        {
            "stats_by_source": {
                "receiver_position": {"R_scale_p50": 25.0, "R_scale_p95": 25.0},
                "receiver_velocity": {"R_scale_p50": 1.0, "R_scale_p95": 1.0},
                "raw_doppler_velocity": {"R_scale_p50": 1.0, "R_scale_p95": 1.0},
            }
        }
    )
    assert report["pass"] is False
