import csv

from legsa_gins.raw_gnss.raw_doppler_velocity_comparison import compare_raw_doppler_velocity_to_receiver_velocity


def _write_factor(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "vn", "ve", "vd"])
        writer.writeheader()
        writer.writerows(rows)


def test_detects_possible_receiver_velocity_copy(tmp_path):
    # 中文说明：如果 raw Doppler 与 .gnss velocity 完全相同，需要标记来源可疑。
    factor = tmp_path / "factor.csv"
    gnss = tmp_path / "clean.gnss"
    _write_factor(factor, [{"time": 1, "vn": 2, "ve": 3, "vd": 4}])
    gnss.write_text("1 0 0 0 0 0 0 2 3 4 0 0 0 0 0\n", encoding="utf-8")
    report = compare_raw_doppler_velocity_to_receiver_velocity(factor, gnss)
    assert report["aligned_count"] == 1
    assert report["possible_pvt_velocity_copy_suspect"] is True
    assert report["raw_doppler_not_nav_pvt"] is True
    assert report["raw_doppler_not_gnss_15col"] is True


def test_distinguishes_raw_doppler_factor_source(tmp_path):
    factor = tmp_path / "factor.csv"
    gnss = tmp_path / "clean.gnss"
    _write_factor(factor, [{"time": 1, "vn": 2.5, "ve": 2.0, "vd": 3.0}])
    gnss.write_text("1 0 0 0 0 0 0 2 3 4 0 0 0 0 0\n", encoding="utf-8")
    report = compare_raw_doppler_velocity_to_receiver_velocity(factor, gnss)
    assert report["possible_pvt_velocity_copy_suspect"] is False
    assert report["horizontal_velocity_diff_rmse"] > 0
