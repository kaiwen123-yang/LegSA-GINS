"""Unit tests for N8F dataset builder helpers.

中文说明：检查状态向量顺序和时间轴读取。
"""

from legsa_gins.fgo.fgo_legged_factor_dataset_builder import epoch_times_from_rows, rows_to_vectors


def test_rows_to_vectors_preserves_state_order() -> None:
    rows = [
        {
            "index": 0,
            "time": 0.0,
            "lat_deg": 30.0,
            "lon_deg": 120.0,
            "height_m": 10.0,
            "roll_deg": 1.0,
            "pitch_deg": 2.0,
            "yaw_deg": 3.0,
            "vn_mps": 4.0,
            "ve_mps": 5.0,
            "vd_mps": 6.0,
        }
    ]
    assert epoch_times_from_rows(rows) == [0.0]
    assert rows_to_vectors(rows)[0] == [30.0, 120.0, 10.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
