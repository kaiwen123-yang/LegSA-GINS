import pytest

from legsa_gins.writers.eval_nav_writer import write_eval_nav, validate_eval_nav_file


def _row(timestamp):
    return {
        "timestamp": timestamp,
        "lat_deg": 30.0,
        "lon_deg": 120.0,
        "height_m": 10.0,
        "vn_mps": 0.1,
        "ve_mps": 0.2,
        "vd_mps": -0.3,
        "roll_deg": 1.0,
        "pitch_deg": 2.0,
        "yaw_deg": 90.0,
        "status": "valid",
        "source_role": "infrastructure",
    }


def test_writer_emits_valid_two_row_eval_nav(tmp_path):
    output = tmp_path / "nested" / "EVAL_NAV.csv"

    write_eval_nav([_row(1.0), _row(2.0)], output)

    assert validate_eval_nav_file(output) is True


def test_writer_rejects_missing_fields(tmp_path):
    bad_row = _row(1.0)
    bad_row.pop("yaw_deg")

    with pytest.raises(ValueError, match="missing fields"):
        write_eval_nav([bad_row], tmp_path / "EVAL_NAV.csv")


def test_writer_rejects_non_monotonic_timestamps(tmp_path):
    with pytest.raises(ValueError, match="monotonically non-decreasing"):
        write_eval_nav([_row(2.0), _row(1.0)], tmp_path / "EVAL_NAV.csv")
