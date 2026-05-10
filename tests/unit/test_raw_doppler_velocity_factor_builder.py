import csv
from pathlib import Path

from legsa_gins.raw_gnss.raw_doppler_velocity_factor_builder import build_factor_file_from_provider


# 中文说明：factor builder 拒绝 NAV-PVT/.gnss 速度来源，只接受 provider velocity。


def _provider_csv(path: Path, time: str = "100.0") -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "time",
                "vn",
                "ve",
                "vd",
                "std_vn",
                "std_ve",
                "std_vd",
                "sat_count",
                "doppler_obs_count",
                "gdop_like",
                "provider_status",
                "source_epoch_time",
                "quality_flag",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "time": time,
                "vn": "0.1",
                "ve": "0.0",
                "vd": "0.0",
                "std_vn": "0.2",
                "std_ve": "0.2",
                "std_vd": "0.2",
                "sat_count": "8",
                "doppler_obs_count": "8",
                "gdop_like": "0.5",
                "provider_status": "available",
                "source_epoch_time": time,
                "quality_flag": "toy",
            }
        )
    return path


def test_factor_builder_rejects_forbidden_sources(tmp_path: Path):
    provider = _provider_csv(tmp_path / "provider.csv")
    assert build_factor_file_from_provider(provider, tmp_path / "a", source_type="nav_pvt_velocity")["factor_csv_generated"] is False
    assert build_factor_file_from_provider(provider, tmp_path / "b", source_type="gnss_15col_velocity")["factor_csv_generated"] is False


def test_factor_builder_aligns_to_clean_time(tmp_path: Path):
    provider = _provider_csv(tmp_path / "provider.csv", time="100.0")
    clean = tmp_path / "clean.gnss"
    clean.write_text("1.0 30.0 120.0 10.0 9 8 7\n2.0 30.0 120.0 10.0 9 8 7\n", encoding="utf-8")
    report = build_factor_file_from_provider(provider, tmp_path / "out", clean_gnss_path=clean)
    assert report["factor_csv_generated"] is True
    assert report["time_alignment_policy"] == "first_epoch_offset_to_clean_gnss_time_only"
