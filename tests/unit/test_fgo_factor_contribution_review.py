"""中文说明：测试 N8C factor contribution 分类。"""

from legsa_gins.fgo.fgo_factor_contribution_review import review_factor_contributions


def test_factor_contribution_flags_raw_doppler_no_direct_residual() -> None:
    report = review_factor_contributions(
        ablation_summary={
            "variants": [
                {"variant": "default_active_stack_n8a2", "yaw_delta_wrapped_rmse_deg": 1.0, "horizontal_delta_rmse_m": 0.1},
                {"variant": "weak_yaw_smoothness", "yaw_delta_wrapped_rmse_deg": 0.3, "horizontal_delta_rmse_m": 0.1},
                {"variant": "go2_joint_off", "yaw_delta_wrapped_rmse_deg": 1.0, "horizontal_delta_rmse_m": 0.1},
                {"variant": "raw_doppler_off", "yaw_delta_wrapped_rmse_deg": 1.0, "horizontal_delta_rmse_m": 0.1},
            ]
        },
        factor_weight_review={"per_factor_residual_p95": {"SmoothnessFactor": 5.0, "Go2ProprioceptiveJointFactor": 1.0}},
        candidate_review={"candidate_factor_reviews": []},
    )
    assert "SmoothnessFactor" in report["influential_factors"]
    assert "RawDopplerVelocityFactor" in report["suspicious_no_effect_factors"]
    assert report["candidate_factors_diagnostic_only"]
