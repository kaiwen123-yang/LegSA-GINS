"""中文说明：runner 集成测试只使用 toy artifacts，不提交 runtime 输出。"""

import json
import subprocess
import sys
from pathlib import Path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_runner_with_toy_artifacts(tmp_path) -> None:
    root = Path(__file__).resolve().parents[2]
    external = tmp_path / "external" / "runs" / "nominal_none"
    n4h2 = tmp_path / "n4h2"
    out = tmp_path / "out"
    _write(
        external / "KF_GINS_Navresult.nav",
        "0 0 40 116 10 0 0 0 0 0 0\n0 1 40 116 10 0 0 0 0 0 0\n0 2 40 116 10 0 0 0 0 0 0\n",
    )
    _write(external / "KF_GINS_STD.txt", "std\n")
    _write(external / "input.gnss", "0 40 116 10 0 0 0 1 1 1 0 1 1 1 1\n")
    _write(
        external / "summary.json",
        '{"position":{"horizontal_rmse_m":0.0,"up_rmse_m":0.0},"attitude":{"roll_rmse_deg":0.0,"pitch_rmse_deg":0.0,"yaw_rmse_deg":0.0}}\n',
    )
    _write(
        external / "error_series.csv",
        "time,err_n_m,err_e_m,err_u_m,roll_err_deg,pitch_err_deg,yaw_err_deg\n0,0,0,0,0,0,0\n1,0,0,0,0,0,0\n2,0,0,0,0,0,0\n",
    )
    _write(
        n4h2 / "replay" / "standardized" / "FINAL_V23_EVAL_NAV.csv",
        "timestamp,lat_deg,lon_deg,height_m,vn_mps,ve_mps,vd_mps,roll_deg,pitch_deg,yaw_deg,status,source_role\n"
        "0,40,116,10,0,0,0,0,0,0,baseline,baseline\n"
        "1,40,116,10,0,0,0,0,0,0,baseline,baseline\n"
        "2,40,116,10,0,0,0,0,0,0,baseline,baseline\n",
    )
    _write(
        n4h2 / "replay" / "evaluation" / "FINAL_V23_TRACE_ERROR_SERIES.csv",
        "timestamp,reference_timestamp,dt,north_error_m,east_error_m,up_error_m,horizontal_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"
        "0,0,0,0,0,0,0,0,0,-90\n"
        "1,1,0,0,0,0,0,0,0,-90\n"
        "2,2,0,0,0,0,0,0,0,-90\n",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/experiments/run_official_final_v23_case_review_reproduction.py"),
            "--external-source-root",
            str(tmp_path / "external"),
            "--n4h2-artifacts-root",
            str(n4h2),
            "--dual-root",
            str(tmp_path / "missing_dual"),
            "--output-dir",
            str(out),
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    for name in [
        "OFFICIAL_CASE_REPRODUCTION_REPORT.json",
        "OFFICIAL_YAW_EVALUATOR_PARITY_REPORT.json",
        "OFFICIAL_ERROR_SERIES_PARITY_REPORT.json",
        "REPLAY_OFFICIAL_YAW_PARITY_REPORT.json",
        "N4R_DECISION_REPORT.json",
        "YAW_EVALUATOR_CONVENTION_POLICY_REPORT.json",
        "DUAL_FINAL_V23_ARTIFACT_RECOVERY_REPORT.json",
        "N4H2_REPLAY_PROFILE_REEVALUATION_REPORT.json",
        "N4R2_DECISION_REPORT.json",
        "DUAL_FINAL_V23_ARTIFACT_INTAKE_REPORT.json",
        "N4R3_DECISION_REPORT.json",
        "official_final_v23_case_review_reproduction.md",
    ]:
        assert (out / name).exists()
    decision = json.loads((out / "N4R_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["trace_solver_input"] is False
    assert decision["numerical_performance_claim"] is False
    n4r2 = json.loads((out / "N4R2_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert n4r2["solver_output_changed"] is False
    assert n4r2["evaluator_only"] is True
    assert n4r2["trace_solver_input"] is False
    n4r3 = json.loads((out / "N4R3_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert n4r3["solver_output_changed"] is False
    assert n4r3["evaluator_only"] is True
    assert n4r3["trace_solver_input"] is False
