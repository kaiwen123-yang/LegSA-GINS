import csv
import math
from pathlib import Path

from legsa_gins.paper_rebuild.final_v23_clean_input import build_clean_a1_yaw_rows


FIELDS = (
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
)


def _write_status(
    path: Path, *, north: float, east: float = 0.0, seconds: tuple[int, ...] = (100, 101)
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for second in seconds:
            writer.writerow(
                {
                    "header.stamp.secs": second,
                    "header.stamp.nsecs": 0,
                    "rel_pos_n": north,
                    "rel_pos_e": east,
                    "rel_pos_d": 0.0,
                    "rel_acc_n": 0.01,
                    "rel_acc_e": 0.01,
                    "rel_acc_d": 0.01,
                    "rel_valid": "true",
                    "ant_valid": "true",
                    "ant_state": 2,
                }
            )


def test_clean_yaw_is_real_a1_status_without_noise(tmp_path: Path) -> None:
    gnss1 = tmp_path / "gnss1-status.csv"
    gnss2 = tmp_path / "gnss2-status.csv"
    _write_status(gnss1, north=0.0)
    _write_status(gnss2, north=0.35)

    rows, audit = build_clean_a1_yaw_rows(gnss1, gnss2, base_time=0.0)

    assert len(rows) == 2
    assert rows[0]["yaw_source"] == "A1_dual_diff_status"
    assert math.isclose(rows[0]["rel_n"], 0.35)
    assert math.isclose(rows[0]["yaw_ned_deg"], 90.0)
    assert rows[0]["yaw_std"] == 1.5
    assert audit["yaw_noise_injection_enabled"] is False
    assert audit["trace_used_online"] is False


def test_clean_yaw_uses_endpoint_hold_and_minus180_plus180_wrap(tmp_path: Path) -> None:
    gnss1 = tmp_path / "gnss1-status.csv"
    gnss2 = tmp_path / "gnss2-status.csv"
    _write_status(gnss1, north=0.0, seconds=(99, 100, 101, 102))
    _write_status(gnss2, north=-0.2, east=0.2, seconds=(100, 101))

    rows, audit = build_clean_a1_yaw_rows(gnss1, gnss2, base_time=0.0)

    assert len(rows) == 4
    assert rows[0]["rel_n"] == rows[1]["rel_n"] == -0.2
    assert rows[-1]["rel_e"] == rows[-2]["rel_e"] == 0.2
    assert all(-180.0 <= row["yaw_ned_deg"] < 180.0 for row in rows)
    assert math.isclose(rows[0]["yaw_ned_deg"], -135.0)
    assert audit["status2_to_status1_interpolation"] == "numpy_linear_with_endpoint_hold"
    assert audit["endpoint_hold_field_evaluation_count"] == 12
