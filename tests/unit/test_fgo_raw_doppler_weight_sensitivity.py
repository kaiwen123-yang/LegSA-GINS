"""Tests for N8C2 raw Doppler weight sensitivity reruns.

中文说明：验证权重敏感性矩阵是真实 no-feedback solver 重跑。
"""

from legsa_gins.fgo.fgo_raw_doppler_weight_sensitivity import RAW_DOPPLER_SENSITIVITY_VARIANTS, run_raw_doppler_weight_sensitivity


def test_raw_doppler_weight_sensitivity_runs_required_variants() -> None:
    rows = [
        {"index": i, "time": float(i), "lat_deg": 30.0 + i * 1e-6, "lon_deg": 120.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": float(i), "vn_mps": 1.0 + i * 0.01, "ve_mps": 0.1, "vd_mps": 0.0}
        for i in range(6)
    ]
    report, rows_by_variant = run_raw_doppler_weight_sensitivity(ekf_rows=rows)
    assert report["all_required_variants_run"]
    assert sorted(rows_by_variant) == sorted(RAW_DOPPLER_SENSITIVITY_VARIANTS)
    assert report["all_variants_real_solver_rerun"]
    assert not report["trace_weight_tuning"]
