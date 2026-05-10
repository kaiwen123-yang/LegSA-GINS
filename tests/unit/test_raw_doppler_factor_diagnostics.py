import csv

from legsa_gins.raw_gnss.raw_doppler_factor_diagnostics import analyze_raw_doppler_factor_csv


def _write_factor(path, rows):
    fields = ["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "provider_status", "quality_flag"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_factor_diagnostics_detect_stats_and_spikes(tmp_path):
    # 中文说明：factor 诊断检查质量异常，不评价论文性能。
    path = tmp_path / "factor.csv"
    _write_factor(
        path,
        [
            {"time": 1, "vn": 0, "ve": 0, "vd": 0, "std_vn": 0.2, "std_ve": 0.2, "std_vd": 0.2, "sat_count": 7, "provider_status": "available", "quality_flag": "ok"},
            {"time": 2, "vn": 10, "ve": 0, "vd": 0, "std_vn": 8, "std_ve": 0.2, "std_vd": 0.2, "sat_count": 9, "provider_status": "available", "quality_flag": "ok"},
        ],
    )
    report = analyze_raw_doppler_factor_csv(path, clean_start=1, clean_end=2)
    assert report["epoch_count"] == 2
    assert report["valid_epoch_count"] == 2
    assert report["sat_count_min"] == 7
    assert report["sat_count_max"] == 9
    assert report["suspicious_velocity_spikes"] == 1
    assert report["suspicious_std_spikes"] == 1
    assert report["paper_performance_claim"] is False
