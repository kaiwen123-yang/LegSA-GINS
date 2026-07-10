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
    },
    "28ef36d5a9bac87bdeaed2e7567de7bbb9abd238": {
        "superseded_reason": "json_object_artifact_key_order_validation_code_bug",
        "stderr_markers": (
            "FormalProviderError",
            "Formal provider artifact roles/order mismatch",
        ),
    },
}

LOCAL_PATH_RE = re.compile(
    r"(?:(?<![:/A-Za-z0-9_+\-])/(?!/)[^\s'\"`<>]+|"
    r"(?<![A-Za-z0-9])[A-Za-z]:[\\/](?![\\/])[^\r\n'\"`]+)"
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


def validate_failed_clean1_attempt_evidence(
    stage_root: str | Path,
    *,
    raw_root: str | Path,
    code_root: str | Path,
    provider_attempt: str | Path,
    expected_code_commit: str,
) -> dict[str, Any]:
    """Rehash one exact failed stage and prove it contains no result evidence."""

    stage = Path(stage_root).resolve(strict=True)
    raw = Path(raw_root).resolve(strict=True)
    code = Path(code_root).resolve(strict=True)
    attempt = Path(provider_attempt).resolve(strict=True)
    if not stage.is_dir() or not attempt.is_dir():
        raise EvidenceContractError("Failed CLEAN1 stage/provider attempt is missing")
    specification = FAILED_CLEAN1_ATTEMPT_SPECS.get(expected_code_commit)
    if specification is None:
        raise EvidenceContractError("Failed CLEAN1 code commit is not retry-authorized")

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
