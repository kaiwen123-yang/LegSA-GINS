"""中文说明：测试 N8A1 yaw delta 诊断摘要。"""

from legsa_gins.fgo.fgo_yaw_delta_diagnostics import diagnose_yaw_delta


def test_yaw_delta_diagnostics_reports_segments_and_hypothesis() -> None:
    ekf = [{"time": i, "yaw_deg": float(i)} for i in range(12)]
    fgo = [{"time": i, "yaw_deg": float(i + 2)} for i in range(12)]
    report = diagnose_yaw_delta(ekf_rows=ekf, fgo_rows=fgo)
    assert report["aligned_state_count"] == 12
    assert report["yaw_delta_rmse_wrapped_deg"] == 2.0
    assert report["segment_count"] > 0
    assert report["paper_performance_claim"] is False
