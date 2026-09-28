"""BY2 fresh provider regression gates without any reference substitution."""
from __future__ import annotations

import csv
import json
from itertools import zip_longest
from pathlib import Path

from ..clean2r2a_runner import EXPECTED_BYTE_PROVIDER_HASHES as BY2_BYTE_PROVIDER_HASHES
from ..manifest import sha256_file
from ..raw_doppler_parity import (
    AUDIT_ONLY_PROVENANCE_COLUMNS,
    EXPECTED_ACTUAL_FULL_SHA256,
    EXPECTED_SOLVER_SEMANTIC_SHA256,
    RawDopplerParityError,
    audit_cpp_provenance_consumption,
    audit_raw_doppler_minimum_sufficient_parity,
    compute_raw_doppler_solver_semantic_sha256,
)
from .provider_contract import SequenceProviderError

EXPECTED_BYTE_PROVIDER_HASHES = {
    "imu_runtime_input": BY2_BYTE_PROVIDER_HASHES["imu"],
    "gnss_runtime_input": BY2_BYTE_PROVIDER_HASHES["gnss"],
    "go2_attitude_prior": BY2_BYTE_PROVIDER_HASHES["go2_roll_pitch"],
    "go2_horizontal_velocity_prior": BY2_BYTE_PROVIDER_HASHES["go2_horizontal_velocity"],
}


def first_difference(expected_path, actual_path, *, csv_format=False, semantic_only=False):
    """Report the first different time/column/cell, preserving original text."""
    with Path(expected_path).open("r", encoding="utf-8-sig", newline="") as reference, Path(actual_path).open("r", encoding="utf-8-sig", newline="") as actual:
        left = csv.reader(reference) if csv_format else (line.split() for line in reference)
        right = csv.reader(actual) if csv_format else (line.split() for line in actual)
        names = None
        for row_number, (expected, got) in enumerate(zip_longest(left, right), start=1):
            if csv_format and row_number == 1:
                names = expected
            if expected is None or got is None:
                return {"row": row_number, "time": (expected or got or [None])[0], "column": "row_count",
                        "expected": expected, "actual": got}
            for column, (want, value) in enumerate(zip_longest(expected, got), start=1):
                name = names[column-1] if names and column <= len(names) else column
                if semantic_only and name in AUDIT_ONLY_PROVENANCE_COLUMNS:
                    continue
                if want != value:
                    return {"row": row_number, "time": expected[0] if expected else None, "column": name,
                            "column_1_based": column, "expected": want, "actual": value}
    return {"difference": "serialized bytes differ but parsed cells agree; check whitespace/newlines"}


def verified_first_difference(reference, actual, *, expected_hash, csv_format=False, semantic_only=False):
    if reference is None:
        return {"status": "FROZEN_REFERENCE_PATH_NOT_PROVIDED"}
    try:
        digest = (compute_raw_doppler_solver_semantic_sha256(reference) if semantic_only else sha256_file(reference))
    except (OSError, RawDopplerParityError) as exc:
        return {"status": "FROZEN_REFERENCE_INTEGRITY_FAILED", "error": str(exc)}
    if digest != expected_hash:
        return {"status": "FROZEN_REFERENCE_INTEGRITY_FAILED", "expected_sha256": expected_hash,
                "actual_sha256": digest}
    return first_difference(reference, actual, csv_format=csv_format, semantic_only=semantic_only)


def validate_by2_parity(payloads, frozen_reference_paths, code_root, report_path):
    """Hard-gate four byte hashes and Doppler's 18 frozen semantic columns."""
    if payloads["dataset_id"] != "BY2":
        raise SequenceProviderError("BY2 regression gate cannot accept another dataset identity")
    if Path(report_path).exists():
        raise FileExistsError(report_path)
    reports = {}
    entries = payloads["providers"]
    for role, expected in EXPECTED_BYTE_PROVIDER_HASHES.items():
        actual_path = Path(entries[role]["path"])
        digest = sha256_file(actual_path)
        row = {"expected_sha256": expected, "actual_sha256": digest, "pass": digest == expected}
        if not row["pass"]:
            reference = frozen_reference_paths.get(role)
            row["first_difference"] = verified_first_difference(reference, actual_path, expected_hash=expected,
                                                               csv_format=role.startswith("go2_"))
        reports[role] = row
    raw_path = Path(entries["raw_doppler_provider"]["path"])
    actual_full = sha256_file(raw_path)
    raw_report = {"expected_solver_semantic_sha256": EXPECTED_SOLVER_SEMANTIC_SHA256,
                  "actual_full_sha256": actual_full, "historical_full_sha256": EXPECTED_ACTUAL_FULL_SHA256,
                  "full_hash_role": "audit_only; C-03 requires the frozen 18-column semantic identity"}
    try:
        semantic = compute_raw_doppler_solver_semantic_sha256(raw_path)
        static = audit_cpp_provenance_consumption(code_root)
        raw_report.update(actual_solver_semantic_sha256=semantic, cpp_provenance_static_audit=static,
                          passed=semantic == EXPECTED_SOLVER_SEMANTIC_SHA256 and static["passed"])
    except RawDopplerParityError as exc:
        raw_report.update(passed=False, semantic_error=str(exc))
    try:
        old = audit_raw_doppler_minimum_sufficient_parity(provider_path=raw_path, repo_root=code_root)
        raw_report.update(old_audit_passed=True, old_audit_report=old)
    except RawDopplerParityError as exc:
        raw_report.update(old_audit_passed=False, old_audit_error=str(exc),
                          old_extra_full_hash_gate_superseded_by_C03_semantic_gate=bool(raw_report["passed"] and actual_full != EXPECTED_ACTUAL_FULL_SHA256))
    if not raw_report["passed"]:
        reference = frozen_reference_paths.get("raw_doppler_provider")
        raw_report["first_difference"] = verified_first_difference(reference, raw_path,
                                                                  expected_hash=EXPECTED_SOLVER_SEMANTIC_SHA256,
                                                                  csv_format=True, semantic_only=True)
    report = {"dataset_id": "BY2", "byte_provider_gates": reports, "raw_doppler_semantic_gate": raw_report,
              "pass": all(row["pass"] for row in reports.values()) and raw_report["passed"],
              "provider_substitution": False, "retry_count": 0}
    report["passed"] = report["pass"]
    with Path(report_path).open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    if not report["pass"]:
        raise SequenceProviderError(f"Fresh BY2 provider parity FAILED; first-difference report: {Path(report_path).name}")
    return report
