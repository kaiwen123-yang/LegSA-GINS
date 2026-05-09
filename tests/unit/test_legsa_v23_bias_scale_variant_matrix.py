from legsa_gins.evaluation.legsa_v23_bias_scale_variant_matrix import classify_bias_scale_variant_matrix


def _summary(h, up=1.0, yaw=1.0, roll=1.0, pitch=1.0):
    return {
        "horizontal_rmse_m": h,
        "up_rmse_m": up,
        "yaw_rmse_deg": yaw,
        "roll_rmse_deg": roll,
        "pitch_rmse_deg": pitch,
    }


# 中文说明：variant matrix 只产生诊断嫌疑，不把改进 variant 写成性能结论。
def test_classifies_bias_scale_feedback_primary_suspect():
    report = classify_bias_scale_variant_matrix(
        {
            "normal": {"summary": _summary(100.0, roll=100.0)},
            "no_bias_scale_feedback": {"summary": _summary(10.0, roll=10.0)},
            "zero_phi_bias_scale_cross_cov": {"summary": _summary(90.0, roll=20.0)},
        }
    )
    assert report["bias_scale_feedback_primary_suspect"] is True
    assert report["cross_covariance_coupling_suspect"] is True
    assert report["diagnostic_only"] is True
