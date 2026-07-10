#!/usr/bin/env python3
"""Audit CLEAN1 evidence, write the bounded report, and create a redacted export."""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.evidence import (
    BY2_TRACE_RELATIVE_PATH,
    assert_export_text_is_redacted,
    scan_text_for_export_leaks,
)
from legsa_gins.paper_rebuild.formal_provider import load_formal_provider_bundle
from legsa_gins.paper_rebuild.formal_runner import RUN_DIRECTORY_NAMES
from legsa_gins.paper_rebuild.manifest import sha256_file, write_json_atomic
from legsa_gins.paper_rebuild.methods import FORMAL_METHOD_ORDER
from legsa_gins.paper_rebuild.paths import (
    assert_clean1_path_contract,
    guard_path,
    load_clean_paths,
    load_yaml_mapping,
)
from legsa_gins.paper_rebuild.protocol import REQUIRED_WINDOW_STREAMS, load_frozen_window


BLOCKED_STATUS = "BLOCKED_CLEAN1_EVALUATOR_CONTRACT_FAILED"


def _assert_exact_blocked_gate_closure(
    decision: dict[str, Any],
    evaluator_contract: dict[str, Any],
    run_blocked: dict[str, Any],
) -> None:
    expected_run = {
        "schema_version": "paper-rebuild-clean1-four-run-gate-v1",
        "formal_run_count": 0,
        "method_count_required": 4,
        "metric_driven_rerun": False,
        "terminal_status": BLOCKED_STATUS,
        "paper_performance_claim": False,
    }
    if run_blocked != expected_run:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    if (
        decision.get("terminal_status") != BLOCKED_STATUS
        or decision.get("formal_runs_authorized_by_all_gates") is not False
        or decision.get("evaluator_ready") is not False
        or decision.get("paper_performance_claim") is not False
    ):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    expected_evaluator_fields = {
        "method_output_read_during_freeze": False,
        "reference_point_contract_proven": False,
        "reference_attitude_frame_contract_proven": False,
        "formal_metrics_authorized": False,
        "terminal_status": BLOCKED_STATUS,
    }
    if any(
        evaluator_contract.get(field) != expected
        for field, expected in expected_evaluator_fields.items()
    ):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")


def _assert_sha256_sidecar(artifact: Path, sidecar: Path) -> None:
    expected = f"{sha256_file(artifact)}  {artifact.name}"
    if sidecar.read_text(encoding="utf-8").strip() != expected:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")


def _assert_exact_pre_run_gate_closure(
    stage: Path,
    *,
    decision: dict[str, Any],
    raw_summary: dict[str, Any],
    mutation: dict[str, Any],
    window_contract: dict[str, Any],
    bundle: Any,
    backend: dict[str, Any],
) -> None:
    expected_raw = {
        "expected": 22,
        "full_lock_rows": 9980,
        "by2_lock_rows": 22,
        "pre_verified": 22,
        "post_verified": 22,
        "mismatch": 0,
        "missing": 0,
        "symlink_escape": 0,
        "raw_mutation": 0,
        "passed": True,
    }
    if any(raw_summary.get(field) != value for field, value in expected_raw.items()):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    expected_mutation = {
        "schema_version": "paper-rebuild-by2-raw-mutation-audit-v1",
        "pre_verified": 22,
        "post_verified": 22,
        "raw_mutation": 0,
        "changed_relative_paths": [],
        "passed": True,
    }
    if mutation != expected_mutation:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")

    journal = _json(stage / "08_EVIDENCE_AUDIT/PROMOTION_JOURNAL.json")
    marker = _json(stage / "08_EVIDENCE_AUDIT/PROMOTION_COMPLETE.json")
    attempt_name = journal.get("provider_attempt_root_name")
    if (
        not isinstance(attempt_name, str)
        or not attempt_name.startswith(".CLEAN1_BY2_CLEAN_NORMAL_V1.attempt-")
        or "/" in attempt_name
        or "\\" in attempt_name
    ):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    expected_marker = {
        "state": "COMPLETE",
        "provider_bundle_hash": bundle.provider_bundle_hash,
        "provider_final_promoted": True,
        "stage_final_promoted": True,
    }
    if marker != expected_marker:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    expected_journal = {
        "schema_version": "paper-rebuild-clean1-promotion-journal-v1",
        "state": "COMPLETE",
        "provider_attempt_root_name": attempt_name,
        "provider_bundle_hash": bundle.provider_bundle_hash,
        "provider_final_promoted": True,
        "stage_final_promoted": True,
        "delete_used": False,
    }
    if journal != expected_journal:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    if (
        decision.get("provider_bundle_hash") != bundle.provider_bundle_hash
        or decision.get("fresh_provider_generated") is not True
        or decision.get("raw_pre_verified") != 22
        or decision.get("raw_post_verified") != 22
        or decision.get("raw_mutation_count") != 0
        or decision.get("raw_doppler_backend_lineage_proven") is not True
        or decision.get("raw_doppler_valid_epoch_count") != backend.get("valid_epoch_count")
    ):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")

    window_path = stage / "02_PROTOCOL_FREEZE/WINDOW_CONTRACT.yaml"
    evaluator_path = stage / "02_PROTOCOL_FREEZE/EVALUATOR_CONTRACT.yaml"
    _assert_sha256_sidecar(
        window_path, stage / "02_PROTOCOL_FREEZE/WINDOW_CONTRACT.sha256"
    )
    _assert_sha256_sidecar(
        evaluator_path, stage / "02_PROTOCOL_FREEZE/EVALUATOR_CONTRACT.sha256"
    )
    exact_window_fields = {
        "schema_version": "paper-rebuild-window-contract-v1",
        "stage_id": "CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION",
        "case_id": "CLEAN1_BY2_CLEAN_NORMAL",
        "protocol_id": "CLEAN1_BY2_CLEAN_NORMAL_V1",
        "data_mode": "real_by2_raw",
        "policy": "full_common_required_stream_interval",
        "t_start_formula": "max(all_required_stream_first_valid_timestamps)",
        "t_end_formula": "min(all_required_stream_last_valid_timestamps)",
        "internal_dropout_preserved": True,
        "method_specific_window": False,
        "smoke_truncation_applied": False,
        "evaluation_burn_in_seconds": 0.0,
        "trace_or_method_output_used_to_select_window": False,
    }
    if any(
        window_contract.get(field) != value
        for field, value in exact_window_fields.items()
    ):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    start = float(window_contract.get("t_start", math.nan))
    end = float(window_contract.get("t_end", math.nan))
    duration = float(window_contract.get("duration_seconds", math.nan))
    if (
        not all(math.isfinite(value) for value in (start, end, duration))
        or end <= start
        or not math.isclose(duration, end - start, rel_tol=0.0, abs_tol=1.0e-9)
    ):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    decision_window = decision.get("window")
    if not isinstance(decision_window, dict):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    for field in (
        "t_start",
        "t_end",
        "duration_seconds",
        "source_time_origin_seconds",
        "common_initialization",
    ):
        if decision_window.get(field) != window_contract.get(field):
            raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")

    coverage_path = stage / "02_PROTOCOL_FREEZE/WINDOW_SOURCE_COVERAGE.csv"
    with coverage_path.open("r", encoding="utf-8", newline="") as handle:
        coverage_rows = list(csv.DictReader(handle))
    if tuple(row.get("stream_role") for row in coverage_rows) != REQUIRED_WINDOW_STREAMS:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    role_to_artifact = {
        "propagation_imu": "imu_runtime_input",
        "gnss_position": "gnss_runtime_input",
        "receiver_velocity": "gnss_runtime_input",
        "dual_yaw": "dual_yaw_provider",
        "raw_doppler": "raw_doppler_provider",
        "go2_roll_pitch_prior": "go2_attitude_prior",
        "go2_horizontal_velocity_prior": "go2_horizontal_velocity_prior",
    }
    firsts: list[float] = []
    lasts: list[float] = []
    for row in coverage_rows:
        role = str(row["stream_role"])
        artifact = role_to_artifact[role]
        if (
            row.get("source_alias") != "<PROVIDER_ROOT>"
            or row.get("relative_path") != bundle.provider_relpaths[artifact]
            or row.get("source_sha256") != bundle.provider_hashes[artifact]
            or str(row.get("internal_dropout_preserved")).casefold() != "true"
            or int(str(row.get("valid_epoch_count") or 0)) < 2
        ):
            raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
        firsts.append(float(row["first_valid_timestamp"]))
        lasts.append(float(row["last_valid_timestamp"]))
    if (
        not math.isclose(start, max(firsts), rel_tol=0.0, abs_tol=1.0e-9)
        or not math.isclose(end, min(lasts), rel_tol=0.0, abs_tol=1.0e-9)
    ):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path.name}")
    return value


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _artifact_count(root: Path, suffixes: set[str]) -> int:
    if not root.exists():
        return 0
    return sum(path.is_file() and path.suffix.casefold() in suffixes for path in root.rglob("*"))


def _tracked_local_path_issues(paths: Any) -> list[str]:
    listed = subprocess.run(
        [
            "git", "ls-files", "docs/paper_rebuild", "configs/paper_rebuild",
            "scripts/paper_rebuild", "tests/paper_rebuild", "src/legsa_gins/paper_rebuild",
            "src/legsa_gins/input_generation/process_data_compat.py", "cpp/legsa_v23_port_core",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    issues: list[str] = []
    current_local_values = {
        str(value)
        for value in (
            paths.code_root,
            paths.raw_root,
            paths.by2_fix_root,
            paths.by2_go2_body,
            paths.clean_root,
            paths.provider_root,
            paths.runtime_root,
        )
    }
    for relative in listed:
        source = REPO_ROOT / relative
        if not source.is_file():
            continue
        text = source.read_text(encoding="utf-8", errors="replace")
        if any(value in text for value in current_local_values):
            issues.append(f"tracked_local_path:{relative}")
        if relative.startswith(("docs/paper_rebuild/", "configs/paper_rebuild/")):
            for issue in scan_text_for_export_leaks(text):
                issues.append(f"tracked_{issue}:{relative}")
    return sorted(set(issues))


def _export(stage: Path, report_dir: Path) -> Path:
    relative_candidates = [
        "00_AUTHORIZATION/AUTHORIZATION.md",
        "01_GIT_FREEZE/GIT_STATE.json",
        "01_GIT_FREEZE/CODE_FREEZE_COMMIT.txt",
        "02_PROTOCOL_FREEZE/SCOPE_LOCK.yaml",
        "02_PROTOCOL_FREEZE/METHODS_SNAPSHOT.yaml",
        "02_PROTOCOL_FREEZE/METHODS_SNAPSHOT.sha256",
        "02_PROTOCOL_FREEZE/EFFECTIVE_METHOD_FLAG_MATRIX.csv",
        "02_PROTOCOL_FREEZE/METHOD_CONFIG_DIFF_AUDIT.json",
        "02_PROTOCOL_FREEZE/WINDOW_CONTRACT.yaml",
        "02_PROTOCOL_FREEZE/WINDOW_CONTRACT.sha256",
        "02_PROTOCOL_FREEZE/WINDOW_SOURCE_COVERAGE.csv",
        "02_PROTOCOL_FREEZE/EVALUATOR_CONTRACT.yaml",
        "02_PROTOCOL_FREEZE/EVALUATOR_CONTRACT.sha256",
        "02_PROTOCOL_FREEZE/REFERENCE_SCHEMA_AUDIT.json",
        "03_DATA_HASH_AND_ROLES/BY2_RAW_22_PRE_HASH_AUDIT.csv",
        "03_DATA_HASH_AND_ROLES/BY2_RAW_22_POST_HASH_AUDIT.csv",
        "03_DATA_HASH_AND_ROLES/BY2_RAW_22_ROLE_MANIFEST.csv",
        "03_DATA_HASH_AND_ROLES/BY2_RAW_22_SUMMARY.json",
        "03_DATA_HASH_AND_ROLES/PROVIDER_SOLVER_SOURCE_ALLOWLIST.csv",
        "03_DATA_HASH_AND_ROLES/EVALUATOR_ONLY_ALLOWLIST.csv",
        "03_DATA_HASH_AND_ROLES/HASH_VERIFIED_NOT_SOLVER_INPUT.csv",
        "03_DATA_HASH_AND_ROLES/CLEAN1_HARD_DENYLIST.csv",
        "03_DATA_HASH_AND_ROLES/RAW_MUTATION_AUDIT.json",
        "04_PROVIDER_AUDIT/PROVIDER_HASH_MANIFEST.csv",
        "04_PROVIDER_AUDIT/RAW_DOPPLER_BACKEND_REDACTED.json",
        "04_PROVIDER_AUDIT/PROVIDER_FILE_OPEN_CROSSCHECK.json",
        "06_RUN_MANIFESTS/FOUR_METHOD_RUN_BLOCKED.json",
        "08_EVIDENCE_AUDIT/PRE_RUN_GATE_DECISION.json",
        "08_EVIDENCE_AUDIT/FORBIDDEN_INPUT_AUDIT.csv",
        "08_EVIDENCE_AUDIT/MODULE_ACTIVATION_AUDIT.csv",
        "08_EVIDENCE_AUDIT/SOLVER_ACTUAL_INPUT_LEDGER.csv",
        "08_EVIDENCE_AUDIT/EVALUATOR_ACTUAL_READ_LEDGER.csv",
        "08_EVIDENCE_AUDIT/PATH_LEAK_AUDIT.json",
        "09_REPORT/CLEAN1_FULL_REPORT.md",
        "09_REPORT/CLEAN1_FULL_REPORT.json",
    ]
    files = [stage / relative for relative in relative_candidates if (stage / relative).is_file()]
    claim = REPO_ROOT / "docs/paper_rebuild/CLAIM_BOUNDARY.md"
    for source in [*files, claim]:
        assert_export_text_is_redacted(source.read_text(encoding="utf-8"))
    manifest_rows = [
        {
            "archive_path": source.relative_to(stage).as_posix(),
            "sha256": sha256_file(source),
            "size_bytes": source.stat().st_size,
        }
        for source in files
    ]
    manifest_rows.append(
        {"archive_path": "CLAIM_BOUNDARY.md", "sha256": sha256_file(claim), "size_bytes": claim.stat().st_size}
    )
    internal = stage / "10_EXPORT/EXPORT_SHA256_MANIFEST.csv"
    _write_csv(internal, ["archive_path", "sha256", "size_bytes"], manifest_rows)
    assert_export_text_is_redacted(internal.read_text(encoding="utf-8"))
    archive = stage / "10_EXPORT/CLEAN1_CONTEXT_FOR_GPT.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for source in files:
            handle.write(source, source.relative_to(stage).as_posix())
        handle.write(claim, "CLAIM_BOUNDARY.md")
        handle.write(internal, "EXPORT_SHA256_MANIFEST.csv")
    return archive


def _verify_export(archive: Path) -> list[str]:
    issues: list[str] = []
    with zipfile.ZipFile(archive, "r") as handle:
        names = handle.namelist()
        if any(
            name.endswith(".local.yaml")
            or name.casefold().endswith((".nav", ".std", ".pdf", ".png", ".jpg", ".svg"))
            or "ROW_LEVEL_ERRORS" in name
            or "raw_doppler_backend/" in name.casefold()
            for name in names
        ):
            issues.append("forbidden_export_member")
        for name in names:
            if Path(name).suffix.casefold() not in {".md", ".json", ".yaml", ".yml", ".csv", ".txt"}:
                continue
            text = handle.read(name).decode("utf-8")
            issues.extend(scan_text_for_export_leaks(text))
    if archive.stat().st_size > 50 * 1024 * 1024:
        issues.append("export_too_large")
    return sorted(set(issues))


def _evidence_manifest(stage: Path) -> None:
    excluded = {
        "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.csv",
        "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.sha256",
    }
    rows = []
    for source in sorted(path for path in stage.rglob("*") if path.is_file()):
        relative = source.relative_to(stage).as_posix()
        if relative in excluded:
            continue
        rows.append(
            {
                "relative_path": relative,
                "sha256": sha256_file(source),
                "size_bytes": source.stat().st_size,
                "tracked": False,
            }
        )
    manifest = stage / "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.csv"
    _write_csv(manifest, ["relative_path", "sha256", "size_bytes", "tracked"], rows)
    digest = sha256_file(manifest)
    (stage / "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.sha256").write_text(
        f"{digest}  EVIDENCE_MANIFEST.csv\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--report-commit", default="PENDING_TRACKED_REPORT_COMMIT")
    parser.add_argument("--pr-url", default="PENDING_UNMERGED_PR")
    parser.add_argument("--ci-status", default="NOT_AVAILABLE")
    args = parser.parse_args(argv)
    paths = load_clean_paths(args.config)
    assert_clean1_path_contract(paths, REPO_ROOT)
    stage = guard_path(
        paths.clean_root / "06_CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION",
        role="CLEAN1 evidence root",
        allowed_root=paths.clean_root,
        must_exist=True,
    )
    decision = _json(stage / "08_EVIDENCE_AUDIT/PRE_RUN_GATE_DECISION.json")
    backend = _json(stage / "04_PROVIDER_AUDIT/RAW_DOPPLER_BACKEND_REPORT.json")
    provider_manifest = _json(stage / "04_PROVIDER_AUDIT/CLEAN_INPUT_MANIFEST.json")
    provider_open = _json(stage / "04_PROVIDER_AUDIT/PROVIDER_FILE_OPEN_CROSSCHECK.json")
    evaluator_open = _json(
        stage / "02_PROTOCOL_FREEZE/EVALUATOR_FREEZE_FILE_OPEN_CROSSCHECK.json"
    )
    raw_summary = _json(stage / "03_DATA_HASH_AND_ROLES/BY2_RAW_22_SUMMARY.json")
    mutation = _json(stage / "03_DATA_HASH_AND_ROLES/RAW_MUTATION_AUDIT.json")
    evaluator_contract = load_yaml_mapping(stage / "02_PROTOCOL_FREEZE/EVALUATOR_CONTRACT.yaml")
    try:
        window_contract = load_frozen_window(
            stage / "02_PROTOCOL_FREEZE/WINDOW_CONTRACT.yaml"
        )
    except Exception as exc:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION") from exc
    run_blocked = _json(stage / "06_RUN_MANIFESTS/FOUR_METHOD_RUN_BLOCKED.json")
    _assert_exact_blocked_gate_closure(decision, evaluator_contract, run_blocked)
    bundle = load_formal_provider_bundle(paths, allow_report_only_descendant=True)
    try:
        _assert_exact_pre_run_gate_closure(
            stage,
            decision=decision,
            raw_summary=raw_summary,
            mutation=mutation,
            window_contract=window_contract,
            bundle=bundle,
            backend=backend,
        )
    except RuntimeError as exc:
        if str(exc) == "FAIL_CLEAN1_EVIDENCE_CONTAMINATION":
            raise
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION") from exc
    except Exception as exc:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION") from exc
    if backend != bundle.raw_doppler_report or provider_manifest["provider_bundle_hash"] != bundle.provider_bundle_hash:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    if provider_open.get("passed") is not True or evaluator_open.get("passed") is not True:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    if provider_open.get("strace_available") is True:
        provider_trace = paths.provider_root / "audit/PROVIDER_FILE_OPEN_TRACE.raw"
        if not provider_trace.is_file() or sha256_file(provider_trace) != provider_open.get(
            "strace_sha256"
        ):
            raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    if evaluator_open.get("strace_available") is True:
        evaluator_trace = stage / "02_PROTOCOL_FREEZE/EVALUATOR_FREEZE_FILE_OPEN_TRACE.raw"
        if not evaluator_trace.is_file() or sha256_file(evaluator_trace) != evaluator_open.get(
            "strace_sha256"
        ):
            raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    code_commit = (stage / "01_GIT_FREEZE/CODE_FREEZE_COMMIT.txt").read_text(encoding="utf-8").strip()
    run_rows = []
    output_hash_rows = []
    formal_run_count = 0
    for index, (method, directory) in enumerate(zip(FORMAL_METHOD_ORDER, RUN_DIRECTORY_NAMES), start=1):
        manifest = paths.runtime_root / directory / "FORMAL_RUN_MANIFEST.json"
        status = "PASS" if manifest.is_file() else "NOT_RUN_EVALUATOR_GATE_BLOCKED"
        if manifest.is_file():
            formal_run_count += 1
        run_rows.append(
            {
                "method_order": index,
                "algorithm_id": method,
                "run_directory_alias": f"<RUNTIME_ROOT>/{directory}",
                "status": status,
                "formal_manifest_present": manifest.is_file(),
            }
        )
    _write_csv(
        stage / "06_RUN_MANIFESTS/FOUR_METHOD_RUN_INDEX.csv",
        list(run_rows[0]),
        run_rows,
    )
    _write_csv(
        stage / "06_RUN_MANIFESTS/FOUR_METHOD_OUTPUT_HASHES.csv",
        ["method_order", "algorithm_id", "output_role", "sha256"],
        output_hash_rows,
    )
    if evaluator_contract.get("formal_metrics_authorized") is not False or formal_run_count != 0:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    module_rows = [
        {
            "method_order": index,
            "algorithm_id": method,
            "activation_status": "NOT_AVAILABLE_NOT_RUN_EVALUATOR_GATE_BLOCKED",
            "module_counts_verified": False,
        }
        for index, method in enumerate(FORMAL_METHOD_ORDER, start=1)
    ]
    _write_csv(
        stage / "08_EVIDENCE_AUDIT/MODULE_ACTIVATION_AUDIT.csv",
        list(module_rows[0]),
        module_rows,
    )
    solver_ledger_rows = [
        {
            "method_order": index,
            "algorithm_id": method,
            "read_status": "NOT_RUN_EVALUATOR_GATE_BLOCKED",
            "actual_solver_input_count": 0,
            "trace_used_online": False,
        }
        for index, method in enumerate(FORMAL_METHOD_ORDER, start=1)
    ]
    _write_csv(
        stage / "08_EVIDENCE_AUDIT/SOLVER_ACTUAL_INPUT_LEDGER.csv",
        list(solver_ledger_rows[0]),
        solver_ledger_rows,
    )
    evaluator_ledger_source = stage / "02_PROTOCOL_FREEZE/EVALUATOR_FREEZE_ACTUAL_READ_LEDGER.csv"
    with evaluator_ledger_source.open("r", encoding="utf-8", newline="") as handle:
        evaluator_ledger_rows = list(csv.DictReader(handle))
    if not any(
        row.get("role") == "evaluation_only_trace"
        and row.get("relative_path") == BY2_TRACE_RELATIVE_PATH
        for row in evaluator_ledger_rows
    ):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    _write_csv(
        stage / "08_EVIDENCE_AUDIT/EVALUATOR_ACTUAL_READ_LEDGER.csv",
        list(evaluator_ledger_rows[0]),
        evaluator_ledger_rows,
    )
    provider_forbidden_fields = (
        "receiver_imu_as_body_imu",
        "final_v23_output_solver_input",
        "LegSA_output_solver_input",
        "synthetic_data_used",
        "semisynthetic_data_used",
        "per_case_tuning",
        "output_only_correction",
        "epoch_deleted_for_metric",
        "status_fallback_used",
    )
    forbidden_values = {
        "legacy_runtime_input_count": provider_manifest["old_runtime_input_count"],
        "legacy_provider_input_count": provider_manifest.get("legacy_provider_input_count", 0),
        "legacy_row_input_count": provider_manifest.get("legacy_row_input_count", 0),
        "legacy_aggregate_input_count": provider_manifest.get("legacy_aggregate_input_count", 0),
        "shared_unassigned_input_count": sum(
            1
            for entry in provider_manifest["actual_source_read_set"]
            if provider_manifest["raw_source_roles"].get(entry["relative_path"])
            != "actual_provider_source"
        ),
        "trace_used_by_provider": provider_manifest["trace_used_online"] or provider_open["trace_opened_by_provider_process"],
        "trace_used_by_solver": any(row["trace_used_online"] for row in solver_ledger_rows),
        "trace_used_by_evaluator_freeze": any(row.get("role") == "evaluation_only_trace" for row in evaluator_ledger_rows),
        **{field: provider_manifest[field] for field in provider_forbidden_fields},
        "metric_driven_rerun": bool(run_blocked.get("metric_driven_rerun", False)),
        "paper_figure_count": _artifact_count(stage, {".png", ".jpg", ".jpeg", ".svg", ".pdf"}),
        "diagnostic_plot_count": _artifact_count(stage, {".png", ".jpg", ".jpeg", ".svg"}),
        "classic18_run_count": 0 if not paths.runtime_root.exists() else -1,
        "matrix_60x9_run_count": 0 if not paths.runtime_root.exists() else -1,
        "DA03_run": False if not paths.runtime_root.exists() else None,
        "DA05_run": False if not paths.runtime_root.exists() else None,
        "BY3_XB_PG_run_count": 0 if not paths.runtime_root.exists() else -1,
    }
    expected_values = {key: False for key in forbidden_values}
    for key in (
        "legacy_runtime_input_count", "legacy_provider_input_count", "legacy_row_input_count",
        "legacy_aggregate_input_count", "shared_unassigned_input_count", "paper_figure_count",
        "diagnostic_plot_count", "classic18_run_count", "matrix_60x9_run_count", "BY3_XB_PG_run_count",
    ):
        expected_values[key] = 0
    expected_values["trace_used_by_evaluator_freeze"] = True
    forbidden_rows = [
        {
            "check": key,
            "actual": value,
            "expected": expected_values[key],
            "status": "PASS" if value == expected_values[key] else "FAIL",
        }
        for key, value in forbidden_values.items()
    ]
    _write_csv(
        stage / "08_EVIDENCE_AUDIT/FORBIDDEN_INPUT_AUDIT.csv",
        ["check", "actual", "expected", "status"],
        forbidden_rows,
    )
    if any(row["status"] != "PASS" for row in forbidden_rows):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    figure_count = forbidden_values["paper_figure_count"]
    path_issues: list[str] = _tracked_local_path_issues(paths)
    path_audit = {
        "schema_version": "paper-rebuild-clean1-path-leak-audit-v1",
        "tracked_or_export_local_path_issues": sorted(set(path_issues)),
        "local_config_exported": any(
            path.name.endswith(".local.yaml") for path in (stage / "10_EXPORT").glob("*")
        ),
        "post_export_verification_passed": False,
        "passed": not path_issues,
    }
    write_json_atomic(stage / "08_EVIDENCE_AUDIT/PATH_LEAK_AUDIT.json", path_audit)
    if figure_count or not path_audit["passed"]:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")

    with (stage / "03_DATA_HASH_AND_ROLES/BY2_RAW_22_PRE_HASH_AUDIT.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        pre_rows = list(csv.DictReader(handle))
    bag_fpl_rows = [
        row for row in pre_rows if row["relative_path"].endswith((".bag", ".fpl"))
    ]
    bag_fpl_pass = len(bag_fpl_rows) == 2 and all(row["status"] == "PASS" for row in bag_fpl_rows)
    formal_metrics_path = stage / "07_EVALUATION/FORMAL_EVALUATION/FOUR_METHOD_METRICS.json"
    row_level_count = sum(
        1 for path in (stage / "07_EVALUATION").rglob("ROW_LEVEL_ERRORS.csv")
    )
    crosscheck_count = sum(
        1 for path in (stage / "07_EVALUATION").rglob("AGGREGATE_CROSSCHECK.json")
    )
    if (
        paths.runtime_root.exists()
        or formal_metrics_path.exists()
        or row_level_count != 0
        or crosscheck_count != 0
    ):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    redacted_backend = {
        key: backend[key]
        for key in (
            "schema_version", "raw_doppler_backend_lineage_proven", "raw_doppler_backend_id",
            "raw_doppler_backend_source_files", "raw_doppler_backend_source_hashes",
            "helper_executable_hash", "obs_source_hash", "nav_source_hash", "conversion_config_hash",
            "raw_epoch_count", "valid_epoch_count", "invalid_epoch_count", "sat_count_min",
            "sat_count_median", "sat_count_max", "sat_count_semantics", "covariance_policy",
            "rtklib_commit", "external_ephemeris_downloaded", "status_fallback_used",
            "legacy_provider_used", "source_discovery_used",
        )
    }
    write_json_atomic(
        stage / "04_PROVIDER_AUDIT/RAW_DOPPLER_BACKEND_REDACTED.json",
        redacted_backend,
    )
    report = {
        "schema_version": "paper-rebuild-clean1-full-report-v1",
        "terminal_decision": BLOCKED_STATUS,
        "reason": (
            "No source-backed unique identity/transform was established between the evaluation reference point "
            "and the propagation-IMU solver state point; the reference yaw frame/axis semantics were also not "
            "proven by active hash-locked metadata."
        ),
        "base_commit": "4e6b3f3fa9f50ed91b6c4e250f3d1f75d6725cc6",
        "code_freeze_commit": code_commit,
        "report_commit": args.report_commit,
        "branch": "stage/clean1-by2-clean-four-method",
        "push_status": "PENDING" if args.pr_url == "PENDING_UNMERGED_PR" else "PUSHED",
        "pr_url": args.pr_url,
        "ci_status": args.ci_status,
        "raw_hash_lock_sha_match": raw_summary["passed"],
        "full_lock_rows": raw_summary["full_lock_rows"],
        "by2_lock_rows": raw_summary["by2_lock_rows"],
        "by2_pre_hash_verified": raw_summary["pre_verified"],
        "by2_post_hash_verified": raw_summary["post_verified"],
        "raw_mutation_count": mutation["raw_mutation"],
        "bag_fpl_present_and_hash_matched": bag_fpl_pass,
        "actual_provider_source_set": [
            {"path_alias": "<RAW_ROOT>", "relative_path": entry["relative_path"], "role": entry["role"]}
            for entry in provider_manifest["actual_source_read_set"]
        ],
        "evaluator_only_source": {"path_alias": "<RAW_ROOT>", "relative_path": BY2_TRACE_RELATIVE_PATH},
        "fresh_provider_generated": paths.provider_root.is_dir(),
        "provider_bundle_hash": bundle.provider_bundle_hash,
        "provider_hashes": bundle.provider_hashes,
        "source_quality_metadata_role": provider_manifest["artifacts"]["source_quality_metadata"]["artifact_role"],
        "raw_doppler_backend_lineage_proven": backend["raw_doppler_backend_lineage_proven"],
        "raw_doppler_valid_epoch_count": backend["valid_epoch_count"],
        "raw_doppler_invalid_epoch_count": backend["invalid_epoch_count"],
        "raw_doppler_sat_count_min_median_max": [
            backend["sat_count_min"], backend["sat_count_median"], backend["sat_count_max"]
        ],
        "status_fallback_used": backend["status_fallback_used"],
        "common_full_window_frozen": (
            window_contract.get("policy") == "full_common_required_stream_interval"
            and window_contract.get("smoke_truncation_applied") is False
        ),
        "common_window_start": window_contract["t_start"],
        "common_window_end": window_contract["t_end"],
        "common_window_duration_seconds": window_contract["duration_seconds"],
        "evaluator_contract_ready": evaluator_contract["formal_metrics_authorized"],
        "reference_point_contract_proven": evaluator_contract["reference_point_contract_proven"],
        "reference_attitude_frame_contract_proven": evaluator_contract["reference_attitude_frame_contract_proven"],
        "formal_method_count": 4,
        "formal_run_count": formal_run_count,
        "four_method_run_gate": run_blocked.get("terminal_status", BLOCKED_STATUS),
        "formal_metrics_generated": formal_metrics_path.is_file(),
        "row_level_generated": row_level_count > 0,
        "aggregate_crosscheck_run": crosscheck_count > 0,
        "paper_figure_count": figure_count,
        "diagnostic_plot_count": forbidden_values["diagnostic_plot_count"],
        "paper_performance_claim": False,
        "claim_boundary": (
            "CLEAN1 evidence covers one BY2 clean-normal readiness chain only; no degradation robustness, "
            "cross-dataset generalization, statistical significance, or superiority conclusion is established."
        ),
    }
    report_dir = stage / "09_REPORT"
    write_json_atomic(report_dir / "CLEAN1_FULL_REPORT.json", report)
    markdown = f"""# CLEAN1 BY2 Clean Four-Method Stage Report

## Terminal decision

`{BLOCKED_STATUS}`

Fresh source and provider readiness closed, including exact 22/22 pre/post raw verification and a source-backed Raw Doppler backend. Formal execution stopped before any method run because neither the evaluator reference-point identity/transform nor its yaw-frame semantics were uniquely source-backed.

## Frozen evidence

- code freeze commit: `{code_commit}`
- report commit: `{args.report_commit}`
- BY2 raw: 22/22 pre, 22/22 post, zero mutation
- Raw Doppler: {backend['valid_epoch_count']} valid and {backend['invalid_epoch_count']} invalid RAWX epochs; satellites min/median/max {backend['sat_count_min']}/{backend['sat_count_median']}/{backend['sat_count_max']}
- common full window: frozen without smoke truncation or trace selection
- evaluator: offline-only trace contract frozen; reference-point and yaw-frame gates blocked
- source-quality CSV: audit-only validity lineage, not claimed as a separately read source-aware solver input
- formal runs: {formal_run_count}/4
- metrics and figures: not generated

## Claim boundary

No paper-performance, superiority, robustness, generalization, statistical-significance, or submission-readiness claim is made. Classic-18, 60x9, DA03, DA05, BY3/XB/PG, FGO/QM/QA/contact-FK expansion, figures, merge, tag, and next-stage execution remain unauthorized.
"""
    (report_dir / "CLEAN1_FULL_REPORT.md").write_text(markdown, encoding="utf-8")
    archive = _export(stage, report_dir)
    export_issues = _verify_export(archive)
    path_audit["tracked_or_export_local_path_issues"] = sorted(
        set(path_audit["tracked_or_export_local_path_issues"] + export_issues)
    )
    with zipfile.ZipFile(archive, "r") as handle:
        path_audit["local_config_exported"] = any(
            name.endswith(".local.yaml") for name in handle.namelist()
        )
    path_audit["post_export_verification_passed"] = not export_issues
    path_audit["passed"] = not path_audit["tracked_or_export_local_path_issues"] and not path_audit["local_config_exported"]
    write_json_atomic(stage / "08_EVIDENCE_AUDIT/PATH_LEAK_AUDIT.json", path_audit)
    if not path_audit["passed"]:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    archive = _export(stage, report_dir)
    if _verify_export(archive):
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    _evidence_manifest(stage)
    print(json.dumps({"terminal_decision": BLOCKED_STATUS, "formal_run_count": formal_run_count}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
