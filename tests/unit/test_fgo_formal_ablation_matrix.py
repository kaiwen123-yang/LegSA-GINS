"""Tests for N8D formal ablation matrix.

中文说明：toy solver rerun 必须带 Raw Doppler residual/Jacobian 路径。
"""

from legsa_gins.fgo.fgo_formal_ablation_matrix import run_n8d_weight_policy_variants
from legsa_gins.fgo.fgo_factor_types import RawDopplerVelocityFactorRow


def test_n8d_formal_ablation_toy_runs_real_solver() -> None:
    ekf_rows = [
        {
            "index": i,
            "time": i * 0.2,
            "lat_deg": 30.0 + i * 1e-6,
            "lon_deg": 120.0,
            "height_m": 10.0,
            "roll_deg": 0.0,
            "pitch_deg": 0.0,
            "yaw_deg": float(i),
            "vn_mps": 1.0,
            "ve_mps": 0.0,
            "vd_mps": 0.0,
        }
        for i in range(4)
    ]
    raw = [RawDopplerVelocityFactorRow(state_index=i, time=i * 0.2, vn_mps=0.5, ve_mps=0.0, vd_mps=0.0) for i in range(4)]
    report, _ = run_n8d_weight_policy_variants(ekf_rows=ekf_rows, raw_factors=raw, variants=["n8b_weak_yaw_default", "no_raw_doppler_diagnostic"])
    assert report["all_variants_real_solver_rerun"]
    with_raw, without_raw = report["variants"]
    assert with_raw["jacobian_nonzero_count"] > without_raw["jacobian_nonzero_count"]
    assert not with_raw["trace_solver_input"]
