"""中文说明：yaw variant matrix 只验证诊断排序和 formal_allowed 边界。"""

from pathlib import Path

from legsa_gins.evaluation.yaw_input_variant_matrix import build_yaw_input_variant_matrix


def _write_input(path: Path) -> None:
    lines = []
    for index in range(20):
        lines.append(f"{index} 0 0 0 1 1 1 0 0 0 1 1 1 10 1.5")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_variant_matrix_ranks_status_and_marks_trace_diagnostic(tmp_path: Path):
    input_path = tmp_path / "input.gnss"
    _write_input(input_path)
    trace_rows = [{"time": float(index), "yaw": 10.0} for index in range(20)]
    report = build_yaw_input_variant_matrix(input_path, trace_yaw_rows=trace_rows, output_dir=tmp_path)
    assert report["best_status_variant"]["yaw_vs_trace_rmse_deg"] == 0.0
    trace = next(item for item in report["variants"] if item["variant_name"] == "trace_yaw_diagnostic_only")
    assert trace["trace_yaw_for_solver"] is True
    assert trace["formal_allowed"] is False
    auto_best = next(item for item in report["variants"] if item["variant_name"] == "status_A1_auto_best_install_diagnostic")
    assert auto_best["formal_allowed"] is False
