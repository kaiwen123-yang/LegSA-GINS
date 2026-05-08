"""中文说明：N4H1 15-column final_v23 .gnss 输入审计单元测试。"""

import pytest

from legsa_gins.evaluation.final_v23_input_audit import (
    audit_position_source,
    audit_position_std_source,
    parse_final_v23_gnss_file,
)


def _write(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_parse_final_v23_gnss_file_and_source_match(tmp_path):
    gnss = tmp_path / "toy.gnss"
    _write(
        gnss,
        [
            "10 30.0 120.0 15.0 1.5 1.5 2.0 0.1 0.2 -0.1 0.05 0.05 0.05 315.0 1.5",
            "10.1 30.000001 120.000002 15.1 1.6 1.6 2.1 0.1 0.2 -0.1 0.05 0.05 0.05 315.0 1.5",
        ],
    )
    rows = parse_final_v23_gnss_file(gnss)
    assert rows[0]["time"] == 10.0
    assert rows[0]["yaw"] == 315.0

    status_rows = [
        {
            "time": "10.0",
            "pos_lat": "30.0",
            "pos_lon": "120.0",
            "pos_height": "15.0",
            "pos_acc_h": "1.5",
            "pos_acc_v": "2.0",
        },
        {
            "time": "10.1",
            "pos_lat": "30.000001",
            "pos_lon": "120.000002",
            "pos_height": "15.1",
            "pos_acc_h": "1.6",
            "pos_acc_v": "2.1",
        },
    ]
    assert audit_position_source(rows, status_rows)["position_source_status"] == "matched_gnss1_status"
    assert (
        audit_position_std_source(rows, status_rows)["position_std_source_status"]
        == "matched_pos_acc_h_pos_acc_v"
    )


def test_parse_final_v23_gnss_bad_column_count_and_time(tmp_path):
    bad_count = tmp_path / "bad_count.gnss"
    _write(bad_count, ["1 2 3"])
    with pytest.raises(ValueError, match="expected 15"):
        parse_final_v23_gnss_file(bad_count)

    bad_time = tmp_path / "bad_time.gnss"
    _write(
        bad_time,
        [
            "2 30 120 15 1 1 1 0 0 0 1 1 1 0 1",
            "1 30 120 15 1 1 1 0 0 0 1 1 1 0 1",
        ],
    )
    with pytest.raises(ValueError, match="monotonic"):
        parse_final_v23_gnss_file(bad_time)
