import os
from pathlib import Path

from legsa_gins.raw_gnss.rtklib_doppler_velocity_provider import run_rtklib_doppler_velocity_provider


# 中文说明：synthetic helper 输出 Doppler-derived ECEF velocity，provider 转为 NED factor。


def test_synthetic_helper_output_to_provider_csv(tmp_path: Path):
    helper = tmp_path / "helper.sh"
    helper.write_text(
        "#!/bin/sh\n"
        "cat > \"$3\" <<'EOF'\n"
        "time,vecef_x,vecef_y,vecef_z,std_vx,std_vy,std_vz,sat_count,doppler_obs_count,provider_status,source_epoch_time,quality_flag\n"
        "10.0,1.0,0.0,0.0,0.2,0.2,0.2,8,8,available,10.0,toy\n"
        "EOF\n",
        encoding="utf-8",
    )
    os.chmod(helper, 0o755)
    obs = tmp_path / "toy.obs"
    nav = tmp_path / "toy.nav"
    obs.write_text("obs", encoding="utf-8")
    nav.write_text("nav", encoding="utf-8")
    gnss = tmp_path / "clean.gnss"
    gnss.write_text("1.0 30.0 120.0 10.0 99 99 99\n", encoding="utf-8")
    report = run_rtklib_doppler_velocity_provider(
        obs_path=obs,
        nav_path=nav,
        helper_exe=helper,
        approx_position_source=gnss,
        output_dir=tmp_path,
    )
    assert report["factor_csv_generated"] is True
    assert report["factor_valid_epoch_count"] == 1
    assert report["gnss_velocity_used_as_raw_doppler"] is False
