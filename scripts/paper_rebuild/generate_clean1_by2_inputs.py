#!/usr/bin/env python3
"""Create CLEAN1 pre-run evidence, fresh providers, window, and evaluator gate."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import signal
import shutil
import subprocess
import sys
import uuid
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.evidence import (
    BY2_TRACE_RELATIVE_PATH,
    BY2_RAW_RELATIVE_PATHS,
    assert_export_text_is_redacted,
    compare_pre_post_raw_audits,
    parse_strace_openat_paths,
    validate_failed_clean1_attempt_evidence,
    verify_by2_raw_22,
    write_raw_audit,
    write_read_ledger,
    write_source_role_manifests,
)
from legsa_gins.paper_rebuild.formal_provider import (
    FORMAL_PROVIDER_ACTUAL_SOURCE_PATHS,
    MAINTAINED_SHARED_SOURCE_FILES,
    load_formal_provider_bundle,
)
from legsa_gins.paper_rebuild.formal_runner import build_effective_method_metadata
from legsa_gins.paper_rebuild.manifest import git_code_state, sha256_file, write_json_atomic
from legsa_gins.paper_rebuild.methods import load_method_catalog, write_method_freeze
from legsa_gins.paper_rebuild.paths import (
    assert_clean1_path_contract,
    guard_path,
    is_within,
    legacy_reason,
    load_clean_paths,
)
from legsa_gins.paper_rebuild.protocol import (
    REQUIRED_WINDOW_STREAMS,
    build_common_covariance_contract,
    compute_full_common_window,
    coverage_from_timestamps,
    freeze_window_contract,
    load_clean1_protocol,
)
from legsa_gins.paper_rebuild.providers import infer_source_day_base_time
from legsa_gins.paper_rebuild.subprocess_guard import run_process_group


STAGE_DIR_NAME = "06_CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION"
FAILED_ATTEMPT_DIR_NAME = f"{STAGE_DIR_NAME}_FAILED_ATTEMPTS"
FAILED_ATTEMPT_CODE_FREEZE_COMMIT = "409508def7f20521db290d9bfb7e1506a1f72ef9"
EVIDENCE_SUBDIRS = (
    "00_AUTHORIZATION",
    "01_GIT_FREEZE",
    "02_PROTOCOL_FREEZE",
    "03_DATA_HASH_AND_ROLES",
    "04_PROVIDER_AUDIT",
    "05_BUILD_AND_TESTS",
    "06_RUN_MANIFESTS",
    "07_EVALUATION",
    "08_EVIDENCE_AUDIT",
    "09_REPORT",
    "10_EXPORT",
)


def _git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True, timeout=60
    ).stdout.strip()


def _git_ok(args: list[str]) -> bool:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, check=False, capture_output=True, text=True, timeout=60
    ).returncode == 0


def _git_commit_is_ancestor(code_root: Path, ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=code_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    ).returncode == 0


def _create_stage_root(clean_root: Path) -> tuple[Path, Path]:
    final = guard_path(clean_root / STAGE_DIR_NAME, role="CLEAN1 stage root", allowed_root=clean_root)
    if final.exists():
        raise RuntimeError("CLEAN1 stage evidence root already exists")
    stage = guard_path(
        clean_root / f".{STAGE_DIR_NAME}.attempt-{uuid.uuid4().hex}",
        role="CLEAN1 stage attempt root",
        allowed_root=clean_root,
    )
    stage.mkdir(parents=True, exist_ok=False)
    for name in EVIDENCE_SUBDIRS:
        (stage / name).mkdir()
    return stage, final


def _preserve_exact_raw_doppler_blocked_stage_for_retry(
    paths: Any,
    *,
    new_code_commit: str,
) -> dict[str, Any]:
    """Archive one exact no-run technical blocker without deleting or overwriting it."""

    stage_final = guard_path(
        paths.clean_root / STAGE_DIR_NAME,
        role="blocked CLEAN1 stage evidence",
        allowed_root=paths.clean_root,
    )
    archive_parent = guard_path(
        paths.clean_root / FAILED_ATTEMPT_DIR_NAME,
        role="CLEAN1 failed-attempt archive root",
        allowed_root=paths.clean_root,
    )
    archive = guard_path(
        archive_parent / FAILED_ATTEMPT_CODE_FREEZE_COMMIT,
        role="CLEAN1 exact failed-attempt archive",
        allowed_root=archive_parent,
    )
    if stage_final.exists() == archive.exists():
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    failed_stage = stage_final if stage_final.exists() else archive
    archive_recovered_after_interruption = archive.exists()
    if paths.provider_root.exists() or paths.runtime_root.exists():
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")

    def load_object(relative: str) -> dict[str, Any]:
        value = json.loads((failed_stage / relative).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
        return value

    decision = load_object("08_EVIDENCE_AUDIT/PRE_RUN_GATE_DECISION.json")
    run_gate = load_object("06_RUN_MANIFESTS/FOUR_METHOD_RUN_BLOCKED.json")
    raw_summary = load_object("03_DATA_HASH_AND_ROLES/BY2_RAW_22_SUMMARY.json")
    report = load_object("09_REPORT/CLEAN1_FULL_REPORT.json")
    terminal = "BLOCKED_CLEAN1_RAW_DOPPLER_BACKEND_LINEAGE_NOT_PROVEN"
    old_commit = decision.get("code_freeze_commit")
    if (
        not isinstance(old_commit, str)
        or len(old_commit) != 40
        or any(character not in "0123456789abcdef" for character in old_commit)
        or old_commit != FAILED_ATTEMPT_CODE_FREEZE_COMMIT
        or old_commit == new_code_commit
        or decision.get("terminal_status") != terminal
        or decision.get("formal_run_count") != 0
        or decision.get("provider_promoted") is not False
        or decision.get("raw_pre_verified") != 22
        or decision.get("raw_post_verified") != 22
        or decision.get("raw_mutation_count") != 0
        or report.get("terminal_decision") != terminal
        or report.get("formal_run_count") != 0
        or report.get("metrics_generated") is not False
        or report.get("paper_figure_count") != 0
        or raw_summary.get("passed") is not True
        or raw_summary.get("pre_verified") != 22
        or raw_summary.get("post_verified") != 22
        or raw_summary.get("raw_mutation") != 0
    ):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    expected_run_gate = {
        "schema_version": "paper-rebuild-clean1-four-run-gate-v1",
        "formal_run_count": 0,
        "method_count_required": 4,
        "metric_driven_rerun": False,
        "terminal_status": terminal,
        "paper_performance_claim": False,
    }
    if run_gate != expected_run_gate:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    if not _git_commit_is_ancestor(paths.code_root, old_commit, new_code_commit):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    provider_attempts = [
        child
        for child in paths.provider_root.parent.iterdir()
        if child.is_dir()
        and child.name.startswith(".CLEAN1_BY2_CLEAN_NORMAL_V1.attempt-")
    ]
    if len(provider_attempts) != 1:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    provider_attempt = guard_path(
        provider_attempts[0],
        role="preserved failed CLEAN1 provider attempt",
        allowed_root=paths.provider_root.parent,
        must_exist=True,
    )
    try:
        validated = validate_failed_clean1_attempt_evidence(
            failed_stage,
            raw_root=paths.raw_root,
            code_root=paths.code_root,
            provider_attempt=provider_attempt,
            expected_code_commit=old_commit,
        )
    except Exception as exc:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION") from exc
    evidence_digest = str(validated["evidence_manifest_sha256"])
    if failed_stage == stage_final:
        archive_parent.mkdir(parents=False, exist_ok=True)
        stage_final.rename(archive)
    return {
        "schema_version": "paper-rebuild-clean1-prior-technical-attempt-v1",
        "archived_stage_alias": f"<CLEAN_ROOT>/{FAILED_ATTEMPT_DIR_NAME}/{old_commit}",
        "code_freeze_commit": old_commit,
        "terminal_status": terminal,
        "formal_run_count": 0,
        "provider_promoted": False,
        "provider_attempt_preserved": bool(decision.get("provider_attempt_generated")),
        "provider_attempt_alias": (
            f"<CLEAN_ROOT>/04_PROVIDER_FREEZE/{provider_attempt.name}"
        ),
        "raw_pre_verified": 22,
        "raw_post_verified": 22,
        "raw_mutation_count": 0,
        "evidence_manifest_sha256": evidence_digest,
        "evidence_file_count": validated["evidence_file_count"],
        "export_member_count": validated["export_member_count"],
        "preserved_without_delete": True,
        "archive_recovered_after_interruption": archive_recovered_after_interruption,
        "superseded_reason": "case_insensitive_dual_yaw_artifact_self_copy_code_bug",
        "replacement_code_commit": new_code_commit,
    }


def _recover_pending_promotion(paths: Any) -> dict[str, Any] | None:
    """Complete a stage-first/provider-second promotion without deleting any attempt."""

    stage_final = paths.clean_root / STAGE_DIR_NAME
    if not stage_final.exists():
        candidates = []
        prefix = f".{STAGE_DIR_NAME}.attempt-"
        for child in paths.clean_root.iterdir():
            if not child.is_dir() or not child.name.startswith(prefix):
                continue
            journal_candidate = child / "08_EVIDENCE_AUDIT/PROMOTION_JOURNAL.json"
            if not journal_candidate.is_file():
                continue
            try:
                candidate_payload = json.loads(
                    journal_candidate.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
            if (
                isinstance(candidate_payload, dict)
                and candidate_payload.get("state")
                == "STAGE_ATTEMPT_READY_PROVIDER_PENDING"
            ):
                candidates.append(child)
        if not candidates:
            return None
        if len(candidates) != 1:
            raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
        candidates[0].rename(stage_final)
    journal_path = stage_final / "08_EVIDENCE_AUDIT/PROMOTION_JOURNAL.json"
    if not journal_path.is_file():
        raise RuntimeError("BLOCKED_CLEAN1_GIT_OR_CODE_FREEZE_FAILED")
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    if not isinstance(journal, dict):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    if journal.get("state") not in {
        "STAGE_ATTEMPT_READY_PROVIDER_PENDING",
        "STAGE_PROMOTED_PROVIDER_PENDING",
        "COMPLETE",
    }:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    attempt_name = journal.get("provider_attempt_root_name")
    if (
        not isinstance(attempt_name, str)
        or "/" in attempt_name
        or "\\" in attempt_name
        or not attempt_name.startswith(".CLEAN1_BY2_CLEAN_NORMAL_V1.attempt-")
    ):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    if journal.get("state") == "STAGE_ATTEMPT_READY_PROVIDER_PENDING":
        if journal.get("stage_final_promoted") is not False:
            raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
        journal["state"] = "STAGE_PROMOTED_PROVIDER_PENDING"
        journal["stage_final_promoted"] = True
        write_json_atomic(journal_path, journal)
    if paths.provider_root.exists():
        bundle = load_formal_provider_bundle(paths)
    else:
        attempt = guard_path(
            paths.provider_root.parent / attempt_name,
            role="recoverable CLEAN1 provider attempt",
            allowed_root=paths.clean_root,
            must_exist=True,
        )
        attempt_paths = replace(paths, provider_root=attempt)
        bundle = load_formal_provider_bundle(attempt_paths)
        attempt.rename(paths.provider_root)
        bundle = load_formal_provider_bundle(paths)
    if bundle.provider_bundle_hash != journal.get("provider_bundle_hash"):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    decision_path = stage_final / "08_EVIDENCE_AUDIT/PRE_RUN_GATE_DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    if (
        not isinstance(decision, dict)
        or decision.get("provider_bundle_hash") != bundle.provider_bundle_hash
        or decision.get("formal_runs_authorized_by_all_gates") is not False
    ):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    complete_payload = {
        "state": "COMPLETE",
        "provider_bundle_hash": bundle.provider_bundle_hash,
        "provider_final_promoted": True,
        "stage_final_promoted": True,
    }
    complete_path = stage_final / "08_EVIDENCE_AUDIT/PROMOTION_COMPLETE.json"
    if journal.get("state") == "COMPLETE":
        if (
            journal.get("provider_final_promoted") is not True
            or journal.get("stage_final_promoted") is not True
        ):
            raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
        if complete_path.is_file():
            existing = json.loads(complete_path.read_text(encoding="utf-8"))
            if existing != complete_payload:
                raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
            raise RuntimeError("CLEAN1 stage evidence root already exists")
        write_json_atomic(complete_path, complete_payload)
    else:
        journal["state"] = "COMPLETE"
        journal["provider_final_promoted"] = True
        journal["stage_final_promoted"] = True
        write_json_atomic(journal_path, journal)
        write_json_atomic(complete_path, complete_payload)
    decision["promotion_recovered_without_delete"] = True
    write_json_atomic(decision_path, decision)
    return decision


def _provider_strace_crosscheck(
    strace_path: Path,
    destination: Path,
    *,
    expected_relative_paths: list[str],
    raw_root: Path,
    clean_root: Path,
    provider_attempt_root: Path,
    raw_hash_lock: Path,
) -> dict[str, Any]:
    opened = parse_strace_openat_paths(strace_path, cwd=REPO_ROOT)
    expected_paths = {
        relative: (raw_root / relative).resolve(strict=True)
        for relative in expected_relative_paths
    }
    raw_opened = [path for path in opened if is_within(path, raw_root)]
    observed_counts = {
        relative: sum(path == expected for path in raw_opened)
        for relative, expected in expected_paths.items()
    }
    missing = sorted(relative for relative, count in observed_counts.items() if count == 0)
    expected_set = set(expected_paths.values())
    unexpected_raw = sorted(
        {
            path.relative_to(raw_root).as_posix()
            for path in raw_opened
            if path not in expected_set
        }
    )
    unexpected_clean = sorted(
        {
            path.relative_to(clean_root).as_posix()
            for path in opened
            if is_within(path, clean_root)
            and not is_within(path, provider_attempt_root)
            and path != raw_hash_lock.resolve(strict=True)
        }
    )
    legacy_read_count = sum(legacy_reason(path) is not None for path in opened)
    trace_opened = (raw_root / BY2_TRACE_RELATIVE_PATH).resolve(strict=True) in raw_opened
    report = {
        "schema_version": "paper-rebuild-provider-file-open-crosscheck-v1",
        "strace_sha256": sha256_file(strace_path),
        "strace_available": True,
        "provider_process_isolated": True,
        "expected_raw_relative_paths": expected_relative_paths,
        "observed_expected_raw_open_counts": observed_counts,
        "missing_expected_raw_opens": missing,
        "unexpected_raw_root_relative_paths": unexpected_raw,
        "unexpected_clean_root_relative_paths": unexpected_clean,
        "trace_opened_by_provider_process": trace_opened,
        "legacy_path_read_count": legacy_read_count,
        "opened_path_count": len(opened),
        "passed": not missing and not unexpected_raw and not unexpected_clean and not trace_opened and legacy_read_count == 0,
    }
    write_json_atomic(destination, report)
    if not report["passed"]:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    return report


def _evaluator_strace_crosscheck(
    strace_path: Path,
    destination: Path,
    *,
    paths: Any,
    stage_attempt: Path,
) -> dict[str, Any]:
    opened = parse_strace_openat_paths(strace_path, cwd=REPO_ROOT)
    trace_path = (paths.raw_root / BY2_TRACE_RELATIVE_PATH).resolve(strict=True)
    raw_opened = [path for path in opened if is_within(path, paths.raw_root)]
    trace_open_count = sum(path == trace_path for path in raw_opened)
    unexpected_raw = sorted(
        {
            path.relative_to(paths.raw_root).as_posix()
            for path in raw_opened
            if path != trace_path
        }
    )
    provider_runtime_reads = sorted(
        {
            "provider" if is_within(path, paths.provider_root) else "runtime"
            for path in opened
            if is_within(path, paths.provider_root) or is_within(path, paths.runtime_root)
        }
    )
    unexpected_clean = sorted(
        {
            path.relative_to(paths.clean_root).as_posix()
            for path in opened
            if is_within(path, paths.clean_root)
            and not is_within(path, stage_attempt)
            and path != paths.raw_hash_lock.resolve(strict=True)
        }
    )
    report = {
        "schema_version": "paper-rebuild-evaluator-freeze-file-open-crosscheck-v1",
        "strace_sha256": sha256_file(strace_path),
        "evaluator_process_isolated": True,
        "evaluation_only_trace_open_count": trace_open_count,
        "unexpected_raw_root_relative_paths": unexpected_raw,
        "provider_or_runtime_root_reads": provider_runtime_reads,
        "unexpected_clean_root_relative_paths": unexpected_clean,
        "opened_path_count": len(opened),
        "passed": trace_open_count > 0 and not unexpected_raw and not provider_runtime_reads and not unexpected_clean,
    }
    write_json_atomic(destination, report)
    if not report["passed"]:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    return report


def _materialize_provider_attempt(
    paths: Any,
    protocol_path: Path,
    stage: Path,
    *,
    rtklib_source_root: str | None,
    materialize_pinned_rtklib: bool,
) -> tuple[Any, Any]:
    if paths.provider_root.exists():
        raise RuntimeError("Fresh CLEAN1 provider root already exists")
    paths.provider_root.parent.mkdir(parents=True, exist_ok=True)
    attempt = guard_path(
        paths.provider_root.parent / f".{paths.provider_root.name}.attempt-{uuid.uuid4().hex}",
        role="CLEAN1 provider attempt root",
        allowed_root=paths.clean_root,
    )
    strace_path = paths.provider_root.parent / f".{paths.provider_root.name}.strace-{uuid.uuid4().hex}.log"
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts/paper_rebuild/materialize_clean1_by2_provider.py"),
        "--config",
        str(paths.config_path),
        "--provider-attempt-root",
        str(attempt),
        "--protocol",
        str(protocol_path),
    ]
    if rtklib_source_root:
        command.extend(["--rtklib-source-root", rtklib_source_root])
    if materialize_pinned_rtklib:
        command.append("--materialize-pinned-rtklib")
    strace = shutil.which("strace")
    traced_command = (
        [strace, "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat", "-o", str(strace_path), *command]
        if strace
        else command
    )
    try:
        process = subprocess.Popen(
            traced_command,
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=1800)
            completed = subprocess.CompletedProcess(
                traced_command, process.returncode, stdout, stderr
            )
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
            completed = subprocess.CompletedProcess(
                traced_command, 124, stdout, stderr + "\nprovider attempt timeout"
            )
    except OSError as exc:
        completed = subprocess.CompletedProcess(
            traced_command, 127, "", f"provider attempt launch failure: {exc}"
        )
    if completed.returncode != 0:
        blocked_payload = {
            "terminal_status": "BLOCKED_CLEAN1_RAW_DOPPLER_BACKEND_LINEAGE_NOT_PROVEN",
            "returncode": completed.returncode,
            "provider_final_root_created": paths.provider_root.exists(),
            "failed_attempt_preserved": attempt.exists(),
            "strace_available": bool(strace and strace_path.is_file()),
            "strace_sha256": sha256_file(strace_path) if strace and strace_path.is_file() else "NOT_AVAILABLE",
        }
        (stage / "04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_STDOUT.txt").write_text(
            completed.stdout, encoding="utf-8"
        )
        (stage / "04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_STDERR.txt").write_text(
            completed.stderr, encoding="utf-8"
        )
        if strace and strace_path.is_file():
            strace_path.rename(
                stage / "04_PROVIDER_AUDIT/PROVIDER_FAILED_FILE_OPEN_TRACE.raw"
            )
        write_json_atomic(
            stage / "04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_BLOCKED.json",
            blocked_payload,
        )
        raise RuntimeError("BLOCKED_CLEAN1_RAW_DOPPLER_BACKEND_LINEAGE_NOT_PROVEN")
    attempt_paths = replace(paths, provider_root=attempt)
    try:
        bundle = load_formal_provider_bundle(attempt_paths)
    except Exception as exc:
        if strace and strace_path.is_file():
            strace_path.rename(
                stage / "04_PROVIDER_AUDIT/PROVIDER_FAILED_FILE_OPEN_TRACE.raw"
            )
        write_json_atomic(
            stage / "04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_BLOCKED.json",
            {
                "terminal_status": "BLOCKED_CLEAN1_RAW_DOPPLER_BACKEND_LINEAGE_NOT_PROVEN",
                "provider_final_root_created": paths.provider_root.exists(),
                "failed_attempt_preserved": attempt.exists(),
                "provider_bundle_validation_passed": False,
                "error_class": type(exc).__name__,
            },
        )
        raise RuntimeError("BLOCKED_CLEAN1_RAW_DOPPLER_BACKEND_LINEAGE_NOT_PROVEN")
    if strace:
        expected = [entry["relative_path"] for entry in bundle.actual_source_read_set]
        try:
            _provider_strace_crosscheck(
                strace_path,
                stage / "04_PROVIDER_AUDIT/PROVIDER_FILE_OPEN_CROSSCHECK.json",
                expected_relative_paths=expected,
                raw_root=paths.raw_root,
                clean_root=paths.clean_root,
                provider_attempt_root=attempt,
                raw_hash_lock=paths.raw_hash_lock,
            )
        except Exception:
            if strace_path.is_file():
                strace_path.rename(
                    stage / "04_PROVIDER_AUDIT/PROVIDER_FAILED_FILE_OPEN_TRACE.raw"
                )
            write_json_atomic(
                stage / "04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_BLOCKED.json",
                {
                    "terminal_status": "FAIL_CLEAN1_EVIDENCE_CONTAMINATION",
                    "provider_final_root_created": paths.provider_root.exists(),
                    "failed_attempt_preserved": attempt.exists(),
                    "file_open_crosscheck_passed": False,
                },
            )
            raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
        audit_dir = attempt / "audit"
        audit_dir.mkdir(exist_ok=False)
        strace_path.rename(audit_dir / "PROVIDER_FILE_OPEN_TRACE.raw")
    else:
        write_json_atomic(
            stage / "04_PROVIDER_AUDIT/PROVIDER_FILE_OPEN_CROSSCHECK.json",
            {
                "schema_version": "paper-rebuild-provider-file-open-crosscheck-v1",
                "strace_available": False,
                "fallback": "explicit_input_registry_static_dependency_audit",
                "trace_opened_by_provider_process": False,
                "passed": True,
            },
        )
    return attempt_paths, bundle


def _write_git_and_authorization(stage: Path, code_commit: str) -> None:
    auth = stage / "00_AUTHORIZATION" / "AUTHORIZATION.md"
    auth.write_text(
        "# CLEAN1 Human Authorization\n\n"
        "- stage: `CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION`\n"
        "- case: `CLEAN1_BY2_CLEAN_NORMAL`\n"
        "- protocol: `CLEAN1_BY2_CLEAN_NORMAL_V1`\n"
        "- base commit: `4e6b3f3fa9f50ed91b6c4e250f3d1f75d6725cc6`\n"
        "- methods: exactly four frozen methods in tracked order\n"
        "- no merge, tag, deletion, figures, classic-18, matrix, DA03, DA05, or next stage\n",
        encoding="utf-8",
    )
    git_state = {
        "schema_version": "paper-rebuild-clean1-git-state-v1",
        "repository_alias": "<CODE_ROOT>",
        "origin_url": _git(["remote", "get-url", "origin"]),
        "origin_main_sha": _git(["rev-parse", "origin/main"]),
        "pr58_merge_commit": "4e6b3f3fa9f50ed91b6c4e250f3d1f75d6725cc6",
        "pr58_merged": True,
        "base_commit": "4e6b3f3fa9f50ed91b6c4e250f3d1f75d6725cc6",
        "code_freeze_commit": code_commit,
        "branch": _git(["branch", "--show-current"]),
        "clean0_smoke_is_base_ancestor": _git_ok(
            ["merge-base", "--is-ancestor", "85984627439cdc861243eedb094f9be0c7dc1a76", "4e6b3f3fa9f50ed91b6c4e250f3d1f75d6725cc6"]
        ),
        "base_is_origin_main_ancestor": _git_ok(
            ["merge-base", "--is-ancestor", "4e6b3f3fa9f50ed91b6c4e250f3d1f75d6725cc6", "origin/main"]
        ),
        "origin_main_commits_after_base": int(
            _git(["rev-list", "--count", "4e6b3f3fa9f50ed91b6c4e250f3d1f75d6725cc6..origin/main"])
        ),
        "worktree_clean": True,
    }
    write_json_atomic(stage / "01_GIT_FREEZE" / "GIT_STATE.json", git_state)
    (stage / "01_GIT_FREEZE" / "CODE_FREEZE_COMMIT.txt").write_text(code_commit + "\n", encoding="utf-8")
    tracked = _git(
        [
            "ls-files",
            "docs/paper_rebuild",
            "configs/paper_rebuild",
            "scripts/paper_rebuild",
            "tests/paper_rebuild",
            "src/legsa_gins/paper_rebuild",
            "cpp/legsa_v23_port_core",
            *MAINTAINED_SHARED_SOURCE_FILES,
        ]
    ).splitlines()
    rows = []
    for relative in tracked:
        source = REPO_ROOT / relative
        if source.is_file():
            rows.append({"relative_path": relative, "sha256": sha256_file(source), "code_commit": code_commit})
    with (stage / "01_GIT_FREEZE" / "TRACKED_FILE_HASH_MANIFEST.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["relative_path", "sha256", "code_commit"])
        writer.writeheader()
        writer.writerows(rows)


def _write_post_raw_evidence(
    stage: Path,
    paths: Any,
    protocol: Any,
    pre: Any,
    actual_source_reads: list[dict[str, Any]],
    *,
    allow_empty_actual_for_blocked_attempt: bool = False,
    failed_attempt_read_relpaths: set[str] | None = None,
) -> tuple[Any, dict[str, Any]]:
    post = verify_by2_raw_22(
        paths.raw_root,
        paths.raw_hash_lock,
        expected_lock_sha256=protocol.payload["raw_hash_lock_expected_sha256"],
        expected_full_rows=protocol.payload["expected_full_lock_rows"],
        expected_by2_rows=protocol.payload["expected_by2_lock_rows"],
        audit_phase="post_generation",
        return_failed_file_audit=True,
    )
    data_dir = stage / "03_DATA_HASH_AND_ROLES"
    write_raw_audit(data_dir / "BY2_RAW_22_POST_HASH_AUDIT.csv", post)
    mutation = compare_pre_post_raw_audits(pre, post)
    write_json_atomic(data_dir / "RAW_MUTATION_AUDIT.json", mutation)
    write_source_role_manifests(
        data_dir,
        pre,
        actual_source_reads,
        allow_empty_actual_for_blocked_attempt=allow_empty_actual_for_blocked_attempt,
        failed_attempt_read_relpaths=failed_attempt_read_relpaths,
    )
    summary = {
        "schema_version": "paper-rebuild-by2-raw-22-pre-post-summary-v1",
        "expected": 22,
        "full_lock_rows": pre.summary["full_lock_rows"],
        "by2_lock_rows": pre.summary["by2_lock_rows"],
        "pre_verified": len(pre.verified_hashes),
        "post_verified": len(post.verified_hashes),
        "mismatch": pre.summary["mismatch"] + post.summary["mismatch"],
        "missing": pre.summary["missing"] + post.summary["missing"],
        "symlink_escape": pre.summary["symlink_escape"] + post.summary["symlink_escape"],
        "raw_mutation": mutation["raw_mutation"],
        "passed": mutation["passed"],
    }
    write_json_atomic(data_dir / "BY2_RAW_22_SUMMARY.json", summary)
    return post, mutation


def _finalize_stable_blocked_stage(
    stage: Path,
    stage_final: Path,
    *,
    terminal_status: str,
    code_commit: str,
    pre_verified: int,
    post_verified: int,
    raw_mutation_count: int,
    provider_attempt_generated: bool,
    raw_doppler_backend_lineage_proven: bool,
    blocked_component: str,
    claim_boundary: str,
    narrative: str,
) -> dict[str, Any]:
    """Promote a complete, redacted, no-run failure record without a provider."""

    if stage_final.exists():
        raise RuntimeError("CLEAN1 stage evidence root already exists")
    decision = {
        "schema_version": "paper-rebuild-clean1-pre-run-decision-v1",
        "code_freeze_commit": code_commit,
        "raw_pre_verified": pre_verified,
        "raw_post_verified": post_verified,
        "raw_mutation_count": raw_mutation_count,
        "raw_doppler_backend_lineage_proven": raw_doppler_backend_lineage_proven,
        "fresh_provider_generated": False,
        "provider_attempt_generated": provider_attempt_generated,
        "provider_promoted": False,
        "formal_runs_authorized_by_all_gates": False,
        "formal_run_count": 0,
        "terminal_status": terminal_status,
        "blocked_component": blocked_component,
        "paper_performance_claim": False,
    }
    write_json_atomic(stage / "08_EVIDENCE_AUDIT/PRE_RUN_GATE_DECISION.json", decision)
    write_json_atomic(
        stage / "06_RUN_MANIFESTS/FOUR_METHOD_RUN_BLOCKED.json",
        {
            "schema_version": "paper-rebuild-clean1-four-run-gate-v1",
            "formal_run_count": 0,
            "method_count_required": 4,
            "metric_driven_rerun": False,
            "terminal_status": terminal_status,
            "paper_performance_claim": False,
        },
    )
    report = {
        "schema_version": "paper-rebuild-clean1-readiness-report-v1",
        "terminal_decision": terminal_status,
        "blocked_component": blocked_component,
        "code_freeze_commit": code_commit,
        "raw_pre_verified": pre_verified,
        "raw_post_verified": post_verified,
        "raw_mutation_count": raw_mutation_count,
        "provider_attempt_generated": provider_attempt_generated,
        "provider_generated": False,
        "provider_promoted": False,
        "raw_doppler_backend_lineage_proven": raw_doppler_backend_lineage_proven,
        "formal_run_count": 0,
        "metrics_generated": False,
        "paper_figure_count": 0,
        "paper_performance_claim": False,
        "claim_boundary": claim_boundary,
    }
    report_dir = stage / "09_REPORT"
    write_json_atomic(report_dir / "CLEAN1_FULL_REPORT.json", report)
    (report_dir / "CLEAN1_FULL_REPORT.md").write_text(
        "# CLEAN1 blocked readiness report\n\n"
        f"`{terminal_status}`\n\n"
        f"{narrative}\n\n"
        "No formal method ran, and no metrics or figures were generated.\n",
        encoding="utf-8",
    )
    candidate_relpaths = (
        "00_AUTHORIZATION/AUTHORIZATION.md",
        "01_GIT_FREEZE/GIT_STATE.json",
        "01_GIT_FREEZE/CODE_FREEZE_COMMIT.txt",
        "03_DATA_HASH_AND_ROLES/BY2_RAW_22_SUMMARY.json",
        "03_DATA_HASH_AND_ROLES/RAW_MUTATION_AUDIT.json",
        "04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_BLOCKED.json",
        "04_PROVIDER_AUDIT/PROVIDER_FILE_OPEN_CROSSCHECK.json",
        "02_PROTOCOL_FREEZE/EVALUATOR_FREEZE_PROCESS_STATUS.json",
        "02_PROTOCOL_FREEZE/EVALUATOR_FREEZE_FILE_OPEN_CROSSCHECK.json",
        "06_RUN_MANIFESTS/FOUR_METHOD_RUN_BLOCKED.json",
        "08_EVIDENCE_AUDIT/PRE_RUN_GATE_DECISION.json",
        "09_REPORT/CLEAN1_FULL_REPORT.md",
        "09_REPORT/CLEAN1_FULL_REPORT.json",
    )
    export_sources = [stage / relative for relative in candidate_relpaths if (stage / relative).is_file()]
    claim = REPO_ROOT / "docs/paper_rebuild/CLAIM_BOUNDARY.md"
    for source in [*export_sources, claim]:
        assert_export_text_is_redacted(source.read_text(encoding="utf-8"))
    export_dir = stage / "10_EXPORT"
    export_manifest = export_dir / "EXPORT_SHA256_MANIFEST.csv"
    export_rows = [
        {
            "archive_path": source.relative_to(stage).as_posix(),
            "sha256": sha256_file(source),
            "size_bytes": source.stat().st_size,
        }
        for source in export_sources
    ]
    export_rows.append(
        {
            "archive_path": "CLAIM_BOUNDARY.md",
            "sha256": sha256_file(claim),
            "size_bytes": claim.stat().st_size,
        }
    )
    with export_manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(export_rows[0]))
        writer.writeheader()
        writer.writerows(export_rows)
    archive = export_dir / "CLEAN1_CONTEXT_FOR_GPT.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for source in export_sources:
            handle.write(source, source.relative_to(stage).as_posix())
        handle.write(claim, "CLAIM_BOUNDARY.md")
        handle.write(export_manifest, "EXPORT_SHA256_MANIFEST.csv")
    evidence_rows = []
    for source in sorted(path for path in stage.rglob("*") if path.is_file()):
        relative = source.relative_to(stage).as_posix()
        if relative.startswith("08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST"):
            continue
        evidence_rows.append(
            {
                "relative_path": relative,
                "sha256": sha256_file(source),
                "size_bytes": source.stat().st_size,
                "tracked": False,
            }
        )
    evidence_manifest = stage / "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.csv"
    with evidence_manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(evidence_rows[0]))
        writer.writeheader()
        writer.writerows(evidence_rows)
    (stage / "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.sha256").write_text(
        f"{sha256_file(evidence_manifest)}  EVIDENCE_MANIFEST.csv\n", encoding="utf-8"
    )
    stage.rename(stage_final)
    return decision


def _finalize_raw_doppler_blocked_stage(
    stage: Path,
    stage_final: Path,
    paths: Any,
    protocol: Any,
    pre: Any,
    code_commit: str,
    *,
    forced_terminal_status: str | None = None,
    provider_attempt_generated: bool = False,
) -> dict[str, Any]:
    failed_trace = stage / "04_PROVIDER_AUDIT/PROVIDER_FAILED_FILE_OPEN_TRACE.raw"
    failed_read_relpaths: set[str] | None = None
    failed_trace_unexpected: list[str] = []
    if failed_trace.is_file():
        try:
            failed_opened = parse_strace_openat_paths(failed_trace, cwd=REPO_ROOT)
            failed_read_relpaths = {
                path.relative_to(paths.raw_root).as_posix()
                for path in failed_opened
                if is_within(path, paths.raw_root)
            }
            failed_trace_unexpected = sorted(
                failed_read_relpaths - set(FORMAL_PROVIDER_ACTUAL_SOURCE_PATHS)
            )
        except Exception as exc:
            write_json_atomic(
                stage / "04_PROVIDER_AUDIT/PROVIDER_FAILED_FILE_OPEN_PARSE_BLOCKED.json",
                {"parse_status": "UNKNOWN", "error_class": type(exc).__name__},
            )
    post, mutation = _write_post_raw_evidence(
        stage,
        paths,
        protocol,
        pre,
        [],
        allow_empty_actual_for_blocked_attempt=True,
        failed_attempt_read_relpaths=failed_read_relpaths,
    )
    terminal_status = forced_terminal_status or (
        "FAIL_CLEAN1_EVIDENCE_CONTAMINATION"
        if failed_trace_unexpected
        else "BLOCKED_CLEAN1_RAW_DOPPLER_BACKEND_LINEAGE_NOT_PROVEN"
        if mutation["passed"]
        else "BLOCKED_CLEAN1_BY2_RAW_HASH_OR_ROLE_FAILED"
    )
    write_json_atomic(
        stage / "04_PROVIDER_AUDIT/PROVIDER_FAILED_ACTUAL_READ_AUDIT.json",
        {
            "strace_available": failed_trace.is_file(),
            "observed_partial_failed_attempt_raw_reads": sorted(failed_read_relpaths or []),
            "unexpected_raw_reads": failed_trace_unexpected,
            "promoted_provider_actual_read_set": [],
            "passed": not failed_trace_unexpected,
        },
    )
    blocked_attempt_path = stage / "04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_BLOCKED.json"
    if blocked_attempt_path.is_file():
        blocked_attempt = json.loads(blocked_attempt_path.read_text(encoding="utf-8"))
        if not isinstance(blocked_attempt, dict):
            raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
        provider_attempt_generated = provider_attempt_generated or bool(
            blocked_attempt.get("failed_attempt_preserved")
        )
    return _finalize_stable_blocked_stage(
        stage,
        stage_final,
        terminal_status=terminal_status,
        code_commit=code_commit,
        pre_verified=len(pre.verified_hashes),
        post_verified=len(post.verified_hashes),
        raw_mutation_count=mutation["raw_mutation"],
        provider_attempt_generated=provider_attempt_generated,
        raw_doppler_backend_lineage_proven=False,
        blocked_component="provider_generation_or_file_open_closure",
        claim_boundary=(
            "Provider/Raw Doppler readiness blocked before any formal method run or metric generation."
        ),
        narrative=(
            "Fresh provider or Raw Doppler lineage did not close. The 22-file BY2 raw set was "
            "rehash-audited after the failed attempt; no provider was promoted."
        ),
    )


def _numeric_rows(path: Path) -> list[list[float]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            rows.append([float(value) for value in line.split()])
    return rows


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _strict_times(values: list[float], role: str) -> list[float]:
    finite = [value for value in values if math.isfinite(value)]
    if len(finite) < 2 or any(b <= a for a, b in zip(finite, finite[1:])):
        raise RuntimeError(f"Invalid formal timestamps for {role}")
    return finite


def _freeze_window(paths: Any, bundle: Any, protocol: Any, destination: Path) -> dict[str, Any]:
    imu_rows = _numeric_rows(bundle.artifacts["imu_runtime_input"])
    gnss_rows = _numeric_rows(bundle.artifacts["gnss_runtime_input"])
    if any(len(row) != 18 for row in gnss_rows):
        raise RuntimeError("Formal GNSS input is not exactly 18 columns")
    dual_rows = _csv_rows(bundle.artifacts["dual_yaw_provider"])
    raw_rows = _csv_rows(bundle.artifacts["raw_doppler_provider"])
    attitude_rows = _csv_rows(bundle.artifacts["go2_attitude_prior"])
    velocity_rows = _csv_rows(bundle.artifacts["go2_horizontal_velocity_prior"])
    stream_times = {
        "propagation_imu": _strict_times([row[0] for row in imu_rows], "propagation_imu"),
        "gnss_position": _strict_times([row[0] for row in gnss_rows if int(row[15]) == 1], "gnss_position"),
        "receiver_velocity": _strict_times([row[0] for row in gnss_rows if int(row[16]) == 1], "receiver_velocity"),
        "dual_yaw": _strict_times([float(row["time"]) for row in dual_rows if row["source_status"] == "active"], "dual_yaw"),
        "raw_doppler": _strict_times([float(row["time"]) for row in raw_rows if row["valid"] == "1" and row["provider_status"] == "available"], "raw_doppler"),
        "go2_roll_pitch_prior": _strict_times([float(row["time"]) for row in attitude_rows if row["source_status"] == "active"], "go2_roll_pitch_prior"),
        "go2_horizontal_velocity_prior": _strict_times([float(row["time"]) for row in velocity_rows if row["source_status"] == "active"], "go2_horizontal_velocity_prior"),
    }
    role_to_artifact = {
        "propagation_imu": "imu_runtime_input",
        "gnss_position": "gnss_runtime_input",
        "receiver_velocity": "gnss_runtime_input",
        "dual_yaw": "dual_yaw_provider",
        "raw_doppler": "raw_doppler_provider",
        "go2_roll_pitch_prior": "go2_attitude_prior",
        "go2_horizontal_velocity_prior": "go2_horizontal_velocity_prior",
    }
    coverages = []
    for role in REQUIRED_WINDOW_STREAMS:
        artifact = role_to_artifact[role]
        coverages.append(
            coverage_from_timestamps(
                role,
                stream_times[role],
                source_alias="<PROVIDER_ROOT>",
                relative_path=bundle.provider_relpaths[artifact],
                source_sha256=bundle.provider_hashes[artifact],
            )
        )
    start = max(item.first_valid_timestamp for item in coverages)
    init_gnss = next(
        row for row in gnss_rows if row[0] >= start and int(row[15]) == int(row[16]) == 1
    )
    init_yaw = next(row for row in gnss_rows if row[0] >= start and int(row[17]) == 1)
    init_attitude = next(row for row in attitude_rows if float(row["time"]) >= start)
    common = protocol.payload["solver_common"]
    covariance_contract = build_common_covariance_contract(common)
    initialization = {
        "position_geodetic_deg_m": init_gnss[1:4],
        "velocity_ned_mps": init_gnss[7:10],
        "roll_pitch_deg": [math.degrees(float(init_attitude["roll_rad"])), math.degrees(float(init_attitude["pitch_rad"]))],
        "yaw_ned_deg": init_yaw[13] % 360.0,
        "bias_scale_state": [0.0] * 12,
        "covariance_diagonal": covariance_contract["covariance_diagonal_internal"],
        "covariance_contract": covariance_contract,
        "position_velocity_source_role": "gnss_source_at_common_start",
        "roll_pitch_source_role": "go2_body_attitude_at_common_start",
        "yaw_source_role": "fixed_physical_dual_yaw_at_common_start",
        "trace_used": False,
        "method_specific": False,
        "common_initialization_dual_yaw_used": True,
        "bias_scale_policy": "tracked_solver_common_zero_initial_bias_scale",
        "covariance_policy": "tracked_solver_common_shared_initial_covariance",
        "antenna_lever_source_status": common["antenna_lever_source_status"],
    }
    source_origin = infer_source_day_base_time(paths.by2_fix_root / "gnss1-status.csv")
    frozen = compute_full_common_window(
        coverages,
        source_time_origin_seconds=source_origin,
        common_initialization=initialization,
    )
    freeze_window_contract(protocol, frozen, destination)
    return json.loads(json.dumps({
        "t_start": frozen.t_start,
        "t_end": frozen.t_end,
        "duration_seconds": frozen.duration_seconds,
        "source_time_origin_seconds": frozen.source_time_origin_seconds,
        "common_initialization": frozen.common_initialization,
    }))


def _build_success_pre_run_decision(
    *,
    code_commit: str,
    raw_pre_verified: int,
    raw_post_verified: int,
    raw_mutation_count: int,
    raw_doppler_backend_lineage_proven: bool,
    raw_doppler_valid_epoch_count: int,
    provider_bundle_hash: str,
    window_summary: dict[str, Any],
    evaluator_ready: bool,
    evaluator_terminal_status: str,
) -> dict[str, Any]:
    """Build the producer side of the final audit's exact decision contract."""

    return {
        "schema_version": "paper-rebuild-clean1-pre-run-decision-v1",
        "code_freeze_commit": code_commit,
        "raw_pre_verified": raw_pre_verified,
        "raw_post_verified": raw_post_verified,
        "raw_mutation_count": raw_mutation_count,
        "raw_doppler_backend_lineage_proven": raw_doppler_backend_lineage_proven,
        "raw_doppler_valid_epoch_count": raw_doppler_valid_epoch_count,
        "provider_bundle_hash": provider_bundle_hash,
        "fresh_provider_generated": True,
        "window": window_summary,
        "evaluator_ready": evaluator_ready,
        "formal_runs_authorized_by_all_gates": evaluator_ready,
        "terminal_status": evaluator_terminal_status,
        "paper_performance_claim": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--protocol", default=str(REPO_ROOT / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml"))
    parser.add_argument("--evaluator", default=str(REPO_ROOT / "configs/paper_rebuild/evaluator_contract.yaml"))
    parser.add_argument("--methods", default=str(REPO_ROOT / "configs/paper_rebuild/methods.yaml"))
    parser.add_argument("--rtklib-source-root")
    parser.add_argument("--materialize-pinned-rtklib", action="store_true")
    parser.add_argument("--retry-after-exact-blocked-attempt", action="store_true")
    args = parser.parse_args(argv)

    paths = load_clean_paths(args.config)
    assert_clean1_path_contract(paths, REPO_ROOT)
    code_commit, dirty = git_code_state(paths.code_root)
    if (
        dirty
        or _git(["branch", "--show-current"]) != "stage/clean1-by2-clean-four-method"
        or not _git_ok(
            ["merge-base", "--is-ancestor", "4e6b3f3fa9f50ed91b6c4e250f3d1f75d6725cc6", code_commit]
        )
    ):
        raise RuntimeError("BLOCKED_CLEAN1_GIT_OR_CODE_FREEZE_FAILED")
    protocol = load_clean1_protocol(args.protocol)
    prior_attempt = None
    if args.retry_after_exact_blocked_attempt:
        prior_attempt = _preserve_exact_raw_doppler_blocked_stage_for_retry(
            paths, new_code_commit=code_commit
        )
    recovered = _recover_pending_promotion(paths)
    if recovered is not None:
        print(json.dumps(recovered, ensure_ascii=False, sort_keys=True))
        return 0
    stage, stage_final = _create_stage_root(paths.clean_root)
    _write_git_and_authorization(stage, code_commit)
    if prior_attempt is not None:
        write_json_atomic(
            stage / "00_AUTHORIZATION/PRIOR_TECHNICAL_ATTEMPT.json",
            prior_attempt,
        )
    shutil.copy2(protocol.path, stage / "02_PROTOCOL_FREEZE" / "SCOPE_LOCK.yaml")

    pre = verify_by2_raw_22(
        paths.raw_root,
        paths.raw_hash_lock,
        expected_lock_sha256=protocol.payload["raw_hash_lock_expected_sha256"],
        expected_full_rows=protocol.payload["expected_full_lock_rows"],
        expected_by2_rows=protocol.payload["expected_by2_lock_rows"],
        audit_phase="pre_generation",
    )
    write_raw_audit(stage / "03_DATA_HASH_AND_ROLES" / "BY2_RAW_22_PRE_HASH_AUDIT.csv", pre)
    try:
        attempt_paths, bundle = _materialize_provider_attempt(
            paths,
            protocol.path,
            stage,
            rtklib_source_root=args.rtklib_source_root,
            materialize_pinned_rtklib=args.materialize_pinned_rtklib,
        )
    except RuntimeError as exc:
        terminal = str(exc)
        if terminal not in {
            "BLOCKED_CLEAN1_RAW_DOPPLER_BACKEND_LINEAGE_NOT_PROVEN",
            "FAIL_CLEAN1_EVIDENCE_CONTAMINATION",
        }:
            raise
        decision = _finalize_raw_doppler_blocked_stage(
            stage,
            stage_final,
            paths,
            protocol,
            pre,
            code_commit,
            forced_terminal_status=(
                "FAIL_CLEAN1_EVIDENCE_CONTAMINATION"
                if terminal == "FAIL_CLEAN1_EVIDENCE_CONTAMINATION"
                else None
            ),
            provider_attempt_generated=(
                terminal == "FAIL_CLEAN1_EVIDENCE_CONTAMINATION"
            ),
        )
        print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
        return 2
    manifest = json.loads(
        (attempt_paths.provider_root / "CLEAN_INPUT_MANIFEST.json").read_text(encoding="utf-8")
    )
    post, mutation = _write_post_raw_evidence(
        stage, paths, protocol, pre, manifest["actual_source_read_set"]
    )
    if not mutation["passed"]:
        write_json_atomic(
            stage / "04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_BLOCKED.json",
            {
                "terminal_status": "BLOCKED_CLEAN1_BY2_RAW_HASH_OR_ROLE_FAILED",
                "provider_attempt_generated": True,
                "provider_final_root_created": paths.provider_root.exists(),
                "failed_attempt_preserved": attempt_paths.provider_root.exists(),
                "raw_mutation_count": mutation["raw_mutation"],
            },
        )
        decision = _finalize_stable_blocked_stage(
            stage,
            stage_final,
            terminal_status="BLOCKED_CLEAN1_BY2_RAW_HASH_OR_ROLE_FAILED",
            code_commit=code_commit,
            pre_verified=len(pre.verified_hashes),
            post_verified=len(post.verified_hashes),
            raw_mutation_count=mutation["raw_mutation"],
            provider_attempt_generated=True,
            raw_doppler_backend_lineage_proven=bool(
                bundle.raw_doppler_report["raw_doppler_backend_lineage_proven"]
            ),
            blocked_component="post_generation_raw_hash_and_mutation_gate",
            claim_boundary=(
                "Post-generation raw integrity failed before provider promotion, formal runs, or metrics."
            ),
            narrative=(
                "The post-generation exact 22-file audit did not match the pre-generation hash lock. "
                "The provider attempt was preserved but was not promoted."
            ),
        )
        print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
        return 2
    shutil.copy2(attempt_paths.provider_root / "CLEAN_INPUT_MANIFEST.json", stage / "04_PROVIDER_AUDIT")
    shutil.copy2(attempt_paths.provider_root / "RAW_DOPPLER_BACKEND_REPORT.json", stage / "04_PROVIDER_AUDIT")
    for name in ("DUAL_YAW_PHYSICAL_GATE.json", "DUAL_YAW_RUNTIME_CROSSCHECK.json"):
        shutil.copy2(attempt_paths.provider_root / name, stage / "04_PROVIDER_AUDIT" / name)
    shutil.copy2(
        bundle.artifacts["dual_yaw_provider"],
        stage / "04_PROVIDER_AUDIT/DUAL_YAW_PROVIDER.csv",
    )
    provider_rows = [
        {
            "provider_role": role,
            "relative_path": bundle.provider_relpaths[role],
            "sha256": digest,
            "solver_input": manifest["artifacts"][role]["solver_input"],
            "artifact_role": manifest["artifacts"][role]["artifact_role"],
        }
        for role, digest in bundle.provider_hashes.items()
    ]
    with (stage / "04_PROVIDER_AUDIT" / "PROVIDER_HASH_MANIFEST.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(provider_rows[0]))
        writer.writeheader()
        writer.writerows(provider_rows)
    ledger_rows = [
        {
            "read_order": index,
            "path_alias": "<RAW_ROOT>",
            "relative_path": entry["relative_path"],
            "role": entry["role"],
            "sha256": entry["actual_sha256"],
            "reader_component": entry["reader_component"],
        }
        for index, entry in enumerate(manifest["actual_source_read_set"], start=1)
    ]
    write_read_ledger(
        stage / "04_PROVIDER_AUDIT" / "PROVIDER_ACTUAL_READ_LEDGER.csv",
        ledger_rows,
        allowed_roles={row["role"] for row in ledger_rows},
    )

    try:
        window_summary = _freeze_window(
            paths, bundle, protocol, stage / "02_PROTOCOL_FREEZE"
        )
    except Exception as exc:
        terminal = (
            "FAIL_CLEAN1_EVIDENCE_CONTAMINATION"
            if str(exc) == "FAIL_CLEAN1_EVIDENCE_CONTAMINATION"
            else "BLOCKED_CLEAN1_WINDOW_OR_INITIALIZATION_CONTRACT_FAILED"
        )
        write_json_atomic(
            stage / "02_PROTOCOL_FREEZE/WINDOW_FREEZE_BLOCKED.json",
            {
                "terminal_status": terminal,
                "error_class": type(exc).__name__,
                "provider_attempt_preserved": attempt_paths.provider_root.exists(),
            },
        )
        decision = _finalize_stable_blocked_stage(
            stage,
            stage_final,
            terminal_status=terminal,
            code_commit=code_commit,
            pre_verified=len(pre.verified_hashes),
            post_verified=len(post.verified_hashes),
            raw_mutation_count=mutation["raw_mutation"],
            provider_attempt_generated=True,
            raw_doppler_backend_lineage_proven=True,
            blocked_component="window_or_common_initialization_freeze",
            claim_boundary="Window/initialization freeze failed before provider promotion or any formal run.",
            narrative=(
                "Fresh provider lineage and post-generation raw integrity closed, but the common "
                "window or initialization contract did not freeze. The provider attempt was not promoted."
            ),
        )
        print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
        return 2
    evaluator_command = [
            sys.executable,
            str(REPO_ROOT / "scripts/paper_rebuild/freeze_clean1_by2_evaluator.py"),
            "--config",
            str(paths.config_path),
            "--contract",
            str(Path(args.evaluator).resolve(strict=True)),
            "--protocol",
            str(protocol.path),
            "--output-dir",
            str(stage / "02_PROTOCOL_FREEZE"),
        ]
    evaluator_strace = stage / "02_PROTOCOL_FREEZE/EVALUATOR_FREEZE_FILE_OPEN_TRACE.raw"
    strace = shutil.which("strace")
    evaluator_traced_command = (
        [strace, "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat", "-o", str(evaluator_strace), *evaluator_command]
        if strace
        else evaluator_command
    )
    evaluator_process = run_process_group(
        evaluator_traced_command,
        cwd=REPO_ROOT,
        timeout_seconds=300,
        timeout_message="evaluator-freeze timeout; entire process group terminated",
        launch_failure_message="evaluator-freeze launch failure",
    )
    (stage / "02_PROTOCOL_FREEZE/EVALUATOR_FREEZE_STDOUT.txt").write_text(
        evaluator_process.stdout, encoding="utf-8"
    )
    (stage / "02_PROTOCOL_FREEZE/EVALUATOR_FREEZE_STDERR.txt").write_text(
        evaluator_process.stderr, encoding="utf-8"
    )
    write_json_atomic(
        stage / "02_PROTOCOL_FREEZE/EVALUATOR_FREEZE_PROCESS_STATUS.json",
        {
            "returncode": evaluator_process.returncode,
            "failure_class": {
                0: "",
                124: "timeout",
                127: "launch_failure",
            }.get(evaluator_process.returncode, "evaluator_freeze_nonzero_returncode"),
            "process_group_isolated": True,
            "terminal_success": evaluator_process.returncode == 0,
        },
    )
    if evaluator_process.returncode != 0:
        decision = _finalize_stable_blocked_stage(
            stage,
            stage_final,
            terminal_status="BLOCKED_CLEAN1_EVALUATOR_CONTRACT_FAILED",
            code_commit=code_commit,
            pre_verified=len(pre.verified_hashes),
            post_verified=len(post.verified_hashes),
            raw_mutation_count=mutation["raw_mutation"],
            provider_attempt_generated=True,
            raw_doppler_backend_lineage_proven=True,
            blocked_component="evaluator_freeze_process",
            claim_boundary="Evaluator freeze process failed before provider promotion or any formal run.",
            narrative=(
                "Fresh provider, raw integrity, and common window closed, but the isolated evaluator-freeze "
                "process failed. The provider attempt was preserved and not promoted."
            ),
        )
        print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
        return 2
    if strace:
        try:
            _evaluator_strace_crosscheck(
                evaluator_strace,
                stage / "02_PROTOCOL_FREEZE/EVALUATOR_FREEZE_FILE_OPEN_CROSSCHECK.json",
                paths=paths,
                stage_attempt=stage,
            )
        except RuntimeError:
            decision = _finalize_stable_blocked_stage(
                stage,
                stage_final,
                terminal_status="FAIL_CLEAN1_EVIDENCE_CONTAMINATION",
                code_commit=code_commit,
                pre_verified=len(pre.verified_hashes),
                post_verified=len(post.verified_hashes),
                raw_mutation_count=mutation["raw_mutation"],
                provider_attempt_generated=True,
                raw_doppler_backend_lineage_proven=True,
                blocked_component="evaluator_freeze_file_open_closure",
                claim_boundary=(
                    "Evaluator file-read isolation failed before provider promotion or any formal run."
                ),
                narrative=(
                    "The isolated evaluator-freeze file-open ledger did not close. The provider "
                    "attempt was preserved and not promoted."
                ),
            )
            print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
            return 2
    window_path = stage / "02_PROTOCOL_FREEZE" / "WINDOW_CONTRACT.yaml"
    from legsa_gins.paper_rebuild.paths import load_yaml_mapping
    window_payload = load_yaml_mapping(window_path)
    window_payload["_contract_path"] = str(window_path)
    catalog = load_method_catalog(args.methods)
    effective = build_effective_method_metadata(
        catalog,
        bundle,
        window_payload,
        stage / "02_PROTOCOL_FREEZE/EVALUATOR_CONTRACT.yaml",
        protocol.payload,
        code_commit=code_commit,
        executable_hash=sha256_file(paths.port_core_exe),
    )
    write_method_freeze(catalog, stage / "02_PROTOCOL_FREEZE", effective_configs=effective)
    evaluator_payload = load_yaml_mapping(stage / "02_PROTOCOL_FREEZE/EVALUATOR_CONTRACT.yaml")
    evaluator_ready = evaluator_payload.get("formal_metrics_authorized") is True
    decision = _build_success_pre_run_decision(
        code_commit=code_commit,
        raw_pre_verified=len(pre.verified_hashes),
        raw_post_verified=len(post.verified_hashes),
        raw_mutation_count=mutation["raw_mutation"],
        raw_doppler_backend_lineage_proven=bool(
            bundle.raw_doppler_report["raw_doppler_backend_lineage_proven"]
        ),
        raw_doppler_valid_epoch_count=int(
            bundle.raw_doppler_report["valid_epoch_count"]
        ),
        provider_bundle_hash=bundle.provider_bundle_hash,
        window_summary=window_summary,
        evaluator_ready=evaluator_ready,
        evaluator_terminal_status=str(evaluator_payload["terminal_status"]),
    )
    write_json_atomic(stage / "08_EVIDENCE_AUDIT" / "PRE_RUN_GATE_DECISION.json", decision)
    write_json_atomic(
        stage / "08_EVIDENCE_AUDIT/PROMOTION_JOURNAL.json",
        {
            "schema_version": "paper-rebuild-clean1-promotion-journal-v1",
            "state": "STAGE_ATTEMPT_READY_PROVIDER_PENDING",
            "provider_attempt_root_name": attempt_paths.provider_root.name,
            "provider_bundle_hash": bundle.provider_bundle_hash,
            "provider_final_promoted": False,
            "stage_final_promoted": False,
            "delete_used": False,
        },
    )
    stage.rename(stage_final)
    write_json_atomic(
        stage_final / "08_EVIDENCE_AUDIT/PROMOTION_JOURNAL.json",
        {
            "schema_version": "paper-rebuild-clean1-promotion-journal-v1",
            "state": "STAGE_PROMOTED_PROVIDER_PENDING",
            "provider_attempt_root_name": attempt_paths.provider_root.name,
            "provider_bundle_hash": bundle.provider_bundle_hash,
            "provider_final_promoted": False,
            "stage_final_promoted": True,
            "delete_used": False,
        },
    )
    attempt_paths.provider_root.rename(paths.provider_root)
    write_json_atomic(
        stage_final / "08_EVIDENCE_AUDIT/PROMOTION_JOURNAL.json",
        {
            "schema_version": "paper-rebuild-clean1-promotion-journal-v1",
            "state": "COMPLETE",
            "provider_attempt_root_name": attempt_paths.provider_root.name,
            "provider_bundle_hash": bundle.provider_bundle_hash,
            "provider_final_promoted": True,
            "stage_final_promoted": True,
            "delete_used": False,
        },
    )
    write_json_atomic(
        stage_final / "08_EVIDENCE_AUDIT/PROMOTION_COMPLETE.json",
        {
            "state": "COMPLETE",
            "provider_bundle_hash": bundle.provider_bundle_hash,
            "provider_final_promoted": True,
            "stage_final_promoted": True,
        },
    )
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
