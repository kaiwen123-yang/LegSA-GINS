from pathlib import Path
import hashlib

import pytest

from legsa_gins.paper_rebuild.canonical541 import execution_plan
from legsa_gins.paper_rebuild.canonical541 import preparation


SCIENTIFIC = "a" * 40
PREPARATION = "b" * 40


def test_dual_freeze_accepts_frozen_science_and_current_clean_preparation(monkeypatch, tmp_path):
    monkeypatch.setattr(execution_plan, "git_code_state", lambda repo: (PREPARATION, False))
    execution_plan._validate_dual_freeze(
        repo=Path(tmp_path), supplied_scientific_commit=SCIENTIFIC,
        recorded_scientific_commit=SCIENTIFIC,
        recorded_preparation_commit=PREPARATION,
    )


@pytest.mark.parametrize(
    ("current", "dirty", "supplied", "recorded_scientific", "recorded_preparation"),
    [
        (PREPARATION, True, SCIENTIFIC, SCIENTIFIC, PREPARATION),
        ("c" * 40, False, SCIENTIFIC, SCIENTIFIC, PREPARATION),
        (PREPARATION, False, "c" * 40, SCIENTIFIC, PREPARATION),
    ],
)
def test_dual_freeze_rejects_dirty_head_or_scientific_drift(
    monkeypatch, tmp_path, current, dirty, supplied, recorded_scientific, recorded_preparation,
):
    monkeypatch.setattr(execution_plan, "git_code_state", lambda repo: (current, dirty))
    with pytest.raises(execution_plan.ExecutionPlanError, match="dual-freeze"):
        execution_plan._validate_dual_freeze(
            repo=Path(tmp_path), supplied_scientific_commit=supplied,
            recorded_scientific_commit=recorded_scientific,
            recorded_preparation_commit=recorded_preparation,
        )


def test_execution_runner_checks_preparation_head_not_scientific_head(monkeypatch, tmp_path):
    executable = tmp_path / "solver"
    executable.write_bytes(b"reviewed executable")
    executable_hash = hashlib.sha256(executable.read_bytes()).hexdigest()
    monkeypatch.setattr(execution_plan, "git_code_state", lambda repo: (PREPARATION, False))
    monkeypatch.setattr(execution_plan, "persist_execution_status", lambda **kwargs: None)
    monkeypatch.setattr(execution_plan, "rebuild_attempt_registry", lambda **kwargs: None)
    unique = [{
        "run_id": "RUN_00001", "run_order": 1,
        "scientific_code_freeze_commit": SCIENTIFIC,
        "preparation_code_commit": PREPARATION,
        "executable_hash": executable_hash,
    }]
    monkeypatch.setattr(execution_plan, "load_execution_plan", lambda **kwargs: ({}, unique, []))
    updated, records = execution_plan.execute_unique_selection(
        selected_run_ids=(), unique_rows=unique, logical_rows=(),
        stage_root=tmp_path, executable=executable,
        raw_root=tmp_path, clean_root=tmp_path, repo_root=tmp_path,
        code_freeze_commit=SCIENTIFIC, jobs=1,
    )
    assert updated == unique
    assert records == []


def test_execution_runner_reloads_authoritative_registry_immediately_before_executor(monkeypatch, tmp_path):
    executable = tmp_path / "solver"; executable.write_bytes(b"reviewed executable")
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    unique = [{"run_id": "RUN_00001", "run_order": 1,
               "scientific_code_freeze_commit": SCIENTIFIC,
               "preparation_code_commit": PREPARATION, "executable_hash": digest}]
    monkeypatch.setattr(execution_plan, "git_code_state", lambda repo: (PREPARATION, False))
    changed = [dict(unique[0], execution_key="tampered")]
    monkeypatch.setattr(execution_plan, "load_execution_plan", lambda **kwargs: ({}, changed, []))
    with pytest.raises(execution_plan.ExecutionPlanError, match="changed before launch"):
        execution_plan.execute_unique_selection(
            selected_run_ids=(), unique_rows=unique, logical_rows=(), stage_root=tmp_path,
            executable=executable, raw_root=tmp_path, clean_root=tmp_path,
            repo_root=tmp_path, code_freeze_commit=SCIENTIFIC, jobs=1,
        )


def test_authoritative_plan_marker_is_after_completeness_gate():
    source = Path(preparation.__file__).read_text(encoding="utf-8")
    function = source[source.index("def prepare_only_execution_plan("):]
    audit = function.index("audit = _preparation_completeness_audit(")
    rejection = function.index('if not audit["passed"]:', audit)
    ready = function.index('phase="READY_FOR_AUTOMATIC_EXECUTION"', rejection)
    marker = function.index('_atomic_json(stage / "07_FULL_ALGORITHM_REGISTRY/EXECUTION_PLAN.json", plan)', ready)
    assert audit < rejection < ready < marker
