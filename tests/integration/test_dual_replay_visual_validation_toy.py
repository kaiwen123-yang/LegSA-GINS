"""中文说明：toy 集成测试只生成临时图像包，不提交图像。"""

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _nav_line(time: float, yaw: float) -> str:
    index = int(time - 100.0)
    return f"2234 {time:.1f} {30.0 + index * 1e-6:.10f} {120.0 + index * 1e-6:.10f} {50.0 + index * 0.01:.3f} 0.1 0 0 0.5 -0.2 {yaw:.3f}\n"


def _std_line(time: float) -> str:
    return " ".join(str(v) for v in [time, 0.4, 0.4, 0.5, 0.02, 0.02, 0.03, 0.5, 0.5, 0.8, 0.01, 0.01, 0.01, 1, 1, 1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]) + "\n"


def _gnss_line(time: float) -> str:
    index = int(time - 100.0)
    return " ".join(
        str(v)
        for v in [
            time,
            30.0 + index * 1e-6,
            120.0 + index * 1e-6,
            50.0 + index * 0.01,
            0.4,
            0.4,
            0.5,
            0.1,
            0,
            0,
            0.02,
            0.02,
            0.03,
            10.0,
            1.0,
        ]
    ) + "\n"


def test_dual_replay_visual_validation_toy(tmp_path):
    dual = tmp_path / "dual"
    n4h2 = tmp_path / "n4h2"
    out = tmp_path / "out"
    nav_lines = []
    replay_lines = []
    error_lines = ["timestamp,north_error_m,east_error_m,up_error_m,horizontal_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"]
    for i in range(35):
        time = 100.0 + i
        nav_lines.append(_nav_line(time, 10.0))
        replay_lines.append(_nav_line(time, 11.0))
        error_lines.append(f"{time:.1f},0,0,0,0,0,0,0\n")
    _write(dual / "KF_GINS_Navresult.nav", "".join(nav_lines))
    _write(dual / "KF_GINS_STD.txt", "".join(_std_line(100.0 + i) for i in range(35)))
    _write(dual / "input.gnss", "".join(_gnss_line(100.0 + i) for i in range(35)))
    _write(dual / "error_series.csv", "".join(error_lines))
    _write(dual / "summary.json", json.dumps({"count": 35, "horizontal_rmse_m": 0.0, "up_rmse_m": 0.0, "yaw_rmse_deg": 0.0, "roll_rmse_deg": 0.0, "pitch_rmse_deg": 0.0}))
    _write(n4h2 / "replay/kfgins_output/KF_GINS_Navresult.nav", "".join(replay_lines))
    _write(n4h2 / "replay/kfgins_output/KF_GINS_STD.txt", "".join(_std_line(100.0 + i) for i in range(35)))
    _write(n4h2 / "inputs/BY2_PROCESS_DATA_COMPAT.gnss", "".join(_gnss_line(100.0 + i) for i in range(35)))

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/experiments/run_dual_replay_visual_validation.py"),
            "--dual-root",
            str(dual),
            "--n4h2-artifacts-root",
            str(n4h2),
            "--output-dir",
            str(out),
            "--case-name",
            "toy",
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert (out / "01_trajectory/dual_replay_traj_truth_est.png").exists()
    assert (out / "02_position_errors/dual_replay_pos_horizontal.png").exists()
    assert (out / "04_attitude/dual_replay_yaw_error_deg.png").exists()
    assert (out / "08_summary_panels/dual_replay_summary_panel.png").exists()
    assert (out / "09_case_review/visual_case_review.md").exists()
    generated_names = "\n".join(str(path) for path in out.rglob("*"))
    assert "pure_ins" not in generated_names
    assert "single_antenna" not in generated_names
    assert "compare" not in generated_names
    report = json.loads((out / "VISUAL_VALIDATION_REPORT.json").read_text(encoding="utf-8"))
    assert report["manual_visual_review_required"]
    assert not report["solver_output_changed"]
