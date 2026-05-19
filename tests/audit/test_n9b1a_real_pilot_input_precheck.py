from pathlib import Path

from legsa_gins.reporting.by2_real_pilot_input_generator import (
    MATRIX_STEMS,
    REPORT_NAMES,
    run_real_pilot_input_precheck,
    validate_n9b1a_result,
)


ROOT = Path(__file__).resolve().parents[2]


def test_n9b1a_audit_contract(tmp_path):
    runtime_root = tmp_path / "n9b1a"
    result = run_real_pilot_input_precheck(ROOT, runtime_root=runtime_root, write_outputs=True)
    validation = validate_n9b1a_result(
        runtime_root,
        result["degraded_input_index"],
        result["random_value_index"],
        result["solver_command_plan_index"],
        True,
    )
    assert validation["status"] == "pass"
    for name in REPORT_NAMES:
        assert (runtime_root / "reports" / name).is_file()
    for stem in MATRIX_STEMS:
        assert (runtime_root / "matrix" / f"{stem}.csv").is_file()
        assert (runtime_root / "matrix" / f"{stem}.json").is_file()
    assert all(row["solver_run"] is False for row in result["solver_command_plan_index"])
    assert all(row["official_evaluator_run"] is False for row in result["solver_command_plan_index"])
    assert all(row["toy_only"] is False for row in result["random_value_index"])
    assert all(row["pilot_only"] is True for row in result["random_value_index"])
