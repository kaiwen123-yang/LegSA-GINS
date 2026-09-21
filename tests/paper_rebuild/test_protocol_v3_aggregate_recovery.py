"""Synthetic metadata tests only; never dispatch a scientific process."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys

import pytest

from legsa_gins.paper_rebuild.protocol_v3 import aggregate_recovery as recovery


def terminals():
    native = [dict(run_id="RUN_1", code_commit=recovery.SCIENCE_FREEZE,
        status="COMPLETED", trace_open_count=0,
        access_audit=dict(passed=True, trace_open_count=0),
        effective_echo_gate=dict(passed=True))]
    evaluated = [dict(row=dict(run_id="RUN_1", evaluator_contract="evaluator_contract_" + version,
        code_commit=recovery.SCIENCE_FREEZE, evaluation_invoked=True, evaluation_status="COMPLETED"),
        audit=dict(passed=True, trace_open_count=1)) for version in recovery.VERSIONS]
    return native, evaluated


def test_exact_coverage():
    native, evaluated = terminals()
    recovery.validate_coverage([dict(run_id="RUN_1")], native, evaluated, expected_native=1)


@pytest.mark.parametrize("kind", ["native_duplicate", "evaluation_duplicate", "native_trace", "native_audit_missing", "evaluation_trace", "echo_false", "freeze"])
def test_coverage_fails_closed(kind):
    native, evaluated = terminals()
    if kind == "native_duplicate":
        native.append(deepcopy(native[0]))
    elif kind == "evaluation_duplicate":
        evaluated[1] = deepcopy(evaluated[0])
    elif kind == "native_trace":
        native[0]["access_audit"]["trace_open_count"] = 1
    elif kind == "native_audit_missing":
        native[0]["access_audit"] = {}
    elif kind == "evaluation_trace":
        evaluated[0]["audit"]["trace_open_count"] = 0
    elif kind == "echo_false":
        native[0]["effective_echo_gate"]["passed"] = False
    else:
        native[0]["code_commit"] = "f" * 40
    with pytest.raises(RuntimeError):
        recovery.validate_coverage([dict(run_id="RUN_1")], native, evaluated, expected_native=1)


def test_classified_failure_keeps_absent_echo_and_no_evaluator():
    native, evaluated = terminals()
    native[0].update(status="ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT", effective_echo_gate=dict(passed=None))
    for item in evaluated:
        item["row"].update(evaluation_invoked=False, evaluation_status="NOT_RUN_ALGORITHM_FAILURE")
        item["audit"] = {}
    recovery.validate_coverage([dict(run_id="RUN_1")], native, evaluated, expected_native=1)
    evaluated[0]["row"]["evaluation_status"] = "COMPLETED"
    with pytest.raises(RuntimeError, match="NOT_INVOKED"):
        recovery.validate_coverage([dict(run_id="RUN_1")], native, evaluated, expected_native=1)


def f04_rows():
    return [dict(row=dict(evaluator_contract="evaluator_contract_v3", method_id="F04",
        domain="CORE" if seq == "BY2" else "SEQUENCE", sequence_id=seq, case_id="C00_clean_normal",
        evaluation_status="COMPLETED", yaw_rmse_deg=value)) for seq, value in
        zip(recovery.F04_YAW, (1.8862718548526467, 1.93377013508875, 2.433814932823714))]


def test_f04_exact_display_identity():
    assert recovery.f04_gate(f04_rows())["actual"] == recovery.F04_YAW
    rows = f04_rows()
    rows[1]["row"]["yaw_rmse_deg"] = 1.95
    with pytest.raises(RuntimeError, match="T5AR_MISMATCH"):
        recovery.f04_gate(rows)


def test_f04_duplicate_is_not_silently_overwritten():
    rows = f04_rows()
    with pytest.raises(RuntimeError, match="DUPLICATE"):
        recovery.f04_gate(rows + rows[:1])


def test_f04_full_precision_t5ar_pin_gate():
    rows = f04_rows()
    reference = [dict(sequence_id=r["row"]["sequence_id"], method_id="F04", variant="R5",
        yaw_rmse_deg=str(r["row"]["yaw_rmse_deg"])) for r in rows]
    assert recovery.f04_gate(rows, reference)["t5ar_full_precision_identical"] is True
    reference[0]["yaw_rmse_deg"] = str(float(reference[0]["yaw_rmse_deg"]) + 1e-10)
    with pytest.raises(RuntimeError, match="FULL_PRECISION"):
        recovery.f04_gate(rows, reference)


def test_emitted_main_table_f04_gate_before_figures():
    rows = [r["row"] for r in f04_rows()] + [dict(method_id="EXTERNAL") for _ in range(49)]
    expected = {r["sequence_id"]: float(r["yaw_rmse_deg"]) for r in rows[:3]}
    recovery.main_table_f04_gate(rows, expected)
    rows[1]["yaw_rmse_deg"] += 0.0001
    with pytest.raises(RuntimeError, match="MAIN_TABLE_F04"):
        recovery.main_table_f04_gate(rows, expected)


def test_openat_summary_is_a_required_full_matrix_gate():
    summary = dict(status="PASS", native_count=6468, evaluator_terminal_slots=12936,
        native_trace_open_count=0, evaluator_each_trace_exactly_one=True, native_calls=0,
        evaluator_calls=0, raw_trace_reads=0, completed_batches=279, original_hard_stop_sha256="a" * 64)
    recovery.validate_audit(summary, "a" * 64)
    for field in ("native_trace_open_count", "evaluator_each_trace_exactly_one", "native_count"):
        bad = deepcopy(summary)
        bad[field] = -1
        with pytest.raises(RuntimeError, match="OPENAT_GATE"):
            recovery.validate_audit(bad, "a" * 64)


def test_guard_exact_source_exception_raw_and_process_denied(tmp_path, monkeypatch):
    raw, code = tmp_path / "raw", tmp_path / "code"
    raw.mkdir(); code.mkdir()
    source = code / recovery.TRACE_SOURCE
    source.parent.mkdir(parents=True)
    source.write_text("# source only\n")
    monkeypatch.setattr(recovery, "TRACE_SOURCE_SHA256", hashlib.sha256(source.read_bytes()).hexdigest())
    rawfile = raw / "gnss1-raw.csv"
    rawfile.write_text("raw")
    fake = code / "trace_another.py"
    fake.write_text("no")
    bag = code / "input.bag"
    bag.write_text("no")
    with recovery.aggregation_guard(raw, code) as guard:
        assert source.read_text() == "# source only\n"
        for path in (rawfile, fake, bag):
            with pytest.raises(PermissionError, match="RAW_DENIED"):
                path.read_bytes()
        with pytest.raises(PermissionError, match="RAW_DENIED"):
            source.write_text("change")
        with pytest.raises(PermissionError, match="PROCESS_LAUNCH"):
            sys.audit("subprocess.Popen", "native", ["native"], None, None)
    assert guard["source_module_opens"] == 1
    assert source.read_text() == "# source only\n"
    assert rawfile.read_text() == "raw"  # hook disabled after its context


def test_guard_source_identity_is_not_prefix_allowlist(tmp_path):
    code = tmp_path / "code"
    source = code / recovery.TRACE_SOURCE
    source.parent.mkdir(parents=True)
    source.write_text("wrong")
    with pytest.raises(RuntimeError, match="TRACE_SOURCE_HASH"):
        with recovery.aggregation_guard(tmp_path / "raw", code):
            pass


def test_pin_changed_file_refused(tmp_path):
    path = tmp_path / "record.json"
    path.write_text('{"a":1}')
    pins = recovery.Pins()
    assert pins.json(path) == dict(a=1)
    path.write_text('{"a":2}')
    with pytest.raises(RuntimeError, match="INPUT_CHANGED"):
        pins.json(path)


def test_failure_family_config_keeps_f02_zero_and_class_separation():
    current = [dict(case_family="heading_fault", method_id="F04", evaluation_status="NOT_RUN_ALGORITHM_FAILURE",
        failure_classification="ALGORITHM_FAILURE_DIVERGED") for _ in range(193)]
    current += [dict(case_family="heading_fault", method_id="F02", evaluation_status="NOT_RUN_ALGORITHM_FAILURE",
        failure_classification="ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT") for _ in range(90)]
    frozen = [dict(case_family="heading_fault", method_id="F04", evaluation_status="NOT_RUN_ALGORITHM_FAILURE",
        solver_terminal_status="ALGORITHM_FAILURE_ALL_YAW_REJECTED") for _ in range(177)]
    result = recovery.failure_family_rows(current, frozen, "v3")
    assert sum(r["failure_count"] for r in result if r["protocol"] == "v3") == 283
    assert sum(r["failure_count"] for r in result if r["protocol"] == "v2.1") == 177
    assert any(r["method_id"] == "F02" and r["protocol"] == "v2.1" and r["failure_count"] == 0 for r in result)
    assert any(r["method_id"] == "F02" and r["protocol"] == "v3" and r["failure_count"] == 90 for r in result)
    with pytest.raises(RuntimeError, match="FAILURE_TOTAL"):
        recovery.failure_family_rows(current[:-1], frozen, "v3")


def test_comparison_changes_only_frozen_class_token():
    common = dict(dataset_id="BY2", case_id="D27_seed_00", method_id="F04")
    frozen = [{**common, "evaluation_status": "NOT_RUN_ALGORITHM_FAILURE",
        "solver_terminal_status": "ALGORITHM_FAILURE_ALL_YAW_REJECTED"}]
    comparison = [{**common, "v21_status": "NOT_RUN_ALGORITHM_FAILURE", "v21_failure": "NONE",
        "v3_status": "COMPLETED", "v3_yaw_rmse_deg": "1.2345678901234", "paired_finite": "False"}]
    result = recovery.corrected_failure_comparison(comparison, frozen)
    assert result[0]["v21_failure"] == "ALGORITHM_FAILURE_ALL_YAW_REJECTED"
    assert {k: v for k, v in result[0].items() if k != "v21_failure"} == {k: v for k, v in comparison[0].items() if k != "v21_failure"}
    assert comparison[0]["v21_failure"] == "NONE"


def test_machine_figure_qa_failure_stops(tmp_path):
    render = dict(status="COMPLETE", rendered_count=10, code_freeze=recovery.SCIENCE_FREEZE,
        figures=[dict(figure_id=name, status="RENDERED", qa=[{"pass": False}])
            for name in [*(f"MFIG{i:02}" for i in range(7)), "SFIG01", "FIG02S", "FIG02S-b"]])
    with pytest.raises(RuntimeError, match="FIGURE_QA"):
        recovery.verify_render(tmp_path, render)


def test_missing_render_is_not_done(tmp_path):
    with pytest.raises(RuntimeError, match="INCOMPLETE"):
        recovery.verify_render(tmp_path, dict(status="INCOMPLETE", rendered_count=9))
