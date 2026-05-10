import csv

from legsa_gins.raw_gnss.raw_doppler_time_alignment import analyze_factor_time_alignment


def _factor(path, times):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time"])
        writer.writeheader()
        for time in times:
            writer.writerow({"time": time})


def test_alignment_ok(tmp_path):
    # 中文说明：时间对齐只检查 factor 与 clean GNSS/IMU overlap，不用 trace 调参。
    factor = tmp_path / "factor.csv"
    _factor(factor, [1, 2, 3])
    report = analyze_factor_time_alignment(factor, [1, 2, 3], [1, 2, 3], {"raw_doppler_update_count": 3}, tolerance=0.08)
    assert report["update_alignment_ok"] is True
    assert report["actual_update_count"] == 3


def test_alignment_mismatch(tmp_path):
    factor = tmp_path / "factor.csv"
    _factor(factor, [10, 20])
    report = analyze_factor_time_alignment(factor, [1, 2], [1, 2], {"raw_doppler_update_count": 0}, tolerance=0.08)
    assert report["update_alignment_ok"] is False
    assert report["recommended_tolerance_if_not_ok"] is not None
