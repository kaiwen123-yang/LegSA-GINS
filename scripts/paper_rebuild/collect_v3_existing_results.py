#!/usr/bin/env python3
"""Read control records/archive table members and join collection inventories.

No project imports, process launch, extraction, scientific computation or source
mutation. Run after the two collectors. Root paths are read from ignored config.
Archive reads are limited to the explicit result-table members selected below;
central-directory enumeration is never described as reading member payloads.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

csv.field_size_limit(2**31 - 1)


CONTROL_FILES = [
    "00_CONTROL/RETENTION_POLICY.json",
    "00_CONTROL/RETENTION_INDEX.csv",
    "00_CONTROL/FIRST_EIGHT_BATCHES_RETENTION_RELEASE_SUMMARY.json",
    "00_CONTROL/AGGREGATE_RECOVERY/OPENAT_AUDIT_SUMMARY.json",
    "00_CONTROL/AGGREGATE_RECOVERY/OPENAT_AUDIT_ROWS.csv",
    "00_CONTROL/AGGREGATE_RECOVERY/OPENAT_SOURCE_PINS.json",
    "00_CONTROL/AGGREGATE_RECOVERY/ORIGINAL_HARD_STOP.json",
    "00_CONTROL/STATE.json", "00_CONTROL/DONE.json",
    "00_CONTROL/SUMMARY.json", "09_HANDOFF/TABLE_REVIEW.json",
    "09_HANDOFF/VISUAL_REVIEW.json", "09_HANDOFF/PACKAGE_DISPOSITION.json",
    "09_HANDOFF/FINAL_ACCEPTANCE.json", "09_HANDOFF/FINAL_DELIVERY.json",
]
ARCHIVES = {
    "c541_v2_handoff_v3.zip": "B_PROTOCOL_V2_PACKAGE_REVISION_V3",
    "c541_v21_handoff.zip": "B_PROTOCOL_V21",
    "hext_three_sequences_handoff_v2.zip": "B_EXTERNAL_EARLIER_PACKAGE",
    "t5a_heading_sensitivity_handoff_v2.zip": "B_T5A_SENSITIVITY",
    "t5bc_v3_candidate_pilot_handoff_v2.zip": "B_T5BC_CANDIDATE_NOT_PROTOCOL_V3",
    "ua02_uncertainty_delivery.zip": "B_UA02_POSTPROCESSING",
}


def csv_write(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--local-roots", type=Path, required=True)
    ap.add_argument("--archives", action="store_true",
                    help="read explicit B archive tables; otherwise reuse this collector's prior inventory")
    ap.add_argument("--ledger-only", action="store_true",
                    help="first delivery batch; source-table inventory is still being assembled")
    args = ap.parse_args()
    roots = json.loads(args.local_roots.read_text())["aliases"]
    out = Path(roots["<RESULTS_ROOT>"])
    out.mkdir(parents=True, exist_ok=True)
    v3 = Path(roots["<V3_ROOT>"])
    code = Path(roots["<CODE_ROOT>"])

    def portable(text):
        for alias, path in sorted(roots.items(), key=lambda kv: -len(kv[1])):
            text = text.replace(path, alias)
        return text

    def base(path, category):
        return {"category": category, "source_path": portable(str(path)),
                "source_row_key": "", "read_status": "NOT_READ",
                "retention_status": "PRESENT" if path.is_file() else "NOT_FOUND",
                "archive_path": "", "archive_member": "", "recorded_sha256": "",
                "verified_sha256": "", "row_count": "unknown", "columns": "",
                "sequence_scope": "", "method_scope": "", "case_scope": "",
                "version_scope": "", "notes": "", "storage_kind": "LOOSE_FILE"}

    rows = []
    for rel in CONTROL_FILES:
        p = v3 / rel
        row = base(p, "CONTROL_OR_RETENTION_EVIDENCE")
        if p.is_file():
            data = p.read_bytes()
            if p.suffix == ".csv":
                reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
                records = list(reader)
                row.update(row_count=len(records), columns=";".join(reader.fieldnames or []))
            else:
                obj = json.loads(data)
                keys = list(obj) if isinstance(obj, dict) else []
                row.update(row_count=len(obj), columns=";".join(keys) if len(keys) <= 64 else
                           "JSON_OBJECT_MAP; exact keys retained in source",
                           json_top_level_key_count=len(keys))
            row.update(read_status="READ_PARSED_FULL", verified_sha256=hashlib.sha256(data).hexdigest(),
                       hash_verification_scope="THIS_FILE_BYTES_ONLY_THIS_SESSION")
        rows.append(row)

    archive_rows = []
    archive_inventory = out / "ARCHIVE_RESULT_FILES.csv"
    if args.archives:
        for filename, version in ARCHIVES.items():
            archive = Path(roots["<HANDOFF_ROOT>"]) / filename
            row = base(archive, "B_EXISTING_HANDOFF_ARCHIVE")
            row.update(version_scope=version, storage_kind="ZIP_CONTAINER")
            if not archive.is_file():
                archive_rows.append(row)
                continue
            with zipfile.ZipFile(archive) as z:
                entries = z.infolist()
                row.update(read_status="CENTRAL_DIRECTORY_READ_ONLY", row_count=len(entries),
                           notes="Member count is not payload-read count; no full archive SHA recheck.")
                archive_rows.append(row)
                for member in entries:
                    name = member.filename
                    # Explicit bounded table families; no raw, trajectory or executable members.
                    selected = name.endswith(".csv") and (
                        "/05_AGGREGATE/" in name or "/07_AGGREGATE/" in name
                        or "/13_AGGREGATE/" in name or "/LADDER/" in name
                        or "docs/paper_rebuild/v3/uncertainty/" in name
                        or name.endswith("MAIN_TABLE_V3.csv")
                        or name.endswith("MAIN_TABLE_V2.csv"))
                    if not selected:
                        continue
                    mr = dict(row)
                    mr.update(category="B_ARCHIVE_TABLE_MEMBER", storage_kind="ZIP_MEMBER",
                              source_path=portable(str(archive)) + "!" + name,
                              archive_path=portable(str(archive)), archive_member=name,
                              row_count="unknown", retention_status="EXACT_ARCHIVE_MEMBER_LOCATED",
                              read_status="MEMBER_LOCATED_NOT_READ", zip_crc32=f"{member.CRC:08x}",
                              notes="Archive version is preserved; not automatically adopted as the live table.")
                    with z.open(member) as raw:
                        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
                        n = sum(1 for _ in reader)
                        mr.update(read_status="ARCHIVE_MEMBER_READ_PARSED_FULL", row_count=n,
                                  columns=";".join(reader.fieldnames or []))
                    archive_rows.append(mr)
            print(f"read archive table members: {filename}", flush=True)
        csv_write(archive_inventory, archive_rows)
    elif archive_inventory.exists():
        with archive_inventory.open(newline="") as f:
            archive_rows = list(csv.DictReader(f))
    rows += archive_rows
    csv_write(out / "CONTROL_RESULT_FILES.csv", rows[:len(CONTROL_FILES)])

    inventories = ["RUN_RESULT_FILES.csv"]
    if not args.ledger_only:
        inventories.append("TABLE_RESULT_FILES.csv")
    for filename in inventories:
        p = out / filename
        if p.exists():
            with p.open(newline="") as f:
                rows.extend(csv.DictReader(f))
    csv_write(out / "V3_RESULT_FILES.csv", rows)
    # Every alias is resolved locally; this derived file remains ignored.
    local = []
    for row in rows:
        original = row.get("source_path", "")
        resolved = original
        for alias, path in roots.items():
            resolved = resolved.replace(alias, path)
        windows = ""
        if resolved.startswith("/mnt/g/"):
            windows = "G:\\" + resolved[len("/mnt/g/"):].replace("/", "\\")
        local.append({"source_path": original, "resolved_wsl_location": resolved,
                      "resolved_windows_location": windows, "read_status": row.get("read_status", "")})
    csv_write(out / "V3_RESULT_FILES.local.csv", local)
    baseline_path = code / "configs/paper_rebuild/V3_RESULTS_BASELINE.local.json"
    baseline = json.loads(baseline_path.read_text())
    failures = []
    for rel, expected in baseline["original_audit_file_sha256"].items():
        if hashlib.sha256((code / rel).read_bytes()).hexdigest() != expected:
            failures.append(rel)
    summary = {"data_mode": "existing_results_read_only_collection",
               "inventory_scope": "LEDGER_MILESTONE" if args.ledger_only else "RUNS_TABLES_FIGURES_ARCHIVES",
               "synthetic_data_used": False, "semisynthetic_data_used": True,
               "source_data_note": "Includes existing registered semisynthetic rows; creates no experimental data.",
               "baseline_commit": baseline["head"], "file_inventory_rows": len(rows),
               "archive_containers_enumerated": sum(r["category"] == "B_EXISTING_HANDOFF_ARCHIVE" for r in archive_rows),
               "archive_table_members_parsed": sum(r["read_status"] == "ARCHIVE_MEMBER_READ_PARSED_FULL" for r in archive_rows),
               "original_audit_files_compared": len(baseline["original_audit_file_sha256"]),
               "original_audit_files_changed": failures,
               "native_calls": 0, "evaluator_calls": 0, "provider_generator_calls": 0,
               "aggregate_controller_calls": 0, "metric_recomputation_calls": 0,
               "raw_or_reference_payload_reads": 0, "new_archives": 0,
               "counter_basis": "Collector source and executed commands; not a new strace experiment.",
               "local_resolution_file": "<RESULTS_ROOT>/V3_RESULT_FILES.local.csv",
               "root_mapping_file": "<CODE_ROOT>/configs/paper_rebuild/V3_RESULTS_ROOTS.local.json"}
    (out / "COLLECTION_RECEIPT.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if failures:
        raise SystemExit("Original audit baseline changed")


if __name__ == "__main__":
    main()
