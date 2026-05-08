"""中文说明：N4H4D toy clean replay 集成测试。"""

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TOY_ROOT = Path("/tmp/legsa_n4h4d_pytest_toy_clean")
TOY_DUAL = Path("/tmp/legsa_n4h4d_pytest_toy_dual")
TOY_OUT = Path("/tmp/legsa_n4h4d_pytest_toy_output")


def _write_toy_fixture():
    for path in [TOY_ROOT, TOY_DUAL, TOY_OUT]:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
    (TOY_ROOT / "CLEAN_STATUS_YAW.imu").write_text(
        "\n".join(f"{i * 0.01:.2f} 0 0 0 0 0 -0.0980665" for i in range(11)) + "\n",
        encoding="utf-8",
    )
    (TOY_ROOT / "CLEAN_STATUS_YAW.gnss").write_text(
        "\n".join(
            f"{i * 0.02:.2f} 31 121 10 1 1 1 0 0 0 0.1 0.1 0.1 10 1.5"
            for i in range(1, 6)
        )
        + "\n",
        encoding="utf-8",
    )
    (TOY_ROOT / "kf-gins-n4h2g-clean-replay.yaml").write_text(
        "starttime: 0\nendtime: 0.10\ninitpos: [31,121,10]\ninitvel: [0,0,0]\n"
        "initatt: [0,0,10]\ninitposstd: [1,1,1]\ninitvelstd: [0.1,0.1,0.1]\n"
        "initattstd: [1,1,1]\nantlever: [0,0,0]\n",
        encoding="utf-8",
    )
    (TOY_DUAL / "KF_GINS_Navresult.nav").write_text(
        "\n".join(f"0 {i * 0.01:.2f} 31 121 10 0 0 0 0 0 10" for i in range(1, 11)) + "\n",
        encoding="utf-8",
    )
    (TOY_DUAL / "error_series.csv").write_text(
        "timestamp,north_error_m,east_error_m,up_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"
        + "\n".join(f"{i * 0.01:.2f},0,0,0,0,0,0" for i in range(1, 11))
        + "\n",
        encoding="utf-8",
    )
    (TOY_DUAL / "summary.json").write_text(
        json.dumps(
            {
                "horizontal_rmse_m": 0,
                "up_rmse_m": 0,
                "yaw_rmse_deg": 0,
                "roll_rmse_deg": 0,
                "pitch_rmse_deg": 0,
                "count": 10,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_legsa_v23_clean_replay_toy_generates_report_and_gap_screen():
    _write_toy_fixture()
    for command in [["cmake", "-S", "cpp", "-B", "build/cpp"], ["cmake", "--build", "build/cpp"]]:
        result = subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_legsa_v23_clean_replay_parity.py",
            "--clean-root",
            str(TOY_ROOT),
            "--dual-root",
            str(TOY_DUAL),
            "--output-dir",
            str(TOY_OUT),
            "--exe",
            "./build/cpp/legsa_v23_core_demo",
            "--allow-run",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for filename in [
        "LEGSA_V23_CLEAN_REPLAY_SUMMARY.json",
        "LEGSA_V23_CLEAN_REPLAY_REPORT.json",
        "LEGSA_V23_CLEAN_REPLAY_GAP_SCREEN.json",
        "LEGSA_V23_CLEAN_REPLAY_DECISION.json",
    ]:
        assert (TOY_OUT / filename).is_file()
    report = json.loads((TOY_OUT / "LEGSA_V23_CLEAN_REPLAY_REPORT.json").read_text(encoding="utf-8"))
    assert report["trace_solver_input"] is False
    assert report["final_v23_output_substitution"] is False
    assert report["output_only_correction"] is False
