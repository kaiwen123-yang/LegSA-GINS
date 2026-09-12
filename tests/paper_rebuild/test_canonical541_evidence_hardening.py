import csv
import hashlib
import os
import zipfile

import pytest

from legsa_gins.paper_rebuild.canonical541 import evidence
from legsa_gins.paper_rebuild.canonical541.authorization import STAGE_ID


ROLE = {"a.txt": ("terminal_audit", "current_clean_audit")}


def _evidence_root(tmp_path, suffix="one"):
    attempt = tmp_path / STAGE_ID / f".attempt_{suffix}"
    attempt.mkdir(parents=True, exist_ok=True)
    return attempt / "17_FINAL_EVIDENCE"


def _closed(root):
    root.mkdir(); (root / "a.txt").write_text("alpha\n", encoding="utf-8")
    evidence.build_manifest(root, ROLE)
    return root


def test_manifest_rejects_unclassified_and_extra_payload(tmp_path):
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    with pytest.raises(evidence.EvidenceClosureError, match="classification mismatch"):
        evidence.build_manifest(tmp_path, {})
    evidence.build_manifest(tmp_path, ROLE)
    (tmp_path / "unlisted.txt").write_text("not bound\n", encoding="utf-8")
    with pytest.raises(evidence.EvidenceClosureError, match="entry set mismatch"):
        evidence.validate_stage_closure(tmp_path)


def test_manifest_rejects_payload_tamper(tmp_path):
    _closed(tmp_path / "closed")
    (tmp_path / "closed" / "a.txt").write_text("changed\n", encoding="utf-8")
    with pytest.raises(evidence.EvidenceClosureError, match="payload closure mismatch"):
        evidence.validate_stage_closure(tmp_path / "closed")


def test_manifest_rejects_symlink_payload(tmp_path):
    source = tmp_path / "source.txt"; source.write_text("source\n", encoding="utf-8")
    root = tmp_path / "root"; root.mkdir(); (root / "a.txt").symlink_to(source)
    with pytest.raises(evidence.EvidenceClosureError, match="symlink"):
        evidence.build_manifest(root, ROLE)


def test_curator_rejects_traversal_and_symlink_source(tmp_path):
    source = tmp_path / "source.txt"; source.write_text("source\n", encoding="utf-8")
    with pytest.raises(evidence.EvidenceClosureError, match="unsafe archive_path"):
        evidence.stage_curated_payloads(
            stage_evidence_root=_evidence_root(tmp_path, "traversal"), attempt_id="one",
            payloads=[evidence.PayloadSpec(source, "../escape", "audit", "current")],
        )
    link = tmp_path / "link.txt"; link.symlink_to(source)
    with pytest.raises(evidence.EvidenceClosureError, match="symlink"):
        evidence.stage_curated_payloads(
            stage_evidence_root=_evidence_root(tmp_path, "symlink"), attempt_id="two",
            payloads=[evidence.PayloadSpec(link, "link.txt", "audit", "current")],
        )


def test_atomic_promotion_failure_preserves_staging(tmp_path, monkeypatch):
    staging = _closed(tmp_path / ".staging_attempt")
    real_replace = evidence.os.replace

    def fail_once(source, destination):
        if str(source).endswith(".staging_attempt"):
            raise OSError("injected rename failure")
        return real_replace(source, destination)

    monkeypatch.setattr(evidence.os, "replace", fail_once)
    with pytest.raises(evidence.EvidenceClosureError, match="atomic promotion failed"):
        evidence.promote_finalized(staging_root=staging, finalized_root=tmp_path / "FINALIZED")
    assert staging.is_dir()
    assert not (tmp_path / "FINALIZED").exists()
    assert evidence.validate_stage_closure(staging)["sidecar_check"]


def test_finalize_curated_evidence_atomic_success(tmp_path):
    source = tmp_path / "report.json"; source.write_text("{}\n", encoding="utf-8")
    root = _evidence_root(tmp_path, "success"); root.mkdir()  # pre-created empty stage skeleton
    report = evidence.finalize_curated_evidence(
        stage_evidence_root=root, attempt_id="attempt_1",
        payloads=[evidence.PayloadSpec(source, "audits/report.json", "terminal_audit", "current_clean_audit")],
    )
    assert report["atomic_promotion"]
    assert not (root / ".staging_attempt_1").exists()
    assert (root / "FINALIZED").is_dir()


def test_nonempty_stage_evidence_skeleton_fails_closed(tmp_path):
    source = tmp_path / "report.json"; source.write_text("{}\n", encoding="utf-8")
    root = _evidence_root(tmp_path, "nonempty"); root.mkdir(); (root / "unexpected.txt").write_text("x")
    with pytest.raises(evidence.EvidenceClosureError, match="empty skeleton"):
        evidence.finalize_curated_evidence(
            stage_evidence_root=root, attempt_id="attempt_1",
            payloads=[evidence.PayloadSpec(source, "report.json", "audit", "current")],
        )
    assert (root / "unexpected.txt").is_file()


def test_zip_size_failure_rolls_back_attempt_file(tmp_path):
    root = _closed(tmp_path / "FINALIZED")
    output = tmp_path / "LegSA_GINS_CANONICAL541_FINAL_20260719T000001P0800.zip"
    with pytest.raises(evidence.EvidenceClosureError, match="exceeds size limit"):
        evidence.create_final_zip(finalized_root=root, zip_path=output, maximum_bytes=1)
    assert not output.exists()
    assert not output.with_suffix(".zip.sha256").exists()


def test_zip_validator_rejects_extra_and_traversal_entries(tmp_path):
    root = _closed(tmp_path / "FINALIZED")
    stage = evidence.validate_stage_closure(root)
    names = set(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as archive:
        for path in root.rglob("*"):
            if path.is_file(): archive.write(path, path.relative_to(root).as_posix())
        archive.writestr("../escape.txt", "bad")
    with pytest.raises(evidence.EvidenceClosureError, match="entry set mismatch"):
        evidence._validate_zip_exact(bad, stage, names)
