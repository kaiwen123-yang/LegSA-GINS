"""中文说明：测试 N8A1 state/epoch 映射审计。"""

from legsa_gins.fgo.fgo_state_epoch_mapping_audit import audit_state_epoch_mapping


def test_state_count_interpreted_as_epoch_count() -> None:
    rows = [
        {"time": 0, "lat_deg": 30, "lon_deg": 120, "height_m": 10, "roll_deg": 0, "pitch_deg": 0, "yaw_deg": 0, "vn_mps": 1, "ve_mps": 0, "vd_mps": 0},
        {"time": 1, "lat_deg": 30, "lon_deg": 120, "height_m": 10, "roll_deg": 0, "pitch_deg": 0, "yaw_deg": 1, "vn_mps": 1, "ve_mps": 0, "vd_mps": 0},
    ]
    report = audit_state_epoch_mapping(ekf_rows=rows, fgo_rows=rows, dataset_report={"state_count": 2})
    assert report["state_count_interpretation"] == "epoch_count"
    assert report["state_dimension_per_epoch"] == 9
    assert report["variable_count"] == 18
    assert report["time_monotonic"] is True
