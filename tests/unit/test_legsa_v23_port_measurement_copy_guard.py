"""中文说明：测试 NAV/EVAL_NAV 是否被 clean GNSS 逐行复制。"""

from pathlib import Path

from legsa_gins.evaluation.legsa_v23_port_measurement_copy_guard import analyze_measurement_copy


def _write_gnss(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "1.00 30.0 120.0 10.0 0.5 0.5 0.8 0 0 0 0.1 0.1 0.1 5.0 1.0",
                "2.00 30.0 120.0 10.0 0.5 0.5 0.8 0 0 0 0.1 0.1 0.1 5.0 1.0",
                "3.00 30.0 120.0 10.0 0.5 0.5 0.8 0 0 0 0.1 0.1 0.1 5.0 1.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_detects_nav_copied_from_gnss(tmp_path):
    gnss = tmp_path / "clean.gnss"
    nav = tmp_path / "nav.nav"
    eval_nav = tmp_path / "eval.csv"
    _write_gnss(gnss)
    nav.write_text(
        "# time lat_deg lon_deg height_m vn ve vd roll_deg pitch_deg yaw_deg\n"
        "1.00 30.0 120.0 10.0 0 0 0 0 0 5.0\n"
        "2.00 30.0 120.0 10.0 0 0 0 0 0 5.0\n"
        "3.00 30.0 120.0 10.0 0 0 0 0 0 5.0\n",
        encoding="utf-8",
    )
    eval_nav.write_text(
        "time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg\n"
        "1.00,30.0,120.0,10.0,0,0,0,0,0,5.0\n"
        "2.00,30.0,120.0,10.0,0,0,0,0,0,5.0\n"
        "3.00,30.0,120.0,10.0,0,0,0,0,0,5.0\n",
        encoding="utf-8",
    )
    report = analyze_measurement_copy(nav, eval_nav, gnss)
    assert report["measurement_copy_suspect"] is True


def test_non_copy_case_passes(tmp_path):
    gnss = tmp_path / "clean.gnss"
    nav = tmp_path / "nav.nav"
    eval_nav = tmp_path / "eval.csv"
    _write_gnss(gnss)
    nav.write_text(
        "# time lat_deg lon_deg height_m vn ve vd roll_deg pitch_deg yaw_deg\n"
        "1.00 30.00001 120.0 10.5 0 0 0 0 0 5.8\n",
        encoding="utf-8",
    )
    eval_nav.write_text(
        "time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg\n"
        "1.00,30.00001,120.0,10.5,0,0,0,0,0,5.8\n",
        encoding="utf-8",
    )
    report = analyze_measurement_copy(nav, eval_nav, gnss)
    assert report["measurement_copy_suspect"] is False
