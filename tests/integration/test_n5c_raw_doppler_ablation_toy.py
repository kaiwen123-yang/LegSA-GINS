import csv

from legsa_gins.raw_gnss.raw_doppler_ablation_decision import make_n5c_decision
from legsa_gins.raw_gnss.raw_doppler_ablation_evaluator import compare_variants
from legsa_gins.raw_gnss.raw_doppler_ablation_matrix import build_n5c_ablation_matrix
from legsa_gins.raw_gnss.raw_doppler_factor_diagnostics import analyze_raw_doppler_factor_csv
from legsa_gins.raw_gnss.raw_doppler_time_alignment import analyze_factor_time_alignment
from legsa_gins.raw_gnss.raw_doppler_velocity_comparison import compare_raw_doppler_velocity_to_receiver_velocity


def test_n5c_toy_ablation_reports_generated(tmp_path):
    # 中文说明：toy 消融只验证报告链路和 claim flags，不代表真实数据性能。
    factor = tmp_path / "RAW_DOPPLER_VELOCITY_FACTORS.csv"
    with factor.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "provider_status", "quality_flag"])
        writer.writeheader()
        for idx in range(3):
            writer.writerow({"time": idx + 1, "vn": 1.0, "ve": 0.0, "vd": 0.0, "std_vn": 0.2, "std_ve": 0.2, "std_vd": 0.2, "sat_count": 8, "provider_status": "available", "quality_flag": "ok"})
    gnss = tmp_path / "clean.gnss"
    gnss.write_text("1 0 0 0 0 0 0 1.1 0 0 0 0 0 0 0\n2 0 0 0 0 0 0 1.1 0 0 0 0 0 0 0\n3 0 0 0 0 0 0 1.1 0 0 0 0 0 0 0\n", encoding="utf-8")
    matrix = build_n5c_ablation_matrix(factor, tmp_path)
    comparison = compare_variants(
        [
            {"variant_id": "baseline_full", "summary": {"horizontal_rmse_m": 1.0, "up_rmse_m": 1.0, "yaw_rmse_deg": 1.0}, "raw_doppler_update_count": 0},
            {"variant_id": "baseline_plus_raw_doppler_r1", "summary": {"horizontal_rmse_m": 1.0, "up_rmse_m": 1.0, "yaw_rmse_deg": 1.0}, "raw_doppler_update_count": 3},
            {"variant_id": "position_yaw_only", "summary": {"horizontal_rmse_m": 2.0, "up_rmse_m": 1.0, "yaw_rmse_deg": 1.0}, "raw_doppler_update_count": 0},
            {"variant_id": "position_yaw_plus_raw_doppler_r1", "summary": {"horizontal_rmse_m": 1.9, "up_rmse_m": 1.0, "yaw_rmse_deg": 1.0}, "raw_doppler_update_count": 3},
        ]
    )
    decision = make_n5c_decision(
        analyze_raw_doppler_factor_csv(factor),
        compare_raw_doppler_velocity_to_receiver_velocity(factor, gnss),
        analyze_factor_time_alignment(factor, [1, 2, 3], [1, 2, 3], {"raw_doppler_update_count": 3}),
        comparison,
    )
    assert matrix["variant_count"] == 7
    assert comparison["raw_doppler_update_count"] == 3
    assert decision["paper_performance_claim"] is False
