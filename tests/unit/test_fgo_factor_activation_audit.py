"""Tests for N8C2 factor activation audit.

中文说明：验证 Raw Doppler 代理残差不会被误写成直接 solver 残差。
"""

from legsa_gins.fgo.fgo_factor_activation_audit import build_factor_activation_audit


def _rows() -> list[dict]:
    return [
        {"index": i, "time": float(i), "lat_deg": 30.0 + i * 1e-6, "lon_deg": 120.0, "height_m": 10.0, "roll_deg": 0.1 * i, "pitch_deg": 0.0, "yaw_deg": float(i), "vn_mps": 1.0, "ve_mps": 0.1, "vd_mps": 0.0}
        for i in range(5)
    ]


def test_activation_audit_separates_raw_doppler_proxy_from_direct_residual() -> None:
    ekf = _rows()
    fgo = [{**row, "vn_mps": row["vn_mps"] + 0.01, "yaw_deg": row["yaw_deg"] + 0.1} for row in ekf]
    report = build_factor_activation_audit(
        ekf_rows=ekf,
        rows_by_variant={"weak_yaw_smoothness": fgo},
        ablation_summary={"variants": [{"variant": "default_active_stack_n8a2"}, {"variant": "raw_doppler_off"}]},
        factor_weight_review={"per_factor_residual_p95": {"ReceiverVelocityFactor": 0.1, "SmoothnessFactor": 1.0, "Go2ProprioceptiveJointFactor": 0.1}},
    )
    raw = next(row for row in report["factor_activation_rows"] if row["factor_type"] == "RawDopplerVelocityFactor")
    assert raw["proxy_residual_evidence"]
    assert not raw["direct_solver_residual_evidence"]
    assert raw["contribution_status"] == "suspicious_no_effect"
    assert not report["trace_solver_input"]
