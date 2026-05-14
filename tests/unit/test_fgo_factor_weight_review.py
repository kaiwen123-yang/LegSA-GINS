"""中文说明：测试 N8B factor weight review 输出。"""

from legsa_gins.fgo.fgo_factor_weight_review import review_factor_weights
from legsa_gins.fgo.fgo_policy_ablation_runner import run_n8b_policy_ablations
from legsa_gins.fgo.fgo_policy_grid import build_n8b_policy_grid


def test_factor_weight_review_reports_per_factor_p95() -> None:
    rows = [
        {"index": index, "time": float(index), "lat_deg": 30.0 + index * 1e-6, "lon_deg": 120.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": yaw, "vn_mps": 1.0, "ve_mps": 0.0, "vd_mps": 0.0}
        for index, yaw in enumerate([359.0, 1.0, 2.0, 3.0, 4.0])
    ]
    ablations, by_variant = run_n8b_policy_ablations(ekf_rows=rows, policy_grid=build_n8b_policy_grid())
    report = review_factor_weights(ekf_rows=rows, default_fgo_rows=by_variant["default_active_stack_n8a2"], ablation_summary=ablations)
    assert "SmoothnessFactor" in report["per_factor_residual_p95"]
    assert "DualYawFactor" in report["per_factor_residual_p95"]
    assert not report["trace_weight_tuning"]
