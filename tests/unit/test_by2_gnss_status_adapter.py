"""中文说明：BY2 GNSS status adapter 单元测试只使用 toy CSV，不读取真实 BY2，不代表性能评价。
"""

import csv
import math

import pytest

from legsa_gins.datasets.by2.gnss_status_adapter import parse_gnss_status_csv


HEADER = [
    "Time",
    "time_gps_wno",
    "time_gps_tow",
    "msg_valid",
    "pos_lat",
    "pos_lon",
    "pos_height",
    "pos_acc_h",
    "pos_acc_v",
    "pos_valid",
    "fix_ok",
    "fix_type",
    "rel_pos_n",
    "rel_pos_e",
    "rel_pos_d",
    "rel_acc_n",
    "rel_acc_e",
    "rel_acc_d",
    "rel_valid",
    "ant_valid",
]


def _write_status(path, rows, header=HEADER):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _row(tow="100.0", rel_n="1.0", rel_e="1.0"):
    return {
        "Time": "1700000000",
        "time_gps_wno": "2400",
        "time_gps_tow": tow,
        "msg_valid": "1",
        "pos_lat": "30.0",
        "pos_lon": "120.0",
        "pos_height": "10.0",
        "pos_acc_h": "0.5",
        "pos_acc_v": "0.8",
        "pos_valid": "1",
        "fix_ok": "1",
        "fix_type": "3",
        "rel_pos_n": rel_n,
        "rel_pos_e": rel_e,
        "rel_pos_d": "0.0",
        "rel_acc_n": "0.1",
        "rel_acc_e": "0.1",
        "rel_acc_d": "0.2",
        "rel_valid": "1",
        "ant_valid": "1",
    }


def test_parse_position_heading_and_has_position(tmp_path):
    path = tmp_path / "gnss1-status.csv"
    _write_status(path, [_row()])

    rows = parse_gnss_status_csv(path, source_name="gnss1")

    assert len(rows) == 1
    row = rows[0]
    assert row["has_position"] is True
    assert row["lat_deg"] == 30.0
    assert row["source_role"] == "receiver_native_gnss_status"
    assert row["heading_valid"] is True
    assert math.isclose(row["heading_deg"], 45.0)


def test_missing_required_field_raises(tmp_path):
    path = tmp_path / "gnss1-status.csv"
    reduced_header = [field for field in HEADER if field != "pos_lat"]
    row = _row()
    row.pop("pos_lat")
    _write_status(path, [row], header=reduced_header)

    with pytest.raises(ValueError, match="missing required"):
        parse_gnss_status_csv(path, source_name="gnss1")


def test_non_monotonic_tow_raises(tmp_path):
    path = tmp_path / "gnss1-status.csv"
    _write_status(path, [_row(tow="101.0"), _row(tow="100.0")])

    with pytest.raises(ValueError, match="monotonic"):
        parse_gnss_status_csv(path, source_name="gnss1")


def test_missing_relative_fields_keeps_position_without_heading(tmp_path):
    path = tmp_path / "gnss1-status.csv"
    header = [field for field in HEADER if not field.startswith("rel_") and field != "ant_valid"]
    row = {key: value for key, value in _row().items() if key in header}
    _write_status(path, [row], header=header)

    rows = parse_gnss_status_csv(path, source_name="gnss1")

    assert rows[0]["has_position"] is True
    assert rows[0]["heading_valid"] is False
