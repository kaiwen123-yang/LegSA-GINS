from legsa_gins.raw_gnss.raw_doppler_ablation_evaluator import compare_variants


def test_compare_variants_computes_deltas_and_diagnostic_labels():
    # 中文说明：delta 标签只用于诊断，不产生 paper performance claim。
    reports = [
        {"variant_id": "baseline_full", "summary": {"horizontal_rmse_m": 1.0, "up_rmse_m": 1.0, "yaw_rmse_deg": 1.0}, "raw_doppler_update_count": 0},
        {"variant_id": "baseline_plus_raw_doppler_r1", "summary": {"horizontal_rmse_m": 0.9, "up_rmse_m": 1.0, "yaw_rmse_deg": 1.0}, "raw_doppler_update_count": 3, "raw_doppler_reject_count": 0},
        {"variant_id": "position_yaw_only", "summary": {"horizontal_rmse_m": 2.0, "up_rmse_m": 1.0, "yaw_rmse_deg": 1.0}, "raw_doppler_update_count": 0},
        {"variant_id": "position_yaw_plus_raw_doppler_r1", "summary": {"horizontal_rmse_m": 1.8, "up_rmse_m": 1.0, "yaw_rmse_deg": 1.0}, "raw_doppler_update_count": 3},
    ]
    report = compare_variants(reports)
    assert report["delta_baseline_plus_raw_doppler_minus_baseline"]["horizontal_rmse_m"] < 0
    assert report["velocity_isolation_delta"]["horizontal_rmse_m"] < 0
    assert report["raw_doppler_activation_consistent"] is True
    assert report["paper_performance_claim"] is False
