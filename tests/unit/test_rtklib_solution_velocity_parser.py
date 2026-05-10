from pathlib import Path

from legsa_gins.raw_gnss.rtklib_solution_velocity_parser import (
    ecef_velocity_to_ned,
    read_clean_gnss_position_and_times,
    reject_position_solution_as_factor,
)


# 中文说明：只读 clean GNSS 的时间/位置，不读取速度作为 raw Doppler。


def test_clean_gnss_position_reader_and_position_rejection(tmp_path: Path):
    gnss = tmp_path / "clean.gnss"
    gnss.write_text("1.0 30.0 120.0 10.0 9 8 7\n", encoding="utf-8")
    report = read_clean_gnss_position_and_times(gnss)
    assert report["position"]["lat_deg"] == 30.0
    assert report["times"] == [1.0]
    reject = reject_position_solution_as_factor(tmp_path / "diag.pos")
    assert reject["accepted_as_factor_input"] is False
    vn, ve, vd = ecef_velocity_to_ned(1.0, 0.0, 0.0, 0.0, 0.0)
    assert vd == -1.0
    assert vn == 0.0
    assert ve == 0.0
