from tests.paper10m1r2b_common import read_csv, read_text


def test_guard_report_confirms_no_solver_or_evaluator_run():
    report = read_text("07_GUARDS/PAPER10M1R2B_GUARD_VALIDATION_REPORT.md")
    assert "no_solver_run: PASS" in report
    assert "no_evaluator_run: PASS" in report
    assert "no_full_matrix: PASS" in report
    assert "no_internal_ablation: PASS" in report


def test_forbidden_input_audit_passes_all_checks():
    rows = read_csv("07_GUARDS/PAPER10M1R2B_FORBIDDEN_INPUT_AUDIT.csv")
    assert rows
    assert {row["status"] for row in rows} == {"PASS"}
