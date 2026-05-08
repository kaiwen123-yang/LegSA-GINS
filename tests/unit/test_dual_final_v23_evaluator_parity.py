"""中文说明：dual evaluator parity 测试只用 toy NAV/reference。"""

import json
from pathlib import Path

from legsa_gins.evaluation.dual_final_v23_evaluator_parity import evaluate_dual_final_v23_evaluator_parity


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_dual_toy(tmp_path):
    dual = tmp_path / "external" / "extended_degradation_results" / "final_v23" / "dual" / "E001_single_nominal_none"
    _write(
        dual / "KF_GINS_Navresult.nav",
        "0 0 40 116 10 0 0 0 0 0 0\n0 1 40 116 10 0 0 0 0 0 0\n",
    )
    _write(dual / "KF_GINS_STD.txt", "std\n")
    _write(dual / "input.gnss", "gnss\n")
    _write(
        dual / "summary.json",
        json.dumps(
            {
                "position": {"horizontal_rmse_m": 0.0, "up_rmse_m": 0.0},
                "attitude": {"roll_rmse_deg": 0.0, "pitch_rmse_deg": 0.0, "yaw_rmse_deg": 0.0},
            }
        )
        + "\n",
    )
    _write(
        dual / "error_series.csv",
        "time,err_n_m,err_e_m,err_u_m,roll_err_deg,pitch_err_deg,yaw_err_deg\n"
        "0,0,0,0,0,0,0\n1,0,0,0,0,0,0\n",
    )
    n4h2 = tmp_path / "n4h2"
    _write(
        n4h2 / "replay" / "standardized" / "FINAL_V23_EVAL_NAV.csv",
        "timestamp,lat_deg,lon_deg,height_m,vn_mps,ve_mps,vd_mps,roll_deg,pitch_deg,yaw_deg,status,source_role\n"
        "0,40,116,10,0,0,0,0,0,0,baseline,baseline\n"
        "1,40,116,10,0,0,0,0,0,0,baseline,baseline\n",
    )
    _write(
        n4h2 / "replay" / "evaluation" / "FINAL_V23_TRACE_ERROR_SERIES.csv",
        "timestamp,reference_timestamp,dt,north_error_m,east_error_m,up_error_m,horizontal_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"
        "0,0,0,0,0,0,0,0,0,-90\n"
        "1,1,0,0,0,0,0,0,0,-90\n",
    )
    return dual, n4h2


def test_dual_evaluator_profile_confirmed_only_when_summary_close(tmp_path) -> None:
    dual, n4h2 = _make_dual_toy(tmp_path)
    group = {
        "group_id": "TOY_DUAL:0",
        "role_alias": "DUAL_FINAL_V23_CANDIDATE:0",
        "artifacts": {
            "KF_GINS_Navresult.nav": str(dual / "KF_GINS_Navresult.nav"),
            "summary.json": str(dual / "summary.json"),
            "error_series.csv": str(dual / "error_series.csv"),
        },
    }
    report = evaluate_dual_final_v23_evaluator_parity(
        group,
        external_source_root=tmp_path / "external",
        n4h2_artifacts_root=n4h2,
        output_dir=tmp_path / "out",
    )
    assert report["direct_identity_matches"] is False
    assert report["official_candidate_matches"] is True
    assert report["dual_evaluator_profile_confirmed"] is True
    assert report["recommended_profile_name"] == "official_candidate_ref_heading_to_math"
    assert report["solver_output_changed"] is False
    assert report["trace_solver_input"] is False
