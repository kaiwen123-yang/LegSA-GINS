import csv

from legsa_gins.evaluation.legsa_v23_imu_error_feedback_audit import analyze_imu_error_feedback


# 中文说明：构造大 bias/scale dx，验证 D6 审计能识别 IMU 误差反馈过修正。
def test_detects_bias_and_scale_feedback_overcorrection(tmp_path):
    path = tmp_path / "IMU_ERROR_FEEDBACK_TRACE.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "update_index",
                "gnss_time",
                "dx_bg_norm",
                "dx_ba_norm",
                "dx_sg_norm",
                "dx_sa_norm",
                "gyrbias_norm_before",
                "accbias_norm_before",
                "gyrscale_norm_before",
                "accscale_norm_before",
                "gyrbias_norm_after",
                "accbias_norm_after",
                "gyrscale_norm_after",
                "accscale_norm_after",
                "bias_scale_feedback_applied",
                "attitude_feedback_applied",
                "pos_vel_feedback_applied",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "update_index": 1,
                "gnss_time": 1.0,
                "dx_bg_norm": 0.02,
                "dx_ba_norm": 0.1,
                "dx_sg_norm": 0.02,
                "dx_sa_norm": 0.03,
                "gyrbias_norm_before": 0.0,
                "accbias_norm_before": 0.0,
                "gyrscale_norm_before": 0.0,
                "accscale_norm_before": 0.0,
                "gyrbias_norm_after": 0.02,
                "accbias_norm_after": 0.1,
                "gyrscale_norm_after": 0.02,
                "accscale_norm_after": 0.03,
                "bias_scale_feedback_applied": "true",
                "attitude_feedback_applied": "true",
                "pos_vel_feedback_applied": "true",
            }
        )
    report = analyze_imu_error_feedback(path)
    assert report["bias_feedback_overcorrection"] is True
    assert report["scale_feedback_overcorrection"] is True
    assert report["bias_scale_feedback_primary_suspect"] is True
