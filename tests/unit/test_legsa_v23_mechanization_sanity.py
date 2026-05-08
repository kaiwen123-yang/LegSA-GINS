"""中文说明：N4H4D2 mechanization sanity 单元测试。"""

from pathlib import Path

from legsa_gins.evaluation.legsa_v23_mechanization_sanity import (
    analyze_imu_specific_force,
    analyze_short_propagation_debug,
)


def test_mechanization_sanity_detects_gravity_sign_issue(tmp_path: Path):
    imu = tmp_path / "bad.imu"
    imu.write_text("\n".join(f"{i * 0.01:.2f} 0 0 0 0 0 0.098" for i in range(20)) + "\n", encoding="utf-8")
    report = analyze_imu_specific_force(imu, {})
    assert report["gravity_sign_suspect"] is True


def test_long_only_free_ins_drift_not_immediate_bug(tmp_path: Path):
    csv_path = tmp_path / "FIRST_PROPAGATIONS.csv"
    csv_path.write_text(
        "time_cur,height_m,roll_deg,pitch_deg,yaw_deg,vel_n,vel_e,vel_d,cov_min_diag\n"
        "0.00,10,0,0,0,0,0,0,1\n"
        "0.50,10.2,0.1,0.1,0,0,0,0,1\n"
        "1.00,10.3,0.2,0.2,0,0,0,0,1\n",
        encoding="utf-8",
    )
    report = analyze_short_propagation_debug(csv_path)
    assert report["mechanization_immediate_jump"] is False
    assert report["free_ins_long_drift_only"] is True

