"""Finalization tests use a completed purge of disposable synthetic fixture files."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild import storage_purge as purge


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/storage_purge_finalize_ledger.py"
SPEC = importlib.util.spec_from_file_location("storage_purge_finalize_fixture", SCRIPT)
finalizer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(finalizer)


@pytest.fixture
def closed(tmp_path):
    clean, code = tmp_path / "clean", tmp_path / "code"
    run = clean / "stages/CLEAN5_DEGSUBSET_BY2/03_RUNS/CLEAN5_DEGSUBSET_CAL/RUN_1"
    run.mkdir(parents=True)
    code.mkdir()
    (run / "KF_GINS_Navresult.nav").write_bytes(b"synthetic nav fixture")
    (run / "KF_GINS_STD.txt").write_bytes(b"synthetic std fixture")
    (run / "RUN_MANIFEST.json").write_bytes(b"{}")
    policy = code / "configs/paper_rebuild/clean6/STORAGE_PURGE_POLICY.yaml"
    policy.parent.mkdir(parents=True)
    policy.write_bytes((SCRIPT.parents[2] / "configs/paper_rebuild/clean6/STORAGE_PURGE_POLICY.yaml").read_bytes())
    closure = tmp_path / "closure.json"
    closure.write_text(json.dumps(dict(schema_version="clean6.storage_reference_closure.v1",
                                      keep_files=[], keep_dirs=[], required_paths=[])))
    audit = clean / "storage_purge/20260911T010203Z"
    utility = purge.StoragePurge(clean, code, policy, closure, audit)
    utility.plan(hash_workers=1)
    utility.gate()
    utility.quarantine_files()
    _, binding = utility._ledger()
    c5 = audit / "C5_RECEIPT.json"
    c5.write_text(json.dumps(dict(binding, gates={"C5": "PASS"},
                                 checks={key: "PASS" for key in purge.C5_CHECKS})))
    utility.purge(c5)
    before, after = audit / "FREE_SPACE_BEFORE.json", audit / "FREE_SPACE_AFTER.json"
    before.write_bytes(b'{ "time_utc": "2026-09-11T01:02:03+00:00", "filesystem_alias": "G: / <CLEAN_ROOT>", "available_bytes": 10, "free_bytes" : 10, "total_bytes": 100, "note": "before" }\n')
    after.write_bytes(b'{\n  "time_utc": "2026-09-11T01:03:04+00:00", "filesystem_alias": "G: / <CLEAN_ROOT>", "available_bytes": 52, "free_bytes": 52, "total_bytes": 100, "note": "after"\n}\n')
    archive = code / "docs/paper_rebuild/purge/DELETION_LEDGER_20260911T010203Z.json.gz"
    return dict(clean_root=clean, code_root=code, policy=policy, closure=audit / "REFERENCE_CLOSURE.json", audit_root=audit,
                c5_receipt=c5, before_free_space=before, after_free_space=after, archive_path=archive)


def read_record(closed, name):
    return json.loads((closed["audit_root"] / name).read_text())


def edit_record(closed, name, mutate):
    path = closed["audit_root"] / name
    value = json.loads(path.read_text())
    mutate(value)
    path.write_text(json.dumps(value))


def rewrite_journal(closed, mutate):
    path = closed["audit_root"] / "JOURNAL.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    mutate(events)
    previous = "0" * 64
    for index, event in enumerate(events, 1):
        event.pop("event_sha256", None)
        event.update(sequence=index, previous_sha256=previous)
        event["event_sha256"] = purge._digest(purge._json_bytes(event))
        previous = event["event_sha256"]
    path.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events))


def test_final_ledger_preserves_control_and_gzip_literal_bytes_without_payload_reads(closed, monkeypatch):
    control_path = closed["audit_root"] / "DELETION_LEDGER.json"
    control_bytes = control_path.read_bytes()
    control = json.loads(control_bytes)
    monkeypatch.setattr(purge, "hash_file", lambda *a, **k: pytest.fail("finalization must not read payloads"))
    monkeypatch.setattr(purge.StoragePurge, "_references", lambda *a, **k: pytest.fail("no package rehash"))
    outcome = finalizer.finalize(**closed)
    final_path = closed["audit_root"] / "FINAL/DELETION_LEDGER.json"
    literal = final_path.read_bytes()
    archive = closed["archive_path"].read_bytes()
    final = json.loads(literal)
    assert outcome["file_count"] == 2 and final["logical_bytes"] == control["candidate_bytes"]
    assert control_path.read_bytes() == control_bytes
    assert gzip.decompress(archive) == literal and archive[4:8] == b"\x00" * 4
    assert final["sources"]["control_ledger"]["sha256"] == hashlib.sha256(control_bytes).hexdigest()
    for old, new in zip(control["entries"], final["entries"]):
        assert {key: new[key] for key in old} == old
        assert set(new["operation_event_sha256"]) == set(finalizer.ACTION_ORDER)
        assert len(new["operation_event_history"]) == 4
        assert new["move_prepared_at_utc"] <= new["quarantine_verified_at_utc"]
        assert new["purge_prepared_at_utc"] <= new["purge_recorded_at_utc"]
    for phase in ["before", "after"]:
        assert final["free_space_evidence"][phase]["raw_utf8_text"].encode() == closed[phase + "_free_space"].read_bytes()
    assert str(closed["clean_root"]) not in literal.decode()
    assert finalizer.finalize(**closed) == outcome  # Deterministic existing-byte verification.


def test_recovered_event_is_explicit_and_times_remain_journal_bounds(closed):
    def mark(events):
        for event in events:
            if event["action"] in {"MOVED_HASH_VERIFIED", "PURGED"}:
                event["recovered_after_prepare"] = True
    rewrite_journal(closed, mark)
    finalizer.finalize(**closed)
    final = read_record(closed, "FINAL/DELETION_LEDGER.json")
    assert all(row["recovered_after_prepare"] == {"quarantine_verification": True, "purge_record": True}
               for row in final["entries"])
    assert final["operation_time_semantics"]["timestamps_are_durable_journal_observations_not_exact_operation_times"]


@pytest.mark.parametrize("name,field,value", [
    ("GATE_PRE_MOVE.json", "candidate_count", 3),
    ("GATE_PRE_MOVE.json", "keep_match_count", 1),
    ("GATE_QUARANTINE.json", "verified_files", 1),
    ("GATE_QUARANTINE.json", "exact_quarantine_set", False),
    ("PURGE_RESULT.json", "purged_files", 1),
    ("PURGE_RESULT.json", "purged_logical_bytes", 0),
    ("PURGE_RESULT.json", "original_directories_retained", False),
])
def test_incomplete_count_or_gate_evidence_produces_no_final_outputs(closed, name, field, value):
    edit_record(closed, name, lambda obj: obj.update({field: value}))
    with pytest.raises(purge.PurgeError):
        finalizer.finalize(**closed)
    assert not (closed["audit_root"] / "FINAL").exists() and not closed["archive_path"].exists()


@pytest.mark.parametrize("kind", ["broken_hash", "missing_purged", "duplicate_purged", "bad_order", "non_utc_time"])
def test_invalid_hash_chain_or_event_coverage_rejected(closed, kind):
    if kind == "broken_hash":
        path = closed["audit_root"] / "JOURNAL.jsonl"
        events = path.read_text().splitlines()
        event = json.loads(events[0])
        event["event_sha256"] = "0" * 64
        events[0] = json.dumps(event)
        path.write_text("\n".join(events) + "\n")
    else:
        def mutate(events):
            if kind == "missing_purged":
                events.pop()
            elif kind == "duplicate_purged":
                events.append(dict(events[-1]))
            elif kind == "bad_order":
                events[0], events[1] = events[1], events[0]
            else:
                events[0]["time_utc"] = "2026-09-11T01:02:03"
        rewrite_journal(closed, mutate)
    with pytest.raises(purge.PurgeError):
        finalizer.finalize(**closed)
    assert not closed["archive_path"].exists()


def test_c5_receipt_literal_hash_must_match_successful_purge(closed):
    path = closed["c5_receipt"]
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(purge.PurgeError, match="C5 literal bytes"):
        finalizer.finalize(**closed)


def test_failed_c5_never_finalizes(closed):
    value = json.loads(closed["c5_receipt"].read_text())
    value["checks"]["repository_record_tests"] = "FAIL"
    closed["c5_receipt"].write_text(json.dumps(value))
    with pytest.raises(purge.PurgeError, match="C5"):
        finalizer.finalize(**closed)


def test_archive_scope_and_symlink_guards(closed, tmp_path):
    wrong = dict(closed, archive_path=tmp_path / "wrong.json.gz")
    with pytest.raises(purge.PurgeError, match="exact timestamped"):
        finalizer.finalize(**wrong)
    destination = closed["archive_path"].parent
    destination.parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    destination.symlink_to(outside, target_is_directory=True)
    with pytest.raises(purge.PurgeError, match="symlink"):
        finalizer.finalize(**closed)


def test_output_collision_never_overwrites_or_writes_the_other_output(closed):
    archive = closed["archive_path"]
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"preexisting unrelated archive")
    with pytest.raises(purge.PurgeError, match="different bytes"):
        finalizer.finalize(**closed)
    assert archive.read_bytes() == b"preexisting unrelated archive"
    assert not (closed["audit_root"] / "FINAL").exists()


def test_resume_after_final_json_written_before_archive(closed, monkeypatch):
    write = finalizer._write_new
    def interrupted(path, data):
        if path == closed["archive_path"]:
            raise OSError("fixture interruption before archive create")
        return write(path, data)
    monkeypatch.setattr(finalizer, "_write_new", interrupted)
    with pytest.raises(OSError):
        finalizer.finalize(**closed)
    final_path = closed["audit_root"] / "FINAL/DELETION_LEDGER.json"
    original = final_path.read_bytes()
    monkeypatch.setattr(finalizer, "_write_new", write)
    finalizer.finalize(**closed)
    assert final_path.read_bytes() == original
    assert gzip.decompress(closed["archive_path"].read_bytes()) == original


@pytest.mark.parametrize("field", ["closure", "c5_receipt", "before_free_space", "after_free_space"])
def test_required_inputs_must_use_fixed_audit_filenames(closed, tmp_path, field):
    copy = tmp_path / (field + ".json")
    copy.write_bytes(closed[field].read_bytes())
    with pytest.raises(purge.PurgeError, match="fixed audit file"):
        finalizer.finalize(**dict(closed, **{field: copy}))
    assert not (closed["audit_root"] / "FINAL").exists()


def test_source_alias_cannot_fall_back_to_external_basename(closed, tmp_path):
    copy = tmp_path / "external_policy.yaml"
    copy.write_bytes(closed["policy"].read_bytes())
    with pytest.raises(purge.PurgeError, match="must have a CLEAN_ROOT"):
        finalizer.finalize(**dict(closed, policy=copy))


@pytest.mark.parametrize("field,value", [
    ("available_bytes", -1), ("available_bytes", 1.5), ("available_bytes", True),
    ("free_bytes", "10"), ("total_bytes", None),
    ("filesystem_alias", "G:"), ("time_utc", "2026-09-11T01:02:03"),
    ("time_utc", "2026-09-11T09:02:03+08:00"),
])
def test_free_space_schema_is_checked_before_any_final_output(closed, field, value):
    path = closed["before_free_space"]
    record = json.loads(path.read_text())
    record[field] = value
    path.write_text(json.dumps(record))
    with pytest.raises(purge.PurgeError):
        finalizer.finalize(**closed)
    assert not (closed["audit_root"] / "FINAL").exists()


@pytest.mark.parametrize("local_path", [
    "/mnt/g/private/data", "opened=/home/user/file", "C:\\Users\\name\\file.json",
    "G:/local/data", "\\\\server\\share\\file", "file:///home/user/local.json",
])
def test_local_absolute_path_content_is_not_embedded_in_archive(closed, local_path):
    path = closed["after_free_space"]
    record = json.loads(path.read_text())
    record["nested"] = {"notes": ["safe", local_path]}
    path.write_text(json.dumps(record))
    with pytest.raises(purge.PurgeError, match="local absolute path"):
        finalizer.finalize(**closed)
    assert not closed["archive_path"].exists()


def test_missing_free_space_field_and_non_json_are_rejected(closed):
    path = closed["after_free_space"]
    record = json.loads(path.read_text())
    del record["available_bytes"]
    path.write_text(json.dumps(record))
    with pytest.raises(purge.PurgeError, match="available_bytes"):
        finalizer.finalize(**closed)
    path.write_bytes(b"not JSON\n")
    with pytest.raises(purge.PurgeError, match="UTF-8 JSON"):
        finalizer.finalize(**closed)
