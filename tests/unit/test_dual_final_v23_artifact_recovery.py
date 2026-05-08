"""中文说明：dual_final_v23 recovery 测试只使用 toy artifact，不复制外部数据。"""

import json

from legsa_gins.source_audit.dual_final_v23_artifact_recovery import recover_dual_final_v23_artifacts


def _write_summary(path, horizontal: float, up: float, yaw: float, roll: float = 0.1, pitch: float = 0.2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "position": {"horizontal_rmse_m": horizontal, "up_rmse_m": up},
                "attitude": {"yaw_rmse_deg": yaw, "roll_rmse_deg": roll, "pitch_rmse_deg": pitch},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_group(directory, horizontal: float, yaw: float) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    _write_summary(directory / "summary.json", horizontal, 0.8, yaw)
    (directory / "KF_GINS_Navresult.nav").write_text("0 0 40 116 10 0 0 0 0 0 0\n", encoding="utf-8")
    (directory / "KF_GINS_STD.txt").write_text("std\n", encoding="utf-8")
    (directory / "input.gnss").write_text("gnss\n", encoding="utf-8")
    (directory / "error_series.csv").write_text("time,yaw_err_deg\n0,0\n", encoding="utf-8")


def test_dual_scoring_prefers_dual_metrics(tmp_path) -> None:
    dual = tmp_path / "extended_degradation_results" / "final_v23" / "dual" / "E001_single_nominal_none"
    single_like = tmp_path / "tmp_single_antenna_compare" / "runs" / "nominal_none"
    _write_group(dual, 0.353, 1.814)
    _write_group(single_like, 38.947, 41.375)
    report = recover_dual_final_v23_artifacts({"TOY_ROOT": tmp_path}, max_depth=8)
    best = report["best_dual_candidate_group"]
    assert report["dual_artifact_found"] is True
    assert best["summary_metrics"]["horizontal_rmse_m"] == 0.353
    assert best["summary_metrics"]["yaw_rmse_deg"] == 1.814
    assert "single_antenna_like_penalty" not in best["candidate_rank_evidence"]
    assert report["dual_input_recovered"] is True
    assert report["trace_solver_input"] is False
