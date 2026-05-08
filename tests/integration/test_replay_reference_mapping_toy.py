"""中文说明：N4H2D integration test 只构造 toy official/replay artifacts。"""

import json
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_toy(tmp_path: Path) -> tuple[Path, Path]:
    dual = tmp_path / "dual"
    n4h2 = tmp_path / "n4h2"
    _write(dual / "KF_GINS_Navresult.nav", "0 0 40 116 10 0 0 0 0 0 10\n0 1 40 116 10 0 0 0 0 0 10\n")
    _write(
        dual / "error_series.csv",
        "time,err_n_m,err_e_m,err_u_m,roll_err_deg,pitch_err_deg,yaw_err_deg\n"
        "0,0,0,0,0,0,2\n"
        "1,0,0,0,0,0,2\n",
    )
    _write(
        dual / "summary.json",
        json.dumps({"position": {"horizontal_rmse_m": 0.0, "up_rmse_m": 0.0}, "attitude": {"roll_rmse_deg": 0.0, "pitch_rmse_deg": 0.0, "yaw_rmse_deg": 2.0}}),
    )
    _write(n4h2 / "replay" / "kfgins_output" / "KF_GINS_Navresult.nav", "0 0 40 116 10 0 0 0 0 0 10\n0 1 40 116 10 0 0 0 0 0 10\n")
    _write(n4h2 / "replay" / "evaluation" / "FINAL_V23_TRACE_EVAL_SUMMARY.json", json.dumps({"yaw_rmse_deg": 93.0, "horizontal_rmse_m": 0.0, "up_rmse_m": 0.0, "count": 2}))
    _write(n4h2 / "replay" / "N4H2_REPLAY_REPORT.json", json.dumps({"reference_role": "trace_evaluation_only"}))
    return dual, n4h2


def test_replay_reference_mapping_runner_toy(tmp_path) -> None:
    dual, n4h2 = _make_toy(tmp_path)
    out = tmp_path / "out"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/experiments/run_replay_reference_mapping_audit.py"),
            "--dual-root",
            str(dual),
            "--n4h2-artifacts-root",
            str(n4h2),
            "--output-dir",
            str(out),
        ],
        check=True,
        cwd=REPO_ROOT,
    )
    for name in [
        "OFFICIAL_REFERENCE_RECONSTRUCTION_REPORT.json",
        "ACTUAL_DUAL_SUMMARY_REPRODUCTION_REPORT.json",
        "FRESH_REPLAY_SUMMARY.json",
        "FRESH_REPLAY_EVALUATION_REPORT.json",
        "OLD_VS_FRESH_REPLAY_SUMMARY_REPORT.json",
        "SUMMARY_STALENESS_AUDIT_REPORT.json",
        "N4H2D_DECISION_REPORT.json",
        "n4h2d_replay_reference_mapping_audit.md",
    ]:
        assert (out / name).exists()
    decision = json.loads((out / "N4H2D_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["trace_solver_input"] is False
    assert decision["output_only_correction"] is False
    assert decision["solver_output_changed"] is False
    assert decision["numerical_performance_claim"] is False
    assert decision["old_summary_invalidated"] is True
