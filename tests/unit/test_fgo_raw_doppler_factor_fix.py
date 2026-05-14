"""Tests for N8C3 Raw Doppler factor fix variant runner.

中文说明：验证 N8C3 变体矩阵使用 direct Raw Doppler equation 重跑。
"""

from legsa_gins.fgo.fgo_factor_types import RawDopplerVelocityFactorRow
from legsa_gins.fgo.fgo_raw_doppler_factor_fix import N8C3_RAW_DOPPLER_VARIANTS, run_n8c3_raw_doppler_variants


def test_n8c3_variant_runner_runs_all_variants() -> None:
    rows = [
        {"index": index, "time": float(index), "lat_deg": 30.0, "lon_deg": 120.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": float(index), "vn_mps": 1.0, "ve_mps": 0.0, "vd_mps": 0.0}
        for index in range(4)
    ]
    factors = [RawDopplerVelocityFactorRow(state_index=index, time=float(index), vn_mps=0.5, ve_mps=0.0, vd_mps=0.0) for index in range(4)]
    report, rows_by_variant = run_n8c3_raw_doppler_variants(ekf_rows=rows, raw_factors=factors)
    assert report["all_required_variants_run"]
    assert sorted(rows_by_variant) == sorted(N8C3_RAW_DOPPLER_VARIANTS)
    assert report["raw_doppler_direct_equation_available"]
    assert not report["trace_weight_tuning"]
