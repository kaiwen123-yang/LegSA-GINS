"""中文说明：N4H2 replay profile re-evaluation 测试只重算 evaluator。"""

from pathlib import Path

from legsa_gins.evaluation.n4h2_replay_profile_revaluation import reevaluate_n4h2_replay_profiles


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_candidate_yaw_206_does_not_pass_strict_gate(tmp_path) -> None:
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
        "0,0,0,0,0,0,0,0,0,-92.06\n"
        "1,1,0,0,0,0,0,0,0,-92.06\n",
    )
    report = reevaluate_n4h2_replay_profiles(n4h2, output_dir=tmp_path / "out")
    assert report["direct_yaw_rmse_deg"] == 92.06
    assert abs(report["official_candidate_yaw_rmse_deg"] - 2.06) < 1.0e-9
    assert report["yaw_gate_pass_for_each_profile"]["official_candidate_ref_heading_to_math"] is False
    assert report["recommended_profile_status"] == "near_gate_candidate_only"
    assert report["solver_output_changed"] is False
    assert report["evaluator_only"] is True
    assert report["trace_solver_input"] is False
