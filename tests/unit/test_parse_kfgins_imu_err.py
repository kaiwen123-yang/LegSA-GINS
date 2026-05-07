"""中文说明：unit 测试验证小模块约定和边界，不做 numerical performance claim。
"""

import csv
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "baseline/final_v23_reproduction/scripts/parse_kfgins_imu_err.py"
spec = importlib.util.spec_from_file_location("parse_kfgins_imu_err", SCRIPT)
parse_kfgins_imu_err = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(parse_kfgins_imu_err)


TOY_IMU_ROW_1 = "100.0 0.01 0.01 0.01 1 1 1 0.1 0.1 0.1 0.1 0.1 0.1"
TOY_IMU_ROW_2 = "101.0 0.01 0.01 0.01 1 1 1 0.1 0.1 0.1 0.1 0.1 0.1"


def test_parse_kfgins_imu_err_and_write_csv(tmp_path):
    imu = tmp_path / "KF_GINS_IMU_ERR.txt"
    imu.write_text(f"{TOY_IMU_ROW_1}\n{TOY_IMU_ROW_2}\n", encoding="utf-8")
    rows = parse_kfgins_imu_err.parse_imu_err_file(imu)
    assert len(rows) == 2
    assert rows[0]["tow"] == 100.0
    assert rows[0]["gyrbias_x_dph"] == 0.01

    output = tmp_path / "FINAL_V23_IMU_ERR.csv"
    parse_kfgins_imu_err.write_imu_err_csv(rows, output)
    with output.open(newline="", encoding="utf-8") as handle:
        written = list(csv.DictReader(handle))
    assert len(written) == 2
    assert written[0]["accscale_z_ppm"] == "0.1"


def test_parse_kfgins_imu_err_rejects_bad_column_count(tmp_path):
    imu = tmp_path / "bad.txt"
    imu.write_text("100.0 0.01\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_kfgins_imu_err.parse_imu_err_file(imu)


def test_parse_kfgins_imu_err_rejects_nonmonotonic_tow(tmp_path):
    imu = tmp_path / "bad.txt"
    imu.write_text(f"{TOY_IMU_ROW_2}\n{TOY_IMU_ROW_1}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_kfgins_imu_err.parse_imu_err_file(imu)
