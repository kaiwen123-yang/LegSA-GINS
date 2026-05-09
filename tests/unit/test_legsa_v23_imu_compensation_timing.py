import csv

from legsa_gins.evaluation.legsa_v23_imu_compensation_timing import analyze_imu_compensation_timing


# 中文说明：用 toy trace 覆盖重复补偿、补偿未持久化和 res=3 插值补偿风险。
def test_detects_repeated_compensation_and_res3_issue(tmp_path):
    path = tmp_path / "IMU_COMPENSATION_TRACE.csv"
    fields = [
        "propagation_index",
        "imu_time",
        "imu_dt",
        "dtheta_norm_before",
        "dtheta_norm_after",
        "dvel_norm_before",
        "dvel_norm_after",
        "gyrbias_norm",
        "accbias_norm",
        "gyrscale_norm",
        "accscale_norm",
        "compensation_applied",
        "compensation_count_for_current_imu",
        "repeated_compensation_detected",
        "imupre_compensated",
        "imucur_compensated",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "propagation_index": 1,
                "imu_time": 1.0,
                "imu_dt": 0.01,
                "dtheta_norm_before": 0.1,
                "dtheta_norm_after": 0.1,
                "dvel_norm_before": 1.0,
                "dvel_norm_after": 1.0,
                "compensation_applied": "true",
                "compensation_count_for_current_imu": 2,
                "repeated_compensation_detected": "true",
                "imupre_compensated": "false",
                "imucur_compensated": "true",
            }
        )
        writer.writerow(
            {
                "propagation_index": 2,
                "imu_time": 1.5,
                "imu_dt": 0.005,
                "dtheta_norm_before": 0.1,
                "dtheta_norm_after": 0.1,
                "dvel_norm_before": 1.0,
                "dvel_norm_after": 1.0,
                "compensation_applied": "false",
                "compensation_count_for_current_imu": 0,
                "repeated_compensation_detected": "false",
                "imupre_compensated": "false",
                "imucur_compensated": "false",
            }
        )
    report = analyze_imu_compensation_timing(path)
    assert report["repeated_compensation_detected"] is True
    assert report["compensation_not_persistent_issue"] is True
    assert report["res3_interpolation_compensation_issue"] is True
