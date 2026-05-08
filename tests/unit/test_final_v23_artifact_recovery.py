"""中文说明：artifact recovery 单元测试只用 toy 文件，不读取真实路径。"""

from pathlib import Path

from legsa_gins.source_audit.final_v23_artifact_recovery import recover_final_v23_artifacts


def test_artifact_recovery_groups_toy_case(tmp_path: Path):
    case = tmp_path / "final_v23" / "single" / "E001_single_nominal_none"
    case.mkdir(parents=True)
    (case / "input.gnss").write_text("0 0 0 0 1 1 1 0 0 0 1 1 1 0 1\n", encoding="utf-8")
    (case / "KF_GINS_Navresult.nav").write_text("0 nav\n", encoding="utf-8")
    (case / "KF_GINS_STD.txt").write_text("0 std\n", encoding="utf-8")
    (case / "summary.json").write_text('{"yaw_rmse_deg": 1.5}\n', encoding="utf-8")
    report = recover_final_v23_artifacts({"TOY_ROOT": tmp_path}, max_depth=6)
    assert report["artifact_groups_found"] == 1
    best = report["best_final_v23_candidate_group"]
    assert best["contains_input_gnss"] is True
    assert best["contains_nav"] is True
    assert best["contains_std"] is True
    assert best["contains_summary"] is True
    assert best["summary_metrics"]["yaw_rmse_deg"] == 1.5
