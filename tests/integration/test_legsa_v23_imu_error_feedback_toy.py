import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


# 中文说明：toy 输入只用于 runtime-only 集成测试，不提交为 clean replay artifact。
def _write_toy_inputs(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "CLEAN_STATUS_YAW.imu").write_text(
        "\n".join(f"{i * 0.01:.2f} 0 0 0 0 0 -0.0980665" for i in range(60)) + "\n",
        encoding="utf-8",
    )
    (root / "CLEAN_STATUS_YAW.gnss").write_text(
        "\n".join(
            f"{t:.2f} 39.98482973 116.34312609 41.80208107 1 1 1 0 0 0 0.1 0.1 0.1 0.688505 1.5"
            for t in [0.01, 0.20, 0.40]
        )
        + "\n",
        encoding="utf-8",
    )
    rows = ["time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg"]
    rows.extend(f"{i * 0.01:.2f},39.98482973,116.34312609,41.80208107,0,0,0,0,0,0.688505" for i in range(60))
    (root / "EXTERNAL_EVAL_NAV.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")


# 中文说明：集成测试确认 D6 pipeline 生成诊断报告和 debug trace，不做性能声明。
def test_d6_toy_pipeline_generates_reports(tmp_path):
    clean = tmp_path / "clean"
    out = tmp_path / "out"
    build = tmp_path / "build"
    _write_toy_inputs(clean)
    cmd = [
        sys.executable,
        "scripts/experiments/run_legsa_v23_imu_error_feedback_audit.py",
        "--clean-root",
        str(clean),
        "--dual-root",
        str(clean),
        "--d5-root",
        str(tmp_path),
        "--output-dir",
        str(out),
        "--build-dir",
        str(build),
        "--exe",
        str(build / "legsa_v23_core_demo"),
        "--allow-run",
    ]
    completed = subprocess.run(cmd, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr[-1000:] + completed.stdout[-1000:]
    assert (out / "N4H4D6_DECISION_REPORT.json").exists()
    assert (out / "debug" / "IMU_ERROR_FEEDBACK_TRACE.csv").exists()
    assert (out / "debug" / "IMU_COMPENSATION_TRACE.csv").exists()
