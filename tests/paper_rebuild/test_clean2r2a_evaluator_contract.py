import importlib.util
import inspect
import json
from pathlib import Path

import pytest

import legsa_gins.paper_rebuild.clean2r2a_evaluator as evaluator_module
from legsa_gins.paper_rebuild.clean2r2a_evaluator import (
    Clean2R2AEvaluationError,
    EXACT_ERROR_COLUMNS,
    EXACT_EVALUATOR_SHA256,
    EXACT_SUMMARY_FIELDS,
    FROZEN_BASE_TIME,
    _assert_persisted_crosscheck,
    _audit_evaluator_file_opens,
    _resolve_frozen_evaluation_inputs,
    evaluate_sealed_outputs,
    revalidate_offline_evaluation,
    validate_exact_evaluator_payload,
)
from legsa_gins.paper_rebuild.manifest import sha256_file, write_json_atomic


def _summary() -> dict:
    payload = {}
    for section, fields in EXACT_SUMMARY_FIELDS.items():
        payload[section] = {field: ("enu" if field == "yaw_truth_mode" else 1.0) for field in fields}
    payload["meta"]["num_samples"] = 56642
    payload["meta"]["base_time"] = FROZEN_BASE_TIME
    return payload


def test_exact_evaluator_frozen_summary_and_error_columns() -> None:
    validate_exact_evaluator_payload(_summary(), EXACT_ERROR_COLUMNS)
    bad = _summary(); del bad["position"]["position_3d_rmse_m"]
    with pytest.raises(Clean2R2AEvaluationError):
        validate_exact_evaluator_payload(bad, EXACT_ERROR_COLUMNS)


def test_exact_evaluator_rejects_arbitrary_matching_self_hash(tmp_path: Path) -> None:
    arbitrary = tmp_path / "arbitrary_evaluator.py"
    arbitrary.write_text("print('not the exact evaluator')\n", encoding="utf-8")
    assert sha256_file(arbitrary) != EXACT_EVALUATOR_SHA256
    assert "evaluator_sha256" not in inspect.signature(evaluate_sealed_outputs).parameters
    # 旧 API 会接受调用者同时提交这个文件自身的 SHA；新 API 只接受代码内冻结 SHA。
    with pytest.raises(Clean2R2AEvaluationError, match="hard-coded"):
        _resolve_frozen_evaluation_inputs(
            local_config=tmp_path / "unused.yaml",
            exact_evaluator=arbitrary,
        )


def test_base_time_cannot_be_overridden_by_payload_or_cli() -> None:
    bad = _summary()
    bad["meta"]["base_time"] = FROZEN_BASE_TIME + 1.0
    with pytest.raises(Clean2R2AEvaluationError, match="base time"):
        validate_exact_evaluator_payload(bad, EXACT_ERROR_COLUMNS)
    assert "base_time" not in inspect.signature(evaluate_sealed_outputs).parameters

    script = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/evaluate_clean2r2a_clean_ablation.py"
    spec = importlib.util.spec_from_file_location("clean2r2a_evaluate_cli", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    option_strings = {
        option
        for action in module.parser()._actions
        for option in action.option_strings
    }
    assert "--base-time" not in option_strings
    assert "--trace" not in option_strings
    assert "--evaluator-sha256" not in option_strings
    assert "--trace-sha256" not in option_strings


def test_false_strace_missing_std_and_extra_raw_is_rejected(tmp_path: Path) -> None:
    raw = tmp_path / "raw"; raw.mkdir()
    runtime = tmp_path / "runtime"; runtime.mkdir()
    trace = raw / "trace.csv"; trace.write_text("trace\n", encoding="utf-8")
    other_raw = raw / "other.csv"; other_raw.write_text("other\n", encoding="utf-8")
    nav = runtime / "nav"; nav.write_text("nav\n", encoding="utf-8")
    std = runtime / "std"; std.write_text("std\n", encoding="utf-8")
    evaluator = tmp_path / "evaluator.py"; evaluator.write_text("pass\n", encoding="utf-8")
    with pytest.raises(Clean2R2AEvaluationError, match="omitted required"):
        _audit_evaluator_file_opens(
            configuration_id="AB0000",
            opened_paths=[trace, nav, evaluator, other_raw],
            trace=trace,
            nav=nav,
            std=std,
            evaluator=evaluator,
            raw_root=raw,
            runtime_root=runtime,
            strace_sha256="a" * 64,
            output_seal_manifest_sha256="b" * 64,
            seal_validation_completed_ns=1,
            evaluator_started_ns=2,
        )
    with pytest.raises(Clean2R2AEvaluationError, match="unexpected raw-root"):
        _audit_evaluator_file_opens(
            configuration_id="AB0000",
            opened_paths=[trace, nav, std, evaluator, other_raw],
            trace=trace,
            nav=nav,
            std=std,
            evaluator=evaluator,
            raw_root=raw,
            runtime_root=runtime,
            strace_sha256="a" * 64,
            output_seal_manifest_sha256="b" * 64,
            seal_validation_completed_ns=1,
            evaluator_started_ns=2,
        )


def test_persisted_crosscheck_tamper_is_rejected() -> None:
    recomputed = {
        "row_count": 1,
        "checks": {"yaw_rmse_deg": {"computed": 1.0, "reported": 1.0,
                                      "absolute_difference": 0.0, "passed": True}},
        "passed": True,
    }
    tampered = dict(recomputed)
    tampered["row_count"] = 2
    with pytest.raises(Clean2R2AEvaluationError, match="persisted aggregate"):
        _assert_persisted_crosscheck(tampered, recomputed, "AB0000")


def test_terminal_revalidation_rejects_summary_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stage = tmp_path / "stage"; stage.mkdir()
    evaluation = stage / "08_OFFLINE_EVALUATION"; evaluation.mkdir()
    runtime_root = stage / "06_FORMAL_RUNS"; runtime_root.mkdir()
    run_id = "03_AB0000"
    runtime = runtime_root / run_id; runtime.mkdir()
    nav = runtime / "KF_GINS_Navresult.nav"; nav.write_text("1 2 3\n", encoding="utf-8")
    std = runtime / "KF_GINS_STD.txt"; std.write_text("1 2 3\n", encoding="utf-8")
    raw_root = tmp_path / "raw"; raw_root.mkdir()
    trace = raw_root / "trace.csv"; trace.write_text("trace\n", encoding="utf-8")
    exact_evaluator = tmp_path / "exact.py"; exact_evaluator.write_text("pass\n", encoding="utf-8")
    local_config = tmp_path / "local.yaml"; local_config.write_text("paths: {}\n", encoding="utf-8")
    output = evaluation / run_id; output.mkdir()

    summary = _summary(); summary["meta"]["num_samples"] = 1
    write_json_atomic(output / "summary.json", summary)
    error_row = {column: 1.0 for column in EXACT_ERROR_COLUMNS}
    evaluator_module._write_csv(
        output / "error_series.csv", sorted(EXACT_ERROR_COLUMNS), [error_row]
    )
    strace_path = output / "EVALUATOR_FILE_OPEN_TRACE.raw"
    strace_path.write_text(
        "\n".join(
            f'openat(AT_FDCWD, {json.dumps(str(path))}, O_RDONLY) = 3'
            for path in (trace, nav, std, exact_evaluator)
        ) + "\n",
        encoding="utf-8",
    )
    seal = {"rows": [{}], "manifest_sha256": "a" * 64, "journal_sha256": "b" * 64}
    audit, ledger_rows = _audit_evaluator_file_opens(
        configuration_id="AB0000",
        opened_paths=[trace, nav, std, exact_evaluator],
        trace=trace,
        nav=nav,
        std=std,
        evaluator=exact_evaluator,
        raw_root=raw_root,
        runtime_root=runtime_root,
        strace_sha256=sha256_file(strace_path),
        output_seal_manifest_sha256=seal["manifest_sha256"],
        seal_validation_completed_ns=1,
        evaluator_started_ns=2,
    )
    audit_path = output / "EVALUATOR_FILE_OPEN_AUDIT.json"
    write_json_atomic(audit_path, audit)
    monkeypatch.setattr(evaluator_module, "METHOD_ORDER", ("AB0000",))
    result_row = evaluator_module._result_row("AB0000", runtime, summary)
    evaluator_module._write_csv(
        evaluation / "CLEAN2R2A_FACTORIAL_RESULTS.csv",
        evaluator_module.RESULT_FIELDS,
        [result_row],
    )
    evaluator_module._write_csv(
        evaluation / "CLEAN2R2A_MATCH_COVERAGE.csv",
        evaluator_module.COVERAGE_FIELDS,
        [{key: result_row[key] for key in evaluator_module.COVERAGE_FIELDS}],
    )
    evaluator_module._write_csv(
        evaluation / "EVALUATOR_READ_LEDGER.csv",
        evaluator_module.LEDGER_FIELDS,
        ledger_rows,
    )
    crosscheck = evaluator_module._crosscheck(output / "error_series.csv", summary)
    write_json_atomic(evaluation / "CLEAN2R2A_AGGREGATE_CROSSCHECK.json", {
        "schema_version": "paper_rebuild.clean2r2a_aggregate_crosscheck.v2",
        "method_crosschecks": {"AB0000": crosscheck},
        "method_order": ["AB0000"],
        "method_count": 1,
        "all_outputs_sealed_before_trace_open": True,
        "trace_offline_only": True,
        "passed": True,
    })
    frozen_inputs = {
        "evaluator": exact_evaluator,
        "trace": trace,
        "raw_root": raw_root,
        "runtime_root": runtime_root,
        "local_config": local_config,
    }
    monkeypatch.setattr(
        evaluator_module, "_resolve_frozen_evaluation_inputs", lambda **_: frozen_inputs
    )
    monkeypatch.setattr(evaluator_module, "_output_seal_identity", lambda _: seal)
    write_json_atomic(
        evaluation / "OFFLINE_EVALUATION_MANIFEST.json",
        evaluator_module._expected_manifest(
            inputs=frozen_inputs,
            seal=seal,
            destination=evaluation,
            audit_hashes={"AB0000": sha256_file(audit_path)},
        ),
    )
    assert revalidate_offline_evaluation(
        stage_root=stage,
        local_config=local_config,
        exact_evaluator=exact_evaluator,
    )["passed"] is True

    tampered = _summary(); tampered["meta"]["num_samples"] = 1
    tampered["attitude"]["yaw_rmse_deg"] = 2.0
    write_json_atomic(output / "summary.json", tampered)
    with pytest.raises(Clean2R2AEvaluationError, match="aggregate crosscheck failed"):
        revalidate_offline_evaluation(
            stage_root=stage,
            local_config=local_config,
            exact_evaluator=exact_evaluator,
        )
