#!/usr/bin/env python3
"""Authorized D6 status bookkeeping after the unchanged H-EXT-02 aggregator.

This wrapper never invokes a native filter/evaluator or reads a reference trace.
It preserves the original aggregate bytes, then annotates the exact frozen
horizontal-baseline precondition failure without changing any numeric field.
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import shutil

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"

from legsa_gins.paper_rebuild.hext.aggregate import aggregate_stage
from legsa_gins.paper_rebuild.hext.execution import archive_batch, stage_roots
from legsa_gins.paper_rebuild.hext.legsa_gap_diagnostic import run_legsa_gap_diagnostic
from legsa_gins.paper_rebuild.hext.sequence_paths import alias_path, load_sequence_paths
from legsa_gins.paper_rebuild.manifest import sha256_file

ERROR = "geometric audit baseline has inadequate horizontal length"
CLASSIFICATION = "PRECONDITION_HORIZONTAL_BASELINE_LE_0P1"
ORIGINAL_DIRECTORY = "BOOKKEEPING_GEOMETRY_STATUS_ORIGINAL"
TABLES = ("HORIZONTAL_TABLE_V3_THREE_SEQUENCES.csv", "HORIZONTAL_TABLE_V2_THREE_SEQUENCES.csv")
PRESERVED = (*TABLES, "FIELD_DEFINITIONS.json", "FINAL_SUMMARY.json")
NUMERIC_FIELDS = (
    "h_rmse_m", "position_3d_rmse_m", "up_rmse_m", "yaw_rmse_deg",
    "yaw_p95_absolute_deg", "roll_rmse_deg", "pitch_rmse_deg",
    "body_forward_bias_m", "body_right_bias_m", "body_up_bias_m",
    "output_epoch_count", "matched_epoch_count", "coverage_ratio",
    "gap_events_in_window", "gnss2_pacc_inflated_epochs", "gnss2_float_epochs",
)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, payload, *, replace=False):
    with Path(path).open("w" if replace else "x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def verify_freeze(sequence, freeze):
    hashes = freeze["source_hashes"]
    if len(hashes) != 37:
        raise RuntimeError("Expected the recorded 37-file scientific freeze")
    mismatches = [name for name, digest in hashes.items()
                  if sha256_file(sequence.code_root / name) != digest]
    if mismatches:
        raise RuntimeError("Scientific freeze changed: " + ", ".join(mismatches))
    return {"file_count": 37, "matched_count": 37, "code_commit": freeze["code_freeze"]}


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def resolve_native(path, sequence):
    text = str(path).replace("<CLEAN_ROOT>", str(sequence.clean_root)).replace(
        "<HEXT_SCRATCH>", str(sequence.hext_scratch))
    candidate = Path(text)
    if candidate.is_symlink() or candidate.name != "NATIVE_SUMMARY.json":
        raise ValueError("Expected an unchanged native summary")
    resolved = candidate.resolve()
    if not any(root.resolve() in resolved.parents
               for root in (sequence.output_root, sequence.hext_scratch)):
        raise ValueError("Native summary outside resolved H-EXT roots")
    return candidate


def annotate_table(path, originals, sequence):
    fields, rows = read_csv(path)
    changed = []
    for index, row in enumerate(rows, 2):
        notes = json.loads(row["notes"])
        if row["geometric_audit_status"] != "UNAVAILABLE" or notes.get("result_reused") is not False:
            continue
        native_path = resolve_native(notes["native_source"], sequence)
        if sha256_file(native_path) != notes["native_sha256"]:
            raise RuntimeError("Native summary differs from the aggregate provenance")
        native = read_json(native_path)
        geometry = native["geometric_audit"]
        if geometry.get("terminal_status") != "UNAVAILABLE" or geometry.get("error") != ERROR:
            continue
        if (native["sequence_id"], native["configuration_id"], native["start_mode"]) != (
                row["sequence_id"], row["method_id"], row["start_convention"]):
            raise RuntimeError("Native summary and aggregate row identities differ")
        if row["evaluation_status"] not in ("COMPLETED", "AVAILABLE"):
            raise RuntimeError("D6 annotation requires an available evaluated row")
        row["evaluation_status"] = "AVAILABLE_GEOMETRIC_AUDIT_FAIL"
        notes["geometry_status_bookkeeping"] = {
            "classification": CLASSIFICATION, "original_error": ERROR,
            "geometric_statistics": "UNAVAILABLE_PRECONDITION_FAILED_BEFORE_STATISTICS",
            "thresholds_or_audit_recomputed": False,
            "authorization": "H-EXT-02 D6 and bookkeeping self-adjudication",
        }
        row["notes"] = json.dumps(notes, ensure_ascii=False, sort_keys=True)
        changed.append({"line": index, "sequence_id": row["sequence_id"],
                        "method_id": row["method_id"], "start_convention": row["start_convention"]})
    if not changed:
        raise RuntimeError("No exact precondition failure rows found for the authorized D6 annotation")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    old_fields, before = read_csv(originals / path.name)
    new_fields, after = read_csv(path)
    if old_fields != new_fields or len(before) != len(after):
        raise RuntimeError("Bookkeeping altered aggregate topology")
    for old, new in zip(before, after):
        if any(old[key] != new[key] for key in NUMERIC_FIELDS):
            raise RuntimeError("Bookkeeping altered a numeric metric/count token")
        if any(old[key] != new[key] for key in fields if key not in ("evaluation_status", "notes")):
            raise RuntimeError("Bookkeeping altered a protected aggregate field")
    return changed


def main():
    sequence, scratch, archive = stage_roots()
    freeze = read_json(scratch / "03_PREREG/CODE_FREEZE.json")
    before_freeze = verify_freeze(sequence, freeze)
    records = read_json(scratch / "EXECUTION_RECORDS.json")
    ledger = {"native_actual": len(records),
              "evaluator_actual": sum(len(record["evaluations"]) for record in records),
              "native_budget": 14, "evaluator_budget": 28,
              "prereg_identity_native": 2, "prereg_identity_evaluator": 0}
    output = scratch / "08_AGGREGATE"
    originals = scratch / ORIGINAL_DIRECTORY
    if any(path.exists() for path in (output, originals, scratch / "09_LEGSA_GAP_DIAGNOSTIC",
                                     archive / "08_AGGREGATE", archive / ORIGINAL_DIRECTORY,
                                     archive / "09_LEGSA_GAP_DIAGNOSTIC")):
        raise FileExistsError("Aggregation/diagnostic/bookkeeping destinations must all be new")
    aggregate_stage(sequences={name: load_sequence_paths(name) for name in ("BY2", "BY2H", "BY2O")},
                    records=records, output_root=output, code_commit=freeze["code_freeze"],
                    budget_ledger=ledger)
    originals.mkdir()
    for name in PRESERVED:
        with (output / name).open("rb") as source, (originals / name).open("xb") as target:
            shutil.copyfileobj(source, target)
        if sha256_file(output / name) != sha256_file(originals / name):
            raise RuntimeError("Original aggregate byte preservation failed")
    original_hashes = {name: sha256_file(originals / name) for name in PRESERVED}
    changed = {name: annotate_table(output / name, originals, sequence) for name in TABLES}
    definition_path = output / "FIELD_DEFINITIONS.json"
    definitions = read_json(definition_path)
    definitions["geometry_precondition_status_bookkeeping"] = {
        "classification": CLASSIFICATION,
        "evaluation_status": "AVAILABLE_GEOMETRIC_AUDIT_FAIL",
        "geometric_audit_status": "UNAVAILABLE", "original_error": ERROR,
        "rule": "Exact frozen precondition failure; no numeric audit statistics inferred or recomputed",
    }
    write_json(definition_path, definitions, replace=True)
    summary_path = output / "FINAL_SUMMARY.json"
    summary = read_json(originals / "FINAL_SUMMARY.json")
    original_selection = json.dumps(summary["selection"], sort_keys=True)
    summary["geometry_status_bookkeeping"] = {
        "classification": CLASSIFICATION, "original_hashes": original_hashes,
        "changed_rows": changed, "numeric_tokens_unchanged": True,
        "main_selection_unchanged": True,
        "receipt": alias_path(originals / "BOOKKEEPING_RECEIPT.json", sequence),
    }
    for name in (*TABLES, "FIELD_DEFINITIONS.json"):
        summary["files_sha256"][name] = sha256_file(output / name)
    write_json(summary_path, summary, replace=True)
    updated = read_json(summary_path)
    if json.dumps(updated["selection"], sort_keys=True) != original_selection:
        raise RuntimeError("Bookkeeping changed the registered main-version selection")
    protected_summary = {k: v for k, v in updated.items() if k not in ("files_sha256", "geometry_status_bookkeeping")}
    original_summary = {k: v for k, v in read_json(originals / "FINAL_SUMMARY.json").items()
                        if k != "files_sha256"}
    if protected_summary != original_summary:
        raise RuntimeError("Bookkeeping changed protected final-summary fields")
    run_legsa_gap_diagnostic(stage_root=scratch, code_commit=freeze["code_freeze"])
    after_freeze = verify_freeze(sequence, freeze)
    receipt = {
        "status": "APPLIED_D6_GEOMETRIC_PRECONDITION_STATUS_BOOKKEEPING",
        "authorization": "H-EXT-02 D6; bookkeeping self-adjudication",
        "original_hashes": original_hashes,
        "updated_hashes": {name: sha256_file(output / name) for name in PRESERVED},
        "changed_rows": changed, "numeric_tokens_unchanged": True, "main_selection_unchanged": True,
        "original_bytes_preserved": True, "audit_recomputed": False,
        "epoch_deletion": False, "threshold_changes": False,
        "scientific_freeze_before": before_freeze, "scientific_freeze_after": after_freeze,
        "actual_stage_budget": ledger, "wrapper_native_invocations": 0,
        "wrapper_evaluator_invocations": 0, "wrapper_trace_payload_reads": 0,
        "data_mode": "real_external_and_frozen_comparison",
        "synthetic_data_used": False, "semisynthetic_data_used": False,
    }
    write_json(originals / "BOOKKEEPING_RECEIPT.json", receipt)
    archive_receipts = {}
    for name in ("08_AGGREGATE", "09_LEGSA_GAP_DIAGNOSTIC", ORIGINAL_DIRECTORY):
        archive_receipts[name] = archive_batch(scratch / name, archive / name,
                                              scratch / "ARCHIVE_LEDGER.jsonl", name)
    verify_freeze(sequence, freeze)
    print(json.dumps({"status": receipt["status"], "budget_ledger": ledger,
                      "changed_rows": changed, "selection": summary["selection"],
                      "archive_receipts": archive_receipts,
                      "receipt": alias_path(archive / ORIGINAL_DIRECTORY / "BOOKKEEPING_RECEIPT.json", sequence)},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
