#!/usr/bin/env python3
"""Convert completed audit metadata into recursive stage/attempt storage totals.

Only fixed files in the audit directory are opened. Recorded stage paths are
strings: they are never stat'ed or traversed. The original partitioned table is
preserved byte-for-byte before the owned STORAGE_INVENTORY.csv is replaced.
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from legsa_gins.paper_rebuild.storage_purge import (  # noqa: E402
    STAMP, PurgeError, _absolute_without_links, _csv_bytes, _digest, _exists, _fail,
    _json_bytes, _parent_fd, _read, _regular_single, _relative, _same_stat, _write_new,
)


CLASSES = ("KEEP", "BULK_DELETABLE", "UNKNOWN")
REGULAR_FIELDS = ("regular_files", "logical_bytes", "KEEP_files", "KEEP_bytes",
                  "BULK_DELETABLE_files", "BULK_DELETABLE_bytes", "UNKNOWN_files", "UNKNOWN_bytes")
COUNT_FIELDS = REGULAR_FIELDS + ("directories", "symlinks_and_special")
OUTPUT_COLUMNS = ("group", "root_kind", "aggregation_scope", "size_basis",
                  "cross_level_addition") + COUNT_FIELDS


def _rows(data, required=()):
    with io.TextIOWrapper(io.BytesIO(data), encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            _fail("CSV requires unique column names")
        if not set(required) <= set(reader.fieldnames):
            _fail("CSV lacks required metadata columns")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                _fail("CSV row width differs from its header")
            yield row


def _integer(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
        _fail(f"{name} must be a recorded nonnegative integer")
    return int(value)


def _zero():
    return {name: 0 for name in COUNT_FIELDS}


def _increment(totals, kind, classification, size):
    if kind == "regular":
        totals["regular_files"] += 1
        totals["logical_bytes"] += size
        totals[classification + "_files"] += 1
        totals[classification + "_bytes"] += size
    elif kind == "directory":
        totals["directories"] += 1
    else:
        totals["symlinks_and_special"] += 1


def _closed(totals):
    return (totals["regular_files"] == sum(totals[c + "_files"] for c in CLASSES)
            and totals["logical_bytes"] == sum(totals[c + "_bytes"] for c in CLASSES))


def calculate(file_inventory, partitioned, closure):
    """Pure calculation from audit bytes; no payload/directory filesystem access."""
    if closure.get("schema_version") != "clean6.storage_reference_closure.v1":
        _fail("unsupported reference closure schema")
    explicit = {_relative(path) for field in ("superseded_attempt_dirs", "clean4_nonfinal_attempt_dirs")
                for path in closure.get(field, [])}
    if any(not path.startswith("stages/") for path in explicit):
        _fail("explicit attempt roots must be CLEAN_ROOT-relative stage paths")
    roots, seen, observed_explicit = {}, set(), set()
    source_totals = _zero()
    for row in _rows(file_inventory, ("original_relative_path", "file_type", "classification", "size_bytes")):
        relative = _relative(row["original_relative_path"])
        parts = PurePosixPath(relative).parts
        if len(parts) < 2 or parts[0] != "stages" or relative in seen:
            _fail("FILE_INVENTORY path is duplicated or outside stages")
        seen.add(relative)
        kind, classification = row["file_type"], row["classification"]
        if kind not in {"regular", "directory", "symlink", "special"} or classification not in CLASSES:
            _fail("unknown recorded file type or classification")
        size = _integer(row["size_bytes"], "size_bytes")
        if kind != "regular" and size != 0:
            _fail("nonregular inventory entries cannot contribute logical payload bytes")
        _increment(source_totals, kind, classification, size)
        if kind == "directory":
            if relative in explicit:
                observed_explicit.add(relative)
            if len(parts) == 2:
                roots[relative] = "STAGE"
            elif parts[-1].startswith(".attempt_"):
                roots[relative] = "ATTEMPT"
            elif relative in explicit:
                roots[relative] = "EXPLICIT_ATTEMPT"
    del seen
    totals = {root: _zero() for root in roots}
    stage_roots = {root for root, kind in roots.items() if kind == "STAGE"}
    for row in _rows(file_inventory):
        relative = row["original_relative_path"]
        parts = PurePosixPath(relative).parts
        if "/".join(parts[:2]) not in stage_roots:
            _fail("recorded entry lacks a real stage-directory row")
        # Excluding the full path excludes each root directory from its own totals.
        for depth in range(2, len(parts)):
            ancestor = "/".join(parts[:depth])
            if ancestor in totals:
                _increment(totals[ancestor], row["file_type"], row["classification"], int(row["size_bytes"]))
    partitioned_totals = _zero()
    groups = set()
    for row in _rows(partitioned, ("group",) + COUNT_FIELDS):
        if "aggregation_scope" in row:
            _fail("the preserved source must be the original partitioned table")
        group = _relative(row["group"])
        if group in groups:
            _fail("partitioned groups must be unique")
        groups.add(group)
        counts = {field: _integer(row[field], field) for field in COUNT_FIELDS}
        if not _closed(counts):
            _fail("partitioned row classification totals do not close")
        for field in COUNT_FIELDS:
            partitioned_totals[field] += counts[field]
    stage_totals = {field: sum(totals[root][field] for root in stage_roots) for field in COUNT_FIELDS}
    checks = {field: source_totals[field] == partitioned_totals[field] == stage_totals[field]
              for field in REGULAR_FIELDS}
    checks.update(
        partitioned_directory_count_matches_source=partitioned_totals["directories"] == source_totals["directories"],
        stage_directory_count_excludes_roots=stage_totals["directories"] == source_totals["directories"] - len(stage_roots),
        special_symlink_counts_close=source_totals["symlinks_and_special"] == partitioned_totals["symlinks_and_special"] == stage_totals["symlinks_and_special"],
        all_recursive_rows_close=all(_closed(value) for value in totals.values()),
    )
    if not all(checks.values()):
        _fail("inventory totals do not close: " + ", ".join(k for k, value in checks.items() if not value))
    output = [dict(group=root, root_kind=roots[root], aggregation_scope="RECURSIVE_DESCENDANTS",
                   size_basis="LOGICAL_BYTES_PER_PATH", cross_level_addition="FORBIDDEN", **totals[root])
              for root in sorted(roots)]
    summary = {"stage_root_count": len(stage_roots), "attempt_root_count": len(roots) - len(stage_roots),
               "recursive_row_count": len(output), "partitioned_row_count": len(groups),
               "unobserved_explicit_roots_omitted": sorted(explicit - observed_explicit),
               "file_inventory_totals": source_totals, "partitioned_totals": partitioned_totals,
               "stage_recursive_totals": stage_totals, "closure_checks": checks}
    return _csv_bytes(output, OUTPUT_COLUMNS), summary


def _replace_owned_table(audit, expected_old, new_bytes):
    table = audit / "STORAGE_INVENTORY.csv"
    pending = audit / ".STORAGE_INVENTORY_RECURSIVE.pending.csv"
    if _exists(pending):
        if _read(pending) != new_bytes:
            _fail("conflicting pending recursive table; no overwrite")
    else:
        _write_new(pending, new_bytes)
    with _parent_fd(table) as (parent, name):
        old_stat = os.stat(name, dir_fd=parent, follow_symlinks=False)
        pending_stat = os.stat(pending.name, dir_fd=parent, follow_symlinks=False)
        _regular_single(old_stat, table)
        _regular_single(pending_stat, pending)
        if _read(table) != expected_old or _read(pending) != new_bytes:
            _fail("owned inventory table or pending bytes changed before atomic replacement")
        if (not _same_stat(old_stat, os.stat(name, dir_fd=parent, follow_symlinks=False))
                or not _same_stat(pending_stat, os.stat(pending.name, dir_fd=parent, follow_symlinks=False))):
            _fail("owned inventory file identity changed before atomic replacement")
        os.replace(pending.name, name, src_dir_fd=parent, dst_dir_fd=parent)
        os.fsync(parent)


def convert(clean_root, audit_root):
    clean = _absolute_without_links(clean_root)
    audit = _absolute_without_links(audit_root)
    if audit.parent != clean / "storage_purge" or not STAMP.fullmatch(audit.name):
        _fail("audit root must be <CLEAN_ROOT>/storage_purge/YYYYmmddTHHMMSSZ")
    with _parent_fd(audit / "OPERATION_LOCK") as (parent, name):
        fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            _regular_single(os.fstat(fd), "operation lock")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                _fail("another audit operation holds the lock")
            inputs = {name: audit / name for name in (
                "FILE_INVENTORY.csv", "REFERENCE_CLOSURE.json", "DELETION_PLAN.csv", "DELETION_LEDGER.json")}
            snapshots = {name: _read(path) for name, path in inputs.items()}
            table = audit / "STORAGE_INVENTORY.csv"
            backup = audit / "STORAGE_INVENTORY_PARTITIONED.csv"
            receipt = audit / "INVENTORY_TOTALS_CONVERSION.json"
            current = _read(table)
            if _exists(receipt) and not _exists(backup):
                _fail("completed conversion has no preserved partitioned table")
            original = _read(backup) if _exists(backup) else current
            if not _exists(receipt) and _exists(backup) and current != original:
                _fail("unreceipted table/backup differ; preserve them for review")
            recursive, summary = calculate(snapshots["FILE_INVENTORY.csv"], original,
                                           json.loads(snapshots["REFERENCE_CLOSURE.json"]))
            hashes = {name: _digest(data) for name, data in snapshots.items()}
            report = dict(schema_version="clean6.storage_inventory_recursive_conversion.v1",
                status="PASS_RECURSIVE_TOTALS_AND_ALL_CLASSIFICATIONS_CLOSED",
                audit_timestamp=audit.name, aggregation_scope="RECURSIVE_DESCENDANTS",
                size_basis="LOGICAL_BYTES_PER_PATH",
                cross_level_addition="FORBIDDEN: stage rows include attempt descendants; sum only STAGE rows for global totals",
                table_sha256={"FILE_INVENTORY.csv": hashes["FILE_INVENTORY.csv"],
                              "STORAGE_INVENTORY_PARTITIONED.csv": _digest(original),
                              "STORAGE_INVENTORY.csv": _digest(recursive)},
                closure_sha256=hashes["REFERENCE_CLOSURE.json"],
                deletion_plan_sha256_before=hashes["DELETION_PLAN.csv"],
                deletion_plan_sha256_after=hashes["DELETION_PLAN.csv"],
                control_ledger_sha256_before=hashes["DELETION_LEDGER.json"],
                control_ledger_sha256_after=hashes["DELETION_LEDGER.json"],
                original_partitioned_literal_bytes_preserved=True,
                payload_read_count=0, payload_stat_count=0, stage_tree_walk_count=0,
                filesystem_metadata_access="audit-file safety guards only", scientific_execution_count=0,
                **summary)
            report_bytes = _json_bytes(report)
            if _exists(receipt):
                if current != recursive or _read(receipt) != report_bytes:
                    _fail("existing conversion does not match current inputs and exact outputs")
            else:
                for name, path in inputs.items():
                    if _read(path) != snapshots[name]:
                        _fail(f"audit input changed before conversion: {name}")
                if not _exists(backup):
                    _write_new(backup, original)
                if _read(backup) != original:
                    _fail("partitioned backup byte verification failed")
                _replace_owned_table(audit, current, recursive)
            if _read(table) != recursive or _read(backup) != original:
                _fail("converted table or preserved backup changed")
            # Pin the immutable plan/control ledger (and all other audit inputs)
            # again after replacement; no runtime payload is consulted.
            for name, path in inputs.items():
                if _read(path) != snapshots[name]:
                    _fail(f"audit input changed across conversion: {name}")
            if not _exists(receipt):
                _write_new(receipt, report_bytes)
            return report
        finally:
            os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = convert(args.clean_root, args.audit_root)
        print(json.dumps(report, sort_keys=True), flush=True)
        return 0
    except (PurgeError, OSError, ValueError, KeyError) as exc:
        print(f"STOP_PRESERVE_AUDIT_RECORDS: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
