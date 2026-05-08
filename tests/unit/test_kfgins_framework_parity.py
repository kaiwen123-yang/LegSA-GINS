"""中文说明：framework parity 单元测试确认 LegSA 当前不是完整 KF-GINS flow。"""

from pathlib import Path

from legsa_gins.evaluation.kfgins_framework_parity import compare_legsa_to_kfgins_framework


def test_framework_parity_reports_missing_full_flow_items(tmp_path: Path):
    (tmp_path / "cpp/src/engine").mkdir(parents=True)
    (tmp_path / "cpp/src/engine/legsa_engine.cpp").write_text(
        "void addImuData() {}\nvoid addGnssData() {}\nvoid apply_measurement() {}\n",
        encoding="utf-8",
    )
    (tmp_path / "cpp/src/io").mkdir(parents=True)
    (tmp_path / "cpp/src/io/nav_writer.cpp").write_text(
        "LegSA_NAV.nav LegSA_STD.csv EVAL_NAV.csv\n",
        encoding="utf-8",
    )
    kfgins_flow = {
        "found_missing_matrix": {
            "newImuProcess": {"found": True},
            "F/G/Phi/Qd construction": {"found": True},
            "EKFPredict": {"found": True},
            "EKFUpdate": {"found": True},
        }
    }
    report = compare_legsa_to_kfgins_framework(kfgins_flow, tmp_path)
    assert "newImuProcess" in report["missing_in_legsa"]
    assert "F/G/Phi/Qd" in report["missing_in_legsa"]
    assert "input .gnss/.imu reader" in report["missing_in_legsa"]
    assert "NAV/STD/EVAL writer" in report["implemented_as_toy_only"]
