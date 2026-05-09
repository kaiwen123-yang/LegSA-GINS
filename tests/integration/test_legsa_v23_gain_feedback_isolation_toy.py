import json
import subprocess
import sys
from pathlib import Path


"""中文说明：D5 toy integration 只验证诊断报告生成和 forbidden flags。"""


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_toy(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "CLEAN_STATUS_YAW.imu").write_text(
        "\n".join(f"{i * 0.01:.2f} 0 0 0 0 0 -0.0980665" for i in range(80)) + "\n",
        encoding="utf-8",
    )
    (root / "CLEAN_STATUS_YAW.gnss").write_text(
        "\n".join(
            f"{time:.2f} 39.98482973 116.34312609 41.80208107 1 1 1 0 0 0 0.1 0.1 0.1 0.688505 1.5"
            for time in [0.01, 0.20, 0.40, 0.60]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "EXTERNAL_EVAL_NAV.csv").write_text(
        "time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg\n"
        + "\n".join(f"{i * 0.01:.2f},39.98482973,116.34312609,41.80208107,0,0,0,0,0,0.688505" for i in range(80))
        + "\n",
        encoding="utf-8",
    )


def test_gain_feedback_isolation_toy_pipeline(tmp_path: Path):
    clean = tmp_path / "clean"
    out = tmp_path / "out"
    _write_toy(clean)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_legsa_v23_gain_feedback_isolation.py",
            "--clean-root",
            str(clean),
            "--dual-root",
            str(clean),
            "--d4-root",
            str(tmp_path),
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
    decision = json.loads((out / "N4H4D5_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["shadow_external_nav_solver_input"] is False
    assert decision["numerical_performance_claim"] is False
    assert (out / "UPDATE_BLOCK_CONTRIBUTION_REPORT.json").exists()
