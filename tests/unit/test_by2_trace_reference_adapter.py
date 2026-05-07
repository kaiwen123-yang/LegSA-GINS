"""中文说明：trace reference adapter 测试只验证 evaluation-only 字段，不把 trace 作为 solver input。
"""

import csv

from legsa_gins.datasets.by2.trace_reference_adapter import parse_trace_reference


def test_trace_reference_is_eval_only_and_preserves_values(tmp_path):
    path = tmp_path / "trace.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["time", "lat", "lon", "height", "yaw", "pitch", "roll"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "time": "1700000000",
                "lat": "30.0",
                "lon": "120.0",
                "height": "10.0",
                "yaw": "90.0",
                "pitch": "1.0",
                "roll": "2.0",
            }
        )

    rows = parse_trace_reference(path)

    assert rows[0]["trace_evaluation_only"] is True
    assert rows[0]["trace_solver_input"] is False
    assert rows[0]["lat_deg"] == 30.0
    assert rows[0]["yaw_deg"] == 90.0
