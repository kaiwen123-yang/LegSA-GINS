#!/usr/bin/env python3
"""Seal a completed drvfs purge from literal control records, with no payload I/O."""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from legsa_gins.paper_rebuild.storage_purge import (
    C5_CHECKS, StoragePurge, _digest, _exists, _fail, _json_bytes, _read, _write_new, _write_or_verify,
)
from legsa_gins.paper_rebuild.storage_purge_dispatch import (
    PreflightChallenge, _pairs, _validate,
)
from legsa_gins.paper_rebuild.storage_purge_drvfs import STORAGE_TEST_FILES, pytest_xml_counts

_spec = importlib.util.spec_from_file_location("original_storage_finalizer",
    Path(__file__).with_name("storage_purge_finalize_ledger.py"))
_old = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_old)

ACTIONS = ["MOVE_PREPARED", "MOVED_METADATA_VERIFIED", "PURGE_PREPARED", "PURGED"]
RECEIPTS = ["GATE_PRE_MOVE.json", "GATE_QUARANTINE.json", "C5_RECEIPT.json", "PURGE_RESULT.json"]


def validate_receipts(snapshots, control_binding):
    records = [json.loads(snapshots[name]) for name in RECEIPTS]
    pre = records[0]
    challenge = PreflightChallenge(pre["preflight_id"], _pairs(pre["binding"], "binding"),
                                   _pairs(pre["control_hashes"], "control_hashes", hashes=True))
    for key, value in control_binding.items():
        if pre["control_hashes"].get(key) != value:
            _fail("preflight does not bind the actual control bytes: " + key)
    previous = None
    verified = []
    for phase, gates, record in zip(("preflight", "quarantine", "c5", "purge"),
            (("IO_PROBE", "C1", "C2", "C3"), ("C4",), ("C5",), ("D", "C1", "C2", "C3", "C4", "C5")), records):
        kwargs = {} if previous is None else dict(preflight_sha256=verified[0].receipt_sha256,
                                                  previous_receipt_sha256=previous.receipt_sha256)
        validated = _validate(record, phase=phase, challenge=challenge, gates=gates, **kwargs)
        if phase != "preflight" and record.get("preflight_literal_sha256") != _digest(snapshots[RECEIPTS[0]]):
            _fail("downstream receipt does not bind literal preflight bytes")
        verified.append(validated)
        previous = validated
    return records


def enrich(control, events):
    grouped = {r["original_relative_path"]: [] for r in control["entries"]}
    for event in events:
        if event["original_relative_path"] not in grouped:
            _fail("journal path is outside the unchanged candidate set")
        grouped[event["original_relative_path"]].append(event)
    output = []
    for row in control["entries"]:
        history = grouped[row["original_relative_path"]]
        if [e["action"] for e in history] != ACTIONS:
            _fail("every entry needs exactly one ordered prepare/move/prepare/purge sequence")
        times = [_old._timestamp(e["time_utc"]) for e in history]
        if times != sorted(times):
            _fail("per-entry operation timestamps are not ordered")
        for event in history:
            if any(event[k] != row[k] for k in ("size_bytes", "sha256")):
                _fail("journal size or B SHA differs from the control entry")
        moved = history[1]
        if moved.get("payload_rehashed") is not False or moved.get("sha256_origin") != "B_LEDGER":
            _fail("move event does not explicitly identify reused B SHA")
        if any(moved.get(key) is not True for key in ("source_absent", "destination_present", "size_matches_ledger")):
            _fail("move event does not verify the three authorized postconditions")
        output.append(dict(row, terminal="PURGED", sha256_origin="B_LEDGER", payload_rehashed=False,
            move_prepared_at_utc=history[0]["time_utc"],
            quarantine_metadata_verified_at_utc=moved["time_utc"],
            purge_prepared_at_utc=history[2]["time_utc"], purged_recorded_at_utc=history[3]["time_utc"],
            operation_event_history=[{k:e[k] for k in ("sequence", "action", "time_utc", "event_sha256")}
                                     for e in history]))
    return output


def finalize(clean_root, code_root, policy, audit_root):
    utility = StoragePurge(clean_root, code_root, policy, Path(audit_root) / "REFERENCE_CLOSURE.json", audit_root)
    with utility._operation_lock():
        control, binding = utility._ledger()
        names = [*RECEIPTS, "DELETION_LEDGER.json", "DELETION_PLAN.csv", "REFERENCE_CLOSURE.json",
                 "JOURNAL.jsonl", "FREE_SPACE_BEFORE.json", "FREE_SPACE_AFTER.json",
                 "UNKNOWN_BY_CLASS.csv", "C5_TESTS.xml", "C5_STORAGE_REGRESSION.xml",
                 "C5_STORAGE_REGRESSION.stdout.log",
                 "RECORDS_BASELINE.json", "RECORDS_AFTER_QUARANTINE.json"]
        if control.get("planning_mode") != "FRESH_INVENTORY_POLICY_V2":
            names.append("CONTINUATION_IMPORT.json")
        else:
            names.append("PLANNING_SUMMARY.json")
            if control.get("candidate_selection_recomputed") is not True or "origin_b" in control:
                _fail("fresh B ledger mode is inconsistent")
            cache = control.get("hash_cache_source")
            if cache is not None:
                binding["hash_cache_source_sha256"] = cache["sha256"]
        snapshots = {name:_read(utility.audit / name) for name in names}
        pre, quarantine, c5, purge = validate_receipts(snapshots, binding)
        if (pre["binding"].get("audit") != utility.portable(utility.audit)
                or pre["binding"].get("rename_strategy") != "drvfs_plain_rename_b_sha256.v1"):
            _fail("preflight audit or strategy does not identify this continuation")
        for key in ("keep_match_count", "outside_stages_count", "invalidclassfamily_count"):
            _old._count(pre.get(key), 0, key)
        count, size = control["candidate_count"], control["candidate_bytes"]
        _old._count(pre.get("candidate_count"), count, "preflight candidates")
        _old._count(quarantine.get("verified_files"), count, "quarantine files")
        _old._count(purge.get("purged_files"), count, "purged files")
        _old._count(purge.get("purged_logical_bytes"), size, "purged bytes")
        if (quarantine.get("exact_quarantine_set") is not True
                or purge.get("original_directories_retained") is not True or _exists(utility.quarantine)):
            _fail("exact quarantine completion/removal or original directory retention failed")
        if (not (C5_CHECKS | {"reference_paths_readability", "storage_regression_tests"}) <= c5.get("checks", {}).keys()
                or any(v != "PASS" for v in c5["checks"].values())):
            _fail("C5 independent checks not all PASS")
        record_counts = pytest_xml_counts(snapshots["C5_TESTS.xml"], expected_count=20)
        for key, value in record_counts.items():
            _old._count(c5.get("tests", {}).get(key), value, "C5 record tests " + key)
        storage = c5.get("storage_regression_tests", {})
        if (storage.get("status") != "PASS" or storage.get("test_files") != list(STORAGE_TEST_FILES)
                or storage.get("xml_sha256") != _digest(snapshots["C5_STORAGE_REGRESSION.xml"])
                or storage.get("stdout_sha256") != _digest(snapshots["C5_STORAGE_REGRESSION.stdout.log"])):
            _fail("storage regression evidence/coverage does not match C5")
        storage_counts = pytest_xml_counts(snapshots["C5_STORAGE_REGRESSION.xml"])
        for key, value in storage_counts.items():
            _old._count(storage.get(key), value, "C5 storage regression " + key)
        _old._count(c5.get("reference_path_count"), len(pre["references"]), "C5 required reference paths")
        if (c5.get("xml_sha256") != _digest(snapshots["C5_TESTS.xml"])
                or c5.get("records_sha256") != _digest(snapshots["RECORDS_AFTER_QUARANTINE.json"])
                or pre.get("baseline_sha256") != _digest(snapshots["RECORDS_BASELINE.json"])):
            _fail("C5 source evidence bytes do not match its receipt")
        before_records = json.loads(snapshots["RECORDS_BASELINE.json"])
        after_records = json.loads(snapshots["RECORDS_AFTER_QUARANTINE.json"])
        if (after_records.get("status") != "PASS"
                or after_records.get("records_identical_to_baseline") is not True
                or after_records.get("baseline_sha256") != pre["baseline_sha256"]
                or before_records["records"] != after_records["records"]):
            _fail("retained decision/aggregate/CAL records changed")
        journal_binding = quarantine["journal_binding"]
        if journal_binding != purge["journal_binding"]:
            _fail("C4 and D journal bindings differ")
        for key, value in dict(binding, preflight_id=pre["preflight_id"],
                preflight_sha256=pre["receipt_sha256"],
                preflight_literal_sha256=_digest(snapshots["GATE_PRE_MOVE.json"])).items():
            if journal_binding.get(key) != value:
                _fail("journal does not bind the same preflight/control: " + key)
        events = utility._journal(journal_binding)
        entries = enrich(control, events)
        for phase in ("before", "after"):
            _old._free_space_literal(snapshots["FREE_SPACE_" + phase.upper() + ".json"])
        final = dict(schema_version="clean6.storage_purge_final_ledger.drvfs.v1",
            status="ALL_EXACT_LEDGER_FILES_DURABLY_RECORDED_PURGED", quarantine_timestamp=utility.timestamp,
            binding=binding, journal_binding=journal_binding, gates={"C"+str(i):"PASS" for i in range(1,6)},
            file_count=count, logical_bytes=size, entries=entries,
            control_ledger_metadata={k:v for k,v in control.items() if k != "entries"},
            control_ledger_unchanged=True, all_original_entry_fields_preserved=True,
            sha256_origin="B_LEDGER", candidate_payload_rehashed=False,
            operation_time_semantics="durable journal bounds surrounding plain rename and unlink; completion times are observations",
            journal_event_count=len(events), journal_terminal_event_sha256=events[-1]["event_sha256"],
            c5_checks=c5["checks"],
            storage_regression_tests=storage,
            sources={name:dict(path=utility.portable(utility.audit / name), sha256=_digest(data),
                              size_bytes=len(data)) for name,data in snapshots.items()},
            free_space_evidence={phase:json.loads(snapshots["FREE_SPACE_"+phase.upper()+".json"])
                                 for phase in ("before", "after")},
            finalization_operations=dict(candidate_payload_reads=0, solver_invocations=0,
                                          evaluator_invocations=0, rename_count=0, unlink_count=0))
        data = _json_bytes(final)
        compressed = _old._gzip_literal(data)
        path = utility.audit / "FINAL/DELETION_LEDGER.json"
        archive = utility.code / "docs/paper_rebuild/purge" / ("DELETION_LEDGER_" + utility.timestamp + ".json.gz")
        for name, original in snapshots.items():
            if _read(utility.audit / name) != original:
                _fail("control record changed during finalization: " + name)
        if _read(policy) != utility.policy_bytes:
            _fail("policy changed during finalization")
        for destination, content in ((path,data), (archive,compressed)):
            if _exists(destination) and _read(destination) != content:
                _fail("different existing final ledger output")
        for destination, content in ((path,data), (archive,compressed)):
            if not _exists(destination):
                _write_new(destination, content)
        saved_archive, saved_final = _read(archive), _read(path)
        if (saved_archive != compressed or saved_final != data
                or gzip.decompress(saved_archive) != saved_final):
            _fail("archive does not preserve final ledger literal bytes")
        receipt = dict(status="PASS_FINAL_LEDGER_AND_GZIP_LITERAL_BYTES_VERIFIED", file_count=count,
                       logical_bytes=size, final_ledger=utility.portable(path), final_ledger_sha256=_digest(saved_final),
                       archive=utility.portable(archive), archive_sha256=_digest(saved_archive),
                       control_ledger_sha256=binding["ledger_sha256"], journal_sha256=_digest(snapshots["JOURNAL.jsonl"]))
        _write_or_verify(utility.audit / "LEDGER_ARCHIVE_RECEIPT.json", receipt)
        return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("clean-root", "code-root", "policy", "audit-root"):
        parser.add_argument("--"+name, required=True, type=Path)
    print(json.dumps(finalize(**vars(parser.parse_args())), sort_keys=True))
