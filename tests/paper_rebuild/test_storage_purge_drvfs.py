"""Only synthetic tmp_path candidates are renamed/unlinked by these tests."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import xml.etree.ElementTree as ET

import pytest

from legsa_gins.paper_rebuild import storage_purge as base
from legsa_gins.paper_rebuild import storage_purge_drvfs as mod


P07 = "stages/CLEAN5_DEGSUBSET_BY2/03_RUNS/CLEAN5_DEGSUBSET_CAL/RUN_00001"


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def write_json(path, value):
    return put(path, base._json_bytes(value))


@pytest.fixture
def world(tmp_path, monkeypatch):
    clean, code = tmp_path / "clean", tmp_path / "code"
    clean.mkdir()
    code.mkdir()
    canonical = clean / "stages/CLEAN3_CANONICAL/.attempt_synthetic"
    canonical.mkdir(parents=True)
    policy_rel = "configs/paper_rebuild/clean6/STORAGE_PURGE_POLICY.yaml"
    policy = put(code / policy_rel, (Path(__file__).resolve().parents[2] / policy_rel).read_bytes())
    audit = clean / "storage_purge/20260911T062436Z"
    old_audit = clean / "storage_purge/20260911T040000Z"
    closure = write_json(audit / "REFERENCE_CLOSURE.json", dict(
        schema_version="clean6.storage_reference_closure.v1", keep_files=[], keep_dirs=[],
        required_paths=[], protected_dir_entries=[], superseded_attempt_dirs=[],
        clean4_nonfinal_attempt_dirs=[], source_documents_sha256={}, frozen_source_sha256={},
        seal_sources=[]))
    candidates = [put(clean / P07 / name, data) for name, data in
                  (("KF_GINS_Navresult.nav", b"fixture-A\n"), ("KF_GINS_STD.txt", b"fixture-BB\n"))]
    record = put(clean / P07 / "RUN_MANIFEST.json", b'{"synthetic_fixture": true}\n')
    utility = base.StoragePurge(clean, code, policy, closure, audit)
    entries = []
    for path in candidates:
        s = path.stat()
        rel = path.relative_to(clean).as_posix()
        classification = utility.classify(rel, s)
        entries.append(dict(original_relative_path=rel, size_bytes=s.st_size,
                            device=s.st_dev, inode=s.st_ino, mtime_ns=s.st_mtime_ns, nlink=s.st_nlink,
                            classification=classification[0], family=classification[2], file_class=classification[3],
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), hash_evidence="SYNTHETIC_FIXTURE",
                            seal_provenance=[], quarantine_timestamp=old_audit.name,
                            quarantine_relative_path="_PURGE_PENDING/" + old_audit.name + "/" + rel))
    old_plan = base._csv_bytes(entries, base.PLAN_COLUMNS)
    old = dict(schema_version=base.VERSION, phase="PLANNED", quarantine_timestamp=old_audit.name,
               policy_sha256=base._digest(policy.read_bytes()), closure_sha256=base._digest(closure.read_bytes()),
               plan_sha256=base._digest(old_plan), entries=entries, candidate_count=2,
               candidate_bytes=sum(r["size_bytes"] for r in entries))
    write_json(old_audit / "DELETION_LEDGER.json", old)
    put(old_audit / "DELETION_PLAN.csv", old_plan)
    put(old_audit / "REFERENCE_CLOSURE.json", closure.read_bytes())
    put(old_audit / "JOURNAL.jsonl", b"")
    origin = dict(audit=utility.portable(old_audit), ledger_sha256=base._digest(base._read(old_audit / "DELETION_LEDGER.json")),
                  plan_sha256=base._digest(old_plan), closure_sha256=old["closure_sha256"],
                  policy_sha256=old["policy_sha256"], journal_sha256=base._digest(b""))
    updated = [dict(row, quarantine_timestamp=audit.name,
                    quarantine_relative_path="_PURGE_PENDING/" + audit.name + "/" + row["original_relative_path"]) for row in entries]
    plan = base._csv_bytes(updated, base.PLAN_COLUMNS)
    ledger = dict(old, entries=updated, quarantine_timestamp=audit.name, plan_sha256=base._digest(plan),
                  origin_b=origin, continuation_strategy=mod.STRATEGY,
                  candidate_payload_rehashed=False, candidate_selection_recomputed=False)
    write_json(audit / "DELETION_LEDGER.json", ledger)
    put(audit / "DELETION_PLAN.csv", plan)
    calls = []
    def command(self, args, log_name):
        calls.append((args, log_name))
        put(self.audit / log_name, b"synthetic subprocess transcript\n")
        if "pytest" in args:
            suite = ET.Element("testsuite", tests="20", failures="0", errors="0", skipped="0")
            for number in range(20):
                ET.SubElement(suite, "testcase", name=f"synthetic_{number}")
            put(self.audit / "C5_TESTS.xml", ET.tostring(suite))
        else:
            output = Path(args[args.index("--output") + 1])
            result = dict(status="PASS", checks={k: "PASS" for k in mod.RECORD_CHECKS}, records={},
                          solver_invocations=0, evaluator_invocations=0, raw_content_open_count=0)
            if "--baseline" in args:
                result.update(records_identical_to_baseline=True,
                              baseline_sha256=base._digest(base._read(self.audit / "RECORDS_BASELINE.json")))
            write_json(output, result)
    monkeypatch.setattr(mod.DrvfsStoragePurge, "_code_identity", lambda self: None)
    monkeypatch.setattr(mod.DrvfsStoragePurge, "_command", command)
    def instance():
        return mod.DrvfsStoragePurge(clean, code, policy, closure, audit, code_commit="a" * 40,
                                    canonical_attempt=canonical, metadata_workers=2)
    return SimpleNamespace(clean=clean, code=code, policy=policy, closure=closure, audit=audit,
                           old_audit=old_audit, candidates=candidates, record=record,
                           ledger=ledger, calls=calls, instance=instance, command=command)


def test_success_is_bound_metadata_only_and_retains_all_original_directories(world, monkeypatch):
    original_read = base._read
    def no_payload(path):
        if Path(path).name in {"KF_GINS_Navresult.nav", "KF_GINS_STD.txt"}:
            pytest.fail("candidate payload read forbidden")
        return original_read(path)
    monkeypatch.setattr(base, "_read", no_payload)
    monkeypatch.setattr(base, "hash_file", lambda *a, **kw: pytest.fail("candidate hash forbidden"))
    utility = world.instance()
    old_controls = {name: (world.old_audit / name).read_bytes() for name in
                    ("DELETION_LEDGER.json", "DELETION_PLAN.csv", "REFERENCE_CLOSURE.json", "JOURNAL.jsonl")}
    result = utility.run()
    assert result["status"] == "PASS" and result["purged_files"] == 2
    assert result["purged_logical_bytes"] == sum(r["size_bytes"] for r in world.ledger["entries"])
    assert result["candidate_payload_rehashed"] is False and result["sha256_origin"] == "B_LEDGER"
    assert not utility.quarantine.exists()
    assert all(not path.exists() and path.parent.is_dir() for path in world.candidates)
    assert world.record.read_bytes() == b'{"synthetic_fixture": true}\n'
    assert all((world.old_audit / name).read_bytes() == content for name, content in old_controls.items())
    preflight_bytes = (world.audit / "GATE_PRE_MOVE.json").read_bytes()
    receipts = [base._load(world.audit / name) for name in mod.RECEIPT_FILES.values()]
    assert all(r["preflight_id"] == receipts[0]["preflight_id"] for r in receipts)
    assert all(r["binding"] == receipts[0]["binding"] for r in receipts)
    assert all(r["control_hashes"] == receipts[0]["control_hashes"] for r in receipts)
    assert all(r["preflight_literal_sha256"] == base._digest(preflight_bytes) for r in receipts[1:])
    assert receipts[2]["tests"] == {"passed": 20, "failed": 0, "errors": 0, "skipped": 0}
    events = [json.loads(line) for line in (world.audit / "JOURNAL.jsonl").read_text().splitlines()]
    assert len(events) == 8
    assert all(e["binding"] == result["journal_binding"] for e in events)
    assert all(e["payload_rehashed"] is False and e["sha256_origin"] == "B_LEDGER" for e in events)
    assert [e["action"] for e in events[:4]] == ["MOVE_PREPARED", "MOVED_METADATA_VERIFIED"] * 2
    for name in ("FREE_SPACE_BEFORE.json", "FREE_SPACE_AFTER.json"):
        assert base._load(world.audit / name)["filesystem_alias"] == "G: / <CLEAN_ROOT>"
    assert not (world.audit / "FREE_SPACE_AFTER_STOP.json").exists()
    assert base._load(world.audit / "DRVFS_TERMINAL.json")["status"] == "PURGED"
    assert len(world.calls) == 3
    pytest_args = world.calls[1][0]
    assert tuple(pytest_args[-5:]) == mod.C5_NODES
    assert "--baseline" in world.calls[2][0]


def test_probe_exception_does_not_launch_quarantine_or_c5(world, monkeypatch):
    utility = world.instance()
    failure = OSError("synthetic DrvFS probe failure")
    monkeypatch.setattr(utility, "_probe", Mock(side_effect=failure))
    quarantine, c5, purge = Mock(), Mock(), Mock()
    monkeypatch.setattr(utility, "_quarantine", quarantine)
    monkeypatch.setattr(utility, "_c5", c5)
    monkeypatch.setattr(utility, "_purge", purge)
    with pytest.raises(OSError) as exc:
        utility.run()
    assert exc.value is failure
    assert quarantine.call_count == c5.call_count == purge.call_count == 0
    assert all(p.exists() for p in world.candidates)
    assert not utility.quarantine.exists() and not world.calls
    assert base._load(world.audit / "DRVFS_TERMINAL.json")["status"] == "FAILED"
    assert base._load(world.audit / "QUARANTINE_PROGRESS.json")["moved_files"] == 0


@pytest.mark.parametrize("probe", [None, False, {"status": "FAIL", "exit_code": 0},
                                  {"status": "PASS", "exit_code": 9},
                                  {"status": "PASS", "exit_code": False}])
def test_unsuccessful_probe_return_cannot_launch_quarantine(world, monkeypatch, probe):
    utility = world.instance()
    monkeypatch.setattr(utility, "_probe", Mock(return_value=probe))
    quarantine = Mock()
    monkeypatch.setattr(utility, "_quarantine", quarantine)
    with pytest.raises(base.PurgeError, match="probe"):
        utility.run()
    quarantine.assert_not_called()
    assert not world.calls and all(path.exists() for path in world.candidates)


def test_exact_same_permit_object_reaches_all_three_physical_callbacks(world, monkeypatch):
    utility = world.instance()
    observed = []
    for name in ("_quarantine", "_c5", "_purge"):
        original = getattr(utility, name)
        def observe(*args, original=original):
            observed.append(args[0])
            return original(*args)
        monkeypatch.setattr(utility, name, observe)
    utility.run()
    assert len(observed) == 3 and observed[0] is observed[1] is observed[2]


@pytest.mark.parametrize("change", ["size", "inode", "hardlink", "symlink", "keep", "seal", "origin", "plan"])
def test_preflight_changes_stop_before_any_candidate_move(world, monkeypatch, change):
    utility = world.instance()
    if change == "size":
        world.candidates[0].write_bytes(b"changed size")
    elif change == "inode":
        replacement = world.candidates[0].with_suffix(".replacement")
        replacement.write_bytes(world.candidates[0].read_bytes())
        os.replace(replacement, world.candidates[0])
    elif change == "hardlink":
        os.link(world.candidates[0], world.clean / "retained-link")
    elif change == "symlink":
        world.candidates[0].unlink()
        world.candidates[0].symlink_to(world.record)
    elif change == "keep":
        utility.keep_files.add(world.ledger["entries"][0]["original_relative_path"])
    elif change == "seal":
        monkeypatch.setattr(utility, "_origin_and_seals", Mock(side_effect=base.PurgeError("changed seal")))
    elif change == "origin":
        (world.old_audit / "JOURNAL.jsonl").write_text("changed B metadata")
    else:
        (world.audit / "DELETION_PLAN.csv").write_text("changed plan")
    q = Mock()
    monkeypatch.setattr(utility, "_quarantine", q)
    with pytest.raises(base.PurgeError):
        utility.run()
    q.assert_not_called()
    assert not (world.audit / "JOURNAL.jsonl").exists()
    assert not utility.quarantine.exists()


def test_partial_rename_failure_stops_without_c5_purge_retry_or_rollback(world, monkeypatch):
    utility = world.instance()
    original = mod._plain_rename
    moved = []
    def rename(source, destination, expected):
        if "IO_PROBE" not in source.parts:
            moved.append(source)
            if len(moved) == 2:
                raise OSError("second candidate rename failed")
        return original(source, destination, expected)
    monkeypatch.setattr(mod, "_plain_rename", rename)
    with pytest.raises(OSError, match="second"):
        utility.run()
    assert len(moved) == 2 and len(world.calls) == 1
    assert not world.candidates[0].exists() and world.candidates[1].exists()
    assert (world.clean / world.ledger["entries"][0]["quarantine_relative_path"]).exists()
    assert base._load(world.audit / "DRVFS_TERMINAL.json")["moved_files"] == 1
    assert not (world.audit / "C5_RECEIPT.json").exists()
    assert not (world.audit / "PURGE_RESULT.json").exists()
    with pytest.raises(base.PurgeError, match="no resume"):
        world.instance().run()


@pytest.mark.parametrize("checkpoint", ["MOVED_METADATA_VERIFIED", "PURGED"])
def test_failure_after_physical_action_retains_pending_intent_without_retry(world, monkeypatch, checkpoint):
    utility = world.instance()
    append = utility._append
    attempts = []
    def fail_checkpoint(events, binding, action, row, **extra):
        if action == checkpoint:
            attempts.append(action)
            raise OSError("checkpoint unavailable after physical action")
        return append(events, binding, action, row, **extra)
    monkeypatch.setattr(utility, "_append", fail_checkpoint)
    with pytest.raises(OSError, match="checkpoint"):
        utility.run()
    assert len(attempts) == 1
    terminal = base._load(world.audit / "DRVFS_TERMINAL.json")
    first = world.ledger["entries"][0]
    assert not world.candidates[0].exists()
    if checkpoint == "MOVED_METADATA_VERIFIED":
        assert terminal["moved_files"] == 0
        assert terminal["pending_move_prepared"] == [first["original_relative_path"]]
        assert (world.clean / first["quarantine_relative_path"]).exists()
        assert len(world.calls) == 1
    else:
        assert terminal["moved_files"] == 2 and terminal["purged_files"] == 0
        assert terminal["pending_purge_prepared"] == [first["original_relative_path"]]
        assert not (world.clean / first["quarantine_relative_path"]).exists()
        assert (world.clean / world.ledger["entries"][1]["quarantine_relative_path"]).exists()


@pytest.mark.parametrize("failure", ["process", "skip", "nineteen", "record", "reference"])
def test_c5_failure_never_purges(world, monkeypatch, failure):
    utility = world.instance()
    original_references = utility._references
    def command(self, args, log_name):
        if "pytest" in args and failure == "process":
            raise base.PurgeError("pytest nonzero exit")
        world.command(self, args, log_name)
        if "pytest" in args and failure in {"skip", "nineteen"}:
            path = self.audit / "C5_TESTS.xml"
            root = ET.fromstring(path.read_bytes())
            if failure == "skip":
                ET.SubElement(root[0], "skipped")
                root.set("skipped", "1")
            else:
                root.remove(root[-1])
                root.set("tests", "19")
            path.write_bytes(ET.tostring(root))
        if "--baseline" in args and failure == "record":
            path = self.audit / "RECORDS_AFTER_QUARANTINE.json"
            value = base._load(path)
            value["records_identical_to_baseline"] = False
            write_json(path, value)
    def references(removed):
        if utility._phase == "C5" and failure == "reference":
            raise base.PurgeError("retained reference disappeared")
        return original_references(removed)
    monkeypatch.setattr(mod.DrvfsStoragePurge, "_command", command)
    monkeypatch.setattr(utility, "_references", references)
    with pytest.raises(base.PurgeError):
        utility.run()
    assert all((world.clean / row["quarantine_relative_path"]).exists() for row in world.ledger["entries"])
    assert not (world.audit / "PURGE_RESULT.json").exists()
    events = [json.loads(line) for line in (world.audit / "JOURNAL.jsonl").read_text().splitlines()]
    assert all(not e["action"].startswith("PURG") for e in events)


@pytest.mark.parametrize("target", ["preflight_literal", "plan", "ledger", "policy", "closure", "permit"])
def test_tampering_between_preflight_and_quarantine_prevents_move(world, monkeypatch, target):
    utility = world.instance()
    original = utility._quarantine
    def quarantine(permit):
        if target == "permit":
            from dataclasses import replace
            permit = replace(permit, preflight_id="substituted")
        else:
            path = {"preflight_literal": world.audit / "GATE_PRE_MOVE.json",
                    "plan": world.audit / "DELETION_PLAN.csv", "ledger": world.audit / "DELETION_LEDGER.json",
                    "policy": world.policy, "closure": world.closure}[target]
            path.write_bytes(path.read_bytes() + b"\n")
        return original(permit)
    monkeypatch.setattr(utility, "_quarantine", quarantine)
    with pytest.raises((base.PurgeError, ValueError)):
        utility.run()
    assert all(p.exists() for p in world.candidates)
    assert not (world.audit / "JOURNAL.jsonl").exists()


def test_unexpected_quarantine_file_blocks_purge_and_is_preserved(world, monkeypatch):
    utility = world.instance()
    original = utility._purge
    def purge(*args):
        put(utility.quarantine / "unexpected.bin", b"must not remove")
        return original(*args)
    monkeypatch.setattr(utility, "_purge", purge)
    with pytest.raises(base.PurgeError, match="exact set"):
        utility.run()
    assert (utility.quarantine / "unexpected.bin").read_bytes() == b"must not remove"
    assert all((world.clean / row["quarantine_relative_path"]).exists() for row in world.ledger["entries"])


@pytest.mark.parametrize("changed", ["c5_receipt", "journal", "metadata", "code"])
def test_post_c5_changes_prevent_any_unlink(world, monkeypatch, changed):
    utility = world.instance()
    purge = utility._purge
    def change(*args):
        if changed == "c5_receipt":
            path = world.audit / "C5_RECEIPT.json"
            path.write_bytes(path.read_bytes() + b"\n")
        elif changed == "journal":
            path = world.audit / "JOURNAL.jsonl"
            events = path.read_text().splitlines()
            first = json.loads(events[0])
            first["sha256"] = "f" * 64
            path.write_text(json.dumps(first) + "\n" + "\n".join(events[1:]) + "\n")
        elif changed == "metadata":
            path = world.clean / world.ledger["entries"][0]["quarantine_relative_path"]
            path.write_bytes(b"changed quarantined file")
        else:
            monkeypatch.setattr(utility, "_code_identity", Mock(side_effect=base.PurgeError("changed code commit")))
        return purge(*args)
    monkeypatch.setattr(utility, "_purge", change)
    with pytest.raises(base.PurgeError):
        utility.run()
    assert all((world.clean / row["quarantine_relative_path"]).exists() for row in world.ledger["entries"])


@pytest.mark.parametrize("kind", ["file", "dangling_link", "parent_link"])
def test_rename_destination_conflicts_and_symlink_parent_are_never_followed(tmp_path, kind):
    source = put(tmp_path / "source", b"fixture")
    outside = tmp_path / "outside"
    outside.mkdir()
    target = tmp_path / "dest/item"
    target.parent.mkdir()
    if kind == "file":
        target.write_bytes(b"existing")
    elif kind == "dangling_link":
        target.symlink_to(outside / "missing")
    else:
        target.parent.rmdir()
        target.parent.symlink_to(outside, target_is_directory=True)
    with pytest.raises((base.PurgeError, OSError)):
        mod._plain_rename(source, target, source.stat())
    assert source.read_bytes() == b"fixture"
    assert not (outside / "item").exists()


def test_rename_rejects_cross_filesystem_without_calling_os_rename(tmp_path, monkeypatch):
    source, target = put(tmp_path / "source", b"fixture"), tmp_path / "dest/item"
    before = source.stat()
    monkeypatch.setattr(mod.os, "fstat", lambda fd: SimpleNamespace(st_dev=before.st_dev + 1))
    rename = Mock()
    monkeypatch.setattr(mod.os, "rename", rename)
    with pytest.raises(base.PurgeError, match="cross-filesystem"):
        mod._plain_rename(source, target, before)
    rename.assert_not_called()


def test_command_nonzero_is_checked_and_fixed_environment_is_used(world, monkeypatch):
    utility = world.instance()
    # Bind the original production implementation, bypassing fixture subprocess stub.
    command = ORIGINAL_COMMAND.__get__(utility)
    runner = Mock(return_value=SimpleNamespace(returncode=3))
    monkeypatch.setattr(mod.subprocess, "run", runner)
    with pytest.raises(base.PurgeError, match="exit 3"):
        command(["/usr/bin/python3", "-m", "pytest"], "fixture_command.log")
    assert runner.call_count == 1
    kwargs = runner.call_args.kwargs
    assert kwargs["shell"] is False and kwargs["check"] is False
    assert kwargs["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert kwargs["env"]["LEGSA_CLEAN5_ROOT"] == str(world.clean)


def test_code_identity_checks_only_frozen_operation_paths_and_commit(world, monkeypatch):
    utility = world.instance()
    for relative in mod.CODE_FILES:
        if relative != "configs/paper_rebuild/clean6/STORAGE_PURGE_POLICY.yaml":
            put(world.code / relative, b"synthetic committed code\n")
    put(world.code / "unrelated_untracked.txt", b"allowed unrelated user work\n")
    frozen = {relative: (world.code / relative).read_bytes() for relative in mod.CODE_FILES}
    def git(args, **kwargs):
        assert kwargs["check"] is True
        if args[1] == "rev-parse":
            return SimpleNamespace(stdout=("a" * 40 + "\n").encode())
        return SimpleNamespace(stdout=frozen[args[2].split(":", 1)[1]])
    monkeypatch.setattr(mod.subprocess, "run", git)
    identity = ORIGINAL_IDENTITY.__get__(utility)
    identity()
    (world.code / mod.CODE_FILES[0]).write_bytes(b"changed operation code")
    with pytest.raises(base.PurgeError, match="dirty"):
        identity()


def test_driver_lock_covers_preflight_and_physical_stages(world):
    first, second = world.instance(), world.instance()
    with first._operation_lock():
        with pytest.raises(base.PurgeError, match="operation lock"):
            second.run()
    assert all(p.exists() for p in world.candidates)


ORIGINAL_COMMAND = mod.DrvfsStoragePurge._command
ORIGINAL_IDENTITY = mod.DrvfsStoragePurge._code_identity
