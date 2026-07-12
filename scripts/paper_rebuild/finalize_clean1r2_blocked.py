#!/usr/bin/env python3
"""Publish the fail-closed CLEAN1R2 terminal evidence set.

This entrypoint is reporting-only.  It verifies the already recovered archive
and exact-tag proofs, verifies the immutable BY2 raw lock once more, and writes
only terminal BLOCKED records.  It never opens trace, creates a provider, runs
a solver, evaluates a NAV, or executes any four-method process.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.evidence import verify_by2_raw_22, write_raw_audit
from legsa_gins.paper_rebuild.manifest import sha256_file
from legsa_gins.paper_rebuild.paths import is_within, load_clean_paths, load_yaml_mapping


STAGE_ID = "CLEAN1R2_FINAL_V23_ARCHIVE_PARITY_AND_FOUR_METHOD_REEXECUTION"
CASE_ID = "CLEAN1_BY2_CLEAN_NORMAL"
TERMINAL_STATUS = "BLOCKED_CLEAN1R2_EVIDENCE_CONTAMINATION"
UPSTREAM_NOT_RUN = "NOT_RUN_UPSTREAM_EVIDENCE_CONTAMINATION"
ARCHIVE_SHA256 = "45953164c53e102a4ce7e99912535b484d60420ef0de20466252446f3d76b716"
RAW_LOCK_SHA256 = "f6e5d7965d17857e5b4a846501883f4675f2331a1164fab3de9e5ba9470f1ad7"
TAG_NAME = "final-v23-freeze"
TAG_COMMIT = "a906c3a2e704eddbd15ceb3f98f1ba8de85dc410"
TAG_GI_ENGINE_SHA256 = "9c47637868b399afde9432e6ae8931638b02a2a11048f61f1d1653b48303392e"
TAG_GI_ENGINE_HEADER_SHA256 = "97b66d3baef2d5eb139353907b184d36d1b8f4cef2659895ccb94496b6f56e9c"

RECOVERY_LOG_RELATIVE = Path("17_LOGS/CLEAN1R2_FINAL_V23_ARCHIVE_RECOVERY")
TAG_LOG_RELATIVE = Path("17_LOGS/CLEAN1R2_FINAL_V23_TAG_SOURCE")
RECOVERY_ROOT_RELATIVE = Path(
    "16_FINAL_V23_ARCHIVE_RECOVERY/ARCHIVE_45953164c53e"
)
TAG_SOURCE_RELATIVE = RECOVERY_ROOT_RELATIVE / "exact_tag_source"
TERMINAL_LOG_RELATIVE = Path("17_LOGS/CLEAN1R2_FINAL")
CONTRACT_PATH = REPO_ROOT / "configs/paper_rebuild/final_v23_parity_contract.yaml"

CORE_HASHES = {
    "process_data": "91b82997c11f2d5b18858e169c25e5d7c569a9512a88f04f57213f50dfaff221",
    "run_final_mainline": "d3dc8a86a2f9c73cd1e32e83c46d9b390f4696ae2a3b19db43aabd452d3cfcf3",
    "final_mainline_config": "b1c1abc3db42583de3105bcbee3bd782f8b900a3f4a53cbfad49a84979acdd00",
    "evaluator": "aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da",
}

E001_TARGETS = {
    "same_run_actual_runtime_config": (
        "E001_single_nominal_none/kf-gins.yaml",
        "163cada45462b6b17d9b221304fc6faca2f734ce5e3a85db45654b3164e93737",
    ),
    "same_run_actual_runtime_manifest": (
        "E001_single_nominal_none/run_meta.json",
        "1bc4ee6a535dd52cfac738c681fa6e4792def8a48bf46cca2a95277738903d08",
    ),
    "same_run_actual_run_log": (
        "E001_single_nominal_none/run.log",
        "fa3f6f70756d54b848f0d9d24908d5789f4a7ca22b806802f9ab0ad3d58cd439",
    ),
    "same_run_archived_input_reference": (
        "E001_single_nominal_none/input.gnss",
        "cea5fc832399eb0be3c038e2066666fe3ded26e39dddcf0197cdbb0de2da7196",
    ),
}

METHOD_ORDER = (
    "single_antenna_EKF",
    "basic_dual_yaw_EKF",
    "strong_dual_yaw_EKF",
    "LegSA_Paper_V1",
)


class FinalizationError(RuntimeError):
    """Raised before terminal evidence publication when a proof is incomplete."""


def _json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FinalizationError(f"Expected JSON object: {path.name}")
    return payload


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _atomic_csv(
    path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _copy_verified(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise FinalizationError(f"Required proof is not a regular file: {source.name}")
    source_hash = sha256_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        shutil.copyfile(source, temporary)
        if sha256_file(temporary) != source_hash:
            raise FinalizationError(f"Copy-by-hash failed: {source.name}")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _confined_relative(root: Path, relative: str, *, role: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or "" in pure.parts:
        raise FinalizationError(f"Unsafe {role} relative path")
    candidate = root.joinpath(*pure.parts).resolve(strict=False)
    if not is_within(candidate, root):
        raise FinalizationError(f"{role} escapes its root")
    return candidate


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = load_yaml_mapping(path)
    if contract.get("stage_id") != STAGE_ID:
        raise FinalizationError("final_v23 contract stage mismatch")
    if contract.get("terminal_status") != TERMINAL_STATUS:
        raise FinalizationError("final_v23 contract terminal status mismatch")
    if contract.get("clean_execution_eligible") is not False:
        raise FinalizationError("blocked contract cannot be clean-execution eligible")
    return contract


def build_not_run_record(component: str) -> dict[str, Any]:
    return {
        "schema_version": "paper-rebuild.clean1r2-not-run.v1",
        "stage_id": STAGE_ID,
        "case_id": CASE_ID,
        "component": component,
        "status": UPSTREAM_NOT_RUN,
        "terminal_status": TERMINAL_STATUS,
        "process_started": False,
        "output_generated": False,
        "metrics_generated": False,
        "trace_read": False,
        "legacy_solver_input": False,
        "reason": (
            "The archived same-run input requires Gaussian yaw injection and "
            "online trace access, which conflicts with clean real-data evidence."
        ),
    }


def build_four_method_rows() -> list[dict[str, Any]]:
    return [
        {
            "order": index,
            "method_id": method,
            "status": UPSTREAM_NOT_RUN,
            "solver_process_count": 0,
            "formal_run_count": 0,
            "output_sealed": False,
            "evaluated": False,
            "module_counters": "NOT_AVAILABLE_NO_RUN",
            "metrics": "NOT_AVAILABLE_NO_RUN",
            "upstream_blocker": TERMINAL_STATUS,
        }
        for index, method in enumerate(METHOD_ORDER, start=1)
    ]


def inspect_archived_input(path: Path) -> dict[str, Any]:
    row_count = 0
    times: list[float] = []
    rows_in_window = 0
    unique_widths: set[int] = set()
    velocity_stds: set[tuple[float, float, float]] = set()
    yaw_stds: set[float] = set()
    with path.open("r", encoding="utf-8") as handle:
        for number, raw_line in enumerate(handle, start=1):
            fields = raw_line.split()
            if not fields:
                continue
            unique_widths.add(len(fields))
            if len(fields) != 15:
                raise FinalizationError(
                    f"Archived input row {number} does not contain 15 columns"
                )
            values = [float(value) for value in fields]
            row_count += 1
            times.append(values[0])
            rows_in_window += int(66.0 <= values[0] <= 340.0)
            velocity_stds.add((values[10], values[11], values[12]))
            yaw_stds.add(values[14])
    if not times:
        raise FinalizationError("Archived input reference is empty")
    return {
        "evidence_classification": "PARITY_REFERENCE_ONLY",
        "solver_input_eligible": False,
        "row_count": row_count,
        "column_count_values": sorted(unique_widths),
        "time_start_seconds": min(times),
        "time_end_seconds": max(times),
        "rows_inside_runtime_window": rows_in_window,
        "unique_velocity_std_triplets_mps": [list(value) for value in sorted(velocity_stds)],
        "unique_yaw_std_deg": sorted(yaw_stds),
    }


def build_yaw_audit() -> dict[str, Any]:
    return {
        "schema_version": "paper-rebuild.clean1r2-yaw-std-vs-injection-audit.v1",
        "stage_id": STAGE_ID,
        "terminal_status": TERMINAL_STATUS,
        "measurement": {
            "yaw_measurement_std_deg": 1.5,
            "role": "measurement_covariance_R",
            "source": "process_data.py:1040-1042",
        },
        "injection": {
            "enabled_in_archived_E001_same_run": True,
            "yaw_noise_injection_std_deg": 1.5,
            "seed": 42,
            "distribution": "zero_mean_gaussian",
            "source": "process_data.py:1115-1129 and E001 run.log command",
        },
        "fixed_1p5_implies_noise_injection": False,
        "clarification": (
            "fixed_1p5 defines yaw measurement standard deviation.  The same-run "
            "noise injection is a separate explicitly passed argument."
        ),
        "archived_registry_label": "nominal_none",
        "archived_actual_data_mode": "semisynthetic",
        "clean_normal_required": {
            "yaw_measurement_std_deg": 1.5,
            "yaw_noise_injection_enabled": False,
            "yaw_noise_injection_std_deg": 0.0,
        },
        "closed": True,
        "clean_execution_eligible": False,
    }


def build_receiver_velocity_audit() -> dict[str, Any]:
    return {
        "schema_version": "paper-rebuild.clean1r2-receiver-velocity-audit.v1",
        "stage_id": STAGE_ID,
        "status": "CONTRACT_CLOSED_EXECUTION_NOT_RUN",
        "velocity_offsets_full_message": {
            "velN": [54, 58],
            "velE": [58, 62],
            "velD": [62, 66],
        },
        "archived_sAcc_offset_bug": [68, 72],
        "corrected_sAcc_offset_full_message": [74, 78],
        "scale_to_mps": 0.001,
        "archived_provider_uses_sAcc": False,
        "provider_velocity_std_mps": [0.05, 0.05, 0.05],
        "solver_extra_std_addition_mps": [0.05, 0.05, 0.05],
        "solver_extra_std_is_floor": False,
        "solver_source": "final-v23-freeze/src/kf-gins/gi_engine.cpp:760-778",
        "solver_source_sha256": TAG_GI_ENGINE_SHA256,
        "effective_pre_scale_std_mps": [0.10, 0.10, 0.10],
        "std_combination": "componentwise_add_then_square_for_R",
        "active_clean_parser_fixed_by_this_stage": True,
        "active_clean_parser_module": "legsa_gins.paper_rebuild.ubx_nav_pvt",
    }


def _git_report_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.splitlines()
    return {
        "report_generation_head": commit,
        "report_generation_worktree_dirty": bool(status),
        "code_freeze_commit": "NOT_CREATED_PARITY_GATE_DID_NOT_PASS",
    }


def _validate_recovery(clean_root: Path) -> dict[str, Any]:
    log_root = clean_root / RECOVERY_LOG_RELATIVE
    recovery_root = clean_root / RECOVERY_ROOT_RELATIVE
    summary = _json_object(log_root / "FINAL_V23_ARCHIVE_RECOVERY_SUMMARY.json")
    if (
        summary.get("passed") is not True
        or summary.get("archive_sha256") != ARCHIVE_SHA256
        or summary.get("archive_identity_unchanged") is not True
        or summary.get("source_identity_unique_for_core_four") is not True
    ):
        raise FinalizationError("Archive recovery proof is not terminal-approved")
    quarantine = summary.get("recovery_quarantine_audit")
    if not isinstance(quarantine, dict) or quarantine.get("passed") is not True:
        raise FinalizationError("Recovery quarantine proof is incomplete")

    source_rows = _csv_rows(log_root / "FINAL_V23_ARCHIVE_SOURCE_MAP.csv")
    by_role = {row["logical_role"]: row for row in source_rows}
    if set(by_role) != set(CORE_HASHES):
        raise FinalizationError("Core-four source map role set mismatch")
    for role, expected_hash in CORE_HASHES.items():
        row = by_role[role]
        if (
            row.get("sha256") != expected_hash
            or row.get("selected") != "True"
            or row.get("conflict_resolution") != "UNIQUE_CONTENT_IDENTITY"
        ):
            raise FinalizationError(f"Core source identity mismatch: {role}")

    selected_rows = _csv_rows(
        log_root / "FINAL_V23_SELECTED_EXTRACTION_MANIFEST.csv"
    )
    selected_targets: dict[str, dict[str, str]] = {}
    for role, (suffix, expected_hash) in E001_TARGETS.items():
        candidates = [
            row for row in selected_rows if row.get("archive_member", "").endswith(suffix)
        ]
        if len(candidates) != 1 or candidates[0].get("sha256") != expected_hash:
            raise FinalizationError(f"Unique E001 source-linked identity missing: {role}")
        row = candidates[0]
        local = _confined_relative(
            recovery_root, row["local_relative_path"], role=role
        )
        if local.is_symlink() or not local.is_file() or sha256_file(local) != expected_hash:
            raise FinalizationError(f"Selected E001 file hash mismatch: {role}")
        selected_targets[role] = {**row, "local_path": str(local)}

    process_rows = [
        row
        for row in selected_rows
        if row.get("archive_member") == "KF-GINS/bin/process_data.py"
    ]
    if len(process_rows) != 1:
        raise FinalizationError("Selected process_data.py identity is missing")
    process_path = _confined_relative(
        recovery_root,
        process_rows[0]["local_relative_path"],
        role="selected process_data.py",
    )
    source_lines = process_path.read_text(encoding="utf-8").splitlines()
    if (
        len(source_lines) < 1129
        or 'selected_yaw_df["yaw_std_for_merge_deg"] = 1.5'
        not in source_lines[1040]
        or "np.random.seed(42)" not in source_lines[1115]
        or "yaw_ned = wrap_deg(yaw_ned + noise)" not in source_lines[1128]
    ):
        raise FinalizationError("process_data.py yaw evidence lines changed")

    def source_window_contains(start: int, end: int, token: str) -> bool:
        return token in "\n".join(source_lines[start - 1 : end])

    trace_source_tokens = (
        (741, 798, "run_install_auto_calibration"),
        (967, 977, "df_trace = pd.read_csv(TRACE_PATH)"),
        (1007, 1035, "analyze_status_scheme"),
        (1007, 1035, "df_trace"),
        (1083, 1111, "fallback to trace yaw"),
    )
    if not all(
        source_window_contains(start, end, token)
        for start, end, token in trace_source_tokens
    ):
        raise FinalizationError("process_data.py online-trace evidence lines changed")

    run_log_path = Path(selected_targets["same_run_actual_run_log"]["local_path"])
    run_log = run_log_path.read_text(encoding="utf-8", errors="replace")
    required_command_tokens = (
        "--yaw_std_mode fixed_1p5",
        "--yaw_noise_std_deg 1.500",
        "--outlier_ratio 0.000",
        "--outlier_mode none",
        "--enable_outage false",
    )
    if not all(token in run_log for token in required_command_tokens):
        raise FinalizationError("E001 same-run command does not prove the blocker")

    return {
        "log_root": log_root,
        "recovery_root": recovery_root,
        "summary": summary,
        "source_rows": source_rows,
        "selected_targets": selected_targets,
    }


def _validate_tag_proof(clean_root: Path) -> dict[str, Any]:
    log_root = clean_root / TAG_LOG_RELATIVE
    source_root = clean_root / TAG_SOURCE_RELATIVE
    required = {
        "terminal": source_root / "FINAL_V23_TAG_SOURCE_RECOVERY_MANIFEST.json",
        "provenance": source_root / "TAG_PROVENANCE.json",
        "terminal_log_mirror": log_root
        / "FINAL_V23_TAG_SOURCE_RECOVERY_MANIFEST.json",
        "provenance_log_mirror": log_root / "TAG_PROVENANCE.json",
        "source_manifest": source_root / "TAG_SOURCE_MANIFEST.json",
        "ancillary_json": source_root / "TAG_ANCILLARY_ROLE_MAP.json",
        "ancillary_csv": source_root / "TAG_ANCILLARY_ROLE_MAP.csv",
        "working_tree_conflict_json": source_root
        / "WORKING_TREE_VS_TAG_CONFLICT_MAP.json",
        "working_tree_conflict_csv": source_root
        / "WORKING_TREE_VS_TAG_CONFLICT_MAP.csv",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        raise FinalizationError(
            "Exact final_v23 tag proof is pending: " + ",".join(sorted(missing))
        )
    terminal = _json_object(required["terminal"])
    provenance = _json_object(required["provenance"])
    if (
        sha256_file(required["terminal"]) != sha256_file(required["terminal_log_mirror"])
        or sha256_file(required["provenance"])
        != sha256_file(required["provenance_log_mirror"])
    ):
        raise FinalizationError("Exact tag proof log mirror mismatch")
    source_manifest = _json_object(required["source_manifest"])
    gates = terminal.get("gates")
    if (
        terminal.get("terminal_decision")
        != "APPROVED_EXACT_FINAL_V23_SOLVER_TAG_SOURCE_RECOVERY"
        or terminal.get("tag_name") != TAG_NAME
        or terminal.get("tag_commit") != TAG_COMMIT
        or terminal.get("archive_sha256") != ARCHIVE_SHA256
        or terminal.get("blockers") != []
        or not isinstance(gates, dict)
        or not gates
    ):
        raise FinalizationError("Exact tag source terminal proof is not approved")
    expected_boolean_gates = {
        "archive_pre_post_sha_stat_unchanged": True,
        "tag_ref_unique": True,
        "tag_commit_exact": True,
        "git_fsck_full_no_reflogs_pass": True,
        "selected_source_regular_blob_only": True,
        "required_tag_paths_present": True,
        "required_solver_writer_paths_present": True,
        "dependency_roots_unique": True,
        "static_build_source_closure": True,
        "archive_static_ancillary_bindings_unique": True,
        "missing_tag_ancillary_roles_recorded": True,
        "failed_attempt_quarantines_excluded": True,
        "archive_working_tree_head_used": False,
        "solver_or_binary_executed": False,
    }
    if any(gates.get(key) is not expected for key, expected in expected_boolean_gates.items()):
        raise FinalizationError("Exact tag source boolean gate failed")
    if gates.get("fsck_non_dangling_diagnostic_count") != 0:
        raise FinalizationError("Exact tag source fsck diagnostic count is nonzero")
    expected_missing_ancillary = {
        "bin/process_data.py",
        "bin/evaluate_nav_trace_kfgins_v2.py",
    }
    terminal_missing = terminal.get("missing_from_tag_ancillary_roles")
    if (
        not isinstance(terminal_missing, list)
        or set(terminal_missing) != expected_missing_ancillary
        or len(terminal_missing) != 2
        or gates.get("missing_tag_ancillary_role_count") != 2
    ):
        raise FinalizationError("Exact tag ancillary missing-role set mismatch")
    git_proof = provenance.get("git")
    archive_proof = provenance.get("archive")
    if (
        not isinstance(git_proof, dict)
        or git_proof.get("tag_name") != TAG_NAME
        or git_proof.get("peeled_commit") != TAG_COMMIT
        or not isinstance(archive_proof, dict)
        or archive_proof.get("expected_sha256") != ARCHIVE_SHA256
    ):
        raise FinalizationError("Tag provenance identity mismatch")
    archive_invariant = archive_proof.get("invariant")
    execution_boundary = provenance.get("execution_boundary")
    if (
        not isinstance(archive_invariant, dict)
        or archive_invariant.get("sha256_unchanged") is not True
        or archive_invariant.get("stat_unchanged") is not True
        or not isinstance(execution_boundary, dict)
        or execution_boundary.get("solver_built") is not False
        or execution_boundary.get("solver_run") is not False
        or execution_boundary.get("trace_read") is not False
        or execution_boundary.get("performance_result_read") is not False
    ):
        raise FinalizationError("Tag provenance safety boundary mismatch")
    if source_manifest.get("tag_commit") != TAG_COMMIT:
        raise FinalizationError("Tag source manifest commit mismatch")
    ancillary = _json_object(required["ancillary_json"])
    if ancillary.get("tag_commit") != TAG_COMMIT:
        raise FinalizationError("Tag ancillary role map commit mismatch")
    ancillary_rows = ancillary.get("rows")
    if not isinstance(ancillary_rows, list) or len(ancillary_rows) != 4:
        raise FinalizationError("Tag ancillary role map row set mismatch")
    ancillary_by_path = {
        row.get("logical_path"): row for row in ancillary_rows if isinstance(row, dict)
    }
    expected_ancillary_hashes = {
        "bin/process_data.py": CORE_HASHES["process_data"],
        "bin/evaluate_nav_trace_kfgins_v2.py": CORE_HASHES["evaluator"],
    }
    for logical_path, expected_hash in expected_ancillary_hashes.items():
        row = ancillary_by_path.get(logical_path)
        if (
            not isinstance(row, dict)
            or row.get("tag_status") != "MISSING_FROM_TAG_ANCILLARY_ROLE"
            or row.get("archive_static_candidate_count") != 1
            or row.get("archive_static_sha256") != expected_hash
            or row.get("archive_static_binding_status")
            != "UNIQUE_STATIC_MEMBER_REFERENCE_ONLY"
            or row.get("archive_static_materialized_into_tag_source") is not False
        ):
            raise FinalizationError(f"Tag ancillary static binding mismatch: {logical_path}")
    rows = source_manifest.get("rows")
    if not isinstance(rows, list) or not rows:
        raise FinalizationError("Tag source manifest has no selected source rows")
    normalized: list[dict[str, Any]] = []
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            raise FinalizationError("Tag source row must be an object")
        relative = raw_row.get("materialized_relative")
        expected_hash = raw_row.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise FinalizationError("Tag source row lacks path or hash")
        materialized = _confined_relative(
            source_root, relative, role="tag materialized source"
        )
        if (
            materialized.is_symlink()
            or not materialized.is_file()
            or sha256_file(materialized) != expected_hash
        ):
            raise FinalizationError(f"Tag source materialization mismatch: {relative}")
        normalized.append(dict(raw_row))
    conflict_payload = _json_object(required["working_tree_conflict_json"])
    conflict_rows = conflict_payload.get("rows")
    if not isinstance(conflict_rows, list):
        raise FinalizationError("Tag working-tree conflict map has no rows")
    conflicts_by_path = {
        str(row.get("path", "")): row
        for row in conflict_rows
        if isinstance(row, dict)
    }
    if set(conflicts_by_path) != {str(row["path"]) for row in normalized}:
        raise FinalizationError("Tag working-tree conflict map source set mismatch")
    for source_row in normalized:
        conflict = conflicts_by_path[str(source_row["path"])]
        if (
            conflict.get("tag_commit") != TAG_COMMIT
            or conflict.get("tag_sha256") != source_row["sha256"]
            or conflict.get("comparison_status")
            not in {
                "HASH_MATCH",
                "HASH_DIFFERENT",
                "MISSING_FROM_ARCHIVE_WORKING_TREE",
            }
        ):
            raise FinalizationError(
                f"Tag working-tree conflict row mismatch: {source_row['path']}"
            )
    if set(ancillary_by_path) != {
        "bin/process_data.py",
        "bin/evaluate_nav_trace_kfgins_v2.py",
        "scripts/run_final_mainline.py",
        "docs/final_mainline_config.md",
    }:
        raise FinalizationError("Tag ancillary logical path set mismatch")
    tag_source_by_path = {str(row.get("path")): row for row in normalized}
    for logical_path in (
        "scripts/run_final_mainline.py",
        "docs/final_mainline_config.md",
    ):
        ancillary_row = ancillary_by_path[logical_path]
        source_row = tag_source_by_path.get(logical_path)
        if (
            not isinstance(source_row, dict)
            or ancillary_row.get("tag_status") != "PRESENT_IN_TAG"
            or ancillary_row.get("materialized_into_tag_source") is not True
            or ancillary_row.get("tag_sha256") != source_row.get("sha256")
        ):
            raise FinalizationError(f"Tag ancillary selected-role binding mismatch: {logical_path}")
    return {
        "log_root": log_root,
        "source_root": source_root,
        "files": required,
        "terminal": terminal,
        "provenance": provenance,
        "source_rows": normalized,
        "working_tree_conflicts": conflicts_by_path,
    }


def _consolidated_source_rows(
    recovery: Mapping[str, Any], tag: Mapping[str, Any]
) -> list[dict[str, Any]]:
    def primary_tag_role(tag_path: str, fallback: str) -> str:
        lower_path = tag_path.casefold()
        if lower_path.endswith("scripts/run_final_mainline.py"):
            return "run_final_mainline"
        if lower_path.endswith("docs/final_mainline_config.md"):
            return "final_mainline_config"
        if lower_path.endswith("docs/final_v23_mainline.md"):
            return "final_v23_mainline_note"
        if lower_path.endswith("config/kf-gins.yaml"):
            return "tag_default_solver_config"
        return f"exact_tag_{fallback}:{tag_path}"

    tag_primary_hashes = {
        primary_tag_role(str(row.get("path", "")), str(row.get("logical_role", "tag_source"))): row[
            "sha256"
        ]
        for row in tag["source_rows"]
    }
    rows: list[dict[str, Any]] = []
    for row in recovery["source_rows"]:
        normalized = dict(row)
        role = normalized["logical_role"]
        if role in {"run_final_mainline", "final_mainline_config"}:
            tag_hash = tag_primary_hashes.get(role)
            if not tag_hash:
                raise FinalizationError(f"Exact tag is missing required role: {role}")
            identical = tag_hash == normalized["sha256"]
            normalized["selected"] = "False"
            normalized["selection_reason"] = (
                "The exact final-v23 tag-tree member is the selected row for this "
                "role; archive working-tree content is byte-identical."
                if identical
                else "The exact final-v23 tag-tree member is selected over the "
                "archive working-tree variant for this role."
            )
            normalized["conflict_resolution"] = (
                "IDENTICAL_TAG_AND_ARCHIVE_WORKING_TREE_CONTENT"
                if identical
                else "EXACT_TAG_TREE_MEMBER_SELECTED_OVER_WORKING_TREE_VARIANT"
            )
        else:
            normalized["selection_reason"] = (
                str(normalized["selection_reason"])
                + " The role is missing from the exact tag and remains bound to "
                "the unique archive static identity."
            )
            normalized["conflict_resolution"] = (
                "MISSING_FROM_TAG_ANCILLARY_ROLE_UNIQUE_ARCHIVE_STATIC_IDENTITY"
            )
        rows.append(normalized)
    for role, target in recovery["selected_targets"].items():
        classification = target["evidence_classification"]
        rows.append(
            {
                "logical_role": role,
                "archive_member": target["qualified_member"],
                "sha256": target["sha256"],
                "source_type": classification.lower(),
                "selected": "True",
                "selection_reason": (
                    "Exact same-run E001 source linkage; retained only as static "
                    "runtime specification or parity reference according to classification."
                ),
                "conflict_candidates": "[]",
                "conflict_resolution": "UNIQUE_SOURCE_LINKED_SAME_RUN_IDENTITY",
            }
        )
    working_conflicts = {
        row["logical_role"]: row["sha256"] for row in recovery["source_rows"]
    }
    for tag_row in tag["source_rows"]:
        tag_path = str(tag_row.get("path", ""))
        logical_role = primary_tag_role(
            tag_path, str(tag_row.get("logical_role", "tag_source"))
        )
        conflict_record = tag["working_tree_conflicts"].get(tag_path, {})
        conflict_hash = str(conflict_record.get("archive_working_tree_sha256", ""))
        if not conflict_hash:
            conflict_hash = working_conflicts.get(logical_role, "")
        comparison_status = str(conflict_record.get("comparison_status", ""))
        identical = comparison_status == "HASH_MATCH" or (
            bool(conflict_hash) and conflict_hash == tag_row["sha256"]
        )
        rows.append(
            {
                "logical_role": logical_role,
                "archive_member": f"git-tag://{TAG_NAME}/{tag_path}",
                "sha256": tag_row["sha256"],
                "source_type": "archive_git_tag_static_source",
                "selected": "True",
                "selection_reason": str(tag_row.get("selection_reason", "")),
                "conflict_candidates": (
                    json.dumps(
                        [{"source": "archive_working_tree", "sha256": conflict_hash}],
                        sort_keys=True,
                    )
                    if conflict_hash
                    else "[]"
                ),
                "conflict_resolution": (
                    "IDENTICAL_TAG_AND_ARCHIVE_WORKING_TREE_CONTENT"
                    if identical
                    else (
                        "EXACT_TAG_TREE_MEMBER_SELECTED_OVER_WORKING_TREE_VARIANT"
                        if conflict_hash
                        else f"TAG_TREE_AT_{TAG_COMMIT}"
                    )
                ),
            }
        )
    selected_roles = [
        str(row["logical_role"]) for row in rows if str(row["selected"]) == "True"
    ]
    duplicate_selected_roles = sorted(
        role for role in set(selected_roles) if selected_roles.count(role) > 1
    )
    if duplicate_selected_roles:
        raise FinalizationError(
            "Consolidated source map has duplicate selected roles: "
            + ",".join(duplicate_selected_roles)
        )
    return rows


def _validate_extension_routing(
    recovery: Mapping[str, Any], tag: Mapping[str, Any]
) -> dict[str, Any]:
    by_path = {str(row.get("path", "")): row for row in tag["source_rows"]}
    required_tag_sources = {
        "src/kf-gins/gi_engine.cpp": TAG_GI_ENGINE_SHA256,
        "src/kf-gins/gi_engine.h": TAG_GI_ENGINE_HEADER_SHA256,
        "scripts/run_final_mainline.py": CORE_HASHES["run_final_mainline"],
    }
    source_text: dict[str, str] = {}
    for logical_path, expected_hash in required_tag_sources.items():
        row = by_path.get(logical_path)
        if not isinstance(row, dict) or row.get("sha256") != expected_hash:
            raise FinalizationError(f"Exact tag extension source mismatch: {logical_path}")
        materialized = _confined_relative(
            tag["source_root"],
            str(row["materialized_relative"]),
            role=f"extension routing source {logical_path}",
        )
        source_text[logical_path] = materialized.read_text(encoding="utf-8")

    engine = source_text["src/kf-gins/gi_engine.cpp"]
    foot_tokens = (
        "bool enabled = false;",
        'c.enabled = parseEnvBool("KF_GINS_FOOT_AWARE", false);',
        "if (foot_cfg.enabled) {",
        '"[FOOT-CONFIG] enabled=%d',
    )
    if not all(token in engine for token in foot_tokens):
        raise FinalizationError("Exact tag foot-aware default-off routing changed")
    runner = source_text["scripts/run_final_mainline.py"]
    if "KF_GINS_FOOT_AWARE" in runner:
        raise FinalizationError("Exact tag final runner unexpectedly enables foot-aware routing")

    run_log_path = Path(recovery["selected_targets"]["same_run_actual_run_log"]["local_path"])
    run_log = run_log_path.read_text(encoding="utf-8", errors="replace")
    marker_tokens = {
        "v3_foot_aware": "[FOOT-",
        "v2_4_quality_manager": "[QM-",
        "v4_raw_gnss_frontend": "[RAW-GNSS",
        "qa_fallback": "[QA-",
        "fgo": "[FGO-",
    }
    marker_counts = {name: run_log.count(token) for name, token in marker_tokens.items()}
    if any(marker_counts.values()):
        raise FinalizationError(f"Excluded extension runtime marker present: {marker_counts}")
    if "[YAW-CONFIG] scheme=scheme_C_mainline" not in run_log:
        raise FinalizationError("Selected same-run scheme-C runtime marker is missing")

    return {
        "schema_version": "paper-rebuild.clean1r2-extension-routing-audit.v1",
        "stage_id": STAGE_ID,
        "terminal_status": TERMINAL_STATUS,
        "exact_tag": f"{TAG_NAME}@{TAG_COMMIT}",
        "v3_foot_aware": {
            "source_present_in_exact_tag": True,
            "source_default_enabled": False,
            "enable_environment_variable": "KF_GINS_FOOT_AWARE",
            "runner_explicitly_enables": False,
            "same_run_runtime_marker_count": marker_counts["v3_foot_aware"],
            "same_run_enabled": False,
            "selected_for_parity_contract": False,
        },
        "v2_4_quality_manager": {
            "same_run_runtime_marker_count": marker_counts["v2_4_quality_manager"],
            "selected_for_parity_contract": False,
        },
        "v4_raw_gnss_frontend": {
            "same_run_runtime_marker_count": marker_counts["v4_raw_gnss_frontend"],
            "selected_for_parity_contract": False,
        },
        "qa_fallback": {
            "same_run_runtime_marker_count": marker_counts["qa_fallback"],
            "selected_for_parity_contract": False,
        },
        "fgo": {
            "same_run_runtime_marker_count": marker_counts["fgo"],
            "selected_for_parity_contract": False,
        },
        "semi_physical_yaw_injection": {
            "same_run_enabled": True,
            "selected_for_clean_real_evidence": False,
            "upstream_blocker": TERMINAL_STATUS,
        },
        "scheme_C": {
            "exact_tag_compile_time_constants": True,
            "runner_environment_override_names_have_no_exact_tag_solver_readers": True,
            "same_run_runtime_marker_present": True,
        },
        "closed": True,
    }


def _source_map_markdown(rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "# final_v23 archive source map",
        "",
        "All archive runtime payloads remain non-executable and ineligible as current solver input.",
        "",
        "| Logical role | Archive member | SHA256 | Resolution |",
        "|---|---|---|---|",
    ]
    for row in rows:
        member = str(row["archive_member"]).replace("|", "\\|")
        lines.append(
            f"| {row['logical_role']} | `{member}` | `{row['sha256']}` | "
            f"{row['conflict_resolution']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _proof_markdown(contract_hash: str) -> str:
    return f"""# CLEAN1R2 exact final_v23 contract proof

- Terminal status: `{TERMINAL_STATUS}`
- Tracked contract SHA256: `{contract_hash}`
- Exact archive tag: `{TAG_NAME}` at `{TAG_COMMIT}`
- Exact tag role: selected static solver/build contract only; historical E001
  binary lineage to this tag is not recorded and is not claimed.
- Actual same-run runtime identity: `E001_single_nominal_none`
- Archived same-run actual mode: `semisynthetic`
- Current fresh input, exact run, active-port parity, and four methods: `{UPSTREAM_NOT_RUN}`

## Deterministic blocker

The first divergence is `yaw_noise_injection_std_deg`: clean normal requires
`0.0`, while the archived same-run command passes `1.500`.  The implementing
source is `KF-GINS/bin/process_data.py`, symbol `process_gnss`, lines
1115-1129.  The second divergence is `trace_used_online`: clean requires
`false`, while the archived provider builder reads trace and contains trace
calibration/fallback paths.

`fixed_1p5` is the yaw measurement standard deviation used for measurement
covariance.  It does not itself request noise injection.  The injection is a
separate same-run argument and is independently proven.

No archived input/output was used as current solver input.  No trace was opened
for current evaluation.  No provider, solver output, method metric, or figure
was generated by this terminal reporting step.
"""


def _full_report_markdown(raw_summary: Mapping[str, Any]) -> str:
    return f"""# CLEAN1R2 full report

## Terminal decision

`{TERMINAL_STATUS}`

The recovered archive contract is internally identifiable, but its exact
same-run E001 input is not clean real-data evidence: it injects Gaussian yaw
noise at 1.5 degrees with seed 42 and reads trace during provider generation.
Strict archived input parity and the clean real-data evidence contract therefore
cannot be satisfied by the same run without a human contract choice.

## First deterministic divergence

- File: `E001_single_nominal_none/run.log`
- Field: `yaw_noise_injection_std_deg`
- Clean expected value: `0.0`
- Archived actual value: `1.500`
- Source member: `KF-GINS/bin/process_data.py`
- Symbol: `process_gnss`
- Lines: `1115-1129`
- Exact next fix: the human must choose either semisynthetic historical parity
  (not clean evidence) or clean no-injection execution (not strict archived
  input parity).

The second divergence is `trace_used_online`, clean expected `false`, archived
actual `true` in `process_data` trace read/calibration/fallback paths.

The active clean UBX-NAV-PVT parser was deterministically corrected to decode
`sAcc` from complete-frame bytes `[74:78]`.  That code repair did not generate
a provider or relax the parity gate.

## Execution boundary

- BY2 terminal raw verification: `{raw_summary['verified']}/22`
- Fresh final_v23 input: `{UPSTREAM_NOT_RUN}`
- Exact archived solver run: `{UPSTREAM_NOT_RUN}`
- Active-port parity: `{UPSTREAM_NOT_RUN}`
- Four methods: `{UPSTREAM_NOT_RUN}`
- Current trace read: `false`
- Current solver process count: `0`
- Current formal run count: `0`
- Paper figures: `0`

Historical input/output files remain parity-reference-only.  They are absent
from the current solver-input set and from active performance evidence.
"""


def _write_receiver_contract(path: Path) -> None:
    text = """schema_version: paper_rebuild.final_v23_receiver_velocity_contract.v1
stage_id: CLEAN1R2_FINAL_V23_ARCHIVE_PARITY_AND_FOUR_METHOD_REEXECUTION
status: CONTRACT_CLOSED_EXECUTION_NOT_RUN
source: GNSS1_raw_UBX_NAV_PVT
full_message_offsets:
  velN: [54, 58]
  velE: [58, 62]
  velD: [62, 66]
  archived_sAcc_bug: [68, 72]
  corrected_sAcc: [74, 78]
unit_scale_to_mps: 0.001
merge_policy: nearest_0p1_seconds_then_forward_fill_back_fill
sAcc_used_by_archived_provider: false
provider_fixed_std_mps: [0.05, 0.05, 0.05]
solver_extra_std_addition_mps: [0.05, 0.05, 0.05]
solver_extra_std_is_floor: false
effective_pre_scale_std_mps: [0.10, 0.10, 0.10]
solver_std_combination: componentwise_add_then_square_for_R
active_clean_parser_fixed_by_this_stage: true
active_clean_parser_module: legsa_gins.paper_rebuild.ubx_nav_pvt
"""
    _atomic_text(path, text)


def _manifest_role(name: str) -> tuple[str, str]:
    if name.startswith("FINAL_V23_ARCHIVE_INVENTORY"):
        return "archive_inventory", "MIGRATABLE_STATIC_SPECIFICATION"
    if name == "FINAL_V23_ARCHIVE_EVIDENCE_CLASSIFICATION.csv":
        return "archive_evidence_classification", "MIGRATABLE_STATIC_SPECIFICATION"
    if "TAG_SOURCE" in name or name == "TAG_PROVENANCE.json":
        return "exact_tag_source_proof", "MIGRATABLE_STATIC_SPECIFICATION"
    if name.startswith("RAW_FINAL"):
        return "current_raw_integrity_audit", "CURRENT_INTEGRITY_EVIDENCE"
    if name in {"FOUR_METHOD_SUMMARY.csv", "AGGREGATE_CROSSCHECK.json"}:
        return "truthful_not_run_record", "NOT_RUN"
    return "clean1r2_terminal_governance", "CURRENT_TERMINAL_EVIDENCE"


def _write_evidence_manifest(output_root: Path) -> None:
    excluded = {"EVIDENCE_MANIFEST.csv", "EVIDENCE_MANIFEST.sha256"}
    rows: list[dict[str, Any]] = []
    for path in sorted(output_root.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.name in excluded:
            continue
        role, classification = _manifest_role(path.name)
        rows.append(
            {
                "relative_path": path.name,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "evidence_role": role,
                "evidence_classification": classification,
                "active_performance_evidence": False,
                "solver_input_eligible": False,
                "status": (
                    UPSTREAM_NOT_RUN
                    if classification == "NOT_RUN"
                    else "RECORDED_AND_HASHED"
                ),
            }
        )
    manifest = output_root / "EVIDENCE_MANIFEST.csv"
    _atomic_csv(
        manifest,
        rows,
        (
            "relative_path",
            "sha256",
            "size_bytes",
            "evidence_role",
            "evidence_classification",
            "active_performance_evidence",
            "solver_input_eligible",
            "status",
        ),
    )
    digest = sha256_file(manifest)
    _atomic_text(output_root / "EVIDENCE_MANIFEST.sha256", f"{digest}  EVIDENCE_MANIFEST.csv\n")


def _verify_evidence_manifest(output_root: Path) -> None:
    manifest = output_root / "EVIDENCE_MANIFEST.csv"
    digest_file = output_root / "EVIDENCE_MANIFEST.sha256"
    rows = _csv_rows(manifest)
    listed = {row["relative_path"] for row in rows}
    actual = {
        path.name
        for path in output_root.iterdir()
        if path.is_file()
        and path.name not in {"EVIDENCE_MANIFEST.csv", "EVIDENCE_MANIFEST.sha256"}
    }
    if listed != actual:
        raise FinalizationError("Terminal evidence manifest file set mismatch")
    for row in rows:
        path = output_root / row["relative_path"]
        if path.is_symlink() or not path.is_file():
            raise FinalizationError("Terminal evidence manifest contains a non-regular file")
        if sha256_file(path) != row["sha256"] or path.stat().st_size != int(
            row["size_bytes"]
        ):
            raise FinalizationError(f"Terminal evidence hash mismatch: {path.name}")
        if row["solver_input_eligible"] != "False":
            raise FinalizationError("Terminal report cannot contain a solver-eligible artifact")
    expected_line = f"{sha256_file(manifest)}  EVIDENCE_MANIFEST.csv\n"
    if digest_file.read_text(encoding="utf-8") != expected_line:
        raise FinalizationError("Terminal evidence manifest digest mismatch")


def _copy_terminal_proofs(
    output_root: Path, recovery: Mapping[str, Any], tag: Mapping[str, Any]
) -> None:
    recovery_log = recovery["log_root"]
    copies = {
        "FINAL_V23_ARCHIVE_INVENTORY.csv": recovery_log
        / "FINAL_V23_ARCHIVE_INVENTORY.csv",
        "FINAL_V23_ARCHIVE_INVENTORY.json": recovery_log
        / "FINAL_V23_ARCHIVE_INVENTORY.json",
        "FINAL_V23_ARCHIVE_EVIDENCE_CLASSIFICATION.csv": recovery_log
        / "FINAL_V23_ARCHIVE_EVIDENCE_CLASSIFICATION.csv",
        "FINAL_V23_ARCHIVE_SHA256.txt": recovery_log / "FINAL_V23_ARCHIVE_SHA256.txt",
        "FINAL_V23_ARCHIVE_RECOVERY_SUMMARY.json": recovery_log
        / "FINAL_V23_ARCHIVE_RECOVERY_SUMMARY.json",
        "FINAL_V23_TAG_SOURCE_RECOVERY_MANIFEST.json": tag["files"]["terminal"],
        "TAG_PROVENANCE.json": tag["files"]["provenance"],
        "TAG_SOURCE_MANIFEST.json": tag["files"]["source_manifest"],
        "TAG_ANCILLARY_ROLE_MAP.json": tag["files"]["ancillary_json"],
        "TAG_ANCILLARY_ROLE_MAP.csv": tag["files"]["ancillary_csv"],
        "WORKING_TREE_VS_TAG_CONFLICT_MAP.json": tag["files"][
            "working_tree_conflict_json"
        ],
        "WORKING_TREE_VS_TAG_CONFLICT_MAP.csv": tag["files"][
            "working_tree_conflict_csv"
        ],
        "FINAL_V23_PARITY_CONTRACT.yaml": CONTRACT_PATH,
    }
    for name, source in copies.items():
        _copy_verified(source, output_root / name)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize the truthful CLEAN1R2 EVIDENCE_CONTAMINATION blocker"
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Explicit ignored local path configuration; no path discovery is performed.",
    )
    return parser.parse_args()


def _finalize_into(paths: Any, output_root: Path) -> dict[str, Any]:
    clean_root = paths.clean_root.resolve(strict=True)
    contract = load_contract()
    recovery = _validate_recovery(clean_root)
    tag = _validate_tag_proof(clean_root)
    extension_routing = _validate_extension_routing(recovery, tag)
    if output_root.resolve(strict=True) != output_root or not is_within(output_root, clean_root):
        raise FinalizationError("Terminal log root is not confined to CLEAN_ROOT")

    raw = verify_by2_raw_22(
        paths.raw_root,
        paths.raw_hash_lock,
        expected_lock_sha256=RAW_LOCK_SHA256,
        audit_phase="clean1r2_terminal_blocked_pre_generation_recheck",
    )
    if raw.summary.get("passed") is not True:
        raise FinalizationError("Terminal BY2 raw verification failed")
    write_raw_audit(output_root / "RAW_FINAL_AUDIT.csv", raw)
    recovery_pre = recovery["summary"].get("raw_pre_recovery")
    if (
        not isinstance(recovery_pre, dict)
        or recovery_pre.get("verified") != 22
        or recovery_pre.get("raw_hash_lock_sha256") != RAW_LOCK_SHA256
    ):
        raise FinalizationError("Pre-recovery raw proof is incomplete")
    raw_summary = {
        "schema_version": "paper-rebuild.clean1r2-terminal-raw-audit.v1",
        "pre_recovery": recovery_pre,
        "terminal_pre_generation_recheck": raw.summary,
        "post_generation": UPSTREAM_NOT_RUN,
        "post_run": UPSTREAM_NOT_RUN,
        "raw_mutation": 0,
        "performed_integrity_checks_passed": True,
        "required_pass_checkpoints_complete": False,
    }
    _atomic_json(output_root / "RAW_FINAL_AUDIT.json", raw_summary)

    _copy_terminal_proofs(output_root, recovery, tag)
    consolidated = _consolidated_source_rows(recovery, tag)
    source_fields = (
        "logical_role",
        "archive_member",
        "sha256",
        "source_type",
        "selected",
        "selection_reason",
        "conflict_candidates",
        "conflict_resolution",
    )
    _atomic_csv(
        output_root / "FINAL_V23_ARCHIVE_SOURCE_MAP.csv",
        consolidated,
        source_fields,
    )
    _atomic_text(
        output_root / "FINAL_V23_ARCHIVE_SOURCE_MAP.md",
        _source_map_markdown(consolidated),
    )

    archived_input_path = Path(
        recovery["selected_targets"]["same_run_archived_input_reference"]["local_path"]
    )
    archived_input = inspect_archived_input(archived_input_path)
    expected_input = contract["archived_same_run_reference"]
    for actual_key, contract_key in (
        ("row_count", "input_rows"),
        ("time_start_seconds", "input_time_start_seconds"),
        ("time_end_seconds", "input_time_end_seconds"),
        ("rows_inside_runtime_window", "rows_inside_runtime_window"),
    ):
        if archived_input[actual_key] != expected_input[contract_key]:
            raise FinalizationError(f"Archived E001 input metadata mismatch: {actual_key}")
    input_report = {
        "schema_version": "paper-rebuild.clean1r2-input-parity-blocked.v1",
        "stage_id": STAGE_ID,
        "status": UPSTREAM_NOT_RUN,
        "upstream_blocker": TERMINAL_STATUS,
        "archived_input_reference": {
            **archived_input,
            "sha256": E001_TARGETS["same_run_archived_input_reference"][1],
            "copied_to_current_provider": False,
        },
        "current_fresh_input": None,
        "p1_input_parity_evaluated": False,
        "reason": "No fresh input may be generated before resolving the clean-versus-semisynthetic contract conflict.",
    }
    _atomic_json(
        output_root / "FINAL_V23_INPUT_PARITY_VS_ARCHIVED.json", input_report
    )
    input_manifest = build_not_run_record("fresh_final_v23_input_generation")
    input_manifest.update(
        {
            "data_mode": "real_by2_raw_intended_not_run",
            "synthetic_data_used": False,
            "semisynthetic_data_used": False,
            "trace_used_online": False,
            "receiver_imu_as_body_imu": False,
            "final_v23_output_solver_input": False,
            "LegSA_output_solver_input": False,
            "per_case_tuning": False,
            "output_only_correction": False,
            "epoch_deleted_for_metric": False,
            "old_runtime_input_count": 0,
            "fresh_imu_path": None,
            "fresh_gnss_path": None,
            "fresh_provider_hashes": None,
            "archived_input_copied": False,
            "raw_pre_generation_verified": 22,
            "raw_post_generation": UPSTREAM_NOT_RUN,
        }
    )
    _atomic_json(output_root / "FINAL_V23_INPUT_MANIFEST.json", input_manifest)
    column_rows = [
        {
            "index": column["index"],
            "name": column["name"],
            "expected_unit": column["unit"],
            "expected_source": column["source"],
            "current_fresh_input_value": "NOT_AVAILABLE_NO_INPUT",
            "status": UPSTREAM_NOT_RUN,
            "upstream_blocker": TERMINAL_STATUS,
        }
        for column in contract["input_format"]["columns"]
    ]
    _atomic_csv(
        output_root / "FINAL_V23_INPUT_COLUMN_AUDIT.csv",
        column_rows,
        (
            "index",
            "name",
            "expected_unit",
            "expected_source",
            "current_fresh_input_value",
            "status",
            "upstream_blocker",
        ),
    )
    _atomic_json(
        output_root / "FINAL_V23_INPUT_TIME_AUDIT.json",
        {
            "schema_version": "paper-rebuild.clean1r2-input-time-audit.v1",
            "stage_id": STAGE_ID,
            "status": UPSTREAM_NOT_RUN,
            "upstream_blocker": TERMINAL_STATUS,
            "expected_base_time_unix_seconds": 1772784000.0,
            "expected_starttime_seconds": 66.0,
            "expected_endtime_seconds": 340.0,
            "current_fresh_input_time_start": None,
            "current_fresh_input_time_end": None,
            "current_fresh_input_row_count": 0,
            "archived_reference_metadata_file": "FINAL_V23_INPUT_PARITY_VS_ARCHIVED.json",
        },
    )

    contract_hash = sha256_file(CONTRACT_PATH)
    proof = {
        "schema_version": "paper-rebuild.clean1r2-final-v23-contract-proof.v1",
        "stage_id": STAGE_ID,
        "terminal_status": TERMINAL_STATUS,
        "tracked_contract_sha256": contract_hash,
        "archive_sha256": ARCHIVE_SHA256,
        "exact_tag": TAG_NAME,
        "exact_tag_commit": TAG_COMMIT,
        "source_identity_unique": True,
        "exact_tag_role": "selected_static_solver_and_build_contract_only",
        "historical_E001_solver_identity": "NOT_RECORDED_SAME_RUN",
        "historical_E001_binary_lineage_to_exact_tag": "NOT_PROVEN",
        "actual_runtime_config_recovered": True,
        "process_data_exact_recovered": True,
        "run_final_mainline_exact_recovered": True,
        "evaluator_identity_recovered": True,
        "yaw_std_vs_noise_injection_closed": True,
        "receiver_velocity_contract_closed": True,
        "clean_execution_eligible": False,
        "four_method_gate_open": False,
    }
    _atomic_json(output_root / "FINAL_V23_PARITY_CONTRACT_PROOF.json", proof)
    _atomic_text(
        output_root / "FINAL_V23_PARITY_CONTRACT_PROOF.md",
        _proof_markdown(contract_hash),
    )
    _atomic_json(
        output_root / "FINAL_V23_YAW_STD_VS_NOISE_INJECTION_AUDIT.json",
        build_yaw_audit(),
    )
    _write_receiver_contract(
        output_root / "FINAL_V23_RECEIVER_VELOCITY_CONTRACT.yaml"
    )
    _atomic_json(
        output_root / "FINAL_V23_RECEIVER_VELOCITY_PARITY_AUDIT.json",
        build_receiver_velocity_audit(),
    )
    _atomic_json(
        output_root / "FINAL_V23_EXTENSION_ROUTING_AUDIT.json",
        extension_routing,
    )

    exact_run = build_not_run_record("exact_archived_final_v23_fresh_run")
    exact_run.update(
        {
            "method_id": "final_v23_parity_EKF",
            "data_mode": "real_by2_raw_intended_not_run",
            "synthetic_data_used": False,
            "semisynthetic_data_used": False,
            "archived_reference_semisynthetic_data_used": True,
            "trace_used_online": False,
            "receiver_imu_as_body_imu": False,
            "final_v23_output_solver_input": False,
            "LegSA_output_solver_input": False,
            "per_case_tuning": False,
            "output_only_correction": False,
            "epoch_deleted_for_metric": False,
            "old_runtime_input_count": 0,
            "code_commit": "NOT_RUN",
            "config_hash": contract_hash,
        }
    )
    _atomic_json(output_root / "EXACT_FINAL_V23_RUN_MANIFEST.json", exact_run)
    active_port = build_not_run_record("active_port_final_v23_parity")
    active_port.update(
        {
            "strong_dual_yaw_equals_final_v23": "NOT_EVALUATED",
            "active_parity_solver_modified": False,
            "active_clean_provider_parser_modified": True,
            "active_clean_provider_parser_change": (
                "UBX_NAV_PVT_sAcc_full_frame_offset_74_78"
            ),
            "parity_gate_passed": False,
        }
    )
    _atomic_json(
        output_root / "ACTIVE_PORT_FINAL_V23_PARITY_REPORT.json", active_port
    )

    historical_map = {
        "schema_version": "paper-rebuild.clean1r2-historical-metric-identity-map.v1",
        "identities": [
            {
                "identity": "archived_E001_direct_Fixposition_trace",
                "reference_identity": "Fixposition_same_source_direct_trace",
                "evaluator_sha256": CORE_HASHES["evaluator"],
                "input_sha256": E001_TARGETS["same_run_archived_input_reference"][1],
                "solver": "NOT_RECORDED_SAME_RUN",
                "exact_tag_static_contract_selected": f"{TAG_NAME}@{TAG_COMMIT}",
                "historical_binary_lineage_to_exact_tag": "NOT_PROVEN",
                "time_window_seconds": [66.0, 340.0],
                "historical_output_count": 56642,
                "metric_source": "archived_same_run_summary",
                "evidence_classification": "PARITY_REFERENCE_ONLY",
                "current_metric_claim_eligible": False,
            },
            {
                "identity": "historical_official_or_reconstructed_reference",
                "reference_identity": "DISTINCT_FROM_DIRECT_TRACE",
                "evaluator": "NOT_PROVEN_BY_SELECTED_SAME_RUN_LINKAGE",
                "input": "NOT_PROMOTED",
                "solver": "NOT_PROMOTED",
                "time_window": "NOT_PROMOTED",
                "count": "NOT_PROMOTED",
                "metric_source": "historical_reference_only",
                "evidence_classification": "PARITY_REFERENCE_ONLY",
                "current_metric_claim_eligible": False,
            },
        ],
        "identity_mixing_forbidden": True,
        "historical_metric_used_for_tuning": False,
    }
    _atomic_json(
        output_root / "FINAL_V23_HISTORICAL_METRIC_IDENTITY_MAP.json",
        historical_map,
    )

    parity_rows = [
        {
            "layer": "P1",
            "check": "yaw_noise_injection_std_deg",
            "status": "BLOCKED",
            "expected_clean": 0.0,
            "archived_actual": 1.5,
            "current_actual": "NOT_RUN",
            "evidence": "E001 run.log; process_data.py:1115-1129",
            "blocking": True,
        },
        {
            "layer": "P1",
            "check": "trace_used_online",
            "status": "BLOCKED",
            "expected_clean": False,
            "archived_actual": True,
            "current_actual": "NOT_RUN",
            "evidence": "process_data.py:741-798,967-977,1007-1035,1083-1111",
            "blocking": True,
        },
        {
            "layer": "P1",
            "check": "fresh_current_raw_input",
            "status": UPSTREAM_NOT_RUN,
            "expected_clean": True,
            "archived_actual": "PARITY_REFERENCE_ONLY",
            "current_actual": False,
            "evidence": TERMINAL_STATUS,
            "blocking": True,
        },
        {
            "layer": "P2",
            "check": "runtime_contract_parity",
            "status": UPSTREAM_NOT_RUN,
            "expected_clean": "exact_contract",
            "archived_actual": "recovered",
            "current_actual": "NOT_RUN",
            "evidence": TERMINAL_STATUS,
            "blocking": True,
        },
        {
            "layer": "P3",
            "check": "numerical_parity",
            "status": UPSTREAM_NOT_RUN,
            "expected_clean": "fresh_exact_output",
            "archived_actual": "REFERENCE_ONLY",
            "current_actual": "NOT_RUN",
            "evidence": TERMINAL_STATUS,
            "blocking": True,
        },
    ]
    _atomic_csv(
        output_root / "FINAL_V23_PARITY_COMPARISON.csv",
        parity_rows,
        (
            "layer",
            "check",
            "status",
            "expected_clean",
            "archived_actual",
            "current_actual",
            "evidence",
            "blocking",
        ),
    )
    _atomic_csv(
        output_root / "FOUR_METHOD_SUMMARY.csv",
        build_four_method_rows(),
        (
            "order",
            "method_id",
            "status",
            "solver_process_count",
            "formal_run_count",
            "output_sealed",
            "evaluated",
            "module_counters",
            "metrics",
            "upstream_blocker",
        ),
    )
    aggregate = {
        "schema_version": "paper-rebuild.clean1r2-aggregate-crosscheck.v1",
        "status": UPSTREAM_NOT_RUN,
        "upstream_blocker": TERMINAL_STATUS,
        "method_output_count": 0,
        "metric_row_count": 0,
        "aggregate_crosscheck_performed": False,
        "aggregate_crosscheck_passed": False,
        "trace_read": False,
        "fabricated_metrics": False,
    }
    _atomic_json(output_root / "AGGREGATE_CROSSCHECK.json", aggregate)

    full_report = {
        "schema_version": "paper-rebuild.clean1r2-full-report.v1",
        "stage_id": STAGE_ID,
        "case_id": CASE_ID,
        "terminal_status": TERMINAL_STATUS,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive": {
            "access": True,
            "sha256": ARCHIVE_SHA256,
            "main_member_count": recovery["summary"]["main_archive_member_count"],
            "recursive_member_count": recovery["summary"][
                "recursive_archive_member_count"
            ],
            "exact_tag": TAG_NAME,
            "exact_tag_commit": TAG_COMMIT,
        },
        "contract_gates": proof,
        "extension_routing": extension_routing,
        "raw": raw_summary,
        "first_divergence": contract["evidence_contamination_gate"][
            "first_divergence"
        ],
        "second_divergence": contract["evidence_contamination_gate"][
            "second_divergence"
        ],
        "execution": {
            "fresh_final_v23_input": UPSTREAM_NOT_RUN,
            "exact_final_v23_fresh_run": UPSTREAM_NOT_RUN,
            "active_port_final_v23_parity": UPSTREAM_NOT_RUN,
            "four_method_execution": UPSTREAM_NOT_RUN,
            "solver_process_count": 0,
            "formal_run_count": 0,
            "trace_read_current": False,
            "legacy_solver_input": False,
            "paper_figure_count": 0,
            "classic18": 0,
            "degradation_execution_count": 0,
        },
        "git": _git_report_state(),
        "exact_next_fix": (
            "Human must choose semisynthetic diagnostic historical parity or "
            "clean no-injection execution; one run cannot truthfully claim both."
        ),
    }
    _atomic_json(output_root / "CLEAN1R2_FULL_REPORT.json", full_report)
    _atomic_text(
        output_root / "CLEAN1R2_FULL_REPORT.md",
        _full_report_markdown(raw.summary),
    )
    _write_evidence_manifest(output_root)
    _verify_evidence_manifest(output_root)
    return {
        "terminal_status": TERMINAL_STATUS,
        "output_alias": "clean://17_LOGS/CLEAN1R2_FINAL",
        "raw_verified": raw.summary["verified"],
        "solver_process_count": 0,
        "formal_run_count": 0,
        "trace_read": False,
    }


def main() -> int:
    args = _parse_args()
    paths = load_clean_paths(args.config)
    if paths.code_root.resolve(strict=True) != REPO_ROOT.resolve(strict=True):
        raise FinalizationError("Local config code_root is not this worktree")
    clean_root = paths.clean_root.resolve(strict=True)
    final_root = clean_root / TERMINAL_LOG_RELATIVE
    if final_root.is_symlink() or final_root.exists():
        raise FinalizationError("Authoritative CLEAN1R2 terminal root already exists")
    parent = final_root.parent
    parent.mkdir(parents=True, exist_ok=True)
    attempt_id = uuid.uuid4().hex
    attempt = parent / f".CLEAN1R2_FINAL.attempt-{attempt_id}"
    attempt.mkdir()
    try:
        result = _finalize_into(paths, attempt)
        if final_root.exists() or final_root.is_symlink():
            raise FinalizationError("Authoritative CLEAN1R2 terminal root appeared during finalization")
        os.replace(attempt, final_root)
    except Exception as exc:
        marker = {
            "schema_version": "paper-rebuild.clean1r2-failed-finalization-attempt.v1",
            "terminal_status": "FAILED_TERMINAL_PUBLICATION_ATTEMPT",
            "reason": f"{type(exc).__name__}: {exc}",
            "active_evidence": False,
            "solver_input_eligible": False,
            "evidence_manifest_eligible": False,
            "final_zip_eligible": False,
            "attempt_id": attempt_id,
        }
        if attempt.is_dir():
            _atomic_json(attempt / "DO_NOT_USE_EVIDENCE.json", marker)
            quarantine = parent / f"CLEAN1R2_FINAL_FAILED_DO_NOT_USE_{attempt_id}"
            os.replace(attempt, quarantine)
        raise
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
