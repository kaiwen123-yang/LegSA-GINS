#!/usr/bin/env python3
"""Archive H-EXT-02 hard-stop evidence after commit 2; never resume execution.

The requested ZIP name is retained, but its explicit failure manifest and
external receipt identify partial evidence, not completion of the task.
Only bookkeeping helpers are imported from the unexecuted full-task packer.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

import yaml

import hext02_package as packaging
from legsa_gins.paper_rebuild.hext.sequence_paths import LOCAL_CONFIG, load_sequence_paths


STOP_DIRECTORIES = (
    "03_PREREG", "03_PROVIDER_CACHE", "04_NATIVE_RUNS", "04_ACCESS_AUDITS",
    "05_GEOMETRIC_AUDIT", "06_V3_NAV_INPUTS", "07_OFFLINE_EVALUATION",
    "09_LEGSA_GAP_DIAGNOSTIC", "99_HARD_STOP", "RAW_CHECKPOINTS",
)
EXPECTED_BUDGET = {
    "comparison_native_attempted": 14, "comparison_native_completed": 14,
    "prereg_identity_native": 2, "evaluator_attempted": 17,
    "evaluator_passed": 16, "evaluator_failed": 1, "evaluator_not_run": 11,
}
FAILED_RUN_ID = "BY2H__EXT05C-S__FILE_START"
FAILED_VERSION = "v3"


def _stop_gates(sequence, scratch, freeze):
    stop_path = sequence.output_root / "99_HARD_STOP/STOP_REPORT.json"
    stop = packaging._read_json(stop_path)
    if (stop.get("status") != "HARD_STOP_EVALUATOR_CONSISTENCY"
            or stop.get("full_task_completed") is not False
            or stop.get("code_freeze") != freeze["code_freeze"]
            or stop.get("failed_run_id") != FAILED_RUN_ID
            or stop.get("failed_version") != FAILED_VERSION
            or any(stop.get("budget", {}).get(key) != value for key, value in EXPECTED_BUDGET.items())):
        raise RuntimeError("STOP_REPORT does not identify the exact registered hard stop")
    if stop.get("figures_unchanged") is not True or stop.get("scientific_code_unchanged") is not True:
        raise RuntimeError("Frozen figure/source invariance did not pass")
    for root in (sequence.output_root, scratch):
        for name in ("08_AGGREGATE", "10_FIGURES"):
            if (root / name).exists():
                raise RuntimeError("Hard-stop package cannot claim unproduced tables/FIG02S when their output directory exists")
    native_paths = sorted((sequence.output_root / "04_NATIVE_RUNS").rglob("NATIVE_SUMMARY.json"))
    if len(native_paths) != 14 or any(packaging._read_json(path).get("status") != "COMPLETED" for path in native_paths):
        raise RuntimeError("Expected fourteen completed native records")
    evaluation_root = sequence.output_root / "07_OFFLINE_EVALUATION"
    audit_paths = sorted(evaluation_root.rglob("EVALUATOR_STRACE_AUDIT.json"))
    result_paths = sorted(evaluation_root.rglob("EVALUATION_RESULT.json"))
    audits = [(path, packaging._read_json(path)) for path in audit_paths]
    if (len(audits) != 17 or len(result_paths) != 16
            or sum(row.get("passed") is True for _, row in audits) != 16
            or sum(row.get("passed") is False for _, row in audits) != 1
            or any(row.get("trace_open_count") != 1 for _, row in audits)):
        raise RuntimeError("Archived evaluator attempts differ from the 17/16/1 hard stop")
    failed_root = evaluation_root / FAILED_VERSION / FAILED_RUN_ID / "EXACT_EVALUATOR_OUTPUT"
    audit_path, capture_path = failed_root / "EVALUATOR_STRACE_AUDIT.json", failed_root / "EVALUATOR_CAPTURE.json"
    audit, capture = packaging._read_json(audit_path), packaging._read_json(capture_path)
    failure = stop["failure"]
    if (audit.get("passed") is not False or audit.get("exit_code") != 0
            or audit.get("trace_open_count") != 1
            or capture.get("consistency", {}).get("passed") is not False
            or failure.get("pure_io_passed") is not True or failure.get("exit_code") != 0
            or failure.get("trace_open_count") != 1
            or packaging._sha(audit_path) != failure["audit_sha256"]
            or packaging._sha(capture_path) != failure["capture_sha256"]):
        raise RuntimeError("Archived failed evaluator capture/audit differs from sealed stop evidence")
    if not (sequence.output_root / "99_HARD_STOP/EVALUATION_LEDGER.csv").is_file():
        raise RuntimeError("Hard-stop 28-slot evaluation ledger is absent")
    return {
        "status": "HARD_STOP_PARTIAL_EVIDENCE", "delivery_scope": "NOT_FULL_TASK_DELIVERY",
        "full_task_completed": False, "scientific_terminal_status": stop["status"],
        "failed_run_id": FAILED_RUN_ID, "failed_version": FAILED_VERSION,
        "budget": stop["budget"], "stop_report_sha256": packaging._sha(stop_path),
        "failure": failure, "not_produced": stop["not_produced"],
        "08_AGGREGATE": "NOT_PRODUCED_AFTER_HARD_STOP",
        "10_FIGURES/FIG02S": "NOT_PRODUCED_AFTER_HARD_STOP",
        "frozen_figures_unchanged": True, "frozen_scientific_code_unchanged": True,
        "package_integrity_is_not_scientific_completion": True,
        "native_rerun_count": 0, "evaluator_retry_count": 0,
        "full_aggregation_invoked": False, "FIG02S_render_invoked": False,
    }


def _commit_gates(sequence, scratch):
    freeze, commits = packaging._commit_gates(sequence, scratch)
    commits["packaging_helper_sha256"] = commits.pop("packaging_script_sha256")
    commits["packaging_script_sha256"] = packaging._sha(Path(__file__))
    commits["result_commit_scope"] = "HARD_STOP_PARTIAL_EVIDENCE_NOT_FULL_TASK_DELIVERY"
    return freeze, commits


def package_stopped_handoff(local_config=LOCAL_CONFIG):
    local_config = Path(local_config)
    sequence = load_sequence_paths("BY2", local_config=local_config)
    scratch = sequence.hext_scratch / "H_EXT_02"
    local = yaml.safe_load(local_config.read_text(encoding="utf-8"))["paths"]
    handoff = Path(local["handoff_root"])
    if handoff.is_symlink() or not handoff.is_dir():
        raise RuntimeError("Configured handoff_root must exist without a symlink")
    freeze, commits = _commit_gates(sequence, scratch)
    stopped = _stop_gates(sequence, scratch, freeze)
    target, receipt_path = handoff / packaging.ZIP_NAME, handoff / packaging.RECEIPT_NAME
    if target.exists() or receipt_path.exists():
        raise FileExistsError("Final handoff ZIP/receipt already exists; never overwrite")
    # Configure only the imported bookkeeping collector's allowlist.  The full
    # completion gate and full-task package_handoff are deliberately never called.
    original_directories = packaging.STAGE_DIRECTORIES
    optional = ("EVALUATION_RAW_CHECKPOINTS",) if (sequence.output_root / "EVALUATION_RAW_CHECKPOINTS").is_dir() else ()
    packaging.STAGE_DIRECTORIES = STOP_DIRECTORIES + optional
    try:
        entries = packaging._collect(sequence, scratch, freeze, local_config)
    finally:
        packaging.STAGE_DIRECTORIES = original_directories
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_STOP_" + uuid.uuid4().hex[:12]
    build = scratch / "PACKAGE" / stamp
    build.mkdir(parents=True, exist_ok=False)
    stop_manifest = build / "HARD_STOP_MANIFEST.json"
    packaging._write_json(stop_manifest, {
        **stopped, "git_commits": commits,
        "included_prior_passed_evaluations": "Partial evidence only; no selected-version or full three-sequence claim",
        "unused_prepared_scripts": ["hext02_package.py", "hext02_aggregate_bookkeeping.py"],
        "unused_script_inclusion_is_not_an_execution_claim": True,
        "trace_payload_open_count": 0, "raw_payload_open_count": 0,
        "solver_invocation_count": 0, "evaluator_invocation_count": 0,
    })
    entries["HARD_STOP_MANIFEST.json"] = stop_manifest
    local_zip = build / packaging.ZIP_NAME
    members = packaging._create_zip(local_zip, entries, commits, stopped)
    local_validation = packaging._verify_zip(local_zip, members)
    _freeze_after, commits_after = _commit_gates(sequence, scratch)
    if commits_after != commits or _stop_gates(sequence, scratch, freeze) != stopped:
        raise RuntimeError("Commit/source/stop evidence changed while packaging")
    copied = packaging._exclusive_copy(local_zip, target)
    archived_validation = packaging._verify_zip(target, members)
    receipt = {
        "schema_version": "hext.hard_stop_handoff.validation.v1",
        "status": "PASS_INTEGRITY_HARD_STOP_PARTIAL", "delivery_scope": "NOT_FULL_TASK_DELIVERY",
        "full_task_completed": False, "scientific_terminal_status": stopped["scientific_terminal_status"],
        "package": "<HANDOFF_ROOT>/" + packaging.ZIP_NAME,
        "sha256": copied["sha256"], "bytes": copied["size_bytes"], "member_count": len(members),
        "uncompressed_member_bytes": sum(row["size_bytes"] for row in members),
        "git_commits": commits, "failed_run_id": FAILED_RUN_ID, "failed_version": FAILED_VERSION,
        "budget": stopped["budget"], "not_produced": stopped["not_produced"],
        "ext4_build": "<HEXT_SCRATCH>/H_EXT_02/PACKAGE/" + stamp,
        "archive_copy_retries": copied["retries"], "archive_retry_policy": "ENOMEM_OR_EIO_ONLY_MAX_THREE_RETRIES",
        "ext4_validation": local_validation, "archived_validation": archived_validation, "CRC": "PASS",
        "member_manifest_includes_internal_manifest_sha256": True,
        "trace_payload_open_count": 0, "raw_payload_open_count": 0,
        "solver_invocation_count": 0, "evaluator_invocation_count": 0,
        "original_stop_and_bookkeeping_adjudication_preserved": True, "members": members,
    }
    local_receipt = build / packaging.RECEIPT_NAME
    packaging._write_json(local_receipt, receipt)
    receipt_copy = packaging._exclusive_copy(local_receipt, receipt_path)
    compact = {key: receipt[key] for key in (
        "status", "delivery_scope", "full_task_completed", "scientific_terminal_status",
        "package", "sha256", "bytes", "member_count", "CRC", "git_commits",
        "failed_run_id", "failed_version", "budget", "not_produced", "archive_copy_retries",
    )}
    compact.update(external_receipt="<HANDOFF_ROOT>/" + packaging.RECEIPT_NAME,
                   external_receipt_sha256=receipt_copy["sha256"])
    packaging._write_json(build / "FINAL_HANDOFF_RECEIPT.json", compact)
    packaging._exclusive_copy(build / "FINAL_HANDOFF_RECEIPT.json", sequence.output_root / "FINAL_HANDOFF_RECEIPT.json")
    return compact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-config", type=Path, default=LOCAL_CONFIG)
    args = parser.parse_args()
    print(json.dumps(package_stopped_handoff(args.local_config), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
