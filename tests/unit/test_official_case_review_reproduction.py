"""中文说明：official reproduction 单元测试使用 toy final_v23 artifacts。"""

import json

from legsa_gins.evaluation.official_case_review_reproduction import (
    parse_kfgins_nav,
    recompute_case_metrics,
    reproduce_official_case_review,
)


def _make_toy_case(tmp_path):
    source = tmp_path / "actual"
    source.mkdir()
    (source / "KF_GINS_Navresult.nav").write_text(
        "0 0 40 116 10 0 0 0 0 0 0\n"
        "0 1 40 116 10 0 0 0 0 0 0\n"
        "0 2 40 116 10 0 0 0 0 0 0\n",
        encoding="utf-8",
    )
    (source / "KF_GINS_STD.txt").write_text("std\n", encoding="utf-8")
    (source / "input.gnss").write_text("0 40 116 10 0 0 0 1 1 1 0 1 1 1 1\n", encoding="utf-8")
    (source / "summary.json").write_text(
        json.dumps(
            {
                "position": {"horizontal_rmse_m": 0.0, "up_rmse_m": 0.0},
                "attitude": {"roll_rmse_deg": 0.0, "pitch_rmse_deg": 0.0, "yaw_rmse_deg": 0.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (source / "error_series.csv").write_text(
        "time,err_n_m,err_e_m,err_u_m,roll_err_deg,pitch_err_deg,yaw_err_deg\n"
        "0,0,0,0,0,0,0\n1,0,0,0,0,0,0\n2,0,0,0,0,0,0\n",
        encoding="utf-8",
    )
    n4h2 = tmp_path / "n4h2"
    (n4h2 / "replay" / "standardized").mkdir(parents=True)
    (n4h2 / "replay" / "evaluation").mkdir(parents=True)
    (n4h2 / "replay" / "standardized" / "FINAL_V23_EVAL_NAV.csv").write_text(
        "timestamp,lat_deg,lon_deg,height_m,vn_mps,ve_mps,vd_mps,roll_deg,pitch_deg,yaw_deg,status,source_role\n"
        "0,40,116,10,0,0,0,0,0,0,baseline,baseline\n"
        "1,40,116,10,0,0,0,0,0,0,baseline,baseline\n"
        "2,40,116,10,0,0,0,0,0,0,baseline,baseline\n",
        encoding="utf-8",
    )
    (n4h2 / "replay" / "evaluation" / "FINAL_V23_TRACE_ERROR_SERIES.csv").write_text(
        "timestamp,reference_timestamp,dt,north_error_m,east_error_m,up_error_m,horizontal_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"
        "0,0,0,0,0,0,0,0,0,-90\n"
        "1,1,0,0,0,0,0,0,0,-90\n"
        "2,2,0,0,0,0,0,0,0,-90\n",
        encoding="utf-8",
    )
    return source, n4h2


def test_parse_kfgins_nav_and_transform_recompute(tmp_path) -> None:
    source, _ = _make_toy_case(tmp_path)
    rows = parse_kfgins_nav(source / "KF_GINS_Navresult.nav")
    reference = [{"timestamp": 0.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 90.0}]
    _, direct = recompute_case_metrics(rows[:1], reference)
    _, transformed = recompute_case_metrics(
        rows[:1],
        reference,
        {"est_transform": "identity", "ref_transform": "heading_to_math_yaw"},
    )
    assert direct["yaw_rmse_deg"] == 90.0
    assert transformed["yaw_rmse_deg"] == 0.0


def test_reproduce_official_case_review_toy(tmp_path) -> None:
    source, n4h2 = _make_toy_case(tmp_path)
    group = {
        "group_id": "TOY:0",
        "artifacts": {
            "KF_GINS_Navresult.nav": str(source / "KF_GINS_Navresult.nav"),
            "KF_GINS_STD.txt": str(source / "KF_GINS_STD.txt"),
            "input.gnss": str(source / "input.gnss"),
            "summary.json": str(source / "summary.json"),
            "error_series.csv": str(source / "error_series.csv"),
        },
        "n4h2_artifacts_root": str(n4h2),
    }
    report = reproduce_official_case_review(group, output_dir=tmp_path / "out")
    assert report["evaluator_direct_parity_passed"] is False
    assert report["evaluator_yaw_transform_needed"] is True
    assert report["recommended_next_stage"] == "N4R_fix_yaw_evaluator_convention"
