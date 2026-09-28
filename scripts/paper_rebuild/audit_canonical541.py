#!/usr/bin/env python3
"""Render, audit, and close canonical541 evidence after final analysis exists.

This entrypoint never generates providers, starts a solver, or evaluates a
trace.  Every subcommand first proves the 7,033-row analysis closure.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.canonical541.evidence import (
    PayloadSpec, create_final_zip, finalize_curated_evidence,
    sha256_file,
)
from legsa_gins.paper_rebuild.canonical541.plots import render_diagnostic_figures
from legsa_gins.paper_rebuild.canonical541.runner import (
    validate_method_counters, validate_output_seal,
)
from legsa_gins.paper_rebuild.canonical541.full_method_registry import FULL_METHODS
from legsa_gins.paper_rebuild.canonical541.ablation_registry import ABLATION_METHODS
from legsa_gins.paper_rebuild.canonical541.raw_audit import TRACE_AUDIT_ROLE
from legsa_gins.paper_rebuild.canonical541.authorization import STAGE_ID, validate_attempt_root
from legsa_gins.paper_rebuild.evidence import BY2_RAW_RELATIVE_PATHS


ANALYSIS_FILES = {
    "full_rows": "FULL_ALGORITHM_ROW_RESULTS.csv.gz",
    "ablation_rows": "INTERNAL_ABLATION_ROW_RESULTS.csv.gz",
    "paired_deltas": "PAIRED_METHOD_DELTAS.csv.gz",
    "recovery_metrics": "RECOVERY_METRICS.csv",
    "finite_failure": "FINITE_AND_FAILURE_SUMMARY.csv",
    "worst_cases": "WORST_CASES.csv",
}
MECHANISM_FILES = {
    "source_aware_actions": "SOURCE_AWARE_ACTIONS.csv.gz",
    "schemec_actions": "SCHEMEC_ACTIONS.csv",
}
DEGRADATION_TYPE_SUMMARY_FILES = (
    "FULL_ALGORITHM_DEGRADATION_TYPE_SUMMARY.csv",
    "INTERNAL_ABLATION_DEGRADATION_TYPE_SUMMARY.csv",
)
CURATED_DEGRADATION_TYPE_SUMMARY_PATHS = tuple(
    f"13_RESULT_ANALYSIS/{name}" for name in DEGRADATION_TYPE_SUMMARY_FILES
)
REQUIRED_ANALYSIS_SUPPORT = (
    "FULL_ALGORITHM_METHOD_SUMMARY.csv", "FULL_ALGORITHM_FAMILY_SUMMARY.csv",
    "INTERNAL_ABLATION_METHOD_SUMMARY.csv", "INTERNAL_ABLATION_FAMILY_SUMMARY.csv",
    *DEGRADATION_TYPE_SUMMARY_FILES,
    "SEED_SIGN_CONSISTENCY.csv", "BOOTSTRAP_INTERVALS.csv",
    "AGGREGATE_CROSSCHECK.json",
)
REQUIRED_MECHANISM_SUPPORT = ("SOURCE_ISOLATION_AUDIT.csv",)
TERMINAL_STATUSES = {"COMPLETED_EVALUABLE", "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF"}
STAGE_ID = "CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX"


class TerminalAuditError(RuntimeError):
    pass


def _read_csv(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        if not reader.fieldnames:
            raise TerminalAuditError(f"CSV has no schema: {path}")
    if not rows:
        raise TerminalAuditError(f"CSV has no rows: {path}")
    return rows


def _truth(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "pass"}


def _load_final_tables(stage: Path) -> dict[str, list[dict[str, str]]]:
    analysis = stage / "13_RESULT_ANALYSIS"
    mechanisms = stage / "14_MECHANISM_ANALYSIS"
    missing = [str(analysis / name) for name in (*ANALYSIS_FILES.values(), *REQUIRED_ANALYSIS_SUPPORT)
               if not (analysis / name).is_file()]
    missing += [str(mechanisms / name) for name in (*MECHANISM_FILES.values(), *REQUIRED_MECHANISM_SUPPORT)
                if not (mechanisms / name).is_file()]
    if missing:
        raise TerminalAuditError(f"analysis is incomplete; audit cannot run: {missing}")
    tables = {key: _read_csv(analysis / name) for key, name in ANALYSIS_FILES.items()}
    tables.update({key: _read_csv(mechanisms / name) for key, name in MECHANISM_FILES.items()})
    full, ablation = tables["full_rows"], tables["ablation_rows"]
    if len(full) != 2164 or len(ablation) != 4869:
        raise TerminalAuditError(f"logical row count mismatch: {len(full)} + {len(ablation)}")
    for label, rows, expected_methods in (
        ("full", full, {f"F{index:02d}" for index in range(1, 5)}),
        ("ablation", ablation, {f"A{index:02d}" for index in range(1, 10)}),
    ):
        counts = Counter(str(row.get("method_id")) for row in rows)
        if set(counts) != expected_methods or set(counts.values()) != {541}:
            raise TerminalAuditError(f"{label} method×case closure mismatch: {dict(counts)}")
        cases = {str(row.get("case_id")) for row in rows}
        if len(cases) != 541 or "C00_clean_normal" not in cases:
            raise TerminalAuditError(f"{label} case closure mismatch")
        statuses = {str(row.get("terminal_status")) for row in rows}
        if not statuses or not statuses.issubset(TERMINAL_STATUSES):
            raise TerminalAuditError(f"{label} unresolved terminal status: {statuses}")
        logical_ids = [str(row.get("logical_id", row.get("logical_row_id", ""))) for row in rows]
        if any(not value for value in logical_ids) or len(set(logical_ids)) != len(rows):
            raise TerminalAuditError(f"{label} logical IDs are missing/duplicated")
    crosscheck = json.loads((analysis / "AGGREGATE_CROSSCHECK.json").read_text(encoding="utf-8"))
    if crosscheck.get("passed") is not True:
        raise TerminalAuditError("aggregate crosscheck has not passed")
    isolation = _read_csv(mechanisms / "SOURCE_ISOLATION_AUDIT.csv")
    if not all(_truth(row.get("passed", row.get("invariant_pass", False))) for row in isolation):
        raise TerminalAuditError("source isolation contains a failed row")
    tables["logical_unique"] = []
    for matrix, rows in (("full_algorithm", full), ("internal_ablation", ablation)):
        run_ids = {str(row.get("run_id", row.get("execution_alias_of", ""))) for row in rows}
        if "" in run_ids:
            raise TerminalAuditError(f"{matrix} result lacks run_id")
        tables["logical_unique"].append({
            "matrix": matrix, "logical_row_count": len(rows),
            "unique_execution_count": len(run_ids),
            "execution_alias_count": len(rows) - len(run_ids),
        })
    return tables


def _table_file_hashes(stage: Path, tables: Mapping[str, Any]) -> dict[str, str]:
    analysis = stage / "13_RESULT_ANALYSIS"; mechanisms = stage / "14_MECHANISM_ANALYSIS"
    hashes = {key: sha256_file(analysis / name) for key, name in ANALYSIS_FILES.items()}
    hashes.update({key: sha256_file(mechanisms / name) for key, name in MECHANISM_FILES.items()})
    # logical_unique is derived from the closed result tables and receives its
    # own deterministic semantic binding.
    encoded = json.dumps(tables["logical_unique"], sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    import hashlib
    hashes["logical_unique"] = hashlib.sha256(encoded).hexdigest()
    return hashes


def _json_gate(path: Path, required: Mapping[str, Any]) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise TerminalAuditError(f"required gate is missing/non-regular: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    mismatches = {key: (payload.get(key), value) for key, value in required.items()
                  if payload.get(key) != value}
    if mismatches:
        raise TerminalAuditError(f"gate mismatch {path.name}: {mismatches}")
    return payload


def _verify_raw_checkpoints(stage: Path) -> dict[str, Any]:
    checkpoints = (
        ("PRE_CODE_FREEZE", "CANONICAL541_RAW_22_PRE_CODE_FREEZE"),
        ("PRE_PROVIDER", "CANONICAL541_RAW_22_PRE_PROVIDER"),
        ("POST_PROVIDER", "CANONICAL541_RAW_22_POST_PROVIDER"),
        ("POST_RUN", "CANONICAL541_RAW_22_POST_RUN"),
    )
    reports = []
    expected_paths = set(BY2_RAW_RELATIVE_PATHS)
    for phase, stem in checkpoints:
        csv_path = stage / "16_AUDITS" / f"{stem}.csv"
        json_path = stage / "16_AUDITS" / f"{stem}.json"
        report = _json_gate(json_path, {
            "audit_phase": phase,
            "expected": 22, "verified": 22, "missing": 0, "mismatch": 0,
            "raw_mutation": 0, "symlink_escape": 0, "passed": True,
            "trace_read_role": TRACE_AUDIT_ROLE,
            "trace_provider_or_solver_input": False,
            "trace_used_online": False,
            "trace_open_count_online": 0,
            "old_provider_solver_input": False,
            "directory_discovery_used": False,
            "checkpoint_pair_complete": True,
        })
        rows = _read_csv(csv_path)
        if len(rows) != 22 or {row.get("relative_path") for row in rows} != expected_paths:
            raise TerminalAuditError(f"raw checkpoint exact 22-row set failed: {stem}")
        if any(
            row.get("audit_phase") != phase
            or row.get("status") != "PASS"
            or row.get("exists") != "True"
            or row.get("regular_file") != "True"
            or row.get("realpath_confined") != "True"
            or row.get("no_symlink_components") != "True"
            for row in rows
        ):
            raise TerminalAuditError(f"raw checkpoint row-level closure failed: {stem}")
        if report.get("checkpoint_csv_sha256") != sha256_file(csv_path):
            raise TerminalAuditError(f"raw checkpoint CSV/JSON binding failed: {stem}")
        reports.append(report)
    locks = {row.get("raw_hash_lock_sha256") for row in reports}
    hashes = [row.get("verified_hashes") for row in reports]
    if len(locks) != 1 or None in locks or any(value != hashes[0] for value in hashes[1:]) or len(hashes[0] or {}) != 22:
        raise TerminalAuditError("raw checkpoint hash identity/mutation closure failed")
    return {"checkpoint_count": 4, "verified_each": 22,
            "raw_hash_lock_sha256": next(iter(locks)), "raw_mutation": 0}


def _verify_code_freeze(stage: Path) -> dict[str, Any]:
    gate = _json_gate(stage / "01_GIT_FREEZE" / "CANONICAL541_CODE_FREEZE.json", {
        "stage_id": STAGE_ID, "passed": True,
        "provider_generation_count_at_freeze": 0,
        "formal_solver_run_count_at_freeze": 0,
        "trace_open_count_at_freeze": 0,
        "worktree_clean": True,
        "degraded_provider_generation_started_before_freeze": False,
        "formal_solver_run_started_before_freeze": False,
    })
    commit = str(gate.get("code_freeze_commit", ""))
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise TerminalAuditError("code-freeze commit is not an exact SHA")
    if not re.fullmatch(r"[0-9a-f]{64}", str(gate.get("executable_sha256", ""))):
        raise TerminalAuditError("code-freeze executable SHA256 is absent/invalid")
    completed = subprocess.run(("git", "merge-base", "--is-ancestor", commit, "HEAD"),
                               cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise TerminalAuditError("code-freeze commit is not an ancestor of current HEAD")
    return {"code_freeze_commit": commit, "git_ancestor_check": True,
            "gate_sha256": sha256_file(stage / "01_GIT_FREEZE" / "CANONICAL541_CODE_FREEZE.json")}


def _verify_provider_gate(stage: Path) -> dict[str, Any]:
    gate = _json_gate(stage / "06_PROVIDER_READY" / "PROVIDER_GATE.json", {
        "provider_generation": 541, "effect_validation": 541, "provider_ready": 541,
        "trace_open_count": 0, "raw_mutation": 0, "provider_sha_closure": True,
        "passed": True,
    })
    manifest = _read_csv(stage / "06_PROVIDER_READY" / "CANONICAL541_PROVIDER_READY_MANIFEST.csv")
    effects = _read_csv(stage / "06_PROVIDER_READY" / "CANONICAL541_EFFECT_VALIDATION_RESULTS.csv")
    if (len(manifest) != 541 or len(effects) != 541
            or len({row.get("case_id") for row in manifest}) != 541
            or not all(_truth(row.get("provider_ready")) and _truth(row.get("effect_validation_passed")) for row in manifest)
            or not all(_truth(row.get("passed")) for row in effects)):
        raise TerminalAuditError("provider/effect 541-row closure failed")
    case_manifest = _read_csv(stage / "02_MATRIX_SPEC_LOCK" / "CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv")
    if len(case_manifest) != 541 or len({row.get("case_id") for row in case_manifest}) != 541:
        raise TerminalAuditError("canonical case manifest count/identity failed")
    if any("placeholder" in json.dumps(row).lower() for row in case_manifest):
        raise TerminalAuditError("canonical case manifest contains a placeholder")
    return {"case_count": 541, "provider_ready": 541, "effect_validation": 541,
            "provider_sha_rows": int(gate.get("provider_sha_rows", 0))}


def _verify_queue(path: Path, methods: set[str], expected_rows: int) -> list[dict[str, str]]:
    rows = _read_csv(path)
    counts = Counter(str(row.get("method_id")) for row in rows)
    if (len(rows) != expected_rows or set(counts) != methods or set(counts.values()) != {541}
            or len({row.get("logical_id") for row in rows}) != expected_rows
            or not all(_truth(row.get("provider_ready")) and _truth(row.get("formal")) for row in rows)
            or any(_truth(row.get("trace_used_online")) or _truth(row.get("per_case_tuning"))
                   or _truth(row.get("metric_driven_rerun")) for row in rows)):
        raise TerminalAuditError(f"queue contract failed: {path}")
    return rows


def _verify_attempts(path: Path, unique_ids: set[str], stage: Path) -> tuple[dict[str, Any], set[Path]]:
    rows = _read_csv(path)
    by_run = Counter(str(row.get("run_id")) for row in rows)
    if set(by_run) != unique_ids or max(by_run.values(), default=0) > 2:
        raise TerminalAuditError("attempt registry does not bind exactly all unique runs")
    technical_retries = 0; authorized_roots: set[Path] = set()
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("run_id")), []).append(row)
        if not _truth(row.get("formal", True)) or _truth(row.get("metric_driven_rerun", False)):
            raise TerminalAuditError("non-formal or metric-driven attempt in registry")
        attempt_number = int(row.get("attempt", row.get("attempt_number", row.get("attempt_index", 1))))
        if not row.get("attempt_root") or not row.get("output_root"):
            raise TerminalAuditError("attempt row requires exact attempt_root and output_root")
        output_root = Path(str(row["output_root"])).resolve(strict=True)
        attempt_root = Path(str(row["attempt_root"])).resolve(strict=False)
        allowed = ((stage / "08_FULL_ALGORITHM_RUNS").resolve(),
                   (stage / "10_INTERNAL_ABLATION_RUNS").resolve())
        if not any(output_root == parent or parent in output_root.parents for parent in allowed):
            raise TerminalAuditError("attempt output_root escaped the two formal run roots")
        expected_attempt = output_root.parent / ".attempts" / str(row["run_id"]) / f"attempt_{attempt_number:02d}"
        if attempt_root != expected_attempt:
            raise TerminalAuditError("attempt_root does not match canonical pre-promotion path")
        # A terminal attempt is atomically promoted to output_root, so its old
        # attempt_root legitimately no longer exists. Failed technical attempts
        # remain at the exact attempt_root and are audited there.
        authorized_roots.add(output_root)
        if attempt_root.exists():
            if not attempt_root.is_dir():
                raise TerminalAuditError("existing attempt_root is not a directory")
            authorized_roots.add(attempt_root.resolve(strict=True))
        if attempt_number > 1:
            technical_retries += 1
    for run_id, group in grouped.items():
        ordered = sorted(group, key=lambda row: int(row.get("attempt", row.get("attempt_number", 1))))
        numbers = [int(row.get("attempt", row.get("attempt_number", 1))) for row in ordered]
        if numbers not in ([1], [1, 2]):
            raise TerminalAuditError(f"attempt numbering is not exact for {run_id}: {numbers}")
        if numbers == [1, 2] and not (
            ordered[0].get("terminal_status") == "TECHNICAL_FAILURE_RETRYABLE"
            and _truth(ordered[0].get("retry_authorized"))
            and _truth(ordered[1].get("technical_retry"))
        ):
            raise TerminalAuditError("attempt_02 lacks exact technical authorization from attempt_01")
    return ({"attempt_rows": len(rows), "technical_retry_count": technical_retries,
             "max_attempts_per_unique_run": max(by_run.values(), default=0)}, authorized_roots)


def _verify_runtime_and_seal(stage: Path, raw_root: Path) -> dict[str, Any]:
    seal_root = stage / "11_OUTPUT_SEAL"
    journal = validate_output_seal(seal_root, raw_root=raw_root)
    unique = _read_csv(seal_root / "UNIQUE_RUN_TERMINAL_REGISTRY.csv")
    logical = _read_csv(seal_root / "LOGICAL_RESULT_TERMINAL_REGISTRY.csv")
    if (len(logical) != 7033 or len({row.get("logical_id") for row in logical}) != 7033
            or any(row.get("terminal_status") not in TERMINAL_STATUSES for row in logical)):
        raise TerminalAuditError("terminal logical registry is unresolved")
    unique_ids = {str(row.get("run_id")) for row in unique}
    if "" in unique_ids or len(unique_ids) != len(unique):
        raise TerminalAuditError("unique terminal registry identity failed")
    attempts, attempt_roots = _verify_attempts(seal_root / "RUN_ATTEMPTS.csv", unique_ids, stage)
    manifest = _read_csv(seal_root / "OUTPUT_HASH_MANIFEST.csv")
    proof_rows = {str(row["run_id"]): row for row in manifest
                  if row.get("relative_path") == "CANONICAL541_EXECUTION_PROOF.json"}
    run_manifest_rows = {str(row["run_id"]): row for row in manifest
                         if row.get("relative_path") == "RUN_MANIFEST.json"}
    if set(proof_rows) != unique_ids:
        raise TerminalAuditError("every unique run must have exactly one sealed execution proof")
    profiles = {row.method_id: row for row in (*FULL_METHODS, *ABLATION_METHODS)}
    registered_manifests: set[Path] = set()
    evaluable = 0; failure = 0
    false_fields = (
        "trace_used_online", "synthetic_data_used", "semisynthetic_data_used",
        "receiver_imu_as_body_imu", "final_v23_output_solver_input", "LegSA_output_solver_input",
        "per_case_tuning", "output_only_correction", "epoch_deleted_for_metric",
        "enable_qa_fallback", "qa_active_mode", "enable_multi_state_qm", "selected_fgo_feedback",
        "no_feedback_fgo", "active_nine_factor_fgo", "contact_fk_factor",
    )
    for run_id, row in proof_rows.items():
        run_root = Path(row["run_root"]).resolve(strict=True)
        allowed_roots = ((stage / "08_FULL_ALGORITHM_RUNS").resolve(),
                         (stage / "10_INTERNAL_ABLATION_RUNS").resolve())
        if not any(run_root == allowed or allowed in run_root.parents for allowed in allowed_roots):
            raise TerminalAuditError("sealed run root escaped current formal run directories")
        proof_path = run_root / row["relative_path"]
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        if (proof.get("run_id") != run_id or proof.get("terminal_status") not in TERMINAL_STATUSES
                or proof.get("trace_used_online") is not False
                or proof.get("metric_driven_rerun") is not False
                or proof.get("solver_read_ledger", {}).get("passed") is not True
                or proof.get("solver_read_ledger", {}).get("trace_open_count") != 0
                or proof.get("solver_read_ledger", {}).get("raw_root_open_count") != 0
                or proof.get("solver_read_ledger", {}).get("legacy_open_count") != 0
                or any(int(value) != 0 for value in proof.get("forbidden_counts", {}).values())):
            raise TerminalAuditError(f"execution proof boundary failed: {run_id}")
        case_id = str(proof.get("case_id", "")); method_id = str(proof.get("method_id", ""))
        if (case_id != "C00_clean_normal" and not re.fullmatch(r"D(?:0[1-9]|[1-5][0-9]|60)_seed_0[0-8]", case_id)):
            raise TerminalAuditError(f"out-of-scope case executed: {case_id}")
        if method_id not in profiles:
            raise TerminalAuditError(f"out-of-scope method executed: {method_id}")
        manifest_row = run_manifest_rows.get(run_id)
        if proof["terminal_status"] == "COMPLETED_EVALUABLE" and manifest_row is None:
            raise TerminalAuditError(f"evaluable run lacks sealed RUN_MANIFEST: {run_id}")
        if manifest_row is not None:
            manifest_path = run_root / manifest_row["relative_path"]
            registered_manifests.add(manifest_path.resolve())
            runtime_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (any(runtime_manifest.get(field) is not False for field in false_fields)
                    or runtime_manifest.get("old_runtime_input_count") != 0
                    or runtime_manifest.get("legacy_provider_input_count") != 0
                    or runtime_manifest.get("legacy_row_input_count") != 0
                    or runtime_manifest.get("legacy_aggregate_input_count") != 0):
                raise TerminalAuditError(f"forbidden runtime manifest field: {run_id}")
        if proof["terminal_status"] == "COMPLETED_EVALUABLE":
            evaluable += 1
            validate_method_counters(profiles[method_id], runtime_manifest)
        else:
            failure += 1
    actual_manifests = {path.resolve() for directory in (stage / "08_FULL_ALGORITHM_RUNS", stage / "10_INTERNAL_ABLATION_RUNS")
                        for path in directory.rglob("RUN_MANIFEST.json") if path.is_file()}
    authorized_attempt_manifests = {root / "RUN_MANIFEST.json" for root in attempt_roots
                                    if (root / "RUN_MANIFEST.json").is_file()}
    if actual_manifests != authorized_attempt_manifests or not registered_manifests.issubset(actual_manifests):
        raise TerminalAuditError("unregistered/out-of-scope formal RUN_MANIFEST exists")
    return {"unique_run_count": len(unique), "logical_row_count": len(logical),
            "evaluable_unique_count": evaluable, "algorithm_failure_unique_count": failure,
            "trace_open_count_before_seal": journal["trace_open_count_before_seal"],
            "out_of_scope_run_count": 0, "module_counters_revalidated": evaluable,
            **attempts}


def _verify_evaluator(stage: Path, runtime: Mapping[str, Any]) -> dict[str, Any]:
    root = stage / "12_OFFLINE_EVALUATION"
    aggregate = _json_gate(root / "AGGREGATE_CROSSCHECK.json", {
        "all_outputs_sealed_before_trace": True, "trace_offline_only": True, "passed": True,
    })
    if (int(aggregate.get("unique_output_count", -1)) != runtime["unique_run_count"]
            or int(aggregate.get("evaluable_count", -1)) != runtime["evaluable_unique_count"]):
        raise TerminalAuditError("offline evaluation unique/evaluable count mismatch")
    ledgers = list(root.rglob("EVALUATOR_READ_LEDGER.json"))
    if len(ledgers) != runtime["evaluable_unique_count"]:
        raise TerminalAuditError("evaluator read-ledger count mismatch")
    ledger_hashes = []
    for path in ledgers:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (payload.get("passed") is not True or payload.get("trace_used_online") is not False
                or payload.get("seal_revalidated_before_open") is not True
                or payload.get("unexpected_raw_root_open_count") != 0
                or payload.get("unexpected_runtime_root_open_count") != 0):
            raise TerminalAuditError(f"offline evaluator read-ledger failed: {path}")
        ledger_hashes.append(sha256_file(path))
    summary = {
        "schema_version": "paper_rebuild.canonical541_evaluator_read_ledger_summary.v1",
        "evaluator_read_ledger_count": len(ledgers), "all_passed": True,
        "all_opened_after_output_seal": True, "trace_offline_only": True,
        "ledger_set_sha256": __import__("hashlib").sha256("\n".join(sorted(ledger_hashes)).encode()).hexdigest(),
        "passed": True,
    }
    destination = stage / "16_AUDITS" / "CANONICAL541_EVALUATOR_READ_LEDGER_SUMMARY.json"
    if destination.exists():
        persisted = json.loads(destination.read_text(encoding="utf-8"))
        if persisted != summary:
            raise TerminalAuditError("persisted evaluator read-ledger summary drifted")
    else:
        _atomic_json(destination, summary)
    return summary


def _verify_terminal_gates(stage: Path, raw_root: Path) -> dict[str, Any]:
    code = _verify_code_freeze(stage)
    raw = _verify_raw_checkpoints(stage)
    provider = _verify_provider_gate(stage)
    _verify_queue(stage / "07_FULL_ALGORITHM_REGISTRY" / "FULL_ALGORITHM_QUEUE.csv",
                  {f"F{index:02d}" for index in range(1, 5)}, 2164)
    _verify_queue(stage / "09_INTERNAL_ABLATION_REGISTRY" / "INTERNAL_ABLATION_QUEUE.csv",
                  {f"A{index:02d}" for index in range(1, 10)}, 4869)
    _json_gate(stage / "07_FULL_ALGORITHM_REGISTRY" / "CANONICAL541_C00_STRUCTURAL_GATE.json", {
        "c00_unique_profile_count": 11, "trace_open_count": 0,
        "old_performance_reused": False, "passed": True,
    })
    runtime = _verify_runtime_and_seal(stage, raw_root)
    evaluator = _verify_evaluator(stage, runtime)
    return {"code_freeze": code, "raw": raw, "provider": provider,
            "runtime": runtime, "evaluator": evaluator}


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def render_figures(stage_root: str | Path, attempt_id: str) -> dict[str, Any]:
    stage = validate_attempt_root(stage_root)
    tables = _load_final_tables(stage)
    root = stage / "15_DIAGNOSTIC_FIGURES"
    root.mkdir(parents=True, exist_ok=True)
    staging = root / f".staging_{attempt_id}"
    final = root / "FINALIZED"
    if final.exists() or final.is_symlink():
        raise TerminalAuditError("diagnostic figures are already finalized")
    try:
        report = render_diagnostic_figures(tables=tables, output_root=staging,
                                           table_hashes=_table_file_hashes(stage, tables))
        if report.get("passed") is not True:
            raise TerminalAuditError("FAIL_CANONICAL541_FIGURE_QA")
        os.replace(staging, final)
    except Exception:
        if staging.exists() and staging.name == f".staging_{attempt_id}":
            shutil.rmtree(staging)
        raise
    return {**report, "finalized_root": str(final), "analysis_gate_before_render": True}


def _bind_stage_and_raw(*, local_config: str | Path, stage_root: str | Path) -> tuple[Path, Path]:
    config_path = Path(local_config).resolve(strict=True)
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    paths = payload.get("paths") if isinstance(payload, dict) else None
    if not isinstance(paths, dict) or "runtime_root" not in paths or "raw_root" not in paths:
        raise TerminalAuditError("local config lacks exact runtime_root/raw_root")
    expected_stage = validate_attempt_root(paths["runtime_root"])
    stage = validate_attempt_root(stage_root)
    raw_root = Path(str(paths["raw_root"])).resolve(strict=True)
    if stage != expected_stage:
        raise TerminalAuditError("stage root is not the local-config-bound canonical541 stage")
    return stage, raw_root


def terminal_audit(stage_root: str | Path, local_config: str | Path) -> dict[str, Any]:
    stage, raw_root = _bind_stage_and_raw(local_config=local_config, stage_root=stage_root)
    tables = _load_final_tables(stage)
    gates = _verify_terminal_gates(stage, raw_root)
    figures = stage / "15_DIAGNOSTIC_FIGURES" / "FINALIZED" / "FIGURE_RENDER_QA.json"
    if not figures.is_file():
        raise TerminalAuditError("figure QA is absent; terminal audit cannot pass")
    figure_qa = json.loads(figures.read_text(encoding="utf-8"))
    if figure_qa.get("passed") is not True or figure_qa.get("figure_count") != 25:
        raise TerminalAuditError("FAIL_CANONICAL541_FIGURE_QA")
    logical_unique = tables["logical_unique"]
    full = tables["full_rows"]; ablation = tables["ablation_rows"]
    terminal = {
        "schema_version": "paper_rebuild.canonical541.terminal_audit.v1",
        "terminal_status": "PASS_CANONICAL541_TERMINAL_ANALYSIS_AND_FIGURE_AUDIT",
        "full_algorithm_logical_rows": len(full),
        "internal_ablation_logical_rows": len(ablation),
        "total_logical_rows": len(full) + len(ablation),
        "logical_vs_unique": logical_unique,
        "all_rows_terminal": True,
        "aggregate_crosscheck": True,
        "source_isolation": True,
        "figure_qa": True,
        "gate_evidence": gates,
        "trace_used_online": False,
        "raw_mutation": gates["raw"]["raw_mutation"],
        "provider_ready_count": gates["provider"]["provider_ready"],
        "unique_run_count": gates["runtime"]["unique_run_count"],
        "technical_retry_count": gates["runtime"]["technical_retry_count"],
        "metric_driven_rerun": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "fgo_qm_qa_contact_count": 0,
        "by3_xb_pg_run_count": gates["runtime"]["out_of_scope_run_count"],
        "controlled_degradations_not_real_scenarios": True,
        "universal_superiority_established": False,
        "by3_xb_fgo_qm_qa_contact_executed": False,
        "passed": True,
    }
    audit_root = stage / "16_AUDITS"
    audit_root.mkdir(parents=True, exist_ok=True)
    destination = audit_root / "CANONICAL541_TERMINAL_AUDIT.json"
    if destination.exists():
        raise TerminalAuditError("terminal audit is immutable and already exists")
    _atomic_json(destination, terminal)
    markdown = audit_root / "CANONICAL541_TERMINAL_AUDIT.md"
    markdown.write_text(
        "# Canonical541 terminal audit\n\n"
        "PASS: 541 controlled cases, 2,164 full-method rows, and 4,869 internal-ablation rows are closed.\n\n"
        "These are controlled degradations, not 60 real scenarios. Universal superiority is not established.\n",
        encoding="utf-8",
    )
    return terminal


def _classification(relative: str) -> tuple[str, str]:
    head = relative.split("/", 1)[0]
    if head == "00_AUTHORIZATION":
        return "human_authorization", "current_stage_governance"
    if head == "01_GIT_FREEZE":
        return "git_and_code_freeze", "current_tracked_identity"
    if head in {"02_MATRIX_SPEC_LOCK", "03_SEEDS_AND_ANCHORS", "04_EFFECT_RULES"}:
        return "frozen_protocol", "current_tracked_or_generated_protocol"
    if head in {"06_PROVIDER_READY", "07_FULL_ALGORITHM_REGISTRY", "09_INTERNAL_ABLATION_REGISTRY"}:
        return "registry", "current_clean_registry"
    if head == "11_OUTPUT_SEAL":
        return "output_seal", "current_clean_runtime_hash_index"
    if head == "12_OFFLINE_EVALUATION":
        return "evaluation_audit", "current_offline_same_source_evaluation"
    if head == "13_RESULT_ANALYSIS":
        return "aggregate_analysis", "current_controlled_degradation_result"
    if head == "14_MECHANISM_ANALYSIS":
        return "mechanism_analysis", "current_bounded_mechanism_evidence"
    if head == "15_DIAGNOSTIC_FIGURES":
        return "diagnostic_figure", "current_diagnostic_only"
    if head == "16_AUDITS":
        return "terminal_audit", "current_clean_audit"
    raise TerminalAuditError(f"payload path has no approved classification: {relative}")


def _curated_paths(stage: Path) -> list[Path]:
    """Return only the bounded, lightweight final evidence allowlist."""

    required = [
        "00_AUTHORIZATION/CANONICAL541_AUTHORIZATION.json",
        "00_AUTHORIZATION/CANONICAL541_AUTHORIZATION.md",
        "01_GIT_FREEZE/CANONICAL541_GIT_ENTRY_FREEZE.json",
        "01_GIT_FREEZE/CANONICAL541_CODE_FREEZE.json",
        "02_MATRIX_SPEC_LOCK/CANONICAL_BY2_DEGRADATION_TYPE_REGISTRY.csv",
        "02_MATRIX_SPEC_LOCK/CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv",
        "02_MATRIX_SPEC_LOCK/CANONICAL_BY2_CASE_SPEC_SCHEMA.json",
        "02_MATRIX_SPEC_LOCK/CANONICAL_BY2_CASE_FAMILY_SUMMARY.csv",
        "02_MATRIX_SPEC_LOCK/CANONICAL_BY2_CASE_COUNT_DECISION.md",
        "02_MATRIX_SPEC_LOCK/FROZEN_GENERATOR_SOURCE_MAP.csv",
        "02_MATRIX_SPEC_LOCK/PARAMETER_PROVENANCE_REGISTRY.csv",
        "02_MATRIX_SPEC_LOCK/PARAMETER_PROVENANCE_REPORT.json",
        "02_MATRIX_SPEC_LOCK/PARAMETER_PROVENANCE_REPORT.md",
        "02_MATRIX_SPEC_LOCK/CLEAN_SOURCE_SPEC_MIGRATION_REPORT.json",
        "02_MATRIX_SPEC_LOCK/canonical_by2_degradation_541.yaml",
        "02_MATRIX_SPEC_LOCK/canonical_by2_full_method_modes.yaml",
        "02_MATRIX_SPEC_LOCK/canonical_by2_internal_ablation_modes.yaml",
        "03_SEEDS_AND_ANCHORS/CANONICAL_BY2_RANDOM_SEED_MANIFEST.csv",
        "03_SEEDS_AND_ANCHORS/CANONICAL_BY2_ANCHOR_SELECTION_MANIFEST.csv",
        "03_SEEDS_AND_ANCHORS/CANONICAL541_ANCHOR_SOURCE_PROVENANCE.json",
        "03_SEEDS_AND_ANCHORS/canonical_by2_seed_anchor_policy.yaml",
        "04_EFFECT_RULES/CANONICAL_BY2_EFFECT_VALIDATION_RULES.csv",
        "04_EFFECT_RULES/canonical_by2_effect_validation.yaml",
        "06_PROVIDER_READY/CANONICAL541_PROVIDER_READY_MANIFEST.csv",
        "06_PROVIDER_READY/CANONICAL541_EFFECT_VALIDATION_RESULTS.csv",
        "06_PROVIDER_READY/EFFECT_VALIDATION_DETAIL_TABLE.csv",
        "06_PROVIDER_READY/EFFECT_VALIDATION_FAILURES.csv",
        "06_PROVIDER_READY/COMPONENT_VALIDATION_TABLE.csv",
        "06_PROVIDER_READY/PROVIDER_SHA256_MANIFEST.csv",
        "06_PROVIDER_READY/PROVIDER_GATE.json",
        "07_FULL_ALGORITHM_REGISTRY/FULL_ALGORITHM_QUEUE.csv",
        "07_FULL_ALGORITHM_REGISTRY/CANONICAL541_C00_STRUCTURAL_GATE.json",
        "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv",
        "11_OUTPUT_SEAL/OUTPUT_HASH_MANIFEST.csv",
        "11_OUTPUT_SEAL/OUTPUT_SEAL_JOURNAL.json",
        "11_OUTPUT_SEAL/UNIQUE_RUN_TERMINAL_REGISTRY.csv",
        "11_OUTPUT_SEAL/LOGICAL_RESULT_TERMINAL_REGISTRY.csv",
        "11_OUTPUT_SEAL/RUN_ATTEMPTS.csv",
        "12_OFFLINE_EVALUATION/AGGREGATE_CROSSCHECK.json",
        "13_RESULT_ANALYSIS/FULL_ALGORITHM_ROW_RESULTS.csv.gz",
        "13_RESULT_ANALYSIS/INTERNAL_ABLATION_ROW_RESULTS.csv.gz",
        "13_RESULT_ANALYSIS/PAIRED_METHOD_DELTAS.csv.gz",
        "13_RESULT_ANALYSIS/FULL_ALGORITHM_METHOD_SUMMARY.csv",
        "13_RESULT_ANALYSIS/FULL_ALGORITHM_FAMILY_SUMMARY.csv",
        "13_RESULT_ANALYSIS/INTERNAL_ABLATION_METHOD_SUMMARY.csv",
        "13_RESULT_ANALYSIS/INTERNAL_ABLATION_FAMILY_SUMMARY.csv",
        *CURATED_DEGRADATION_TYPE_SUMMARY_PATHS,
        "13_RESULT_ANALYSIS/SEED_SIGN_CONSISTENCY.csv",
        "13_RESULT_ANALYSIS/BOOTSTRAP_INTERVALS.csv",
        "13_RESULT_ANALYSIS/WORST_CASES.csv",
        "13_RESULT_ANALYSIS/RECOVERY_METRICS.csv",
        "13_RESULT_ANALYSIS/METHOD_CLEAN_PENALTIES.csv",
        "13_RESULT_ANALYSIS/FINITE_AND_FAILURE_SUMMARY.csv",
        "13_RESULT_ANALYSIS/AGGREGATE_CROSSCHECK.json",
        "14_MECHANISM_ANALYSIS/SOURCE_AWARE_ACTIONS.csv.gz",
        "14_MECHANISM_ANALYSIS/SCHEMEC_ACTIONS.csv",
        "14_MECHANISM_ANALYSIS/SOURCE_ISOLATION_AUDIT.csv",
        "15_DIAGNOSTIC_FIGURES/FINALIZED/FIGURE_RENDER_QA.json",
        "16_AUDITS/CANONICAL541_RAW_22_PRE_CODE_FREEZE.csv",
        "16_AUDITS/CANONICAL541_RAW_22_PRE_CODE_FREEZE.json",
        "16_AUDITS/CANONICAL541_RAW_22_PRE_PROVIDER.csv",
        "16_AUDITS/CANONICAL541_RAW_22_PRE_PROVIDER.json",
        "16_AUDITS/CANONICAL541_RAW_22_POST_PROVIDER.csv",
        "16_AUDITS/CANONICAL541_RAW_22_POST_PROVIDER.json",
        "16_AUDITS/CANONICAL541_RAW_22_POST_RUN.csv",
        "16_AUDITS/CANONICAL541_RAW_22_POST_RUN.json",
        "16_AUDITS/CANONICAL541_EVALUATOR_READ_LEDGER_SUMMARY.json",
        "16_AUDITS/CANONICAL541_FULL_REPORT.json",
        "16_AUDITS/CANONICAL541_FULL_REPORT.md",
        "16_AUDITS/CANONICAL541_READ_ONLY_REVIEW.json",
        "16_AUDITS/CANONICAL541_READ_ONLY_REVIEW.md",
        "16_AUDITS/CANONICAL541_TERMINAL_AUDIT.json",
        "16_AUDITS/CANONICAL541_TERMINAL_AUDIT.md",
        "16_AUDITS/CANONICAL541_PRE_FINAL_CLOSURE_GATE.json",
    ]
    paths = []
    for relative in required:
        path = stage / relative
        if not path.is_file() or path.is_symlink():
            raise TerminalAuditError(f"required curated payload missing/non-regular: {relative}")
        paths.append(path)
    # All 25 PNG/PDF figures are explicit bounded payloads.
    figure_root = stage / "15_DIAGNOSTIC_FIGURES" / "FINALIZED"
    expected_figures = {f"{index:02d}_{suffix}.{extension}"
                        for index, suffix in (
                            (1,"yaw_family_heatmap"),(2,"horizontal_heatmap"),(3,"up_heatmap"),
                            (4,"legsa_vs_strong"),(5,"strong_vs_basic"),(6,"basic_vs_single"),
                            (7,"full_vs_no_rd"),(8,"full_vs_no_sa"),(9,"full_vs_no_rp"),
                            (10,"full_vs_no_hv"),(11,"full_vs_no_go2"),(12,"outage_severity"),
                            (13,"sampling_dropout"),(14,"position_family"),(15,"dual_yaw_family"),
                            (16,"velocity_raw"),(17,"go2_prior_metadata"),(18,"latency"),
                            (19,"mixed_recovery"),(20,"schemec_actions"),(21,"source_aware_scale"),
                            (22,"finite_failure"),(23,"worst_cases"),(24,"logical_unique"),
                            (25,"claim_boundary")) for extension in ("png", "pdf")}
    actual_figures = {path.name for path in figure_root.iterdir() if path.suffix in {".png", ".pdf"}}
    if actual_figures != expected_figures:
        raise TerminalAuditError("diagnostic figure exact filename set mismatch")
    paths.extend(figure_root / name for name in sorted(expected_figures))
    optional = (
        "13_RESULT_ANALYSIS/REPRESENTATIVE_WORST_ERROR_SERIES.csv.gz",
        "13_RESULT_ANALYSIS/REPRESENTATIVE_RECOVERY_ERROR_SERIES.csv.gz",
    )
    paths.extend(stage / relative for relative in optional if (stage / relative).is_file())
    forbidden_directories = {"05_PROVIDER_GENERATION", "08_FULL_ALGORITHM_RUNS", "10_INTERNAL_ABLATION_RUNS"}
    forbidden_suffixes = {".nav", ".std", ".imu", ".gnss"}
    for path in paths:
        relative = path.relative_to(stage)
        if relative.parts[0] in forbidden_directories or path.suffix.lower() in forbidden_suffixes:
            raise TerminalAuditError(f"runtime/provider/raw payload is forbidden from final evidence: {relative}")
    return paths


def _load_and_bind_local_config(*, local_config: str | Path, stage_root: str | Path,
                                export_root: str | Path) -> tuple[Path, Path]:
    config_path = Path(local_config).resolve(strict=True)
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    paths = payload.get("paths") if isinstance(payload, dict) else None
    if not isinstance(paths, dict) or "runtime_root" not in paths or "export_root" not in paths:
        raise TerminalAuditError("local config lacks exact runtime_root/export_root")
    expected_stage = validate_attempt_root(paths["runtime_root"])
    supplied_stage = validate_attempt_root(stage_root)
    expected_export = Path(str(paths["export_root"])).resolve(strict=True)
    supplied_export = Path(export_root).resolve(strict=True)
    if supplied_stage != expected_stage:
        raise TerminalAuditError("stage root is not the local-config-bound canonical541 stage")
    if supplied_export != expected_export:
        raise TerminalAuditError("export root is not the exact local-config export_root")
    if (supplied_stage / "17_FINAL_EVIDENCE").parent != supplied_stage:
        raise TerminalAuditError("stage evidence root identity failed")
    return supplied_stage, supplied_export


def finalize(stage_root: str | Path, export_root: str | Path, timestamp: str,
             attempt_id: str, local_config: str | Path) -> dict[str, Any]:
    if not re.fullmatch(r"\d{8}T\d{6}P0800", timestamp):
        raise TerminalAuditError("timestamp must be YYYYMMDDTHHMMSSP0800")
    stage, export = _load_and_bind_local_config(
        local_config=local_config, stage_root=stage_root, export_root=export_root,
    )
    audit_path = stage / "16_AUDITS" / "CANONICAL541_TERMINAL_AUDIT.json"
    if not audit_path.is_file() or json.loads(audit_path.read_text(encoding="utf-8")).get("passed") is not True:
        raise TerminalAuditError("passing terminal audit is required before evidence finalization")
    # This snapshot is included in the manifest and resolves the otherwise
    # circular question "was finalization authorized before the manifest?".
    pre_final_path = stage / "16_AUDITS" / "CANONICAL541_PRE_FINAL_CLOSURE_GATE.json"
    if pre_final_path.exists() or pre_final_path.is_symlink():
        raise TerminalAuditError("pre-final closure snapshot already exists")
    evidence_root = stage / "17_FINAL_EVIDENCE"
    preexisting_manifest = (evidence_root / "FINALIZED/EVIDENCE_MANIFEST.csv").exists()
    preexisting_sidecar = (evidence_root / "FINALIZED/EVIDENCE_MANIFEST.sha256").exists()
    preexisting_zip = any(path.is_file() and path.name.startswith("LegSA_GINS_CANONICAL541_FINAL_")
                          and path.suffix == ".zip" for path in export.iterdir())
    if preexisting_manifest or preexisting_sidecar or preexisting_zip:
        raise TerminalAuditError("terminal manifest/ZIP existed before the pre-final gate")
    # Build the snapshot before collecting the final allowlist.  It binds the
    # gate identities but deliberately does not predict its own manifest hash.
    _atomic_json(pre_final_path, {
        "schema_version": "paper_rebuild.canonical541.pre_final_closure.v1",
        "terminal_audit_sha256": sha256_file(audit_path),
        "terminal_audit_passed": True,
        "stage_root_role": "clean://stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX",
        "export_root_role": "export://LegSA-GINS-project",
        "manifest_exists_before_snapshot": preexisting_manifest,
        "sidecar_exists_before_snapshot": preexisting_sidecar,
        "final_zip_exists_before_snapshot": preexisting_zip,
        "payload_policy": "explicit_lightweight_allowlist_no_runtime_raw_provider",
        "passed": True,
    })
    paths = _curated_paths(stage)
    payloads = []
    for source in paths:
        relative = source.relative_to(stage).as_posix()
        role, source_class = _classification(relative)
        payloads.append(PayloadSpec(source, relative, role, source_class))
    evidence = finalize_curated_evidence(
        stage_evidence_root=stage / "17_FINAL_EVIDENCE", attempt_id=attempt_id,
        payloads=payloads,
    )
    zip_path = export / f"LegSA_GINS_CANONICAL541_FINAL_{timestamp}.zip"
    archive = create_final_zip(finalized_root=stage / "17_FINAL_EVIDENCE" / "FINALIZED",
                               zip_path=zip_path)
    report = {"terminal_status": "PASS_CANONICAL541_EVIDENCE_CLOSURE",
              "pre_final_gate_sha256": sha256_file(pre_final_path),
              "evidence": evidence, "archive": archive, "passed": True}
    _atomic_json(stage / "16_AUDITS" / "CANONICAL541_FINALIZATION_REPORT.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("figures", "audit"):
        child = subparsers.add_parser(command); child.add_argument("--stage-root", required=True)
        if command == "figures": child.add_argument("--attempt-id", required=True)
        else: child.add_argument("--local-config", required=True)
    final = subparsers.add_parser("finalize")
    final.add_argument("--stage-root", required=True); final.add_argument("--export-root", required=True)
    final.add_argument("--timestamp", required=True); final.add_argument("--attempt-id", required=True)
    final.add_argument("--local-config", required=True)
    all_command = subparsers.add_parser("all")
    all_command.add_argument("--stage-root", required=True); all_command.add_argument("--export-root", required=True)
    all_command.add_argument("--timestamp", required=True); all_command.add_argument("--attempt-id", required=True)
    all_command.add_argument("--local-config", required=True)
    args = parser.parse_args()
    if args.command == "figures":
        payload = render_figures(args.stage_root, args.attempt_id)
    elif args.command == "audit":
        payload = terminal_audit(args.stage_root, args.local_config)
    elif args.command == "finalize":
        payload = finalize(args.stage_root, args.export_root, args.timestamp, args.attempt_id,
                           args.local_config)
    else:
        payload = {
            "figures": render_figures(args.stage_root, args.attempt_id),
            "audit": terminal_audit(args.stage_root, args.local_config),
            "finalize": finalize(args.stage_root, args.export_root, args.timestamp, args.attempt_id,
                                 args.local_config),
        }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
