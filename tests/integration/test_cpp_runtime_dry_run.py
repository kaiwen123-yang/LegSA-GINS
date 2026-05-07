"""中文说明：integration 测试验证输出链路和合同文件，不依赖真实 raw data，不代表性能评价。
"""

import csv
from pathlib import Path
import shutil
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

NAV_HEADER = [
    "gps_week",
    "tow",
    "lat_deg",
    "lon_deg",
    "height_m",
    "vn_mps",
    "ve_mps",
    "vd_mps",
    "roll_deg",
    "pitch_deg",
    "yaw_deg",
    "status",
    "source_role",
]

STD_HEADER = [
    "tow",
    "std_pos_n_m",
    "std_pos_e_m",
    "std_pos_d_m",
    "std_vel_n_mps",
    "std_vel_e_mps",
    "std_vel_d_mps",
    "std_roll_deg",
    "std_pitch_deg",
    "std_yaw_deg",
    "std_gyrbias_x_dph",
    "std_gyrbias_y_dph",
    "std_gyrbias_z_dph",
    "std_accbias_x_mgal",
    "std_accbias_y_mgal",
    "std_accbias_z_mgal",
    "std_gyrscale_x_ppm",
    "std_gyrscale_y_ppm",
    "std_gyrscale_z_ppm",
    "std_accscale_x_ppm",
    "std_accscale_y_ppm",
    "std_accscale_z_ppm",
]


def test_cpp_runtime_dry_run_outputs_contract_files(tmp_path):
    if shutil.which("cmake") is None:
        pytest.skip("cmake is not available on this machine")

    build_dir = tmp_path / "build" / "cpp"
    output_dir = tmp_path / "n3a_output"

    subprocess.run(
        ["cmake", "-S", str(REPO_ROOT / "cpp"), "-B", str(build_dir)],
        check=True,
        cwd=REPO_ROOT,
    )
    subprocess.run(["cmake", "--build", str(build_dir)], check=True, cwd=REPO_ROOT)
    subprocess.run(
        [
            str(build_dir / "legsa_gins"),
            "--dry-run",
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    nav_path = output_dir / "LegSA_NAV.nav"
    std_path = output_dir / "LegSA_STD.csv"
    eval_nav_path = output_dir / "EVAL_NAV.csv"
    manifest_path = output_dir / "RUN_MANIFEST.json"

    assert nav_path.exists()
    assert std_path.exists()
    assert eval_nav_path.exists()
    assert manifest_path.exists()

    nav_lines = nav_path.read_text(encoding="utf-8").strip().splitlines()
    assert nav_lines[0].split() == NAV_HEADER
    assert len(nav_lines) >= 3
    for line in nav_lines[1:]:
        assert len(line.split()) == len(NAV_HEADER)

    with std_path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    assert rows[0] == STD_HEADER
    assert len(rows) >= 3
    for row in rows[1:]:
        assert len(row) == len(STD_HEADER)
