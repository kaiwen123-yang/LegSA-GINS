"""Exact BY2 source registry, raw mutation audit, ledgers, and export guards."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .manifest import read_hash_lock, sha256_file, write_json_atomic
from .paths import is_within, legacy_reason


BY2_FIX_PREFIX = (
    "BY2_BY3/2026-03-06/fixption数据/2026.3.6/by2/"
    "vrtk2_a87c6e_2026-03-06-08-00-54_minimal"
)
BY2_BODY_RELATIVE_PATH = "BY2_BY3/2026-03-06/高层数据/by2.txt"
BY2_TRACE_NAME = "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv"
BY2_TRACE_RELATIVE_PATH = f"{BY2_FIX_PREFIX}/{BY2_TRACE_NAME}"

BY2_RAW_RELATIVE_PATHS = (
    f"{BY2_FIX_PREFIX}.bag",
    f"{BY2_FIX_PREFIX}.fpl",
    f"{BY2_FIX_PREFIX}/corr-raw.csv",
    f"{BY2_FIX_PREFIX}/gnss1-raw.csv",
    f"{BY2_FIX_PREFIX}/gnss1-status.csv",
    f"{BY2_FIX_PREFIX}/gnss2-raw.csv",
    f"{BY2_FIX_PREFIX}/gnss2-status.csv",
    f"{BY2_FIX_PREFIX}/imu-biases.csv",
    f"{BY2_FIX_PREFIX}/imu-data.csv",
    f"{BY2_FIX_PREFIX}/imu-temp.csv",
    f"{BY2_FIX_PREFIX}/ntrip-info.csv",
    f"{BY2_FIX_PREFIX}/ntrip-latency.csv",
    f"{BY2_FIX_PREFIX}/tf.csv",
    f"{BY2_FIX_PREFIX}/tf_static.csv",
    BY2_TRACE_RELATIVE_PATH,
    f"{BY2_FIX_PREFIX}/user_io-out-odom_status.csv",
    f"{BY2_FIX_PREFIX}/user_io-out-poi_geodetic.csv",
    f"{BY2_FIX_PREFIX}/user_io-out-poi_odometry.csv",
    f"{BY2_FIX_PREFIX}/user_io-out-poi_smooth_odometry.csv",
    f"{BY2_FIX_PREFIX}/user_io-status.csv",
    f"{BY2_FIX_PREFIX}/userio-raw.csv",
    BY2_BODY_RELATIVE_PATH,
)

RECEIVER_IMU_NAMES = frozenset({"imu-data.csv", "imu-biases.csv", "imu-temp.csv"})
DEVICE_OUTPUT_NAMES = frozenset(
    {
        "user_io-out-odom_status.csv",
        "user_io-out-poi_geodetic.csv",
        "user_io-out-poi_odometry.csv",
        "user_io-out-poi_smooth_odometry.csv",
    }
)
NTRIP_NAMES = frozenset({"ntrip-info.csv", "ntrip-latency.csv"})

PROVIDER_ELIGIBLE_EXPLICIT_PATHS = frozenset(
    {
        f"{BY2_FIX_PREFIX}.bag",
        f"{BY2_FIX_PREFIX}.fpl",
        f"{BY2_FIX_PREFIX}/corr-raw.csv",
        f"{BY2_FIX_PREFIX}/gnss1-raw.csv",
        f"{BY2_FIX_PREFIX}/gnss1-status.csv",
        f"{BY2_FIX_PREFIX}/gnss2-raw.csv",
        f"{BY2_FIX_PREFIX}/gnss2-status.csv",
        f"{BY2_FIX_PREFIX}/tf.csv",
        f"{BY2_FIX_PREFIX}/tf_static.csv",
        f"{BY2_FIX_PREFIX}/user_io-status.csv",
        f"{BY2_FIX_PREFIX}/userio-raw.csv",
        BY2_BODY_RELATIVE_PATH,
    }
)

HARD_DENYLIST_ROWS = (
    ("dataset:BY2_BY3_SHARED_OR_UNASSIGNED", "shared or unassigned derived input"),
    ("alias:LEGACY_NAV_STD_EVAL_NAV", "old algorithm output"),
    ("alias:FINAL_V23_OR_LEGSA_OUTPUT", "forbidden solver input"),
    ("alias:CLEAN0_SMOKE_PROVIDER", "CLEAN1 requires a fresh provider"),
    ("alias:LEGACY_PROVIDER", "legacy provider denied"),
    ("alias:LEGACY_ROW_OR_AGGREGATE", "old result evidence denied"),
    ("alias:LEGACY_FREEZE_PERFORMANCE", "performance content denied"),
    ("data_mode:synthetic_or_semisynthetic", "not eligible for real result table"),
    ("role:trace_online", "trace is evaluator-only"),
)

FAILED_CLEAN1_EXPECTED_RAW_READS = (
    f"{BY2_FIX_PREFIX}/gnss1-status.csv",
    f"{BY2_FIX_PREFIX}/gnss2-status.csv",
    f"{BY2_FIX_PREFIX}/gnss1-raw.csv",
    BY2_BODY_RELATIVE_PATH,
)

FAILED_CLEAN1_ATTEMPT_SPECS: dict[str, dict[str, Any]] = {
    "409508def7f20521db290d9bfb7e1506a1f72ef9": {
        "superseded_reason": "case_insensitive_dual_yaw_artifact_self_copy_code_bug",
        "stderr_markers": (
            "shutil.SameFileError",
            "dual_yaw_provider.csv",
            "DUAL_YAW_PROVIDER.csv",
        ),
        "failure_state": "stable_exported_stage",
    },
    "28ef36d5a9bac87bdeaed2e7567de7bbb9abd238": {
        "superseded_reason": "json_object_artifact_key_order_validation_code_bug",
        "stderr_markers": (
            "FormalProviderError",
            "Formal provider artifact roles/order mismatch",
        ),
        "failure_state": "stable_exported_stage",
    },
    "0aff9ea4c0b8103974591b060ea2b5627a6941ba": {
        "superseded_reason": (
            "git_code_state_ran_inside_traced_provider_child_and_triggered_"
            "strict_legacy_path_crosscheck"
        ),
        "failure_state": "partial_hidden_stage",
        "partial_finalization_reason": (
            "unicode_relative_path_export_redaction_false_positive"
        ),
        "terminal_status": "FAIL_CLEAN1_EVIDENCE_CONTAMINATION",
        "expected_stage_file_count": 23,
        "expected_legacy_git_metadata_event_count": 45,
        "expected_canonical_stage_tree_sha256": (
            "de66b3881e425bbab4f9458fbfd35b8eb2264391d73525a9e4fe14814c762a0e"
        ),
        "expected_provider_manifest_sha256": (
            "653e30f36b4ec4c8a056253719475ad341d8374e3e62b6ec71555dfb5b51bd49"
        ),
    },
}

FAILED_CLEAN1_PARTIAL_STAGE_FILES = frozenset(
    {
        "00_AUTHORIZATION/AUTHORIZATION.md",
        "00_AUTHORIZATION/PRIOR_TECHNICAL_ATTEMPT.json",
        "01_GIT_FREEZE/CODE_FREEZE_COMMIT.txt",
        "01_GIT_FREEZE/GIT_STATE.json",
        "01_GIT_FREEZE/TRACKED_FILE_HASH_MANIFEST.csv",
        "02_PROTOCOL_FREEZE/SCOPE_LOCK.yaml",
        "03_DATA_HASH_AND_ROLES/BY2_RAW_22_POST_HASH_AUDIT.csv",
        "03_DATA_HASH_AND_ROLES/BY2_RAW_22_PRE_HASH_AUDIT.csv",
        "03_DATA_HASH_AND_ROLES/BY2_RAW_22_ROLE_MANIFEST.csv",
        "03_DATA_HASH_AND_ROLES/BY2_RAW_22_SUMMARY.json",
        "03_DATA_HASH_AND_ROLES/CLEAN1_HARD_DENYLIST.csv",
        "03_DATA_HASH_AND_ROLES/EVALUATOR_ONLY_ALLOWLIST.csv",
        "03_DATA_HASH_AND_ROLES/HASH_VERIFIED_NOT_SOLVER_INPUT.csv",
        "03_DATA_HASH_AND_ROLES/PROVIDER_SOLVER_SOURCE_ALLOWLIST.csv",
        "03_DATA_HASH_AND_ROLES/RAW_MUTATION_AUDIT.json",
        "04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_BLOCKED.json",
        "04_PROVIDER_AUDIT/PROVIDER_FAILED_ACTUAL_READ_AUDIT.json",
        "04_PROVIDER_AUDIT/PROVIDER_FAILED_FILE_OPEN_TRACE.raw",
        "04_PROVIDER_AUDIT/PROVIDER_FILE_OPEN_CROSSCHECK.json",
        "06_RUN_MANIFESTS/FOUR_METHOD_RUN_BLOCKED.json",
        "08_EVIDENCE_AUDIT/PRE_RUN_GATE_DECISION.json",
        "09_REPORT/CLEAN1_FULL_REPORT.json",
        "09_REPORT/CLEAN1_FULL_REPORT.md",
    }
)
FAILED_CLEAN1_PARTIAL_STAGE_DIRS = frozenset(
    f"{index:02d}_{name}"
    for index, name in enumerate(
        (
            "AUTHORIZATION",
            "GIT_FREEZE",
            "PROTOCOL_FREEZE",
            "DATA_HASH_AND_ROLES",
            "PROVIDER_AUDIT",
            "BUILD_AND_TESTS",
            "RUN_MANIFESTS",
            "EVALUATION",
            "EVIDENCE_AUDIT",
            "REPORT",
            "EXPORT",
        )
    )
)
FAILED_CLEAN1_PARTIAL_PROVIDER_ROLES = frozenset(
    {
        "imu_runtime_input",
        "gnss_runtime_input",
        "dual_yaw_provider",
        "raw_doppler_provider",
        "go2_attitude_prior",
        "go2_horizontal_velocity_prior",
        "source_quality_metadata",
    }
)
FAILED_CLEAN1_GIT_METADATA_SCAN_PATHS = frozenset(
    {
        "configs/experiments",
        "docs/experiments",
        "experiments",
        "experiments/.gitignore",
        "experiments/dataset_gnss_degraded",
        "experiments/dataset_by",
        "experiments/dataset_indoor_outdoor",
        "src/legsa_gins/experiments",
        "scripts/experiments",
    }
)

FAILED_CLEAN1_RETRY_LAUNCH_SPECS: dict[str, dict[str, Any]] = {
    "b37e0ff1d38a750fb6e035f3b4da3f5b788fbdba": {
        "stage_failure_commit": "28ef36d5a9bac87bdeaed2e7567de7bbb9abd238",
        "failure_class": "ModuleNotFoundError",
        "error_message": "No module named 'scripts'",
        "occurred_before_stage_archive": True,
        "provider_attempt_created": False,
        "formal_run_count": 0,
    }
}

LOCAL_PATH_RE = re.compile(
    r"(?:(?<![:/\w+\-])/(?!/)[^\s'\"`<>]+|"
    r"(?<![\w])[A-Za-z]:[\\/](?![\\/])[^\r\n'\"`]+)"
)
PATH_ALIAS_RE = re.compile(r"<[A-Z0-9_]+>/[^\s'\"`]*")
STRACE_OPENAT_RE = re.compile(
    r'openat\(([^,]+),\s*("(?:\\.|[^"\\])*")'
)


class EvidenceContractError(ValueError):
    """Raw, read-ledger, or export evidence did not close."""


def parse_strace_openat_paths(
    path: str | Path,
    *,
    cwd: str | Path,
    required_substring: str | None = None,
) -> list[Path]:
    """Parse absolute/AT_FDCWD openat paths, including strace UTF-8 octal escapes."""

    source = Path(path).resolve(strict=True)
    base = Path(cwd).resolve(strict=True)
    opened: list[Path] = []
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        if required_substring is not None and required_substring not in line:
            continue
        match = STRACE_OPENAT_RE.search(line)
        if not match:
            continue
        try:
            decoded = ast.literal_eval(match.group(2))
        except (SyntaxError, ValueError):
            continue
        if not isinstance(decoded, str):
            continue
        try:
            decoded = decoded.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        candidate = Path(decoded)
        if not candidate.is_absolute():
            dirfd = match.group(1).strip()
            if dirfd == "AT_FDCWD":
                candidate = base / candidate
            else:
                decoded_fd = re.search(r"<([^>]+)>", dirfd)
                if not decoded_fd or not decoded_fd.group(1).startswith("/"):
                    raise EvidenceContractError(
                        "strace contains an unresolved relative openat path"
                    )
                candidate = Path(decoded_fd.group(1)) / candidate
        opened.append(candidate.resolve(strict=False))
    return opened


@dataclass(frozen=True)
class RawAudit:
    rows: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    verified_hashes: dict[str, str]


def _role_bucket(relative_path: str) -> tuple[str, str]:
    name = Path(relative_path).name
    if relative_path == BY2_TRACE_RELATIVE_PATH:
        return "evaluator_only", "aligned evaluation-only reference"
    if name in RECEIVER_IMU_NAMES:
        return "hash_verified_not_solver_input", "receiver IMU diagnostic or auxiliary; not Go2 body IMU"
    if name in DEVICE_OUTPUT_NAMES:
        return "hash_verified_not_solver_input", "Fixposition device output; not solver input, truth, or correction"
    if name in NTRIP_NAMES:
        return "hash_verified_not_solver_input", "NTRIP diagnostic only"
    if relative_path.endswith((".bag", ".fpl")):
        return "eligible_only_if_actual_conversion_source", "raw capture provenance or explicit fresh conversion source"
    if relative_path == BY2_BODY_RELATIVE_PATH:
        return "eligible_explicit_provider_source", "Go2 body IMU and weak-prior source; never truth"
    if name == "imu-data.csv":
        return "hash_verified_not_solver_input", "receiver IMU diagnostic; never propagation body IMU"
    if name in {"user_io-status.csv", "userio-raw.csv"}:
        return "eligible_only_with_explicit_source_contract", "device source bytes; device solution is never truth"
    return "eligible_explicit_provider_source", "source bytes require an explicit reader and output lineage"


def verify_by2_raw_22(
    raw_root: str | Path,
    hash_lock_path: str | Path,
    *,
    expected_lock_sha256: str,
    expected_full_rows: int = 9980,
    expected_by2_rows: int = 22,
    audit_phase: str = "pre_generation",
    return_failed_file_audit: bool = False,
) -> RawAudit:
    """Verify exactly the frozen 22 paths without directory discovery."""

    root = Path(raw_root).resolve(strict=True)
    lock_path = Path(hash_lock_path).resolve(strict=True)
    lock_hash = sha256_file(lock_path)
    if lock_hash != expected_lock_sha256:
        raise EvidenceContractError("Raw hash lock SHA256 mismatch")
    lock = read_hash_lock(lock_path)
    if len(lock) != expected_full_rows:
        raise EvidenceContractError(f"Raw hash lock row count mismatch: {len(lock)}")
    by2_rows = {relative: row for relative, row in lock.items() if row.get("dataset") == "BY2"}
    if len(by2_rows) != expected_by2_rows:
        raise EvidenceContractError(f"BY2 hash lock row count mismatch: {len(by2_rows)}")
    if set(by2_rows) != set(BY2_RAW_RELATIVE_PATHS):
        missing = sorted(set(BY2_RAW_RELATIVE_PATHS) - set(by2_rows))
        extra = sorted(set(by2_rows) - set(BY2_RAW_RELATIVE_PATHS))
        raise EvidenceContractError(f"BY2 exact path set mismatch; missing={missing}; extra={extra}")

    rows: list[dict[str, Any]] = []
    verified: dict[str, str] = {}
    counts = {"missing": 0, "mismatch": 0, "symlink_escape": 0}
    for relative in BY2_RAW_RELATIVE_PATHS:
        expected = by2_rows[relative]
        raw_candidate = root / relative
        row: dict[str, Any] = {
            "audit_phase": audit_phase,
            "relative_path": relative,
            "dataset": expected.get("dataset"),
            "lock_role": expected.get("role"),
            "expected_size_bytes": expected.get("size_bytes"),
            "expected_sha256": expected.get("sha256"),
            "exists": False,
            "regular_file": False,
            "realpath_confined": False,
            "actual_size_bytes": "",
            "actual_sha256": "",
            "status": "FAIL",
        }
        if not raw_candidate.exists():
            counts["missing"] += 1
            row["reason"] = "missing"
            rows.append(row)
            continue
        resolved = raw_candidate.resolve(strict=True)
        row["exists"] = True
        row["regular_file"] = resolved.is_file()
        row["realpath_confined"] = is_within(resolved, root)
        if not row["realpath_confined"]:
            counts["symlink_escape"] += 1
            row["reason"] = "symlink_escape"
            rows.append(row)
            continue
        if not row["regular_file"]:
            counts["mismatch"] += 1
            row["reason"] = "not_regular_file"
            rows.append(row)
            continue
        actual_size = resolved.stat().st_size
        actual_hash = sha256_file(resolved)
        row["actual_size_bytes"] = actual_size
        row["actual_sha256"] = actual_hash
        size_ok = actual_size == int(str(expected.get("size_bytes") or -1))
        hash_ok = actual_hash == expected.get("sha256")
        if not size_ok or not hash_ok:
            counts["mismatch"] += 1
            row["reason"] = "size_or_sha256_mismatch"
        else:
            row["status"] = "PASS"
            row["reason"] = ""
            verified[relative] = actual_hash
        rows.append(row)

    verified_count = sum(row["status"] == "PASS" for row in rows)
    summary = {
        "schema_version": "paper-rebuild-by2-raw-22-audit-v1",
        "audit_phase": audit_phase,
        "raw_hash_lock_sha256": lock_hash,
        "full_lock_rows": len(lock),
        "by2_lock_rows": len(by2_rows),
        "expected": expected_by2_rows,
        "verified": verified_count,
        **counts,
        "raw_mutation": 0,
        "passed": verified_count == expected_by2_rows and not any(counts.values()),
    }
    if not summary["passed"] and not return_failed_file_audit:
        raise EvidenceContractError("BY2 raw 22 verification failed")
    return RawAudit(rows=tuple(rows), summary=summary, verified_hashes=verified)


def compare_pre_post_raw_audits(pre: RawAudit, post: RawAudit) -> dict[str, Any]:
    changed = sorted(
        relative
        for relative in BY2_RAW_RELATIVE_PATHS
        if pre.verified_hashes.get(relative) != post.verified_hashes.get(relative)
    )
    return {
        "schema_version": "paper-rebuild-by2-raw-mutation-audit-v1",
        "pre_verified": len(pre.verified_hashes),
        "post_verified": len(post.verified_hashes),
        "raw_mutation": len(changed),
        "changed_relative_paths": changed,
        "passed": not changed and len(pre.verified_hashes) == len(post.verified_hashes) == 22,
    }


def validate_provider_source_read_set(
    entries: Sequence[Mapping[str, Any]],
    verified_hashes: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Validate only explicitly registered actual reads; never discover a directory."""

    if not entries:
        raise EvidenceContractError("Provider actual source read set is empty")
    required = {
        "relative_path",
        "role",
        "expected_sha256",
        "actual_sha256",
        "reader_component",
        "reason",
        "output_provider_lineage",
    }
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for raw_entry in entries:
        missing = sorted(required - set(raw_entry))
        if missing:
            raise EvidenceContractError("Actual source entry missing fields: " + ",".join(missing))
        entry = dict(raw_entry)
        relative = str(entry["relative_path"]).replace("\\", "/")
        if relative in seen:
            raise EvidenceContractError(f"Duplicate provider actual read: {relative}")
        seen.add(relative)
        if relative not in PROVIDER_ELIGIBLE_EXPLICIT_PATHS:
            raise EvidenceContractError(f"Source is not eligible for provider/solver reads: {relative}")
        if relative == BY2_TRACE_RELATIVE_PATH:
            raise EvidenceContractError("Trace cannot be read by provider or solver")
        expected = verified_hashes.get(relative)
        if not expected or entry["expected_sha256"] != expected or entry["actual_sha256"] != expected:
            raise EvidenceContractError(f"Actual source hash mismatch: {relative}")
        for field in ("role", "reader_component", "reason", "output_provider_lineage"):
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise EvidenceContractError(f"Actual source entry has empty {field}: {relative}")
        if entry["role"] == "propagation_imu_source" and relative != BY2_BODY_RELATIVE_PATH:
            raise EvidenceContractError("Only the Go2 body source may be the propagation IMU source")
        entry["relative_path"] = relative
        normalized.append(entry)
    return normalized


def write_raw_audit(path: str | Path, audit: RawAudit) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audit.rows[0]))
        writer.writeheader()
        writer.writerows(audit.rows)
    return destination


def write_source_role_manifests(
    output_dir: str | Path,
    audit: RawAudit,
    actual_provider_reads: Sequence[Mapping[str, Any]],
    *,
    allow_empty_actual_for_blocked_attempt: bool = False,
    failed_attempt_read_relpaths: set[str] | None = None,
) -> dict[str, Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    actual = (
        []
        if allow_empty_actual_for_blocked_attempt and not actual_provider_reads
        else validate_provider_source_read_set(actual_provider_reads, audit.verified_hashes)
    )
    actual_set = {entry["relative_path"] for entry in actual}
    role_rows: list[dict[str, Any]] = []
    evaluator_rows: list[dict[str, Any]] = []
    unused_rows: list[dict[str, Any]] = []
    for relative in BY2_RAW_RELATIVE_PATHS:
        bucket, reason = _role_bucket(relative)
        row = {
            "relative_path": relative,
            "expected_sha256": audit.verified_hashes[relative],
            "contract_bucket": bucket,
            "role_reason": reason,
            "actual_provider_or_solver_read": relative in actual_set,
            "failed_attempt_read_status": (
                "NOT_APPLICABLE"
                if not allow_empty_actual_for_blocked_attempt
                else "UNKNOWN_STRACE_UNAVAILABLE"
                if failed_attempt_read_relpaths is None
                else "OBSERVED_PARTIAL_FAILED_ATTEMPT"
                if relative in failed_attempt_read_relpaths
                else "NOT_OBSERVED_PARTIAL_FAILED_ATTEMPT"
            ),
        }
        role_rows.append(row)
        if relative == BY2_TRACE_RELATIVE_PATH:
            evaluator_rows.append(row)
        elif relative not in actual_set:
            unused_rows.append(row)

    def write_csv(name: str, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> Path:
        path = destination / name
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(fields))
            writer.writeheader()
            writer.writerows(rows)
        return path

    paths = {
        "roles": write_csv("BY2_RAW_22_ROLE_MANIFEST.csv", role_rows, list(role_rows[0])),
        "actual": write_csv(
            "PROVIDER_SOLVER_SOURCE_ALLOWLIST.csv",
            actual,
            [
                "relative_path",
                "role",
                "expected_sha256",
                "actual_sha256",
                "reader_component",
                "reason",
                "output_provider_lineage",
            ],
        ),
        "evaluator": write_csv("EVALUATOR_ONLY_ALLOWLIST.csv", evaluator_rows, list(evaluator_rows[0])),
        "unused": write_csv("HASH_VERIFIED_NOT_SOLVER_INPUT.csv", unused_rows, list(unused_rows[0])),
        "denylist": write_csv(
            "CLEAN1_HARD_DENYLIST.csv",
            [{"denied_selector": selector, "reason": reason} for selector, reason in HARD_DENYLIST_ROWS],
            ["denied_selector", "reason"],
        ),
    }
    write_json_atomic(destination / "BY2_RAW_22_SUMMARY.json", audit.summary)
    return paths


def write_read_ledger(
    path: str | Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    allowed_roles: Iterable[str],
) -> Path:
    """Write an alias/relative-path ledger; absolute paths are intentionally excluded."""

    allowed = set(allowed_roles)
    required = ("read_order", "path_alias", "relative_path", "role", "sha256", "reader_component")
    normalized: list[dict[str, Any]] = []
    for raw in rows:
        row = {field: raw.get(field, "") for field in required}
        if row["role"] not in allowed:
            raise EvidenceContractError(f"Read ledger role is not allowed: {row['role']}")
        relative = str(row["relative_path"])
        if relative.startswith("/") or ".." in Path(relative).parts or LOCAL_PATH_RE.search(relative):
            raise EvidenceContractError("Read ledger must use an alias plus safe relative path")
        if not isinstance(row["sha256"], str) or len(row["sha256"]) != 64:
            raise EvidenceContractError("Read ledger SHA256 is invalid")
        normalized.append(row)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(required))
        writer.writeheader()
        writer.writerows(normalized)
    return destination


def scan_text_for_export_leaks(text: str) -> list[str]:
    issues: list[str] = []
    without_alias_paths = PATH_ALIAS_RE.sub("<PATH_ALIAS>", text)
    if LOCAL_PATH_RE.search(without_alias_paths):
        issues.append("absolute_local_path")
    for line in text.splitlines():
        reason = legacy_reason(line)
        if reason:
            issues.append(reason)
    return sorted(set(issues))


def assert_export_text_is_redacted(text: str) -> None:
    issues = scan_text_for_export_leaks(text)
    if issues:
        raise EvidenceContractError("Export text leak: " + ",".join(issues))


def canonical_file_tree_digest(
    root: str | Path, expected_relative_files: Iterable[str]
) -> str:
    """Hash an exact file tree by canonical relative path, file SHA, and size."""

    base = Path(root).resolve(strict=True)
    rows: list[dict[str, Any]] = []
    for relative in sorted(expected_relative_files):
        candidate = base / relative
        if candidate.is_symlink():
            raise EvidenceContractError("Canonical evidence tree contains a symlink")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_file() or not is_within(resolved, base):
            raise EvidenceContractError("Canonical evidence tree file is missing or escapes")
        rows.append(
            {
                "relative_path": relative,
                "sha256": sha256_file(resolved),
                "size_bytes": resolved.stat().st_size,
            }
        )
    payload = json.dumps(
        rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def resolve_path_without_symlink_chain(
    root: str | Path,
    relative: str,
    *,
    role: str,
    must_exist: bool = True,
) -> Path:
    """Resolve one root-relative path only after lstat-like symlink checks."""

    root_input = Path(root)
    if root_input.is_symlink():
        raise EvidenceContractError(f"{role} root is a symlink")
    base = root_input.resolve(strict=True)
    normalized = relative.replace("\\", "/")
    relative_path = Path(normalized)
    if (
        not normalized
        or normalized != relative
        or relative_path.is_absolute()
        or ".." in relative_path.parts
        or "." in relative_path.parts
    ):
        raise EvidenceContractError(f"{role} relative path is unsafe")
    candidate = base
    for component in relative_path.parts:
        candidate = candidate / component
        if candidate.is_symlink():
            raise EvidenceContractError(f"{role} path chain contains a symlink")
        if must_exist and not candidate.exists():
            raise EvidenceContractError(f"{role} path chain is missing")
    resolved = candidate.resolve(strict=must_exist)
    if not is_within(resolved, base):
        raise EvidenceContractError(f"{role} escapes its root")
    return resolved


def _regular_file_without_symlink_chain(
    root: str | Path, relative: str, *, role: str
) -> Path:
    resolved = resolve_path_without_symlink_chain(
        root, relative, role=role, must_exist=True
    )
    if not resolved.is_file():
        raise EvidenceContractError(f"{role} is not a regular file")
    return resolved


def _validate_partial_raw_audit_csv(
    path: Path, *, raw_root: Path, expected_phase: str
) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 22 or {row.get("relative_path") for row in rows} != set(
        BY2_RAW_RELATIVE_PATHS
    ):
        raise EvidenceContractError("Partial failed raw audit path set differs")
    verified: dict[str, str] = {}
    for row in rows:
        relative = str(row.get("relative_path") or "")
        candidate = _regular_file_without_symlink_chain(
            raw_root, relative, role="partial failed raw audit source"
        )
        digest = sha256_file(candidate)
        if (
            row.get("audit_phase") != expected_phase
            or row.get("status") != "PASS"
            or row.get("exists") != "True"
            or row.get("regular_file") != "True"
            or row.get("realpath_confined") != "True"
            or row.get("expected_sha256") != digest
            or row.get("actual_sha256") != digest
            or int(str(row.get("expected_size_bytes") or -1))
            != candidate.stat().st_size
            or int(str(row.get("actual_size_bytes") or -1))
            != candidate.stat().st_size
        ):
            raise EvidenceContractError("Partial failed raw audit row differs")
        verified[relative] = digest
    return verified


def _validate_partial_provider_attempt(
    attempt: Path,
    *,
    raw_root: Path,
    expected_code_commit: str,
) -> dict[str, Any]:
    manifest_path = _regular_file_without_symlink_chain(
        attempt,
        "CLEAN_INPUT_MANIFEST.json",
        role="partial formal provider manifest",
    )
    specification = FAILED_CLEAN1_ATTEMPT_SPECS.get(expected_code_commit)
    if (
        not isinstance(specification, dict)
        or sha256_file(manifest_path)
        != specification.get("expected_provider_manifest_sha256")
    ):
        raise EvidenceContractError("Partial formal provider manifest hash differs")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise EvidenceContractError("Partial provider manifest is not an object")
    raw_hashes = manifest.get("raw_source_hashes")
    actual_reads = manifest.get("actual_source_read_set")
    artifacts = manifest.get("artifacts")
    provider_hashes = manifest.get("provider_hashes")
    if (
        manifest.get("schema_version") != "paper-rebuild-clean1-input-v1"
        or manifest.get("generator_code_commit") != expected_code_commit
        or manifest.get("generator_worktree_dirty") is not False
        or not isinstance(raw_hashes, dict)
        or set(raw_hashes) != set(BY2_RAW_RELATIVE_PATHS)
        or not isinstance(actual_reads, list)
        or not isinstance(artifacts, dict)
        or set(artifacts) != FAILED_CLEAN1_PARTIAL_PROVIDER_ROLES
        or not isinstance(provider_hashes, dict)
        or set(provider_hashes) != FAILED_CLEAN1_PARTIAL_PROVIDER_ROLES
    ):
        raise EvidenceContractError("Partial formal provider manifest closure differs")
    forbidden_false = (
        "synthetic_data_used",
        "semisynthetic_data_used",
        "trace_used_online",
        "receiver_imu_as_body_imu",
        "final_v23_output_solver_input",
        "LegSA_output_solver_input",
        "per_case_tuning",
        "output_only_correction",
        "epoch_deleted_for_metric",
        "status_fallback_used",
        "legacy_provider_used",
    )
    if any(manifest.get(field) is not False for field in forbidden_false) or any(
        manifest.get(field) != 0
        for field in (
            "old_runtime_input_count",
            "legacy_provider_input_count",
            "legacy_row_input_count",
            "legacy_aggregate_input_count",
        )
    ):
        raise EvidenceContractError("Partial formal provider forbidden flag differs")
    forbidden_result_tokens = (
        "row_level",
        "aggregate",
        "formal_run",
        "eval_nav",
        "four_method",
        "result",
        "metric",
    )
    for candidate in attempt.rglob("*"):
        relative_parts = tuple(
            part.casefold() for part in candidate.relative_to(attempt).parts
        )
        if any(
            token in component
            for component in relative_parts
            for token in forbidden_result_tokens
        ):
            raise EvidenceContractError(
                "Partial provider attempt contains unexpected result evidence"
            )
    for relative, digest in raw_hashes.items():
        source = _regular_file_without_symlink_chain(
            raw_root, relative, role="partial formal provider raw source"
        )
        if sha256_file(source) != digest:
            raise EvidenceContractError("Partial formal provider raw hash differs")
    normalized_reads = validate_provider_source_read_set(actual_reads, raw_hashes)
    if {entry["relative_path"] for entry in normalized_reads} != set(
        FAILED_CLEAN1_EXPECTED_RAW_READS
    ):
        raise EvidenceContractError("Partial formal provider actual read set differs")
    computed_hashes: dict[str, str] = {}
    for role in sorted(FAILED_CLEAN1_PARTIAL_PROVIDER_ROLES):
        entry = artifacts[role]
        if not isinstance(entry, dict):
            raise EvidenceContractError("Partial formal provider artifact entry differs")
        relative = str(entry.get("relative_path") or "")
        resolved = _regular_file_without_symlink_chain(
            attempt, relative, role=f"partial formal provider artifact {role}"
        )
        digest = sha256_file(resolved)
        if provider_hashes[role] != digest:
            raise EvidenceContractError("Partial formal provider artifact hash differs")
        computed_hashes[role] = digest
    canonical_hashes = json.dumps(
        computed_hashes, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if manifest.get("provider_bundle_hash") != hashlib.sha256(canonical_hashes).hexdigest():
        raise EvidenceContractError("Partial formal provider bundle hash differs")
    with (attempt / "PROVIDER_HASH_MANIFEST.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != [
            "provider_role",
            "relative_path",
            "sha256",
            "solver_input",
            "artifact_role",
        ]:
            raise EvidenceContractError("Partial provider hash manifest schema differs")
        rows = list(reader)
    if len(rows) != 7 or {row.get("provider_role") for row in rows} != set(
        FAILED_CLEAN1_PARTIAL_PROVIDER_ROLES
    ):
        raise EvidenceContractError("Partial provider hash manifest roles differ")
    for row in rows:
        role = str(row["provider_role"])
        entry = artifacts[role]
        if (
            row.get("relative_path") != entry.get("relative_path")
            or row.get("sha256") != computed_hashes[role]
            or row.get("solver_input") != str(entry.get("solver_input"))
            or row.get("artifact_role") != entry.get("artifact_role")
        ):
            raise EvidenceContractError("Partial provider hash manifest row differs")
    backend_path = _regular_file_without_symlink_chain(
        attempt,
        "RAW_DOPPLER_BACKEND_REPORT.json",
        role="partial Raw Doppler backend report",
    )
    backend = json.loads(backend_path.read_text(encoding="utf-8"))
    if (
        not isinstance(backend, dict)
        or backend != manifest.get("raw_doppler_backend")
        or manifest.get("raw_doppler_backend_report_sha256")
        != sha256_file(backend_path)
    ):
        raise EvidenceContractError("Partial Raw Doppler backend closure differs")
    from .formal_provider import validate_raw_doppler_backend_report

    validated_backend = validate_raw_doppler_backend_report(
        backend, verified_raw_hashes=raw_hashes
    )
    retained = validated_backend["retained_backend_artifacts"]
    if len({str(entry["relative_path"]) for entry in retained.values()}) != 7:
        raise EvidenceContractError("Partial retained backend paths are not unique")
    retained_hashes: dict[str, str] = {}
    for role, entry in retained.items():
        relative = str(entry["relative_path"])
        retained_path = _regular_file_without_symlink_chain(
            attempt,
            relative,
            role=f"partial retained Raw Doppler artifact {role}",
        )
        digest = sha256_file(retained_path)
        if digest != entry["sha256"]:
            raise EvidenceContractError(
                "Partial retained Raw Doppler artifact hash differs"
            )
        retained_hashes[role] = digest
    canonical_retained = json.dumps(
        dict(retained), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if hashlib.sha256(canonical_retained).hexdigest() != validated_backend[
        "retained_backend_bundle_hash"
    ]:
        raise EvidenceContractError("Partial retained backend bundle hash differs")
    top_level_cross_map = {
        "helper_executable_hash": "helper_executable",
        "helper_source_hash": "helper_source",
        "convbin_executable_hash": "convbin_executable",
        "rebuilt_ubx_hash": "rebuilt_ubx",
        "obs_source_hash": "rinex_obs",
        "nav_source_hash": "rinex_nav",
    }
    if any(
        validated_backend[field] != retained_hashes[role]
        for field, role in top_level_cross_map.items()
    ):
        raise EvidenceContractError("Partial retained backend top-level hash differs")
    if (
        retained_hashes["formal_raw_doppler_provider"]
        != computed_hashes["raw_doppler_provider"]
    ):
        raise EvidenceContractError(
            "Partial retained Raw Doppler provider differs from provider role hash"
        )
    return {
        "provider_bundle_hash": manifest["provider_bundle_hash"],
        "provider_role_count": len(computed_hashes),
        "raw_hashes": raw_hashes,
    }


def _validate_partial_failed_clean1_attempt_evidence(
    stage: Path,
    *,
    raw_root: Path,
    code_root: Path,
    provider_attempt: Path,
    expected_code_commit: str,
    specification: Mapping[str, Any],
) -> dict[str, Any]:
    entries = list(stage.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise EvidenceContractError("Partial failed stage contains a symlink")
    actual_files = {
        path.relative_to(stage).as_posix() for path in entries if path.is_file()
    }
    actual_dirs = {
        path.relative_to(stage).as_posix() for path in entries if path.is_dir()
    }
    if (
        actual_files != FAILED_CLEAN1_PARTIAL_STAGE_FILES
        or actual_dirs != FAILED_CLEAN1_PARTIAL_STAGE_DIRS
        or len(actual_files) != specification["expected_stage_file_count"]
    ):
        raise EvidenceContractError("Partial failed stage exact tree differs")
    for forbidden in (
        "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.csv",
        "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.sha256",
        "10_EXPORT/EXPORT_SHA256_MANIFEST.csv",
        "10_EXPORT/CLEAN1_CONTEXT_FOR_GPT.zip",
    ):
        if (stage / forbidden).exists():
            raise EvidenceContractError("Partial failed stage unexpectedly has finalized evidence/export")

    def json_object(relative: str) -> dict[str, Any]:
        value = json.loads((stage / relative).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise EvidenceContractError("Partial failed JSON is not an object")
        return value

    terminal = str(specification["terminal_status"])
    decision = json_object("08_EVIDENCE_AUDIT/PRE_RUN_GATE_DECISION.json")
    report = json_object("09_REPORT/CLEAN1_FULL_REPORT.json")
    run_gate = json_object("06_RUN_MANIFESTS/FOUR_METHOD_RUN_BLOCKED.json")
    blocked = json_object("04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_BLOCKED.json")
    read_audit = json_object(
        "04_PROVIDER_AUDIT/PROVIDER_FAILED_ACTUAL_READ_AUDIT.json"
    )
    raw_summary = json_object("03_DATA_HASH_AND_ROLES/BY2_RAW_22_SUMMARY.json")
    mutation = json_object("03_DATA_HASH_AND_ROLES/RAW_MUTATION_AUDIT.json")
    git_state = json_object("01_GIT_FREEZE/GIT_STATE.json")
    expected_run_gate = {
        "schema_version": "paper-rebuild-clean1-four-run-gate-v1",
        "formal_run_count": 0,
        "method_count_required": 4,
        "metric_driven_rerun": False,
        "terminal_status": terminal,
        "paper_performance_claim": False,
    }
    if (
        decision.get("code_freeze_commit") != expected_code_commit
        or decision.get("terminal_status") != terminal
        or decision.get("formal_run_count") != 0
        or decision.get("provider_promoted") is not False
        or decision.get("provider_attempt_generated") is not True
        or report.get("code_freeze_commit") != expected_code_commit
        or report.get("terminal_decision") != terminal
        or report.get("formal_run_count") != 0
        or report.get("metrics_generated") is not False
        or report.get("paper_figure_count") != 0
        or report.get("provider_promoted") is not False
        or run_gate != expected_run_gate
        or blocked
        != {
            "terminal_status": terminal,
            "provider_final_root_created": False,
            "failed_attempt_preserved": True,
            "file_open_crosscheck_passed": False,
        }
        or read_audit
        != {
            "strace_available": True,
            "observed_partial_failed_attempt_raw_reads": sorted(
                FAILED_CLEAN1_EXPECTED_RAW_READS
            ),
            "unexpected_raw_reads": [],
            "promoted_provider_actual_read_set": [],
            "passed": True,
        }
        or raw_summary.get("passed") is not True
        or raw_summary.get("pre_verified") != 22
        or raw_summary.get("post_verified") != 22
        or raw_summary.get("raw_mutation") != 0
        or mutation.get("passed") is not True
        or mutation.get("pre_verified") != 22
        or mutation.get("post_verified") != 22
        or mutation.get("raw_mutation") != 0
        or mutation.get("changed_relative_paths") != []
        or git_state.get("code_freeze_commit") != expected_code_commit
        or git_state.get("worktree_clean") is not True
        or (stage / "01_GIT_FREEZE/CODE_FREEZE_COMMIT.txt")
        .read_text(encoding="utf-8")
        .strip()
        != expected_code_commit
    ):
        raise EvidenceContractError("Partial failed terminal/raw/run closure differs")

    pre_hashes = _validate_partial_raw_audit_csv(
        stage / "03_DATA_HASH_AND_ROLES/BY2_RAW_22_PRE_HASH_AUDIT.csv",
        raw_root=raw_root,
        expected_phase="pre_generation",
    )
    post_hashes = _validate_partial_raw_audit_csv(
        stage / "03_DATA_HASH_AND_ROLES/BY2_RAW_22_POST_HASH_AUDIT.csv",
        raw_root=raw_root,
        expected_phase="post_generation",
    )
    if pre_hashes != post_hashes:
        raise EvidenceContractError("Partial failed raw pre/post hashes differ")
    provider = _validate_partial_provider_attempt(
        provider_attempt,
        raw_root=raw_root,
        expected_code_commit=expected_code_commit,
    )
    if provider["raw_hashes"] != pre_hashes:
        raise EvidenceContractError("Partial provider and raw audit hashes differ")

    crosscheck = json_object("04_PROVIDER_AUDIT/PROVIDER_FILE_OPEN_CROSSCHECK.json")
    trace = stage / "04_PROVIDER_AUDIT/PROVIDER_FAILED_FILE_OPEN_TRACE.raw"
    expected_raw = list(FAILED_CLEAN1_EXPECTED_RAW_READS)
    if (
        crosscheck.get("schema_version")
        != "paper-rebuild-provider-file-open-crosscheck-v1"
        or crosscheck.get("strace_available") is not True
        or crosscheck.get("provider_process_isolated") is not True
        or crosscheck.get("expected_raw_relative_paths") != expected_raw
        or crosscheck.get("missing_expected_raw_opens") != []
        or crosscheck.get("unexpected_raw_root_relative_paths") != []
        or crosscheck.get("unexpected_clean_root_relative_paths") != []
        or crosscheck.get("trace_opened_by_provider_process") is not False
        or crosscheck.get("legacy_path_read_count")
        != specification["expected_legacy_git_metadata_event_count"]
        or crosscheck.get("passed") is not False
        or not re.fullmatch(r"[0-9a-f]{64}", str(crosscheck.get("strace_sha256") or ""))
        or sha256_file(trace) != crosscheck["strace_sha256"]
    ):
        raise EvidenceContractError("Partial failed file-open crosscheck differs")
    opened = parse_strace_openat_paths(trace, cwd=code_root)
    raw_opened = [path for path in opened if is_within(path, raw_root)]
    expected_paths = {
        relative: (raw_root / relative).resolve(strict=True) for relative in expected_raw
    }
    observed_counts = {
        relative: sum(path == expected for path in raw_opened)
        for relative, expected in expected_paths.items()
    }
    if (
        observed_counts != crosscheck.get("observed_expected_raw_open_counts")
        or any(path not in set(expected_paths.values()) for path in raw_opened)
    ):
        raise EvidenceContractError("Partial failed strace raw closure differs")
    if (raw_root / BY2_TRACE_RELATIVE_PATH).resolve(strict=True) in raw_opened:
        raise EvidenceContractError("Partial failed provider opened trace")
    clean_root = provider_attempt.parent.parent.resolve(strict=True)
    raw_hash_lock = clean_root / "01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv"
    unexpected_clean = {
        path.relative_to(clean_root).as_posix()
        for path in opened
        if is_within(path, clean_root)
        and not is_within(path, provider_attempt)
        and path != raw_hash_lock.resolve(strict=True)
    }
    if unexpected_clean:
        raise EvidenceContractError("Partial failed strace clean-root closure differs")
    legacy_opened = [path for path in opened if legacy_reason(path) is not None]
    legacy_relative_counts: dict[str, int] = {}
    for path in legacy_opened:
        if not is_within(path, code_root):
            raise EvidenceContractError("Partial failed legacy open was outside Git worktree")
        relative = path.relative_to(code_root).as_posix()
        legacy_relative_counts[relative] = legacy_relative_counts.get(relative, 0) + 1
    if legacy_relative_counts != {
        relative: 5 for relative in FAILED_CLEAN1_GIT_METADATA_SCAN_PATHS
    }:
        raise EvidenceContractError("Partial failed Git metadata event set differs")
    if len(opened) != crosscheck.get("opened_path_count"):
        raise EvidenceContractError("Partial failed strace opened-path count differs")

    forbidden_tokens = (
        "ROW_LEVEL_ERRORS",
        "AGGREGATE_METRICS",
        "AGGREGATE_CROSSCHECK",
        "FOUR_METHOD_METRICS",
        "FORMAL_RUN_MANIFEST",
        "EVAL_NAV",
    )
    if any(
        any(token in relative.upper() for token in forbidden_tokens)
        or relative.startswith("07_EVALUATION/")
        or Path(relative).suffix.casefold()
        in {".png", ".jpg", ".jpeg", ".svg", ".pdf", ".nav", ".std"}
        for relative in actual_files
    ):
        raise EvidenceContractError("Partial failed stage contains run/metric/figure payload")
    tree_digest = canonical_file_tree_digest(stage, actual_files)
    if tree_digest != specification["expected_canonical_stage_tree_sha256"]:
        raise EvidenceContractError("Partial failed canonical stage tree differs")
    return {
        "evidence_manifest_sha256": "NOT_AVAILABLE_PARTIAL_STAGE",
        "evidence_manifest_present": False,
        "provider_attempt_name": provider_attempt.name,
        "evidence_file_count": len(actual_files),
        "export_member_count": 0,
        "partial_stage_preserved": True,
        "canonical_stage_tree_sha256": tree_digest,
        "provider_bundle_hash": provider["provider_bundle_hash"],
        "provider_role_count": provider["provider_role_count"],
        "legacy_git_metadata_event_count": len(legacy_opened),
    }


def validate_failed_clean1_attempt_evidence(
    stage_root: str | Path,
    *,
    raw_root: str | Path,
    code_root: str | Path,
    provider_attempt: str | Path,
    expected_code_commit: str,
) -> dict[str, Any]:
    """Rehash one exact failed stage and prove it contains no result evidence."""

    stage_input = Path(stage_root)
    attempt_input = Path(provider_attempt)
    raw_input = Path(raw_root)
    if (
        stage_input.is_symlink()
        or attempt_input.is_symlink()
        or raw_input.is_symlink()
    ):
        raise EvidenceContractError("Failed CLEAN1 stage/provider/raw root is a symlink")
    stage = stage_input.resolve(strict=True)
    raw = raw_input.resolve(strict=True)
    code = Path(code_root).resolve(strict=True)
    attempt = attempt_input.resolve(strict=True)
    if not stage.is_dir() or not attempt.is_dir():
        raise EvidenceContractError("Failed CLEAN1 stage/provider attempt is missing")
    specification = FAILED_CLEAN1_ATTEMPT_SPECS.get(expected_code_commit)
    if specification is None:
        raise EvidenceContractError("Failed CLEAN1 code commit is not retry-authorized")
    if specification.get("failure_state") == "partial_hidden_stage":
        return _validate_partial_failed_clean1_attempt_evidence(
            stage,
            raw_root=raw,
            code_root=code,
            provider_attempt=attempt,
            expected_code_commit=expected_code_commit,
            specification=specification,
        )

    def safe_relative(value: str) -> str:
        normalized = value.replace("\\", "/")
        candidate = Path(normalized)
        if (
            not normalized
            or normalized != value
            or candidate.is_absolute()
            or ".." in candidate.parts
            or "." in candidate.parts
        ):
            raise EvidenceContractError("Failed-attempt manifest path is unsafe")
        return normalized

    def json_object(relative: str) -> dict[str, Any]:
        path = stage / safe_relative(relative)
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise EvidenceContractError("Failed-attempt JSON is not an object")
        return value

    decision = json_object("08_EVIDENCE_AUDIT/PRE_RUN_GATE_DECISION.json")
    run_gate = json_object("06_RUN_MANIFESTS/FOUR_METHOD_RUN_BLOCKED.json")
    report = json_object("09_REPORT/CLEAN1_FULL_REPORT.json")
    blocked = json_object("04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_BLOCKED.json")
    read_audit = json_object(
        "04_PROVIDER_AUDIT/PROVIDER_FAILED_ACTUAL_READ_AUDIT.json"
    )
    terminal = "BLOCKED_CLEAN1_RAW_DOPPLER_BACKEND_LINEAGE_NOT_PROVEN"
    if (
        decision.get("code_freeze_commit") != expected_code_commit
        or decision.get("terminal_status") != terminal
        or decision.get("formal_run_count") != 0
        or decision.get("provider_promoted") is not False
        or report.get("terminal_decision") != terminal
        or report.get("formal_run_count") != 0
        or report.get("metrics_generated") is not False
        or report.get("paper_figure_count") != 0
        or run_gate
        != {
            "schema_version": "paper-rebuild-clean1-four-run-gate-v1",
            "formal_run_count": 0,
            "method_count_required": 4,
            "metric_driven_rerun": False,
            "terminal_status": terminal,
            "paper_performance_claim": False,
        }
    ):
        raise EvidenceContractError("Failed CLEAN1 terminal/run closure differs")
    expected_blocked = {
        "terminal_status": terminal,
        "returncode": 1,
        "provider_final_root_created": False,
        "failed_attempt_preserved": True,
        "strace_available": True,
        "strace_sha256": blocked.get("strace_sha256"),
    }
    if blocked != expected_blocked or not re.fullmatch(
        r"[0-9a-f]{64}", str(blocked.get("strace_sha256") or "")
    ):
        raise EvidenceContractError("Failed provider process record differs")
    expected_read_audit = {
        "strace_available": True,
        "observed_partial_failed_attempt_raw_reads": sorted(
            FAILED_CLEAN1_EXPECTED_RAW_READS
        ),
        "unexpected_raw_reads": [],
        "promoted_provider_actual_read_set": [],
        "passed": True,
    }
    if read_audit != expected_read_audit:
        raise EvidenceContractError("Failed provider read closure differs")
    trace = stage / "04_PROVIDER_AUDIT/PROVIDER_FAILED_FILE_OPEN_TRACE.raw"
    if not trace.is_file() or sha256_file(trace) != blocked["strace_sha256"]:
        raise EvidenceContractError("Failed provider strace hash differs")
    opened = parse_strace_openat_paths(
        trace, cwd=code, required_substring=str(raw)
    )
    observed_raw = sorted(
        {
            path.relative_to(raw).as_posix()
            for path in opened
            if is_within(path, raw)
        }
    )
    if observed_raw != sorted(FAILED_CLEAN1_EXPECTED_RAW_READS):
        raise EvidenceContractError("Failed provider strace raw reads differ")
    stderr = (
        stage / "04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_STDERR.txt"
    ).read_text(encoding="utf-8", errors="strict")
    for marker in specification["stderr_markers"]:
        if marker not in stderr:
            raise EvidenceContractError("Failed provider error is not the exact authorized code bug")

    required_attempt_files = (
        "RAW_DOPPLER_BACKEND_REPORT.json",
        "providers/RAW_DOPPLER_VELOCITY.csv",
        "providers/dual_yaw_provider.csv",
        "runtime_inputs/BY2_PROCESS_DATA_COMPAT.gnss",
        "runtime_inputs/BY2_PROCESS_DATA_COMPAT.imu",
    )
    for relative in required_attempt_files:
        candidate = (attempt / relative).resolve(strict=True)
        if (
            not candidate.is_file()
            or not is_within(candidate, attempt)
            or candidate.stat().st_size <= 0
        ):
            raise EvidenceContractError("Preserved failed provider attempt is incomplete")

    manifest = stage / "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.csv"
    sidecar = stage / "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.sha256"
    manifest_digest = sha256_file(manifest)
    if sidecar.read_text(encoding="utf-8").strip() != (
        f"{manifest_digest}  EVIDENCE_MANIFEST.csv"
    ):
        raise EvidenceContractError("Failed evidence manifest sidecar differs")
    with manifest.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["relative_path", "sha256", "size_bytes", "tracked"]:
            raise EvidenceContractError("Failed evidence manifest schema differs")
        rows = list(reader)
    declared: dict[str, dict[str, str]] = {}
    for row in rows:
        relative = safe_relative(str(row.get("relative_path") or ""))
        if relative in declared:
            raise EvidenceContractError("Failed evidence manifest path is duplicated")
        if row.get("tracked") != "False" or not re.fullmatch(
            r"[0-9a-f]{64}", str(row.get("sha256") or "")
        ):
            raise EvidenceContractError("Failed evidence manifest row differs")
        candidate = (stage / relative).resolve(strict=True)
        if not candidate.is_file() or not is_within(candidate, stage):
            raise EvidenceContractError("Failed evidence manifest file escapes stage")
        if (
            sha256_file(candidate) != row["sha256"]
            or candidate.stat().st_size != int(str(row.get("size_bytes") or -1))
        ):
            raise EvidenceContractError("Failed evidence artifact hash/size differs")
        declared[relative] = row
    excluded = {
        "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.csv",
        "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.sha256",
    }
    actual = {
        path.relative_to(stage).as_posix()
        for path in stage.rglob("*")
        if path.is_file()
    }
    if set(declared) != actual - excluded or actual & excluded != excluded:
        raise EvidenceContractError("Failed evidence manifest file set differs")
    forbidden_tokens = (
        "ROW_LEVEL_ERRORS",
        "AGGREGATE_METRICS",
        "AGGREGATE_CROSSCHECK",
        "FOUR_METHOD_METRICS",
        "FORMAL_RUN_MANIFEST",
        "EVAL_NAV",
    )
    if any(
        any(token in relative.upper() for token in forbidden_tokens)
        or relative.startswith("07_EVALUATION/")
        or (
            relative.startswith("06_RUN_MANIFESTS/")
            and relative != "06_RUN_MANIFESTS/FOUR_METHOD_RUN_BLOCKED.json"
        )
        or Path(relative).suffix.casefold()
        in {".png", ".jpg", ".jpeg", ".svg", ".pdf", ".nav", ".std"}
        for relative in actual
    ):
        raise EvidenceContractError("Failed stage contains result/metric/figure payload")

    export_manifest = stage / "10_EXPORT/EXPORT_SHA256_MANIFEST.csv"
    export_archive = stage / "10_EXPORT/CLEAN1_CONTEXT_FOR_GPT.zip"
    with export_manifest.open("r", encoding="utf-8", newline="") as handle:
        export_reader = csv.DictReader(handle)
        if export_reader.fieldnames != ["archive_path", "sha256", "size_bytes"]:
            raise EvidenceContractError("Failed export manifest schema differs")
        export_rows = list(export_reader)
    export_declared: dict[str, dict[str, str]] = {}
    for row in export_rows:
        name = safe_relative(str(row.get("archive_path") or ""))
        if name in export_declared or not re.fullmatch(
            r"[0-9a-f]{64}", str(row.get("sha256") or "")
        ) or (
            name.endswith(".local.yaml")
            or "raw_doppler_backend/" in name.casefold()
            or "row_level" in name.casefold()
            or Path(name).suffix.casefold()
            in {".nav", ".std", ".pdf", ".png", ".jpg", ".jpeg", ".svg"}
        ):
            raise EvidenceContractError("Failed export manifest row differs")
        export_declared[name] = row
        if name != "CLAIM_BOUNDARY.md":
            source = (stage / name).resolve(strict=True)
            if (
                not source.is_file()
                or not is_within(source, stage)
                or sha256_file(source) != row["sha256"]
                or source.stat().st_size != int(str(row["size_bytes"]))
            ):
                raise EvidenceContractError("Failed export source differs")
    with zipfile.ZipFile(export_archive, "r") as handle:
        members = handle.infolist()
        names = [safe_relative(member.filename) for member in members]
        if len(names) != len(set(names)) or set(names) != (
            set(export_declared) | {"EXPORT_SHA256_MANIFEST.csv"}
        ):
            raise EvidenceContractError("Failed export archive member set differs")
        for name, row in export_declared.items():
            data = handle.read(name)
            if (
                hashlib.sha256(data).hexdigest() != row["sha256"]
                or len(data) != int(str(row["size_bytes"]))
            ):
                raise EvidenceContractError("Failed export member hash/size differs")
            if Path(name).suffix.casefold() in {".md", ".json", ".yaml", ".yml", ".csv", ".txt"}:
                assert_export_text_is_redacted(data.decode("utf-8"))
        if handle.read("EXPORT_SHA256_MANIFEST.csv") != export_manifest.read_bytes():
            raise EvidenceContractError("Failed export embedded manifest differs")
    return {
        "evidence_manifest_sha256": manifest_digest,
        "provider_attempt_name": attempt.name,
        "evidence_file_count": len(declared),
        "export_member_count": len(export_declared) + 1,
    }


def write_csv_atomic(path: str | Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=destination.name + ".", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination
