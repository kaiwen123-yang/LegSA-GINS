"""中文说明：status yaw 测试只验证 A1_dual_diff 输入重建，不使用 trace。"""

import csv
import math

from legsa_gins.input_generation.status_yaw_builder import (
    apply_status_valid_filter,
    apply_yaw_install_and_ned,
    build_a1_dual_diff_yaw_rows,
)


HEADER = [
    "header.stamp.secs",
    "header.stamp.nsecs",
    "rel_pos_n",
    "rel_pos_e",
    "rel_pos_d",
    "rel_acc_n",
    "rel_acc_e",
    "rel_acc_d",
    "rel_valid",
    "ant_valid",
    "ant_state",
]


def _write_status(path, receiver, base_time):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        for index in range(3):
            stamp = base_time + index * 0.1
            secs = int(stamp)
            nsecs = int(round((stamp - secs) * 1.0e9))
            if receiver == "gnss1":
                rel_n, rel_e = 0.0, 0.0
            else:
                rel_n, rel_e = 1.0 + index * 0.1, 1.0 + index * 0.1
            writer.writerow(
                {
                    "header.stamp.secs": secs,
                    "header.stamp.nsecs": nsecs,
                    "rel_pos_n": rel_n,
                    "rel_pos_e": rel_e,
                    "rel_pos_d": 0.0,
                    "rel_acc_n": 0.01,
                    "rel_acc_e": 0.01,
                    "rel_acc_d": 0.02,
                    "rel_valid": "true",
                    "ant_valid": "true",
                    "ant_state": 2,
                }
            )


def test_a1_dual_diff_yaw_and_ned_formula(tmp_path):
    base_time = 1772784000.0
    g1 = tmp_path / "gnss1-status.csv"
    g2 = tmp_path / "gnss2-status.csv"
    _write_status(g1, "gnss1", base_time)
    _write_status(g2, "gnss2", base_time)

    rows, audit = build_a1_dual_diff_yaw_rows(g1, g2, base_time=base_time)
    rows = apply_yaw_install_and_ned(rows, sign=1.0, offset_deg=0.0)

    assert audit["yaw_source"] == "A1_dual_diff_status"
    assert math.isclose(rows[0]["rel_n"], 1.0)
    assert math.isclose(rows[0]["rel_e"], 1.0)
    assert math.isclose(rows[0]["yaw_baseline_deg"], 315.0)
    assert math.isclose(rows[0]["yaw_ned_deg"], 135.0)


def test_valid_filter_rejects_invalid_rows():
    rows = [
        {"rel_valid": "true", "ant_valid": "true", "ant_state": "2"},
        {"rel_valid": "false", "ant_valid": "true", "ant_state": "2"},
        {"rel_valid": "true", "ant_valid": "false", "ant_state": "2"},
        {"rel_valid": "true", "ant_valid": "true", "ant_state": "1"},
    ]
    filtered, stats = apply_status_valid_filter(rows, "toy")

    assert filtered == [rows[0]]
    assert stats["rejected_rel_valid_count"] == 1
    assert stats["rejected_ant_valid_count"] == 1
    assert stats["rejected_ant_state_count"] == 1
