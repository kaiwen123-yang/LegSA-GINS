"""中文说明：N4H4D3 guarded formula fix toy integration 测试。"""

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_toy(root: Path, dual: Path, d2: Path) -> None:
    root.mkdir(parents=True)
    dual.mkdir(parents=True)
    d2.mkdir(parents=True)
    (root / "CLEAN_STATUS_YAW.imu").write_text(
        "\n".join(f"{i * 0.01:.2f} 0 0 0 0 0 -0.0980665" for i in range(21)) + "\n",
        encoding="utf-8",
    )
    (root / "CLEAN_STATUS_YAW.gnss").write_text(
        "\n".join(f"{i * 0.02:.2f} 31.0 121.0 10.0 1 1 1 0 0 0 0.1 0.1 0.1 10.0 1.5" for i in range(1, 10))
        + "\n",
        encoding="utf-8",
    )
    (root / "kf-gins-n4h2g-clean-replay.yaml").write_text(
        "starttime: 0.0\nendtime: 0.20\nimudatalen: 7\nimudatarate: 100\n"
        "initpos: [31.0, 121.0, 10.0]\ninitvel: [0.0, 0.0, 0.0]\ninitatt: [0.0, 0.0, 10.0]\n"
        "initposstd: [1.0, 1.0, 1.0]\ninitvelstd: [0.1, 0.1, 0.1]\n"
        "initattstd: [1.0, 1.0, 1.0]\nantlever: [0.0, 0.0, 0.0]\n",
        encoding="utf-8",
    )
    (dual / "KF_GINS_Navresult.nav").write_text(
        "\n".join(f"0 {i * 0.01:.2f} 31.0 121.0 10.0 0 0 0 0 0 10.0" for i in range(1, 21)) + "\n",
        encoding="utf-8",
    )
    (dual / "error_series.csv").write_text(
        "timestamp,north_error_m,east_error_m,up_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"
        + "\n".join(f"{i * 0.01:.2f},0,0,0,0,0,0" for i in range(1, 21))
        + "\n",
        encoding="utf-8",
    )
    (dual / "summary.json").write_text(
        json.dumps({"horizontal_rmse_m": 0, "up_rmse_m": 0, "yaw_rmse_deg": 0, "roll_rmse_deg": 0, "pitch_rmse_deg": 0, "count": 20})
        + "\n",
        encoding="utf-8",
    )
    (d2 / "UPDATE_FEEDBACK_VARIANT_MATRIX_REPORT.json").write_text(
        json.dumps({"variant_summaries": {"baseline_current": {"summary": {"horizontal_rmse_m": 10, "up_rmse_m": 10, "yaw_rmse_deg": 10, "roll_rmse_deg": 10, "pitch_rmse_deg": 10}}}})
        + "\n",
        encoding="utf-8",
    )


def test_guarded_formula_fix_toy_pipeline(tmp_path: Path):
    clean = tmp_path / "clean"
    dual = tmp_path / "dual"
    d2 = tmp_path / "d2"
    out = tmp_path / "out"
    _write_toy(clean, dual, d2)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_legsa_v23_guarded_formula_fix.py",
            "--clean-root",
            str(clean),
            "--dual-root",
            str(dual),
            "--d2-root",
            str(d2),
            "--output-dir",
            str(out),
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
    decision = json.loads((out / "N4H4D3_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["numerical_performance_claim"] is False
    assert (out / "GUARDED_FORMULA_FIX_AUDIT_REPORT.json").exists()

