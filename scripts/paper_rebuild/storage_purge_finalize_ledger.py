#!/usr/bin/env python3
"""Finalize a successfully purged exact-file ledger without rereading payloads.

Control records remain unchanged. The final JSON and its gzip are deterministic
functions of those records, so a partial output write can be resumed by checking
the existing bytes. This script never moves, unlinks, or invokes scientific code.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import gzip
import io
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from legsa_gins.paper_rebuild.storage_purge import (  # noqa: E402
    C5_CHECKS, PurgeError, StoragePurge, _absolute_without_links, _digest,
    _exists, _fail, _json_bytes, _read, _write_new,
)


SCHEMA = "clean6.storage_purge_final_ledger.v1"
ACTION_ORDER = {"MOVE_PREPARED": 0, "MOVED_HASH_VERIFIED": 1, "PURGE_PREPARED": 2, "PURGED": 3}
TIME_FIELDS = {"MOVE_PREPARED": "move_prepared_at_utc",
               "MOVED_HASH_VERIFIED": "quarantine_verified_at_utc",
               "PURGE_PREPARED": "purge_prepared_at_utc", "PURGED": "purge_recorded_at_utc"}
LOCAL_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|file://|(?:^|[\s=:\"'(\[,])/(?![\s<]))", re.IGNORECASE)


def _timestamp(value):
    if not isinstance(value, str):
        _fail("journal UTC timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + ("+00:00" if value.endswith("Z") else ""))
    except ValueError as exc:
        raise PurgeError("invalid journal UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        _fail("journal timestamps must explicitly identify UTC")
    return parsed


def _count(value, expected, label):
    if type(value) is not int or value != expected:
        _fail(f"{label} count/bytes mismatch")


def _enrich_entries(control, events):
    grouped = {row["original_relative_path"]: [] for row in control["entries"]}
    for event in events:
        if event["original_relative_path"] not in grouped:
            _fail("journal has a path outside the exact ledger")
        grouped[event["original_relative_path"]].append(event)
    enriched = []
    for row in control["entries"]:
        history = grouped[row["original_relative_path"]]
        actions = [event["action"] for event in history]
        if (set(actions) != set(ACTION_ORDER) or actions.count("MOVED_HASH_VERIFIED") != 1
                or actions.count("PURGED") != 1 or not actions or actions[-1] != "PURGED"):
            _fail("every file requires complete prepare/verified/prepare/PURGED coverage")
        ranks = [ACTION_ORDER[action] for action in actions]
        if ranks != sorted(ranks):
            _fail("per-file operation events are out of order")
        parsed_times = [_timestamp(event["time_utc"]) for event in history]
        if parsed_times != sorted(parsed_times):
            _fail("per-file UTC event times cannot define ordered operation bounds")
        for event in history:
            if type(event.get("recovered_after_prepare", False)) is not bool:
                _fail("recovered_after_prepare must be a boolean")
        # Multiple durable preparations can precede one operation after an interruption.
        # The last preparation preceding its completion is the tightest recorded bound.
        selected = {action: next(event for event in reversed(history) if event["action"] == action)
                    for action in ACTION_ORDER}
        additions = {field: selected[action]["time_utc"] for action, field in TIME_FIELDS.items()}
        additions["operation_event_sha256"] = {action: event["event_sha256"] for action, event in selected.items()}
        additions["recovered_after_prepare"] = {
            "quarantine_verification": selected["MOVED_HASH_VERIFIED"].get("recovered_after_prepare", False),
            "purge_record": selected["PURGED"].get("recovered_after_prepare", False),
        }
        additions["operation_event_history"] = [dict(
            sequence=event["sequence"], action=event["action"], time_utc=event["time_utc"],
            event_sha256=event["event_sha256"], recovered_after_prepare=event.get("recovered_after_prepare", False))
            for event in history]
        if set(row) & set(additions):
            _fail("control entry already contains finalization fields; refusing to replace them")
        enriched.append(dict(row, **additions))
    return enriched


def _gzip_literal(data):
    stream = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as archive:
        archive.write(data)
    compressed = stream.getvalue()
    if gzip.decompress(compressed) != data or compressed[4:8] != b"\x00" * 4:
        _fail("gzip literal-byte or mtime verification failed")
    return compressed


def _free_space_literal(data):
    try:
        literal = data.decode("utf-8")
        record = json.loads(data)
    except (UnicodeDecodeError, ValueError) as exc:
        raise PurgeError("free-space evidence must be UTF-8 JSON") from exc
    if not isinstance(record, dict):
        _fail("free-space evidence must be a JSON object")
    _timestamp(record.get("time_utc"))
    if record.get("filesystem_alias") != "G: / <CLEAN_ROOT>":
        _fail("free-space filesystem_alias must be 'G: / <CLEAN_ROOT>'")
    for field in ("available_bytes", "free_bytes", "total_bytes"):
        if type(record.get(field)) is not int or record[field] < 0:
            _fail(f"free-space {field} must be a nonnegative integer")

    def check_strings(value):
        if isinstance(value, str):
            if LOCAL_PATH.search(value):
                _fail("local absolute path content in free-space evidence is forbidden")
        elif isinstance(value, dict):
            for key, item in value.items():
                check_strings(key)
                check_strings(item)
        elif isinstance(value, list):
            for item in value:
                check_strings(item)
    check_strings(record)
    if literal.encode("utf-8") != data:
        _fail("free-space literal bytes changed during embedding")
    return literal


def finalize(clean_root, code_root, policy, closure, audit_root, c5_receipt,
             before_free_space, after_free_space, archive_path):
    utility = StoragePurge(clean_root, code_root, policy, closure, audit_root)
    archive_path = _absolute_without_links(archive_path, missing=True)
    expected_archive = utility.code / "docs/paper_rebuild/purge" / f"DELETION_LEDGER_{utility.timestamp}.json.gz"
    if archive_path != expected_archive:
        _fail("archive must be the exact timestamped docs/paper_rebuild/purge ledger path")
    final_path = utility.audit / "FINAL/DELETION_LEDGER.json"
    _absolute_without_links(final_path, missing=True)
    fixed_inputs = {"closure": (closure, "REFERENCE_CLOSURE.json"),
                    "C5 receipt": (c5_receipt, "C5_RECEIPT.json"),
                    "before free-space": (before_free_space, "FREE_SPACE_BEFORE.json"),
                    "after free-space": (after_free_space, "FREE_SPACE_AFTER.json")}
    for label, (provided, basename) in fixed_inputs.items():
        if _absolute_without_links(provided) != utility.audit / basename:
            _fail(f"{label} must be the fixed audit file {basename}")

    with utility._operation_lock():
        # Only control metadata are opened. Do not call _references/hash_file: its
        # package/payload integrity work already belongs to the completed C gates.
        inputs = {
            "control_ledger": utility.audit / "DELETION_LEDGER.json",
            "deletion_plan": utility.audit / "DELETION_PLAN.csv",
            "closure": Path(closure), "saved_closure": utility.audit / "REFERENCE_CLOSURE.json",
            "policy": Path(policy), "pre_move_receipt": utility.audit / "GATE_PRE_MOVE.json",
            "quarantine_receipt": utility.audit / "GATE_QUARANTINE.json",
            "c5_receipt": Path(c5_receipt), "purge_result": utility.audit / "PURGE_RESULT.json",
            "journal": utility.audit / "JOURNAL.jsonl",
            "before_free_space": Path(before_free_space), "after_free_space": Path(after_free_space),
        }
        inputs = {name: _absolute_without_links(path) for name, path in inputs.items()}
        portable_sources = {name: utility.portable(path) for name, path in inputs.items()}
        if any(path.startswith("<EXTERNAL>") for path in portable_sources.values()):
            _fail("every final ledger source must have a CLEAN_ROOT, CODE_ROOT or HOME alias")
        snapshots = {name: _read(path) for name, path in inputs.items()}
        control, binding = utility._ledger()
        pre = utility._receipt("GATE_PRE_MOVE.json", binding, ["C1", "C2", "C3"])
        quarantine = utility._receipt("GATE_QUARANTINE.json", binding, ["C4"])
        result = utility._receipt("PURGE_RESULT.json", binding, [f"C{i}" for i in range(1, 6)])
        c5 = json.loads(snapshots["c5_receipt"])
        if (any(c5.get(key) != value for key, value in binding.items())
                or c5.get("gates", {}).get("C5") != "PASS"
                or not C5_CHECKS <= c5.get("checks", {}).keys()
                or any(value != "PASS" for value in c5["checks"].values())):
            _fail("C5 independent checks or binding are not PASS")
        if result.get("c5_receipt_sha256") != _digest(snapshots["c5_receipt"]):
            _fail("PURGE_RESULT does not identify the supplied C5 literal bytes")
        n = len(control["entries"])
        total_bytes = sum(row["size_bytes"] for row in control["entries"])
        _count(pre.get("candidate_count"), n, "C1-C3")
        for field in ["keep_match_count", "outside_stages_count", "invalidclassfamily_count"]:
            _count(pre.get(field), 0, field)
        _count(quarantine.get("verified_files"), n, "C4 verified files")
        if quarantine.get("exact_quarantine_set") is not True:
            _fail("C4 exact quarantine set was not verified")
        _count(result.get("purged_files"), n, "D purged files")
        _count(result.get("purged_logical_bytes"), total_bytes, "D purged bytes")
        if result.get("original_directories_retained") is not True:
            _fail("D did not retain the original directories")
        if _exists(utility.quarantine):
            _fail("quarantine root still exists after the recorded successful D")
        events = utility._journal(binding)
        actions = utility._event_actions(control, events)
        if set(actions) != {row["original_relative_path"] for row in control["entries"]}:
            _fail("journal path coverage differs from the exact ledger")
        if any("PURGED" not in value for value in actions.values()):
            _fail("journal does not durably record PURGED for every file")
        enriched = _enrich_entries(control, events)
        free_space = {}
        for phase in ["before", "after"]:
            name = phase + "_free_space"
            literal = _free_space_literal(snapshots[name])
            free_space[phase] = {"source_role": name, "raw_utf8_text": literal,
                                 "sha256": _digest(snapshots[name])}
        final = {
            "schema_version": SCHEMA,
            "status": "ALL_EXACT_LEDGER_FILES_DURABLY_RECORDED_PURGED",
            "quarantine_timestamp": utility.timestamp,
            "binding": binding,
            "gates": {f"C{i}": "PASS" for i in range(1, 6)},
            "file_count": n, "logical_bytes": total_bytes,
            "control_ledger_metadata": {key: value for key, value in control.items() if key != "entries"},
            "control_ledger_unchanged": True, "all_original_entry_fields_preserved": True,
            "entries": enriched,
            "operation_time_semantics": {
                "rename": "between move_prepared_at_utc and quarantine_verified_at_utc",
                "unlink": "between purge_prepared_at_utc and purge_recorded_at_utc",
                "timestamps_are_durable_journal_observations_not_exact_operation_times": True,
                "recovery": "completion observations may occur after process recovery; bounds then widen",
                "repeated_preparations": "use the last preparation before the single completion; retain all events",
            },
            "journal_event_count": len(events),
            "journal_terminal_event_sha256": events[-1]["event_sha256"] if events else None,
            "journal_terminal_recorded_at_utc": events[-1]["time_utc"] if events else None,
            "sources": {name: {"path": portable_sources[name], "sha256": _digest(snapshots[name]),
                               "size_bytes": len(snapshots[name])} for name, path in inputs.items()},
            "free_space_evidence": free_space,
            "archive": {"path": utility.portable(archive_path), "format": "gzip", "mtime": 0,
                        "content": "literal UTF-8 bytes of FINAL/DELETION_LEDGER.json"},
            "payload_read_count": 0, "scientific_execution_count": 0,
            "move_count": 0, "unlink_count": 0,
        }
        final_bytes = _json_bytes(final)
        archive_bytes = _gzip_literal(final_bytes)
        # No input may change between the validated reads and finalization writes.
        for name, path in inputs.items():
            if _read(path) != snapshots[name]:
                _fail(f"control evidence changed during finalization: {name}")
        # Check both destinations before creating either; never overwrite collisions.
        for path, content in [(final_path, final_bytes), (archive_path, archive_bytes)]:
            if _exists(path) and _read(path) != content:
                _fail(f"existing finalization output has different bytes: {utility.portable(path)}")
        for path, content in [(final_path, final_bytes), (archive_path, archive_bytes)]:
            if not _exists(path):
                _write_new(path, content)
        saved_final, saved_archive = _read(final_path), _read(archive_path)
        if saved_final != final_bytes or saved_archive != archive_bytes or gzip.decompress(saved_archive) != saved_final:
            _fail("written archive does not decompress to the exact final ledger bytes")
        return {"status": "PASS_FINAL_LEDGER_AND_GZIP_LITERAL_BYTES_VERIFIED",
                "file_count": n, "logical_bytes": total_bytes,
                "final_ledger": utility.portable(final_path), "final_ledger_sha256": _digest(saved_final),
                "archive": utility.portable(archive_path), "archive_sha256": _digest(saved_archive),
                "control_ledger_sha256": binding["ledger_sha256"], "journal_sha256": _digest(snapshots["journal"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["clean-root", "code-root", "policy", "closure", "audit-root", "c5-receipt",
                 "before-free-space", "after-free-space", "archive-path"]:
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = finalize(**vars(args))
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0
    except (PurgeError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"STOP_NO_CONTROL_RECORD_CHANGED: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
