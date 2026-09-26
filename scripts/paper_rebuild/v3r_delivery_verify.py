#!/usr/bin/env python3
"""Read-only final acceptance of V3-01-R with an explicitly skipped package.

Only existing JSON receipts, pinned aggregate files and the 30 figure exports
are read. No ZIP is needed or opened; no reporting or scientific code is imported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CONTROL = "00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION"
DISPOSITION = "09_HANDOFF/PACKAGE_DISPOSITION.json"
DONE = "00_CONTROL/DONE.json"
RENDER = "08_FIGURES/RENDER_MANIFEST.json"
VISUAL = "09_HANDOFF/VISUAL_REVIEW.json"
BASELINE = CONTROL + "/BASELINE.json"
MACHINE = CONTROL + "/MACHINE_QA_AND_TABLE_IDENTITY.json"
REQUIRED = {DONE, RENDER, VISUAL, BASELINE, MACHINE,
    *(CONTROL + "/" + name for name in
      ("PACKAGE_CANCELLATION.json", "PACKAGE_CLEANUP_MANIFEST.json", "PACKAGE_CLEANUP_RECEIPT.json"))}
FIGURES = {*(f"MFIG{i:02}" for i in range(7)), "SFIG01", "FIG02S", "FIG02S-b"}
TABLE_ROOTS = {"07_AGGREGATE", "07C_FAILURE_FAMILY_CONFIG", "07D_CLASSIFICATION_PROVENANCE"}


def require(condition, reason):
    if not condition:
        raise ValueError("HARD_STOP_V3R_DELIVERY_" + reason)


def path_under(root, name):
    relative = Path(name)
    require(not relative.is_absolute() and ".." not in relative.parts, "PATH")
    path = root / relative
    require(all(not part.is_symlink() for part in (path, *path.parents)), "SYMLINK")
    require(path.is_file(), "MISSING_FILE: " + name)
    return path


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def verify(root):
    root = Path(root).absolute()
    disposition_path = path_under(root, DISPOSITION)
    disposition = json.loads(disposition_path.read_text())
    require(disposition.get("status") == "SKIPPED_BY_USER"
        and disposition.get("explicit_user_decision") is True
        and disposition.get("zip_required") is False, "EXPLICIT_PACKAGE_DECISION")
    pins = disposition.get("files_sha256", {})
    require(set(pins) == REQUIRED, "DISPOSITION_PIN_COVERAGE")
    documents = {}
    for name, expected in pins.items():
        path = path_under(root, name)
        require(digest(path) == expected, "RECEIPT_HASH: " + name)
        documents[name] = json.loads(path.read_text())
    done, rendered, visual = (documents[name] for name in (DONE, RENDER, VISUAL))
    baseline, machine = documents[BASELINE], documents[MACHINE]
    tables = baseline.get("files_sha256", {})
    require(baseline.get("status") == "PASS_REVIEWED_TABLE_BASELINE"
        and baseline.get("csv_count") == 59 and len(tables) == 65
        and sum(name.endswith(".csv") for name in tables) == 59
        and {"07_AGGREGATE/AGGREGATE_MANIFEST.json", "07C_FAILURE_FAMILY_CONFIG/MANIFEST.json",
             "07D_CLASSIFICATION_PROVENANCE/MANIFEST.json"} <= set(tables), "TABLE_INVENTORY")
    for name, expected in tables.items():
        relative = Path(name)
        require(len(relative.parts) == 2 and relative.parts[0] in TABLE_ROOTS
            and relative.suffix in {".csv", ".json", ".md"}, "TABLE_PATH")
        require(digest(path_under(root, name)) == expected, "TABLE_HASH: " + name)
    require(machine.get("status") == "PASS_TEN_FIGURES_MACHINE_QA_TABLES_UNCHANGED"
        and machine.get("baseline_sha256") == pins[BASELINE]
        and machine.get("render_manifest_sha256") == pins[RENDER]
        and machine.get("files_sha256") == tables and machine.get("csv_count") == 59
        and machine.get("qa_checks") == 69 and machine.get("exports") == 30, "MACHINE_BINDING")
    require(done.get("status") == "DONE_MATRIX_AGGREGATE_FIGURES_MACHINE_QA"
        and done.get("render_manifest_sha256") == pins[RENDER]
        and done.get("visual_review_sha256") == pins[VISUAL]
        and done.get("table_identity_receipt_sha256") == pins[MACHINE]
        and done.get("visual_review_status") == "PASS"
        and done.get("table_hashes_unchanged") is True and done.get("csv_count") == 59
        and done.get("figure_repair_commit") == machine.get("figure_repair_commit")
        and bool(done.get("figure_repair_commit")), "DONE_BINDING")
    require(done.get("aggregate_manifest_sha256") == tables.get("07_AGGREGATE/AGGREGATE_MANIFEST.json")
        and done.get("full_ablation_failure_appendix_sha256") == tables.get("07C_FAILURE_FAMILY_CONFIG/MANIFEST.json")
        and done.get("science_freeze") == baseline.get("science_freeze") == rendered.get("code_freeze")
        and bool(done.get("science_freeze")), "SOURCE_BINDING")
    require(all(document.get(field) == 0 for document in (done, machine)
        for field in ("native_calls", "evaluator_calls", "aggregate_calls")), "SCIENTIFIC_CALLS")
    entries = rendered.get("figures", [])
    require(rendered.get("status") == "COMPLETE" and rendered.get("requested_count") == 10
        and rendered.get("rendered_count") == 10 and len(entries) == 10
        and {entry.get("figure_id") for entry in entries} == FIGURES, "FIGURE_COVERAGE")
    require(visual.get("status") == "PASS" and visual.get("actual_raster_review") is True
        and visual.get("render_manifest_sha256") == pins[RENDER]
        and len(visual.get("reviewed_figures", [])) == 10 and set(visual["reviewed_figures"]) == FIGURES
        and set(visual.get("figure_results", {})) == FIGURES
        and all(visual["figure_results"][name].get("status") == "PASS" for name in FIGURES), "VISUAL_BINDING")
    exports, checks = {}, 0
    for entry in entries:
        name = entry["figure_id"]
        qa = entry.get("qa", [])
        require(entry.get("status") == "RENDERED" and bool(qa)
            and all(row.get("pass") is True and row.get("figure_id") == name for row in qa), "RECORDED_QA")
        checks += len(qa)
        hashes = entry.get("output_sha256", {})
        require(set(hashes) == {"png", "pdf", "svg"}, "EXPORT_COVERAGE")
        exports[name] = hashes
        for extension, expected in hashes.items():
            require(digest(path_under(root, f"08_FIGURES/{name}/{name}.{extension}")) == expected, "EXPORT_HASH")
    require(checks == 69 and visual.get("figure_output_sha256") == exports, "QA_EXPORT_BINDING")
    return dict(status="PASS_V3R_FINAL_DELIVERY_PACKAGE_SKIPPED_BY_USER",
        package_status="SKIPPED_BY_USER", zip_required=False, done_utc=done.get("utc"),
        figures=10, recorded_machine_checks=checks, verified_exports=30,
        unchanged_files=65, unchanged_csv=59, table_hashes_unchanged=True,
        package_disposition_sha256=digest(disposition_path), files_sha256=pins,
        native_calls=0, evaluator_calls=0, aggregate_calls=0, figure_qa_calls=0, zip_reads=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.root)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps(dict(status="FAIL_V3R_DELIVERY_VERIFICATION", reason=str(error))))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
