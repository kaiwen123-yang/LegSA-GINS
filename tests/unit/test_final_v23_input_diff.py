"""中文说明：15-column `.gnss` input diff 单元测试只比较 toy runtime input。"""

from pathlib import Path

from legsa_gins.evaluation.final_v23_input_diff import (
    compute_gnss_input_diff,
    nearest_align_by_time,
    parse_15col_gnss,
)


def _write_gnss(path: Path, *, yaw_offset: float) -> None:
    lines = []
    for index in range(12):
        values = [
            index * 0.1,
            30.0 + index * 1.0e-8,
            120.0 + index * 1.0e-8,
            5.0,
            0.02,
            0.02,
            0.03,
            0.1,
            0.2,
            -0.1,
            0.05,
            0.05,
            0.05,
            15.0 + yaw_offset,
            1.5,
        ]
        lines.append(" ".join(str(value) for value in values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_parse_15col_and_nearest_align(tmp_path: Path):
    actual = tmp_path / "actual.gnss"
    reconstructed = tmp_path / "reconstructed.gnss"
    _write_gnss(actual, yaw_offset=0.0)
    _write_gnss(reconstructed, yaw_offset=0.0)
    actual_rows = parse_15col_gnss(actual)
    reconstructed_rows = parse_15col_gnss(reconstructed)
    pairs = nearest_align_by_time(actual_rows, reconstructed_rows, tolerance=0.05)
    assert len(actual_rows) == 12
    assert len(pairs) == 12


def test_position_match_but_yaw_mismatch_status(tmp_path: Path):
    actual = tmp_path / "actual.gnss"
    reconstructed = tmp_path / "reconstructed.gnss"
    _write_gnss(actual, yaw_offset=90.0)
    _write_gnss(reconstructed, yaw_offset=0.0)
    report = compute_gnss_input_diff(parse_15col_gnss(actual), parse_15col_gnss(reconstructed))
    assert report["position_diff_rmse_m"] <= 0.1
    assert report["yaw_diff_rmse_deg"] > 10.0
    assert report["input_diff_status"] == "input_position_matched_but_yaw_mismatch"


def test_yaw_input_matched_status(tmp_path: Path):
    actual = tmp_path / "actual.gnss"
    reconstructed = tmp_path / "reconstructed.gnss"
    _write_gnss(actual, yaw_offset=1.0)
    _write_gnss(reconstructed, yaw_offset=0.0)
    report = compute_gnss_input_diff(parse_15col_gnss(actual), parse_15col_gnss(reconstructed))
    assert report["yaw_diff_rmse_deg"] <= 2.0
    assert report["input_diff_status"] == "yaw_input_matched"
