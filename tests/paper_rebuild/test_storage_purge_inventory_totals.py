"""Recursive inventory arithmetic using metadata fixtures, never payload trees."""
import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/storage_purge_inventory_totals.py"
SPEC = importlib.util.spec_from_file_location("inventory_totals_fixture", SCRIPT)
conversion = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(conversion)


def csv_bytes(rows, columns):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


@pytest.fixture
def audit(tmp_path):
    clean = tmp_path / "clean"
    root = clean / "storage_purge/20260911T010203Z"
    root.mkdir(parents=True)
    a = "stages/S/.attempt_A"
    b = a + "/sub/.attempt_B"
    entries = [
        ("stages/S", "directory", "KEEP", 0),
        (a, "directory", "KEEP", 0), (a + "/sub", "directory", "KEEP", 0),
        (b, "directory", "KEEP", 0), (b + "/b.bin", "regular", "UNKNOWN", 7),
        (a + "/a.nav", "regular", "BULK_DELETABLE", 10),
        ("stages/S/keep.md", "regular", "KEEP", 3),
        ("stages/S/archive_v2", "directory", "KEEP", 0),
        ("stages/S/archive_v2/keep.csv", "regular", "KEEP", 2),
        ("stages/T", "directory", "KEEP", 0),
        ("stages/T/side.nav", "regular", "BULK_DELETABLE", 5),
        ("stages/S/link", "symlink", "KEEP", 0),
        ("stages/T/socket", "special", "KEEP", 0),
    ]
    rows = [dict(zip(("original_relative_path", "file_type", "classification", "size_bytes"), item)) for item in entries]
    (root / "FILE_INVENTORY.csv").write_bytes(csv_bytes(rows, list(rows[0])))
    groups = {}
    for relative, kind, cls, size in entries:
        candidates = [p for p in ["stages/S", a, b, "stages/S/archive_v2", "stages/T"]
                      if relative == p or relative.startswith(p + "/")]
        group = max(candidates, key=len)
        counts = groups.setdefault(group, conversion._zero())
        conversion._increment(counts, kind, cls, size)
    partitioned = [dict(group=key, **counts) for key, counts in sorted(groups.items())]
    (root / "STORAGE_INVENTORY.csv").write_bytes(csv_bytes(partitioned, ["group", *conversion.COUNT_FIELDS]))
    (root / "REFERENCE_CLOSURE.json").write_text(json.dumps({
        "schema_version": "clean6.storage_reference_closure.v1",
        "superseded_attempt_dirs": [],
        "clean4_nonfinal_attempt_dirs": ["stages/S/archive_v2", "stages/S/not_observed"],
    }))
    (root / "DELETION_PLAN.csv").write_bytes(b"path,sha256\nfixture,unchanged\n")
    (root / "DELETION_LEDGER.json").write_bytes(b'{ "immutable": "fixture" }\n')
    return clean, root


def table(root, name="STORAGE_INVENTORY.csv"):
    with (root / name).open() as stream:
        return {row["group"]: row for row in csv.DictReader(stream)}


def test_recursive_stage_and_nested_attempt_totals_close_without_payload_tree(audit, monkeypatch):
    clean, root = audit
    original = (root / "STORAGE_INVENTORY.csv").read_bytes()
    plan = (root / "DELETION_PLAN.csv").read_bytes()
    ledger = (root / "DELETION_LEDGER.json").read_bytes()
    assert not (clean / "stages").exists()  # Any payload walk/stat would fail this fixture.
    def forbidden_walk(*args, **kwargs):
        pytest.fail("conversion must not enumerate any stage tree")
    monkeypatch.setattr(conversion.os, "scandir", forbidden_walk)
    report = conversion.convert(clean, root)
    rows = table(root)
    assert (root / "STORAGE_INVENTORY_PARTITIONED.csv").read_bytes() == original
    assert (root / "DELETION_PLAN.csv").read_bytes() == plan
    assert (root / "DELETION_LEDGER.json").read_bytes() == ledger
    assert len(rows) == 5 and report["stage_root_count"] == 2 and report["attempt_root_count"] == 3
    assert int(rows["stages/S"]["logical_bytes"]) == 22
    assert int(rows["stages/S"]["regular_files"]) == 4
    assert int(rows["stages/S"]["directories"]) == 4
    assert int(rows["stages/S/.attempt_A"]["logical_bytes"]) == 17
    assert int(rows["stages/S/.attempt_A"]["directories"]) == 2
    assert int(rows["stages/S/.attempt_A/sub/.attempt_B"]["directories"]) == 0
    assert int(rows["stages/S/archive_v2"]["logical_bytes"]) == 2
    assert report["unobserved_explicit_roots_omitted"] == ["stages/S/not_observed"]
    assert all(report["closure_checks"].values())
    assert report["stage_recursive_totals"]["logical_bytes"] == 27
    assert report["stage_recursive_totals"]["BULK_DELETABLE_bytes"] == 15
    assert report["stage_recursive_totals"]["KEEP_bytes"] == 5
    assert report["stage_recursive_totals"]["UNKNOWN_bytes"] == 7
    assert report["stage_recursive_totals"]["symlinks_and_special"] == 2
    assert all(r["aggregation_scope"] == "RECURSIVE_DESCENDANTS" and
               r["size_basis"] == "LOGICAL_BYTES_PER_PATH" and r["cross_level_addition"] == "FORBIDDEN"
               for r in rows.values())


def test_completed_conversion_is_idempotent_and_writes_nothing(audit, monkeypatch):
    clean, root = audit
    first = conversion.convert(clean, root)
    def forbidden(*args, **kwargs):
        pytest.fail("completed conversion may only verify")
    monkeypatch.setattr(conversion, "_write_new", forbidden)
    monkeypatch.setattr(conversion.os, "replace", forbidden)
    assert conversion.convert(clean, root) == first


def test_global_closure_mismatch_stops_before_backup_or_table_change(audit):
    clean, root = audit
    rows = list(table(root).values())
    rows[0]["logical_bytes"] = str(int(rows[0]["logical_bytes"]) + 1)
    rows[0]["KEEP_bytes"] = str(int(rows[0]["KEEP_bytes"]) + 1)
    altered = csv_bytes(rows, list(rows[0]))
    (root / "STORAGE_INVENTORY.csv").write_bytes(altered)
    with pytest.raises(conversion.PurgeError, match="do not close"):
        conversion.convert(clean, root)
    assert (root / "STORAGE_INVENTORY.csv").read_bytes() == altered
    assert not (root / "STORAGE_INVENTORY_PARTITIONED.csv").exists()


@pytest.mark.parametrize("mutation", ["duplicate", "missing_stage", "bad_class", "negative_bytes", "external"])
def test_invalid_file_inventory_does_not_generate_totals(audit, mutation):
    clean, root = audit
    path = root / "FILE_INVENTORY.csv"
    rows = list(csv.DictReader(io.StringIO(path.read_text())))
    if mutation == "duplicate":
        rows.append(dict(rows[0]))
    elif mutation == "missing_stage":
        rows = [r for r in rows if r["original_relative_path"] != "stages/S"]
    elif mutation == "bad_class":
        rows[4]["classification"] = "SOMETHING_ELSE"
    elif mutation == "negative_bytes":
        rows[4]["size_bytes"] = "-1"
    else:
        rows[4]["original_relative_path"] = "../outside"
    path.write_bytes(csv_bytes(rows, list(rows[0])))
    with pytest.raises(conversion.PurgeError):
        conversion.convert(clean, root)
    assert not (root / "INVENTORY_TOTALS_CONVERSION.json").exists()


def test_conflicting_pending_file_is_not_overwritten(audit):
    clean, root = audit
    original = (root / "STORAGE_INVENTORY.csv").read_bytes()
    pending = root / ".STORAGE_INVENTORY_RECURSIVE.pending.csv"
    pending.write_bytes(b"unrelated data")
    with pytest.raises(conversion.PurgeError, match="conflicting pending"):
        conversion.convert(clean, root)
    assert pending.read_bytes() == b"unrelated data"
    assert (root / "STORAGE_INVENTORY.csv").read_bytes() == original


def test_control_plan_change_across_conversion_is_detected(audit, monkeypatch):
    clean, root = audit
    replace = conversion._replace_owned_table
    def injected_change(*args):
        replace(*args)
        (root / "DELETION_PLAN.csv").write_bytes(b"changed by external actor\n")
    monkeypatch.setattr(conversion, "_replace_owned_table", injected_change)
    with pytest.raises(conversion.PurgeError, match="changed across conversion"):
        conversion.convert(clean, root)
    assert not (root / "INVENTORY_TOTALS_CONVERSION.json").exists()


def test_unreceipted_partial_conversion_and_changed_completed_receipt_fail_closed(audit, monkeypatch):
    clean, root = audit
    write = conversion._write_new
    def stop_receipt(path, data):
        if path.name == "INVENTORY_TOTALS_CONVERSION.json":
            raise OSError("fixture interruption")
        return write(path, data)
    monkeypatch.setattr(conversion, "_write_new", stop_receipt)
    with pytest.raises(OSError):
        conversion.convert(clean, root)
    monkeypatch.setattr(conversion, "_write_new", write)
    with pytest.raises(conversion.PurgeError, match="unreceipted"):
        conversion.convert(clean, root)


def test_audit_scope_and_input_symlink_rejected(audit, tmp_path):
    clean, root = audit
    with pytest.raises(conversion.PurgeError, match="audit root"):
        conversion.convert(clean, root.parent)
    source = root / "FILE_INVENTORY.csv"
    outside = tmp_path / "source.csv"
    outside.write_bytes(source.read_bytes())
    source.unlink()
    source.symlink_to(outside)
    with pytest.raises(OSError):
        conversion.convert(clean, root)
