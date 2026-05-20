from pathlib import Path

from legsa_gins.reporting.by2_n9b1f_real_legsa_algorithm_runner import (
    MATRIX_STEMS,
    REPORT_NAMES,
    run_n9b1f_real_legsa_algorithm_runner,
    validate_n9b1f_result,
)


ROOT = Path(__file__).resolve().parents[2]


def test_n9b1f_audit_contract(tmp_path):
    runtime_root = tmp_path / "n9b1f"
    result = run_n9b1f_real_legsa_algorithm_runner(ROOT, runtime_root=runtime_root, write_outputs=True)
    validation = validate_n9b1f_result(
        ROOT,
        runtime_root,
        result["algorithm_implementation_inventory"],
        result["normal_parity_metrics"],
        result["n9b1d_ready_execution_matrix"],
        result["wsl_dryrun_ready_commands"],
        runtime_written=True,
    )
    assert validation["status"] == "pass"
    for name in REPORT_NAMES:
        assert (runtime_root / "reports" / name).is_file()
    for stem in MATRIX_STEMS:
        assert (runtime_root / "matrix" / f"{stem}.csv").is_file()
        assert (runtime_root / "matrix" / f"{stem}.json").is_file()
    assert all(row["ready_for_N9B2_execution"] is False for row in result["n9b1d_ready_execution_matrix"])
    assert all(row["degradation_execution"] is False for row in result["normal_parity_metrics"])
    assert all(row["trace_solver_input"] is False for row in result["normal_parity_metrics"])
    assert all(row["final_v23_output_solver_input"] is False for row in result["normal_parity_metrics"])
    assert any(row["algorithm"] == "source_backed_EKF" for row in result["algorithm_implementation_inventory"])
    assert result["decision_report"]["ready_for_N9B2_execution"] is False
