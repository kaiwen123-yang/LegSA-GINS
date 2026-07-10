from __future__ import annotations

import csv
from pathlib import Path

from legsa_gins.paper_rebuild import legacy_delete
from legsa_gins.paper_rebuild.legacy_delete import (
    dry_run_delete_manifest,
    execute_delete_manifest,
    guard_delete_row,
    make_delete_roots,
)
from legsa_gins.paper_rebuild.paths import legacy_reason


def _row(path: Path, *, delete_id: str = "D001") -> dict[str, str]:
    return {
        "delete_id": delete_id,
        "exact_path": str(path),
        "realpath": str(path.resolve()),
        "size_bytes": "1",
        "file_count": "1",
        "category": "legacy_runtime",
        "contains_protected": "false",
        "contains_unique_raw": "false",
        "contains_unique_paper": "false",
        "contains_unique_code": "false",
        "inside_allowed_delete_root": "true",
        "delete_allowed": "true",
        "reason": "superseded",
    }


def test_delete_guard_allows_exact_legacy_candidate_but_protects_roots(tmp_path: Path) -> None:
    project = tmp_path / "project"
    raw = project / "data" / "raw"
    paper = project / "paper"
    clean = project / "clean"
    freeze = project / "freeze"
    code = tmp_path / "code"
    for path in (raw, paper, clean, freeze, code):
        path.mkdir(parents=True)
    candidate = project / "old_runtime"
    candidate.mkdir()
    (candidate / "file.bin").write_bytes(b"x")
    roots = make_delete_roots(
        project_root=project,
        raw_root=raw,
        paper_root=paper,
        clean_root=clean,
        legacy_freeze_root=freeze,
        code_root=code,
    )
    ok, reason, _exact, _real = guard_delete_row(_row(candidate), roots)
    assert ok is True
    assert reason == "PASS"

    protected = raw / "source.csv"
    protected.write_text("raw\n", encoding="utf-8")
    ok, reason, *_ = guard_delete_row(_row(protected, delete_id="D002"), roots)
    assert ok is False
    assert reason.startswith("PROTECTED_ROOT")

    link = project / "raw_link"
    link.symlink_to(protected)
    ok, reason, *_ = guard_delete_row(_row(link, delete_id="D003"), roots)
    assert ok is False
    assert reason.startswith("PROTECTED_ROOT")


def test_legacy_component_detection_is_sequence_aware() -> None:
    denied = "/safe/" + "/".join(("reports", "stages")) + "/old"
    assert legacy_reason(denied) == "legacy_sequence:" + "/".join(("reports", "stages"))
    assert legacy_reason("/safe/new/runtime") is None


def test_exact_delete_checkpoint_executes_only_approved_tmp_candidate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    raw = project / "data" / "raw"
    paper = project / "paper"
    clean = project / "clean"
    freeze = project / "freeze"
    code = tmp_path / "code"
    for path in (raw, paper, clean, freeze, code):
        path.mkdir(parents=True)
    candidate = project / "superseded_output"
    candidate.mkdir()
    (candidate / "large.bin").write_bytes(b"legacy")
    roots = make_delete_roots(
        project_root=project,
        raw_root=raw,
        paper_root=paper,
        clean_root=clean,
        legacy_freeze_root=freeze,
        code_root=code,
    )
    rows = [_row(candidate)]
    log_root = clean / "delete_logs"
    dry_log = log_root / "DELETE_DRY_RUN_LOG.csv"
    _report, passed = dry_run_delete_manifest(rows, roots, dry_log)
    assert passed is True
    summary = execute_delete_manifest(rows, roots, log_root=log_root, dry_run_log=dry_log)
    assert summary["deleted_count_this_invocation"] == 1
    assert summary["failed_count_this_invocation"] == 0
    assert not candidate.exists()
    assert raw.is_dir()


def test_measure_failure_is_checkpointed_and_next_candidate_is_deleted(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "project"
    raw = project / "data" / "raw"
    paper = project / "paper"
    clean = project / "clean"
    freeze = project / "freeze"
    code = tmp_path / "code"
    for path in (raw, paper, clean, freeze, code):
        path.mkdir(parents=True)

    unreadable = project / "unreadable_candidate"
    deletable = project / "deletable_candidate"
    for candidate in (unreadable, deletable):
        candidate.mkdir()
        (candidate / "payload.bin").write_bytes(b"legacy")
    roots = make_delete_roots(
        project_root=project,
        raw_root=raw,
        paper_root=paper,
        clean_root=clean,
        legacy_freeze_root=freeze,
        code_root=code,
    )
    rows = [
        _row(unreadable, delete_id="D_MEASURE_FAIL"),
        _row(deletable, delete_id="D_DELETE_OK"),
    ]
    log_root = clean / "delete_logs"
    dry_log = log_root / "DELETE_DRY_RUN_LOG.csv"
    _report, passed = dry_run_delete_manifest(rows, roots, dry_log)
    assert passed is True

    real_measure_path = legacy_delete.measure_path

    def fail_first_measure(path: Path) -> tuple[int, int, int]:
        if path == unreadable:
            raise PermissionError("simulated measurement denial")
        return real_measure_path(path)

    monkeypatch.setattr(legacy_delete, "measure_path", fail_first_measure)
    summary = execute_delete_manifest(rows, roots, log_root=log_root, dry_run_log=dry_log)

    assert summary["failed_count_this_invocation"] == 1
    assert summary["deleted_count_this_invocation"] == 1
    assert unreadable.is_dir()
    assert not deletable.exists()

    with (log_root / "DELETE_FAILURE_LOG.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        failures = list(csv.DictReader(handle))
    assert any(
        row["delete_id"] == "D_MEASURE_FAIL"
        and row["error"].startswith("MEASURE_FAILED:PermissionError")
        for row in failures
    )

    with (log_root / "DELETE_EXECUTION_LOG.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        executions = list(csv.DictReader(handle))
    assert not any(
        row["delete_id"] == "D_MEASURE_FAIL" and row["status"] == "STARTED"
        for row in executions
    )
    assert any(
        row["delete_id"] == "D_DELETE_OK" and row["status"] == "DELETED"
        for row in executions
    )
