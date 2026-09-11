#!/usr/bin/env python3
"""Import the unchanged B candidate set and summarize its retained UNKNOWN rows.

This preparation command reads control records only. It never inventories,
hashes candidate payloads, moves candidates, or removes files.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import io
import json
from pathlib import Path, PurePosixPath
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from legsa_gins.paper_rebuild.storage_purge import (
    PLAN_COLUMNS, StoragePurge, _csv_bytes, _digest, _exists, _fail,
    _json_bytes, _read, _write_new,
)


def directory_type(parts):
    """First matching category in this fixed order; independent of file size."""
    upper = [part.upper() for part in parts]
    if "FROZEN_EVALUATOR" in upper:
        return "FROZEN_EVALUATOR"
    if "LOGS" in upper:
        return "LOGS"
    if any("BUILD" in p or p == "CMAKEFILES" for p in upper):
        return "BUILD"
    if any("PLOTTING" in p or "FIGURE" in p or "ATLAS" in p for p in upper):
        return "PLOTTING_FIGURES_ATLAS"
    for token, category in (("PROVIDER", "PROVIDER"), ("AGGREGATE", "AGGREGATE"),
                            ("EVALUATION", "EVALUATION")):
        if any(token in p for p in upper):
            return category
    if any("RUNS" in p or "OUTPUTS" in p for p in upper):
        return "RUNS_OUTPUTS"
    return "OTHER"


def unknown_groups(data):
    grouped = defaultdict(lambda: [0, 0])
    for row in csv.DictReader(io.StringIO(data.decode())):
        if row["classification"] != "UNKNOWN" or row["file_type"] != "regular":
            _fail("UNKNOWN source contains a non-UNKNOWN regular file")
        path = PurePosixPath(row["original_relative_path"])
        extension = ("".join(path.suffixes[-2:]) if path.suffix.lower() == ".gz"
                     else path.suffix) or "(none)"
        key = extension.lower(), directory_type(path.parts[2:-1])
        size = int(row["size_bytes"])
        if size < 0:
            _fail("negative UNKNOWN size")
        grouped[key][0] += 1
        grouped[key][1] += size
    return [dict(extension=key[0], directory_type=key[1], file_count=value[0],
                 logical_bytes=value[1]) for key, value in
            sorted(grouped.items(), key=lambda pair: (-pair[1][1], pair[0]))]


def verify_closure_extension(old, new):
    if not set(old.get("source_documents_sha256", {})) <= set(new.get("source_documents_sha256", {})):
        _fail("continuation loses source document pins")
    for field in ("keep_files", "keep_dirs", "protected_dir_entries"):
        if not set(old.get(field, [])) <= set(new.get(field, [])):
            _fail("continuation shrinks old reference protection: " + field)
    old_refs = {(r["path"], r["kind"]) for r in old["required_paths"]}
    new_refs = {(r["path"], r["kind"]) for r in new["required_paths"]}
    if not old_refs <= new_refs or new.get("unresolved_required_paths"):
        _fail("continuation loses or cannot resolve required references")
    for path, digest in old.get("frozen_source_sha256", {}).items():
        if new.get("frozen_source_sha256", {}).get(path) != digest:
            _fail("frozen reference identity changed")


def import_b(utility, old_audit, expected_ledger_sha256, expected_plan_sha256):
    if _exists(utility.audit):
        _fail("continuation audit must be new")
    old_audit = Path(old_audit).absolute()
    if old_audit.parent != utility.clean / "storage_purge" or old_audit == utility.audit:
        _fail("B source must be a different CLEAN_ROOT storage audit")
    old_bytes = _read(old_audit / "DELETION_LEDGER.json")
    plan_bytes = _read(old_audit / "DELETION_PLAN.csv")
    if (_digest(old_bytes) != expected_ledger_sha256
            or _digest(plan_bytes) != expected_plan_sha256):
        _fail("pinned B ledger or plan hash changed")
    old = json.loads(old_bytes)
    if (old["plan_sha256"] != expected_plan_sha256
            or _csv_bytes(old["entries"], PLAN_COLUMNS) != plan_bytes):
        _fail("B entries do not reproduce its literal plan")
    old_closure_bytes = _read(old_audit / "REFERENCE_CLOSURE.json")
    if _digest(old_closure_bytes) != old["closure_sha256"]:
        _fail("B closure binding changed")
    verify_closure_extension(json.loads(old_closure_bytes), utility.closure)
    journal = _read(old_audit / "JOURNAL.jsonl")
    if journal and not journal.endswith(b"\n"):
        _fail("B journal has a torn tail")
    events = [json.loads(line) for line in journal.splitlines()]
    if any(event["action"] != "MOVE_PREPARED" for event in events):
        _fail("B source audit has moved or purged entries; cannot import as unmoved")
    old_binding = {key: old[key] for key in ("policy_sha256", "closure_sha256", "plan_sha256")}
    old_binding["ledger_sha256"] = expected_ledger_sha256
    registered = {r["original_relative_path"]: r for r in old["entries"]}
    previous = "0" * 64
    for index, event in enumerate(events, 1):
        body = {k: v for k, v in event.items() if k != "event_sha256"}
        row = registered.get(event.get("original_relative_path"))
        if (event.get("sequence") != index or event.get("previous_sha256") != previous
                or event.get("binding") != old_binding or _digest(_json_bytes(body)) != event.get("event_sha256")
                or row is None or any(event.get(k) != row[k] for k in ("sha256", "size_bytes"))):
            _fail("B journal chain, binding or candidate identity changed")
        previous = event["event_sha256"]
    old_quarantine = utility.clean / "_PURGE_PENDING" / old["quarantine_timestamp"]
    if _exists(old_quarantine):
        import stat
        if any(not stat.S_ISDIR(s.st_mode) for _, s in utility._walk(old_quarantine)):
            _fail("B source quarantine is not empty")
    entries = [dict(row, quarantine_timestamp=utility.timestamp,
                    quarantine_relative_path="_PURGE_PENDING/" + utility.timestamp + "/"
                    + row["original_relative_path"]) for row in old["entries"]]
    for before, after in zip(old["entries"], entries):
        allowed = {"quarantine_timestamp", "quarantine_relative_path"}
        if {k: v for k, v in before.items() if k not in allowed} != {
                k: v for k, v in after.items() if k not in allowed}:
            _fail("B candidate content/provenance projection changed")
    new_plan = _csv_bytes(entries, PLAN_COLUMNS)
    origin = dict(audit=utility.portable(old_audit), ledger_sha256=expected_ledger_sha256,
                  plan_sha256=expected_plan_sha256, closure_sha256=old["closure_sha256"],
                  policy_sha256=old["policy_sha256"], journal_sha256=_digest(journal))
    ledger = dict(old, **utility.base_binding, quarantine_timestamp=utility.timestamp,
                  entries=entries, plan_sha256=_digest(new_plan), origin_b=origin,
                  candidate_payload_rehashed=False, candidate_selection_recomputed=False,
                  continuation_strategy="drvfs_plain_rename_b_sha256.v1")
    if (len(entries) != old["candidate_count"]
            or sum(r["size_bytes"] for r in entries) != old["candidate_bytes"]):
        _fail("B candidate count or bytes do not close")
    unknown_bytes = _read(old_audit / "UNKNOWN_FILES.csv")
    groups = unknown_groups(unknown_bytes)
    unknown_count = sum(r["file_count"] for r in groups)
    if unknown_count != old["inventory_counts"]["UNKNOWN"]:
        _fail("UNKNOWN counts do not close to B")
    partitioned_bytes = _read(old_audit / "STORAGE_INVENTORY_PARTITIONED.csv")
    partitioned = list(csv.DictReader(io.StringIO(partitioned_bytes.decode())))
    if (unknown_count != sum(int(r["UNKNOWN_files"]) for r in partitioned)
            or sum(r["logical_bytes"] for r in groups) != sum(int(r["UNKNOWN_bytes"]) for r in partitioned)):
        _fail("UNKNOWN counts or bytes differ from the original partitioned inventory")
    summary = dict(origin_b=origin, candidate_count=len(entries),
                   candidate_bytes=old["candidate_bytes"],
                   candidate_projection_exactly_unchanged=True,
                   old_keep_and_required_references_retained=True,
                   candidate_payload_read_count=0, candidate_selection_recomputed=False,
                   unknown_file_count=unknown_count,
                   unknown_bytes=sum(r["logical_bytes"] for r in groups),
                   unknown_source_sha256=_digest(unknown_bytes),
                   unknown_group_rule="first matching category in directory_type; final suffix, or compound suffix for gzip; lowercase extension; byte descending",
                   unknown_top20=groups[:20])
    # All checks above precede any new audit output.
    outputs = {
        "REFERENCE_CLOSURE.json": utility.closure_bytes,
        "DELETION_PLAN.csv": new_plan, "DELETION_LEDGER.json": _json_bytes(ledger),
        "CONTINUATION_IMPORT.json": _json_bytes(summary), "UNKNOWN_FILES.csv": unknown_bytes,
        "UNKNOWN_BY_CLASS.csv": _csv_bytes(groups, ["extension", "directory_type", "file_count", "logical_bytes"]),
    }
    for name in ("STORAGE_INVENTORY.csv", "STORAGE_INVENTORY_PARTITIONED.csv"):
        outputs[name] = _read(old_audit / name)
    for name, data in outputs.items():
        _write_new(utility.audit / name, data)
    utility._ledger()
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("clean-root", "code-root", "policy", "closure", "audit-root", "old-audit"):
        ap.add_argument("--" + name, type=Path, required=True)
    for name in ("expected-ledger-sha256", "expected-plan-sha256"):
        ap.add_argument("--" + name, required=True)
    args = vars(ap.parse_args())
    old_audit = args.pop("old_audit")
    old_ledger, old_plan = args.pop("expected_ledger_sha256"), args.pop("expected_plan_sha256")
    utility = StoragePurge(**args)
    print(json.dumps(import_b(utility, old_audit, old_ledger, old_plan), sort_keys=True))


if __name__ == "__main__":
    main()
