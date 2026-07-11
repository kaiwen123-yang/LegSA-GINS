"""Atomic finalization must never expose PASS before manifest verification."""

import json
from pathlib import Path

import pytest

from scripts.paper_rebuild import audit_clean1r1c_by2 as audit_module


def _audit() -> dict[str, object]:
    return {
        "schema_version": "paper-rebuild-clean1r1c-final-audit-v1",
        "terminal_status": audit_module.PASS_STATUS,
        "gates": {"fixture": True},
    }


def test_manifest_failure_does_not_publish_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stage = tmp_path / "stage"
    (stage / "08_EVIDENCE_AUDIT").mkdir(parents=True)
    (stage / "input.txt").write_text("frozen\n", encoding="utf-8")

    def fail_verification(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected manifest verification failure")

    monkeypatch.setattr(audit_module, "_verify_manifest_rows", fail_verification)
    with pytest.raises(RuntimeError, match="injected"):
        audit_module._finalize_evidence(stage, _audit(), "pending\n", "review\n")

    assert not (stage / "08_EVIDENCE_AUDIT/FINALIZED").exists()
    assert not list(stage.rglob("COMPLETION_SENTINEL.json"))
    hidden_audits = list(stage.rglob("FINAL_AUDIT.json"))
    assert len(hidden_audits) == 1
    assert json.loads(hidden_audits[0].read_text(encoding="utf-8"))[
        "terminal_status"
    ] == audit_module.PENDING_FINALIZATION_STATUS
    with pytest.raises(
        RuntimeError,
        match="BLOCKED_CLEAN1R1C_FINALIZATION_ATTEMPT_EXISTS",
    ):
        audit_module._finalize_evidence(
            stage, _audit(), "second attempt\n", "review\n"
        )
    assert len(
        list((stage / "08_EVIDENCE_AUDIT").glob(".FINALIZED.attempt-*"))
    ) == 1
    assert not (stage / "08_EVIDENCE_AUDIT/FINALIZED").exists()
    assert not list(stage.rglob("COMPLETION_SENTINEL.json"))


def test_verified_manifest_publishes_one_completion_sentinel(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    (stage / "08_EVIDENCE_AUDIT").mkdir(parents=True)
    (stage / "input.txt").write_text("frozen\n", encoding="utf-8")

    final = audit_module._finalize_evidence(
        stage, _audit(), "pending\n", "review\n"
    )

    sentinel = json.loads(
        (final / "COMPLETION_SENTINEL.json").read_text(encoding="utf-8")
    )
    assert sentinel["terminal_status"] == audit_module.PASS_STATUS
    assert sentinel["manifest_verified_before_atomic_publication"] is True
    assert not list((stage / "08_EVIDENCE_AUDIT").glob(".FINALIZED.attempt-*"))
