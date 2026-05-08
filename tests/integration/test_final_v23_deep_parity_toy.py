"""中文说明：N4H2C toy integration 只验证 runner 产物和决策，不接触真实路径。"""

import json
from pathlib import Path
import subprocess
import sys


def _write_gnss(path: Path, *, yaw_offset: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for index in range(20):
        values = [
            float(index),
            30.0,
            120.0,
            5.0,
            0.02,
            0.02,
            0.03,
            0.1,
            0.2,
            -0.1,
            0.05,
            0.05,
            0.05,
            30.0 + yaw_offset,
            1.5,
        ]
        lines.append(" ".join(str(value) for value in values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_source(root: Path) -> None:
    (root / "bin").mkdir(parents=True)
    (root / "src").mkdir(parents=True)
    (root / "bin/process_data.py").write_text(
        "BASE_TIME=1772784000.0\nUSE_STATUS_YAW=True\nYAW_SIGN=1\n"
        "YAW_INSTALL_OFFSET_DEG=0\nAUTO_APPLY_BEST_INSTALL=False\nYAW_SOURCE_MODE='status'\n"
        "YAW_NOISE_STD_DEG=0.0\nOUTAGE_DURATION_SEC=0.0\nOUTLIER_RATIO_DEFAULT=0.0\n"
        "OUTLIER_MODE_DEFAULT='none'\nSTATUS_YAW_STD_MODE_DEFAULT='fixed_1p5'\n"
        "STATUS_FIXED_YAW_STD_DEG_DEFAULT=1.5\nYAW_STD_MODE_DEFAULT='fixed_1p5'\n"
        "IMU_INSTALL_ROLL_DEG_DEFAULT=-1.0\nIMU_INSTALL_PITCH_DEG_DEFAULT=0.0\n"
        "IMU_INSTALL_YAW_DEG_DEFAULT=0.0\nIMU_GNSS_TIME_OFFSET_SEC_DEFAULT=0.0\n"
        "yaw_source_mode='status_yaw'\nyaw_std_mode='fixed_1p5'\n"
        "# process_data.py --generate_both_gnss --yaw_source_mode status --outlier_mode none --yaw_noise_std_deg 0\n"
        "final_status_fixed1p5=True\n",
        encoding="utf-8",
    )
    (root / "src/gnssfileloader.cpp").write_text(
        "GnssFileLoader gnssdata.blh gnssdata.std gnssdata.vel gnssdata.vel_std "
        "gnssdata.yaw gnssdata.yaw_std\n",
        encoding="utf-8",
    )
    (root / "src/gi_engine.cpp").write_text(
        "newImuProcess isToUpdate imuInterpolate imuCompensate insPropagation "
        "EKFPredict EKFUpdate gnssUpdate stateFeedback H_gnssvel H_gnssyaw "
        "velocity update yaw update Phi Qd F_ G_ INSMech::insMech velUpdate posUpdate attUpdate\n",
        encoding="utf-8",
    )
    (root / "src/kf_gins.cpp").write_text("int main(){return 0;}\n", encoding="utf-8")


def test_runner_creates_reports_and_yaw_input_fix_decision(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    case_root = tmp_path / "case"
    artifacts_root = tmp_path / "artifacts"
    source_root = tmp_path / "external"
    out = tmp_path / "out"
    _write_gnss(case_root / "input.gnss", yaw_offset=90.0)
    _write_gnss(artifacts_root / "inputs/BY2_PROCESS_DATA_COMPAT.gnss", yaw_offset=0.0)
    (case_root / "KF_GINS_Navresult.nav").write_text("toy\n", encoding="utf-8")
    (case_root / "KF_GINS_STD.txt").write_text("toy\n", encoding="utf-8")
    (case_root / "summary.json").write_text('{"yaw_rmse_deg": 1.0}\n', encoding="utf-8")
    (case_root / "error_series.csv").write_text("time,yaw\n0,0\n", encoding="utf-8")
    summary = artifacts_root / "replay/evaluation/FINAL_V23_TRACE_EVAL_SUMMARY.json"
    summary.parent.mkdir(parents=True)
    summary.write_text('{"yaw_rmse_deg": 93.0}\n', encoding="utf-8")
    nav = artifacts_root / "replay/standardized/FINAL_V23_NAV.csv"
    nav.parent.mkdir(parents=True)
    nav.write_text(
        "gps_week,tow,lat_deg,lon_deg,height_m,vn_mps,ve_mps,vd_mps,roll_deg,pitch_deg,yaw_deg,status,source_role\n"
        + "\n".join(f"0,{i},0,0,0,0,0,0,0,0,30,baseline,baseline" for i in range(20))
        + "\n",
        encoding="utf-8",
    )
    error = artifacts_root / "replay/evaluation/FINAL_V23_TRACE_ERROR_SERIES.csv"
    error.write_text(
        "timestamp,reference_timestamp,dt,north_error_m,east_error_m,up_error_m,horizontal_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"
        + "\n".join(f"{i},{i},0,0,0,0,0,0,0,0" for i in range(20))
        + "\n",
        encoding="utf-8",
    )
    _write_source(source_root)

    subprocess.run(
        [
            sys.executable,
            str(root / "scripts/experiments/run_final_v23_deep_parity_audit.py"),
            "--final-v23-case-root",
            str(case_root),
            "--n4h2-artifacts-root",
            str(artifacts_root),
            "--external-source-root",
            str(source_root),
            "--output-dir",
            str(out),
        ],
        cwd=root,
        check=True,
    )
    for name in [
        "FINAL_V23_CASE_ROOT_PROBE.json",
        "FINAL_V23_ARTIFACT_RECOVERY_REPORT.json",
        "FINAL_V23_INPUT_DIFF_REPORT.json",
        "PROCESS_DATA_RUNTIME_PARAMETER_REPORT.json",
        "PROCESS_DATA_DEEP_AUDIT.json",
        "FINAL_V23_ENGINE_SOURCE_AUDIT.json",
        "YAW_INPUT_VARIANT_MATRIX_REPORT.json",
        "YAW_UPDATE_RUNTIME_AUDIT.json",
        "REPLAY_YAW_DIAGNOSTICS_REPORT.json",
        "KFGINS_CORE_FLOW_AUDIT.json",
        "LEGSA_KFGINS_FRAMEWORK_PARITY_MATRIX.json",
        "N4H2C_DECISION_REPORT.json",
        "n4h2c_yaw_config_parity_case_review.md",
    ]:
        assert (out / name).exists()
    decision = json.loads((out / "N4H2C_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["recommended_next_stage"] == "N4H2C_yaw_input_config_fix"
