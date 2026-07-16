from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild import clean2_evaluator as evaluator
from legsa_gins.paper_rebuild.clean2_runner import ATTEMPT_FIELDS, validate_attempt_rows
from legsa_gins.paper_rebuild.manifest import sha256_file


def _registry_rows() -> list[dict[str, int | str]]:
    return [
        {"run_id": f"R{order:03d}", "run_order": order}
        for order in range(1, 111)
    ]


def _pass_attempt_rows() -> list[dict[str, object]]:
    return [
        {
            "run_id": f"R{order:03d}",
            "run_order": order,
            "attempt_number": 1,
            "technical_retry": False,
            "retry_reason": "",
            "metric_driven_rerun": False,
            "returncode": 0,
            "runtime_seconds": 1.0,
            "terminal_status": "PASS",
        }
        for order in range(1, 111)
    ]


def _write_attempts(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ATTEMPT_FIELDS))
        writer.writeheader()
        writer.writerows(rows)


def _write_attempt_audit(
    path: Path,
    *,
    registry: Path,
    attempts: Path,
    rows: list[dict[str, object]],
    registry_rows: list[dict[str, int | str]],
) -> None:
    audit = validate_attempt_rows(
        rows,
        registry_rows=registry_rows,
        required_run_ids={str(row["run_id"]) for row in registry_rows},
    )
    path.write_text(
        json.dumps(
            {
                "schema_version": evaluator.ATTEMPT_AUDIT_SCHEMA,
                "stage_id": evaluator.STAGE_ID,
                "registry_sha256": sha256_file(registry),
                "attempts_sha256": sha256_file(attempts),
                **audit,
            }
        ),
        encoding="utf-8",
    )


def _install_pretrace_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tmp_path: Path,
    registry: Path,
    registry_rows: list[dict[str, int | str]],
) -> tuple[Path, Path, Path, evaluator.SolverArtifactIndex, dict[str, bool]]:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    seal = tmp_path / "CLEAN2_COMPLETE_OUTPUT_SEAL.json"
    seal.write_text("{}\n", encoding="utf-8")
    artifact_source = tmp_path / "CLEAN2_SOLVER_ARTIFACT_INDEX.json"
    artifact_source.write_text("{}\n", encoding="utf-8")
    index = evaluator.SolverArtifactIndex(
        {},
        metadata={
            "registry_sha256": sha256_file(registry),
            "runtime_root": str(runtime),
            "run_count": 110,
            "index_sha256": sha256_file(artifact_source),
        },
        source_path=artifact_source,
    )
    sealed_runs = [
        {
            "run_id": str(row["run_id"]),
            "run_order": int(row["run_order"]),
            "files": [
                {
                    "relative_path": (
                        f"{row['run_id']}/attempts/attempt_1/KF_GINS_Navresult.nav"
                    )
                }
            ],
        }
        for row in registry_rows
    ]
    monkeypatch.setattr(evaluator, "read_run_registry", lambda _path: registry_rows)
    monkeypatch.setattr(
        evaluator,
        "load_solver_artifact_index",
        lambda *_args, **_kwargs: index,
    )
    monkeypatch.setattr(
        evaluator,
        "validate_sealed_solver_artifact_index",
        lambda **_kwargs: {"seal": {"runs": sealed_runs}, "passed": True},
    )
    trace_state = {"called": False}

    def forbidden_trace_verify(*_args, **_kwargs):
        trace_state["called"] = True
        raise AssertionError("trace verifier must not run before the attempt gate")

    monkeypatch.setattr(evaluator, "_verify_offline_trace", forbidden_trace_verify)
    return runtime, seal, artifact_source, index, trace_state


def _evaluate_with_bad_gate(
    *,
    runtime: Path,
    seal: Path,
    artifact_source: Path,
    registry: Path,
    attempts: Path,
    attempt_audit: Path,
    tmp_path: Path,
) -> None:
    evaluator.evaluate_clean2_outputs(
        solver_artifact_index_path=artifact_source,
        reference_trace_path=tmp_path / "must_not_be_opened.trace",
        trace_sha256=evaluator.EXPECTED_TRACE_SHA256,
        exact_evaluator_path=tmp_path / "must_not_be_hashed_evaluator.py",
        evaluator_sha256=evaluator.EXACT_EVALUATOR_SHA256,
        execution_protocol_path=tmp_path / "must_not_be_read_protocol.yaml",
        complete_output_seal_path=seal,
        registry_path=registry,
        run_attempts_path=attempts,
        run_attempts_audit_path=attempt_audit,
        output_root=tmp_path / "offline",
        expected_runtime_root=runtime,
    )


def test_attempt_ledger_mutation_fails_before_trace_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = tmp_path / "CLEAN2_RUN_REGISTRY.csv"
    registry.write_text("frozen-registry\n", encoding="utf-8")
    registry_rows = _registry_rows()
    attempts = tmp_path / "CLEAN2_RUN_ATTEMPTS.csv"
    rows = _pass_attempt_rows()
    _write_attempts(attempts, rows)
    attempt_audit = tmp_path / "CLEAN2_RUN_ATTEMPTS_AUDIT.json"
    _write_attempt_audit(
        attempt_audit,
        registry=registry,
        attempts=attempts,
        rows=rows,
        registry_rows=registry_rows,
    )
    # 审计之后的无语义字节改动也必须被 hash binding 捕获。
    attempts.write_bytes(attempts.read_bytes() + b"\n")
    runtime, seal, artifact_source, _, trace_state = _install_pretrace_fakes(
        monkeypatch, tmp_path=tmp_path, registry=registry, registry_rows=registry_rows
    )
    with pytest.raises(Exception, match="three-way binding"):
        _evaluate_with_bad_gate(
            runtime=runtime,
            seal=seal,
            artifact_source=artifact_source,
            registry=registry,
            attempts=attempts,
            attempt_audit=attempt_audit,
            tmp_path=tmp_path,
        )
    assert trace_state["called"] is False


def test_valid_pretrace_gate_binds_current_registry_attempts_and_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = tmp_path / "CLEAN2_RUN_REGISTRY.csv"
    registry.write_text("frozen-registry\n", encoding="utf-8")
    registry_rows = _registry_rows()
    attempts = tmp_path / "CLEAN2_RUN_ATTEMPTS.csv"
    rows = _pass_attempt_rows()
    _write_attempts(attempts, rows)
    attempt_audit = tmp_path / "CLEAN2_RUN_ATTEMPTS_AUDIT.json"
    _write_attempt_audit(
        attempt_audit,
        registry=registry,
        attempts=attempts,
        rows=rows,
        registry_rows=registry_rows,
    )
    runtime, seal, _, index, _ = _install_pretrace_fakes(
        monkeypatch, tmp_path=tmp_path, registry=registry, registry_rows=registry_rows
    )
    result = evaluator.validate_pretrace_formal_chain(
        artifact_index=index,
        complete_output_seal_path=seal,
        registry_path=registry,
        run_attempts_path=attempts,
        run_attempts_audit_path=attempt_audit,
        runtime_root=runtime,
    )
    assert result["registry_sha256"] == sha256_file(registry)
    assert result["run_attempts_sha256"] == sha256_file(attempts)
    assert result["run_attempts_audit_sha256"] == sha256_file(attempt_audit)
    assert result["all_110_attempt_histories_validated_before_trace"] is True
    assert result["terminal_attempt_audit_validated_before_trace"] is True


def test_missing_terminal_attempt_audit_fails_before_trace_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = tmp_path / "CLEAN2_RUN_REGISTRY.csv"
    registry.write_text("frozen-registry\n", encoding="utf-8")
    registry_rows = _registry_rows()
    attempts = tmp_path / "CLEAN2_RUN_ATTEMPTS.csv"
    _write_attempts(attempts, _pass_attempt_rows())
    missing_audit = tmp_path / "CLEAN2_RUN_ATTEMPTS_AUDIT.json"
    runtime, seal, artifact_source, _, trace_state = _install_pretrace_fakes(
        monkeypatch, tmp_path=tmp_path, registry=registry, registry_rows=registry_rows
    )
    with pytest.raises(Exception):
        _evaluate_with_bad_gate(
            runtime=runtime,
            seal=seal,
            artifact_source=artifact_source,
            registry=registry,
            attempts=attempts,
            attempt_audit=missing_audit,
            tmp_path=tmp_path,
        )
    assert trace_state["called"] is False


def test_illegal_retry_history_fails_before_trace_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = tmp_path / "CLEAN2_RUN_REGISTRY.csv"
    registry.write_text("frozen-registry\n", encoding="utf-8")
    registry_rows = _registry_rows()
    rows = _pass_attempt_rows()
    rows.append(
        {
            "run_id": "R001",
            "run_order": 1,
            "attempt_number": 2,
            "technical_retry": True,
            "retry_reason": "metric_worse",
            "metric_driven_rerun": True,
            "returncode": 0,
            "runtime_seconds": 1.0,
            "terminal_status": "PASS",
        }
    )
    attempts = tmp_path / "CLEAN2_RUN_ATTEMPTS.csv"
    _write_attempts(attempts, rows)
    attempt_audit = tmp_path / "CLEAN2_RUN_ATTEMPTS_AUDIT.json"
    attempt_audit.write_text(
        json.dumps(
            {
                "schema_version": evaluator.ATTEMPT_AUDIT_SCHEMA,
                "stage_id": evaluator.STAGE_ID,
                "registry_sha256": sha256_file(registry),
                "attempts_sha256": sha256_file(attempts),
                "run_count": 110,
                "attempt_count": 111,
                "technical_retry_run_count": 1,
                "all_terminal_pass": True,
                "metric_driven_rerun": False,
                "passed": True,
            }
        ),
        encoding="utf-8",
    )
    runtime, seal, artifact_source, _, trace_state = _install_pretrace_fakes(
        monkeypatch, tmp_path=tmp_path, registry=registry, registry_rows=registry_rows
    )
    with pytest.raises(Exception, match="attempt histories"):
        _evaluate_with_bad_gate(
            runtime=runtime,
            seal=seal,
            artifact_source=artifact_source,
            registry=registry,
            attempts=attempts,
            attempt_audit=attempt_audit,
            tmp_path=tmp_path,
        )
    assert trace_state["called"] is False
