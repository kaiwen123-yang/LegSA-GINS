"""Bounded tests for canonical541 raw checkpoint publication."""

from __future__ import annotations

import csv
import importlib.util
import json
import os
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.canonical541 import raw_audit
from legsa_gins.paper_rebuild.evidence import BY2_RAW_RELATIVE_PATHS, BY2_TRACE_RELATIVE_PATH
from legsa_gins.paper_rebuild.manifest import sha256_file


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    raw_root = tmp_path / "raw"
    output_root = tmp_path / "audit"
    raw_root.mkdir()
    output_root.mkdir()
    rows = []
    for index, relative in enumerate(BY2_RAW_RELATIVE_PATHS):
        source = raw_root / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(f"locked BY2 source {index:02d}\n".encode("utf-8"))
        rows.append({
            "relative_path": relative,
            "size_bytes": source.stat().st_size,
            "sha256": sha256_file(source),
            "line_count_or_file_type": "1",
            "role": "evaluation_reference" if relative == BY2_TRACE_RELATIVE_PATH else "raw_source",
            "dataset": "BY2",
            "immutable": "true",
            "mtime_ns": source.stat().st_mtime_ns,
        })
    lock = tmp_path / "RAW_FILE_HASH_LOCK.csv"
    with lock.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return raw_root, lock, output_root, sha256_file(lock)


def _run(raw_root: Path, lock: Path, output: Path, lock_sha: str, *, phase: str = "PRE_PROVIDER"):
    return raw_audit.write_raw_checkpoint(
        raw_root=raw_root,
        hash_lock_path=lock,
        expected_lock_sha256=lock_sha,
        output_root=output,
        phase=phase,
        expected_full_lock_rows=22,
    )


def test_raw_checkpoint_verifies_exact_22_and_binds_trace_role(tmp_path):
    raw_root, lock, output, lock_sha = _fixture(tmp_path)
    summary = _run(raw_root, lock, output, lock_sha)

    assert summary["passed"] is True
    assert summary["expected"] == summary["verified"] == 22
    assert summary["trace_read_role"] == raw_audit.TRACE_AUDIT_ROLE
    assert summary["trace_provider_or_solver_input"] is False
    assert summary["trace_used_online"] is False
    assert summary["directory_discovery_used"] is False
    assert set(summary["verified_hashes"]) == set(BY2_RAW_RELATIVE_PATHS)

    csv_path = output / "CANONICAL541_RAW_22_PRE_PROVIDER.csv"
    json_path = output / "CANONICAL541_RAW_22_PRE_PROVIDER.json"
    assert csv_path.is_file() and json_path.is_file()
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 22
    trace = next(row for row in rows if row["relative_path"] == BY2_TRACE_RELATIVE_PATH)
    assert trace["source_role"] == raw_audit.TRACE_AUDIT_ROLE
    assert all(row["status"] == "PASS" for row in rows)
    assert json.loads(json_path.read_text(encoding="utf-8"))["checkpoint_pair_complete"] is True


def test_raw_checkpoint_accepts_only_four_frozen_phases(tmp_path):
    raw_root, lock, output, lock_sha = _fixture(tmp_path)
    with pytest.raises(raw_audit.RawCheckpointError, match="unsupported raw checkpoint phase"):
        _run(raw_root, lock, output, lock_sha, phase="pre_provider")
    assert list(output.iterdir()) == []


def test_raw_checkpoint_rejects_even_confined_symlink(tmp_path):
    raw_root, lock, output, lock_sha = _fixture(tmp_path)
    relative = BY2_RAW_RELATIVE_PATHS[0]
    source = raw_root / relative
    real = source.with_name(source.name + ".real")
    source.rename(real)
    source.symlink_to(real.name)

    with pytest.raises(raw_audit.RawCheckpointError) as caught:
        _run(raw_root, lock, output, lock_sha)
    assert caught.value.summary["symlink_escape"] == 1
    report = json.loads((output / "CANONICAL541_RAW_22_PRE_PROVIDER.json").read_text(encoding="utf-8"))
    assert report["passed"] is False
    assert report["symlink_escape"] == 1


def test_raw_checkpoint_records_hash_mutation_then_fails_closed(tmp_path):
    raw_root, lock, output, lock_sha = _fixture(tmp_path)
    (raw_root / BY2_RAW_RELATIVE_PATHS[3]).write_bytes(b"mutated\n")

    with pytest.raises(raw_audit.RawCheckpointError) as caught:
        _run(raw_root, lock, output, lock_sha)
    assert caught.value.summary["mismatch"] == 1
    assert caught.value.summary["raw_mutation"] == 1
    report = json.loads((output / "CANONICAL541_RAW_22_PRE_PROVIDER.json").read_text(encoding="utf-8"))
    assert report["verified"] == 21
    assert report["passed"] is False


def test_raw_checkpoint_rejects_non_exact_by2_lock_set(tmp_path):
    raw_root, lock, output, _ = _fixture(tmp_path)
    rows = list(csv.DictReader(lock.open("r", encoding="utf-8", newline="")))
    rows[-1]["dataset"] = "BY3"
    with lock.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    with pytest.raises(raw_audit.RawCheckpointError, match="path set is not exact"):
        _run(raw_root, lock, output, sha256_file(lock))
    assert list(output.iterdir()) == []


def test_raw_checkpoint_pair_publication_rolls_back_first_replace(tmp_path, monkeypatch):
    raw_root, lock, output, lock_sha = _fixture(tmp_path)
    original_replace = os.replace
    calls = 0

    def fail_second(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second publication failure")
        return original_replace(source, destination)

    monkeypatch.setattr(raw_audit.os, "replace", fail_second)
    with pytest.raises(OSError, match="injected second publication failure"):
        _run(raw_root, lock, output, lock_sha)
    assert not (output / "CANONICAL541_RAW_22_PRE_PROVIDER.csv").exists()
    assert not (output / "CANONICAL541_RAW_22_PRE_PROVIDER.json").exists()


def test_raw_checkpoint_is_one_shot_and_does_not_overwrite(tmp_path):
    raw_root, lock, output, lock_sha = _fixture(tmp_path)
    first = _run(raw_root, lock, output, lock_sha)
    before = (output / "CANONICAL541_RAW_22_PRE_PROVIDER.json").read_bytes()
    with pytest.raises(raw_audit.RawCheckpointError, match="immutable and already exists"):
        _run(raw_root, lock, output, lock_sha)
    assert (output / "CANONICAL541_RAW_22_PRE_PROVIDER.json").read_bytes() == before
    assert first["passed"] is True


def test_raw_checkpoint_resume_revalidates_without_overwrite(tmp_path):
    raw_root, lock, output, lock_sha = _fixture(tmp_path)
    _run(raw_root, lock, output, lock_sha)
    before_csv = (output / "CANONICAL541_RAW_22_PRE_PROVIDER.csv").read_bytes()
    before_json = (output / "CANONICAL541_RAW_22_PRE_PROVIDER.json").read_bytes()
    resumed = raw_audit.ensure_raw_checkpoint(
        raw_root=raw_root, hash_lock_path=lock,
        expected_lock_sha256=lock_sha, output_root=output,
        phase="PRE_PROVIDER", expected_full_lock_rows=22,
    )
    assert resumed["resume_revalidated"] is True
    assert (output / "CANONICAL541_RAW_22_PRE_PROVIDER.csv").read_bytes() == before_csv
    assert (output / "CANONICAL541_RAW_22_PRE_PROVIDER.json").read_bytes() == before_json


def test_raw_checkpoint_resume_detects_post_checkpoint_raw_mutation(tmp_path):
    raw_root, lock, output, lock_sha = _fixture(tmp_path)
    _run(raw_root, lock, output, lock_sha)
    (raw_root / BY2_RAW_RELATIVE_PATHS[2]).write_bytes(b"mutated after checkpoint\n")
    with pytest.raises(raw_audit.RawCheckpointError, match="revalidation failed"):
        raw_audit.ensure_raw_checkpoint(
            raw_root=raw_root, hash_lock_path=lock,
            expected_lock_sha256=lock_sha, output_root=output,
            phase="PRE_PROVIDER", expected_full_lock_rows=22,
        )


def test_four_helper_outputs_satisfy_terminal_raw_checkpoint_audit(tmp_path):
    raw_root, lock, _, lock_sha = _fixture(tmp_path)
    stage = tmp_path / "CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX"
    audits = stage / "16_AUDITS"
    audits.mkdir(parents=True)
    for phase in raw_audit.RAW_CHECKPOINT_PHASES:
        raw_audit.write_raw_checkpoint(
            raw_root=raw_root,
            hash_lock_path=lock,
            expected_lock_sha256=lock_sha,
            output_root=audits,
            phase=phase,
            expected_full_lock_rows=22,
        )

    script = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/audit_canonical541.py"
    spec = importlib.util.spec_from_file_location("canonical541_raw_audit_integration", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    result = module._verify_raw_checkpoints(stage)
    assert result["checkpoint_count"] == 4
    assert result["verified_each"] == 22
    assert result["raw_mutation"] == 0
