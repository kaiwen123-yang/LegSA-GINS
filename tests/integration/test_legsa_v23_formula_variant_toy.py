"""中文说明：N4H4D2 toy formula variant integration 测试。"""

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_n4h4d2_formula_variant_runner_without_matrix(tmp_path: Path):
    d1_root = tmp_path / "d1"
    debug = d1_root / "current" / "debug"
    debug.mkdir(parents=True)
    (debug / "INPUT_STREAM_SNAPSHOT.json").write_text('{"first_imu_dtheta_norm": 0, "first_imu_dvel_norm": 0}\n', encoding="utf-8")
    (debug / "FIRST_PROPAGATIONS.csv").write_text(
        "time_cur,height_m,roll_deg,pitch_deg,yaw_deg,vel_n,vel_e,vel_d,cov_min_diag\n0,10,0,0,0,0,0,0,1\n",
        encoding="utf-8",
    )
    (d1_root / "UPDATE_RESIDUAL_DIAGNOSTICS_REPORT.json").write_text('{"yaw_reject_ratio": 0.0}\n', encoding="utf-8")
    (d1_root / "N4H4D1_FAILURE_DECISION_REPORT.json").write_text("{}\n", encoding="utf-8")
    out = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_legsa_v23_formula_variant_audit.py",
            "--clean-root",
            str(tmp_path / "missing_clean"),
            "--dual-root",
            str(tmp_path / "missing_dual"),
            "--d1-root",
            str(d1_root),
            "--external-source-root",
            str(REPO_ROOT / "cpp"),
            "--reference-root",
            "reference/final_v23_repo",
            "--output-dir",
            str(out),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    decision = json.loads((out / "N4H4D2_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["diagnostic_only"] is True

