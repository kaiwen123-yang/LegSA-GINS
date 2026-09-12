"""Control-only continuation preserves exactly the previously admitted B set."""
import importlib.util
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild import storage_purge as storage
from test_storage_purge import world

spec = importlib.util.spec_from_file_location("continuation", Path(__file__).resolve().parents[2]
    / "scripts/paper_rebuild/storage_purge_continuation.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def prepared(world):
    world.candidate()
    world.candidate("unknown.bin", b"unknown")
    old = world.utility()
    old.plan(hash_workers=1)
    (old.audit / "JOURNAL.jsonl").write_bytes(b"")
    (old.audit / "STORAGE_INVENTORY_PARTITIONED.csv").write_bytes(
        (old.audit / "STORAGE_INVENTORY.csv").read_bytes())
    new = storage.StoragePurge(world.clean, world.code, world.policy, world.closure,
                              world.clean / "storage_purge/20260911T020304Z")
    return old, new


def call_import(old, new):
    return module.import_b(new, old.audit, storage._digest(storage._read(old.audit / "DELETION_LEDGER.json")),
                           storage._digest(storage._read(old.audit / "DELETION_PLAN.csv")))


def test_import_reads_no_payload_and_preserves_b_projection(world, monkeypatch):
    old, new = prepared(world)
    old_bytes = (old.audit / "DELETION_LEDGER.json").read_bytes()
    def forbidden(*args, **kwargs):
        raise AssertionError("candidate hash or inventory forbidden")
    monkeypatch.setattr(storage, "hash_file", forbidden)
    monkeypatch.setattr(storage.StoragePurge, "plan", forbidden)
    summary = call_import(old, new)
    before = json.loads(old_bytes)["entries"]
    after = new._ledger()[0]["entries"]
    omit = {"quarantine_timestamp", "quarantine_relative_path"}
    assert [{k:v for k,v in r.items() if k not in omit} for r in before] == [
        {k:v for k,v in r.items() if k not in omit} for r in after]
    assert summary["candidate_payload_read_count"] == 0
    assert (old.audit / "DELETION_LEDGER.json").read_bytes() == old_bytes
    assert not new.quarantine.exists()


def test_import_rejects_any_prior_move(world):
    old, new = prepared(world)
    (old.audit / "JOURNAL.jsonl").write_text(json.dumps({"action":"MOVED_HASH_VERIFIED"}) + "\n")
    with pytest.raises(storage.PurgeError, match="moved or purged"):
        call_import(old, new)
    assert not new.audit.exists()


def test_import_rejects_wrong_b_pin(world):
    old, new = prepared(world)
    with pytest.raises(storage.PurgeError, match="pinned B"):
        module.import_b(new, old.audit, "0"*64, "0"*64)
    assert not new.audit.exists()


def test_import_rejects_unbound_prepare_journal(world):
    old, new = prepared(world)
    (old.audit / "JOURNAL.jsonl").write_text(json.dumps({"action":"MOVE_PREPARED"}) + "\n")
    with pytest.raises(storage.PurgeError, match="B journal chain"):
        call_import(old, new)
    assert not new.audit.exists()


def test_import_rejects_nonempty_old_quarantine(world):
    old, new = prepared(world)
    old.quarantine.mkdir(parents=True)
    (old.quarantine / "unexpected").write_bytes(b"do not move")
    with pytest.raises(storage.PurgeError, match="not empty"):
        call_import(old, new)


@pytest.mark.parametrize("field", ["keep_files", "keep_dirs", "protected_dir_entries"])
def test_closure_cannot_shrink(field):
    old = {field:["stages/protected"], "required_paths":[]}
    with pytest.raises(storage.PurgeError, match="shrinks"):
        module.verify_closure_extension(old, {"required_paths":[]})


def test_closure_cannot_drop_or_retype_reference():
    with pytest.raises(storage.PurgeError, match="loses"):
        module.verify_closure_extension({"required_paths":[{"path":"a", "kind":"file"}]},
                                        {"required_paths":[{"path":"a", "kind":"directory"}]})


def test_closure_cannot_drop_document_pin():
    with pytest.raises(storage.PurgeError, match="source document pins"):
        module.verify_closure_extension({"source_documents_sha256":{"AGENTS.md":"a"},
                                        "required_paths":[]}, {"required_paths":[]})


def test_unknown_byte_change_is_rejected_before_audit_output(world):
    old, new = prepared(world)
    path = old.audit / "UNKNOWN_FILES.csv"
    path.write_bytes(path.read_bytes().replace(b",7,", b",8,"))
    with pytest.raises(storage.PurgeError, match="UNKNOWN counts or bytes"):
        call_import(old, new)
    assert not new.audit.exists()


def test_unknown_groups_partition_compound_extensions_and_precedence():
    rows = [dict(original_relative_path="stages/S/03_RUNS/logs/a.csv.gz", classification="UNKNOWN",
                 file_type="regular", size_bytes=10),
            dict(original_relative_path="stages/S/07_EVALUATION/FROZEN_EVALUATOR/b.csv", classification="UNKNOWN",
                 file_type="regular", size_bytes=20),
            dict(original_relative_path="stages/S/14_PLOTTING/noext", classification="UNKNOWN",
                 file_type="regular", size_bytes=5)]
    groups = module.unknown_groups(storage._csv_bytes(rows, list(rows[0])))
    assert [(r["extension"], r["directory_type"]) for r in groups] == [
        (".csv", "FROZEN_EVALUATOR"), (".csv.gz", "LOGS"), ("(none)", "PLOTTING_FIGURES_ATLAS")]
    assert sum(r["file_count"] for r in groups) == 3
    assert sum(r["logical_bytes"] for r in groups) == 35
