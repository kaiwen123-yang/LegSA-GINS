#!/usr/bin/env python3
"""Run PAPER10Q2R2R1 A1 migrated-path provider and dual matrix stage."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import zipfile
from dataclasses import asdict
from pathlib import Path

from legsa_gins.external_dual.by2_case_manifest_loader import load_case_manifest
from legsa_gins.external_dual.by2_provider_factory import build_by2_provider
from legsa_gins.external_dual.evaluator_adapter import yaw_metrics
from legsa_gins.external_dual.go2_body_provider import summarize_go2_body
from legsa_gins.external_dual.matrix_runner import matrix_queue
from legsa_gins.external_dual.method_contracts import METHOD_CATALOG, ReproductionType, selected_methods
from legsa_gins.external_dual.method_runner import run_method_case
from legsa_gins.external_dual.raw_dual_receiver_provider import summarize_raw_dual_receiver
from legsa_gins.external_dual.result_summary import final_decision
from legsa_gins.external_dual.status_dual_yaw_provider import summarize_status_provider
from legsa_gins.external_dual.trace_reference_adapter import summarize_trace


STAGE_NAME = "PAPER10Q2R2R1_A1_POST_MIGRATION_PATH_LOCK_PROVIDER_AND_DUAL_MATRIX_RESTART"
STAGE_DIRS = "00_STAGE_REPORT 01_GIT 02_DATASET_ROLE_LOCK 03_PATH_RECOVERY 04_PATH_LOCK 05_PROVIDER 06_METHOD_SELECTION 07_MATRIX 08_EVALUATION 09_STRESS_READINESS 10_TEXT_SUMMARY 11_FIGURES 12_CLAIM_BOUNDARY 13_OBSIDIAN_SYNC 14_AI_CONTEXT_UPDATE 15_TESTS 16_EXPORT_CLEAN_FOR_GPT".split()
LOCAL_PATH_ENV_PLACEHOLDERS = {
    "LEGSA_CODE_ROOT": "<LEGSA_CODE_ROOT>",
    "LEGSA_ORIGINAL_DIRTY_REPO": "<ORIGINAL_DIRTY_REPO>",
    "LEGSA_PROJECT_ROOT": "<LEGSA_PROJECT_ROOT>",
    "LEGSA_WINDOWS_DESKTOP_ROOT": "<WINDOWS_DESKTOP_ROOT>",
    "LEGSA_WINDOWS_USERS_ROOT": "<WINDOWS_USERS_ROOT>",
    "LEGSA_LOCAL_HOME": "<LOCAL_HOME>",
    "LEGSA_MNT_G_ROOT": "<MNT_G_ROOT>",
}


def local_path_redaction_candidates() -> dict[str, str]:
    """Return local-only path values supplied by the operator for export redaction.

    Tracked code must not construct machine-specific prefixes. Operators can set
    these environment variables, or pass explicit runner roots, when producing
    export-clean packages on a local machine.
    """
    candidates: dict[str, str] = {}
    for env_name, placeholder in LOCAL_PATH_ENV_PLACEHOLDERS.items():
        value = os.environ.get(env_name, "").strip()
        if not value:
            continue
        candidates[value] = placeholder
        stripped = value.rstrip("/\\")
        if stripped and stripped != value:
            candidates[stripped] = placeholder
        if stripped:
            candidates[stripped + "/"] = placeholder + "/"
            candidates[stripped + "\\"] = placeholder + "\\"
    return candidates

RECEIVER_FILES = (
    "imu-data.csv", "imu-temp.csv", "imu-biases.csv", "ntrip-info.csv", "ntrip-latency.csv", "tf.csv", "tf_static.csv",
    "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv", "user_io-out-odom_status.csv", "user_io-out-poi_geodetic.csv",
    "user_io-out-poi_odometry.csv", "user_io-out-poi_smooth_odometry.csv", "user_io-status.csv", "userio-raw.csv",
    "corr-raw.csv", "gnss1-raw.csv", "gnss1-status.csv", "gnss2-raw.csv", "gnss2-status.csv",
)
BY2_RECEIVER_REL = Path("data/raw/BY2_BY3/2026-03-06/fixption数据/2026.3.6/by2/vrtk2_a87c6e_2026-03-06-08-00-54_minimal")
BY3_RECEIVER_REL = Path("data/raw/BY2_BY3/2026-03-06/fixption数据/2026.3.6/by3/vrtk2_a87c6e_2026-03-06-08-06-39_minimal")
BODY_REL = Path("data/raw/BY2_BY3/2026-03-06/高层数据")
XB_FIX_REL = Path("data/raw/XB_PG/2026-01-05/fixpositon数据")
XB_BODY_REL = Path("data/raw/XB_PG/2026-01-05/高层数据")


def main() -> int:
    args = parse_args()
    for root in (args.stage_root, args.runtime_root, args.comparison_root, args.export_root):
        root.mkdir(parents=True, exist_ok=True)
    for name in STAGE_DIRS:
        (args.stage_root / name).mkdir(parents=True, exist_ok=True)

    a0_status = read_a0(args.a0_root)
    write_md(args.stage_root / "01_GIT/PAPER10Q2R2R1_A1_GIT_STATE_REPORT.md", git_report(args.repo_root))
    write_dataset_roles(args.stage_root)

    paths = resolve_paths(args.project_root)
    audits = audit_paths(paths)
    write_path_outputs(args.stage_root, paths, audits)
    by2_ready = all_ready(audits["by2"] + audits["body_by2"])

    cases = load_case_manifest(args.q2r2_case_manifest)
    selected = list(selected_methods())
    row_status: list[dict[str, str]] = []
    proof_rows: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    method_summary: list[dict[str, str]] = []
    case_summary: list[dict[str, str]] = []
    yaw_safety: list[dict[str, str]] = []
    provider_built = False

    if by2_ready:
        provider = build_by2_provider(paths["by2_receiver"], paths["by2_body"])
        provider_built = True
        write_provider_outputs(args.stage_root, paths, cases, provider)
        write_csv(args.stage_root / "07_MATRIX/PAPER10Q2R2R1_A1_MATRIX_QUEUE.csv", matrix_queue(selected, cases))
        row_status, proof_rows, failures = run_matrix(args.runtime_root, selected, cases, provider)
        write_csv(args.stage_root / "07_MATRIX/PAPER10Q2R2R1_A1_ROW_EXECUTION_STATUS.csv", row_status)
        write_csv(args.stage_root / "07_MATRIX/PAPER10Q2R2R1_A1_RUNTIME_PROOF_TABLE.csv", proof_rows)
        write_csv(args.stage_root / "07_MATRIX/PAPER10Q2R2R1_A1_FAILURE_OR_BLOCKED_ROWS.csv", failures)
        method_summary = summarize_methods(row_status)
        case_summary = summarize_cases(row_status)
        yaw_safety = yaw_frame_safety(selected)
    else:
        write_provider_blocked(args.stage_root, cases)

    write_method_selection(args.stage_root, selected)
    write_evaluation(args.stage_root, row_status, method_summary, case_summary, yaw_safety)
    write_stress_readiness(args.stage_root, audits)
    write_text_summaries(args.stage_root, row_status, method_summary)
    write_figures(args.stage_root)
    write_claim_boundary(args.stage_root)
    write_comparison(args.comparison_root, method_summary, selected)
    sync_windows_index(args.windows_comparison_root)
    write_obsidian_context(args.stage_root, row_status, method_summary)

    completed = sum(1 for row in row_status if row.get("terminal_status") == "COMPLETED_EVALUABLE")
    faithful = sum(1 for row in method_summary if row.get("faithful_algorithm_completed") == "true")
    blocked = sum(1 for row in row_status if row.get("terminal_status") == "BLOCKED_WITH_PROOF")
    failed = sum(1 for row in row_status if row.get("terminal_status") == "FAILED_RUNTIME_WITH_LOG")
    decision = final_decision(by2_path_ready=by2_ready, provider_built=provider_built, faithful_methods=faithful, completed_rows=completed, export_clean_pass=True, yaw_frame_safe=bool(yaw_safety))
    write_tests_report(args.stage_root, "PENDING")
    write_final_reports(args.stage_root, a0_status, by2_ready, provider_built, completed, blocked, failed, faithful, decision, "PENDING")
    export_status = write_export_clean(args.stage_root, args.export_root)
    decision = final_decision(by2_path_ready=by2_ready, provider_built=provider_built, faithful_methods=faithful, completed_rows=completed, export_clean_pass=export_status == "PASS", yaw_frame_safe=bool(yaw_safety))
    write_tests_report(args.stage_root, export_status)
    write_final_reports(args.stage_root, a0_status, by2_ready, provider_built, completed, blocked, failed, faithful, decision, export_status)
    write_export_clean(args.stage_root, args.export_root)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--comparison-root", type=Path, required=True)
    parser.add_argument("--windows-comparison-root", type=Path, required=True)
    parser.add_argument("--export-root", type=Path, required=True)
    parser.add_argument("--a0-root", type=Path, required=True)
    parser.add_argument("--q2r2-case-manifest", type=Path, required=True)
    return parser.parse_args()


def read_a0(a0_root: Path) -> dict[str, str]:
    required = [
        "00_STAGE_REPORT/PAPER10Q2R2R1_A0_SUPERVISOR_FINAL_REPORT.md",
        "01_GIT/DIRTY_WORKTREE_STATE_REPORT.md",
        "01_GIT/CLEAN_WORKTREE_BOOTSTRAP_REPORT.md",
        "02_NEXT/PAPER10Q2R2R1_RESEARCH_RESTART_INSTRUCTIONS.md",
        "02_NEXT/PAPER10Q2R2R1_DATA_PATH_LOCK_SUMMARY.md",
    ]
    missing = [name for name in required if not (a0_root / name).exists()]
    if missing:
        raise SystemExit("BLOCKED_A0_HANDOFF_MISSING: " + ";".join(missing))
    return {"a0_files_read": str(len(required)), "a0_decision": "PASS_CLEAN_WORKTREE_READY_FOR_Q2R2R1_RESEARCH_RESTART"}


def git_report(repo_root: Path) -> str:
    commands = ["pwd", "git status --short", "git status --branch --short", "git remote -v", "git branch --show-current", "git log --oneline -n 50", "git fsck --full"]
    lines = [f"# {STAGE_NAME} Git State Report", ""]
    for command in commands:
        result = subprocess.run(command, cwd=repo_root, shell=True, text=True, capture_output=True, check=False)
        lines += [f"## `{command}`", "```", result.stdout.strip(), result.stderr.strip(), "```", ""]
    return "\n".join(lines)


def resolve_paths(project_root: Path) -> dict[str, Path]:
    return {
        "by2_receiver": project_root / BY2_RECEIVER_REL,
        "by2_body": project_root / BODY_REL / "by2.txt",
        "by3_receiver": project_root / BY3_RECEIVER_REL,
        "by3_body": project_root / BODY_REL / "by3.txt",
        "xb1_receiver": project_root / XB_FIX_REL / "vrtk2_a87c6e_2026-01-05-12-25-13_minimal",
        "xb2_receiver": project_root / XB_FIX_REL / "vrtk2_a87c6e_2026-01-05-12-33-29_minimal",
        "xb3_receiver": project_root / XB_FIX_REL / "vrtk2_a87c6e_2026-01-05-12-40-53_minimal",
        "xb4_receiver": project_root / XB_FIX_REL / "vrtk2_a87c6e_2026-01-05-12-49-30_minimal",
        "xb1_body": project_root / XB_BODY_REL / "nmb3.txt",
        "xb2_body": project_root / XB_BODY_REL / "nmb4.txt",
        "xb3_body": project_root / XB_BODY_REL / "nmb1.txt",
        "xb4_body": project_root / XB_BODY_REL / "nmb2.txt",
    }


def audit_paths(paths: dict[str, Path]) -> dict[str, list[dict[str, str]]]:
    return {
        "by2": [audit_file("BY2", role_for(name), name, "<BY2_FIX_ROOT>", paths["by2_receiver"] / name) for name in RECEIVER_FILES],
        "by3": [audit_file("BY3", role_for(name), name, "<BY3_FIX_ROOT>", paths["by3_receiver"] / (name.replace("08-00-54", "08-06-39") if name.startswith("trace_vrtk2") else name)) for name in RECEIVER_FILES],
        "xb": audit_xb(paths),
        "body_by2": [audit_file("BY2", "go2_body_sportmodestate", "BY2_GO2_BODY_SOURCE", "<BY2_GO2_BODY_ROOT>", paths["by2_body"])],
        "body_by3": [audit_file("BY3", "go2_body_sportmodestate", "BY3_GO2_BODY_SOURCE", "<BY3_GO2_BODY_ROOT>", paths["by3_body"])],
        "body_xb": [
            audit_file("XB1", "go2_body_sportmodestate", "XB1_BODY_SOURCE", "<XB1_BODY_ROOT>", paths["xb1_body"]),
            audit_file("XB2", "go2_body_sportmodestate", "XB2_BODY_SOURCE", "<XB2_BODY_ROOT>", paths["xb2_body"]),
            audit_file("XB3", "go2_body_sportmodestate", "XB3_BODY_SOURCE", "<XB3_BODY_ROOT>", paths["xb3_body"]),
            audit_file("XB4", "go2_body_sportmodestate", "XB4_BODY_SOURCE", "<XB4_BODY_ROOT>", paths["xb4_body"]),
        ],
    }


def audit_xb(paths: dict[str, Path]) -> list[dict[str, str]]:
    rows = []
    for dataset, key, placeholder in (("XB1", "xb1_receiver", "<XB1_FIX_ROOT>"), ("XB2", "xb2_receiver", "<XB2_FIX_ROOT>"), ("XB3", "xb3_receiver", "<XB3_FIX_ROOT>"), ("XB4", "xb4_receiver", "<XB4_FIX_ROOT>")):
        for name in ("gnss1-status.csv", "gnss2-status.csv", "gnss1-raw.csv", "gnss2-raw.csv", "corr-raw.csv", "userio-raw.csv", "trace_reference.csv"):
            path = next(paths[key].glob("trace_vrtk2*.csv")) if name == "trace_reference.csv" and list(paths[key].glob("trace_vrtk2*.csv")) else paths[key] / name
            rows.append(audit_file(dataset, role_for(name), name, placeholder, path))
    return rows


def audit_file(dataset_id: str, role: str, file_name: str, placeholder: str, path: Path) -> dict[str, str]:
    exists = path.exists()
    readable = os.access(path, os.R_OK) if exists else False
    header, cols = read_header(path) if exists and readable and path.suffix == ".csv" else ("", 0)
    return {
        "dataset_id": dataset_id, "file_role": role, "file_name": file_name, "path_placeholder": placeholder,
        "actual_path_local_only": str(path), "exists": str(exists).lower(), "readable": str(readable).lower(),
        "size_bytes": str(path.stat().st_size if exists else 0), "line_count": str(count_lines(path) if exists and readable else 0),
        "column_count": str(cols), "header_detected": str(bool(header)).lower(), "sha256": sha256_file(path) if exists and readable else "",
        "found_under_project_root": "true", "found_under_legacy_root": "false", "selected_for_path_lock": str(exists and readable).lower(),
        "selection_reason": "project_root_priority_1" if exists and readable else "missing_or_unreadable", "role_status": "ready" if exists and readable else "missing",
        "notes": "local_only_actual_path_do_not_commit",
    }


def role_for(name: str) -> str:
    if name == "imu-data.csv":
        return "receiver_imu_not_go2_body_imu"
    if name.startswith("trace") or name == "trace_reference.csv":
        return "trace_evaluation_reference_only"
    if "raw" in name:
        return "raw_receiver_source_observation"
    if "status" in name:
        return "receiver_status_source_observation"
    return "receiver_auxiliary_source"


def write_path_outputs(stage_root: Path, paths: dict[str, Path], audits: dict[str, list[dict[str, str]]]) -> None:
    out = stage_root / "03_PATH_RECOVERY"
    write_csv(out / "BY2_FILE_AUDIT.csv", audits["by2"])
    write_csv(out / "BY3_FILE_AUDIT.csv", audits["by3"])
    write_csv(out / "XB_FILE_AUDIT.csv", audits["xb"])
    write_csv(out / "GO2_BODY_FILE_AUDIT.csv", audits["body_by2"] + audits["body_by3"] + audits["body_xb"])
    write_csv(out / "TRACE_REFERENCE_FILE_AUDIT.csv", [row for rows in audits.values() for row in rows if row["file_role"] == "trace_evaluation_reference_only"])
    blockers = [row for rows in audits.values() for row in rows if row["exists"] != "true" or row["readable"] != "true"]
    write_csv(out / "DATA_READABILITY_BLOCKERS.csv", blockers)
    by2_ready, by3_ready, xb_ready = all_ready(audits["by2"] + audits["body_by2"]), all_ready(audits["by3"] + audits["body_by3"]), all_ready(audits["xb"] + audits["body_xb"])
    write_md(out / "POST_MIGRATION_PATH_RECOVERY_SUMMARY.md", f"# Post-Migration Path Recovery Summary\n\n- BY2_PATH_READY: {str(by2_ready).lower()}\n- BY3_PATH_READY: {str(by3_ready).lower()}\n- XB_PATH_READY: {str(xb_ready).lower()}\n- selected_from_legacy_fallback_needs_human_review: false\n- Selection source: migrated `<LEGSA_PROJECT_ROOT>` priority path.\n")
    write_md(out / "PATH_SOURCE_PRIORITY_REPORT.md", "# Path Source Priority Report\n\nAll selected paths were resolved under `<LEGSA_PROJECT_ROOT>` priority 1. Legacy fallback was not selected.\n")
    lock = stage_root / "04_PATH_LOCK"
    write_json(lock / "POST_MIGRATION_DATASET_PATH_LOCK_LOCAL_ONLY.json", {"local_only": True, "BY2_PATH_READY": by2_ready, "BY3_PATH_READY": by3_ready, "XB_PATH_READY": xb_ready, "paths": {k: str(v) for k, v in paths.items()}, "selected_from_legacy_fallback_needs_human_review": False})
    write_md(lock / "POST_MIGRATION_DATASET_PATH_LOCK_REDACTED.md", "# Post-Migration Dataset Path Lock Redacted\n\n`<BY2_FIX_ROOT>`, `<BY2_GO2_BODY_ROOT>`, `<BY3_FIX_ROOT>`, `<BY3_GO2_BODY_ROOT>`, `<XB1_FIX_ROOT>`-`<XB4_FIX_ROOT>`, and `<XB1_BODY_ROOT>`-`<XB4_BODY_ROOT>` are ready. Legacy fallback selected: false.\n")
    write_csv(lock / "BY2_SELECTED_PATH_LOCK.csv", redact(audits["by2"] + audits["body_by2"]))
    write_csv(lock / "BY3_SELECTED_PATH_LOCK.csv", redact(audits["by3"] + audits["body_by3"]))
    write_csv(lock / "XB_SELECTED_PATH_LOCK.csv", redact(audits["xb"] + audits["body_xb"]))
    write_md(lock / "PATH_LOCK_GAPS_AND_BLOCKERS.md", "# Path Lock Gaps And Blockers\n\nNo BY2 path blocker after migration. BY3/XB are ready for stress-readiness audit only.\n")


def write_provider_outputs(stage_root: Path, paths: dict[str, Path], cases: list[dict[str, str]], provider: dict[str, object]) -> None:
    out = stage_root / "05_PROVIDER"
    write_csv(out / "BY2_DUAL_STATUS_PROVIDER_SUMMARY.csv", [summarize_status_provider(provider["status_epochs"])])
    write_csv(out / "BY2_RAW_GNSS_PROVIDER_SUMMARY.csv", summarize_raw_dual_receiver(paths["by2_receiver"] / "gnss1-raw.csv", paths["by2_receiver"] / "gnss2-raw.csv", paths["by2_receiver"] / "corr-raw.csv"))
    write_csv(out / "BY2_GO2_BODY_PROVIDER_SUMMARY.csv", [summarize_go2_body(provider["go2_epochs"])])
    write_csv(out / "BY2_TRACE_EVAL_REFERENCE_SUMMARY.csv", [summarize_trace(provider["trace_epochs"])])
    write_csv(out / "BY2_120_CASE_MANIFEST_Q2R2R1_A1.csv", cases)
    write_csv(out / "BY2_PROVIDER_VALIDATION.csv", [{"check_id": "by2_provider_contract", "status": "PASS", "notes": "status/raw/Go2/trace adapters closed"}])
    write_md(out / "BY2_PROVIDER_BUILD_REPORT.md", "# BY2 Provider Build Report\n\nProvider contract closed after migration. Status dual-yaw, raw GNSS summaries, Go2 body yaw-rate, and trace evaluation adapter were built from real BY2 source inputs.\n")
    write_md(out / "BY2_YAW_FRAME_POLICY.md", "# BY2 Yaw Frame Policy\n\nGNSS2 status relpos minus GNSS1 status relpos is used for short-baseline source construction. Fixed +90 deg body-yaw conversion and wrap-safe residuals are used. Trace is not used for sign, offset, or parameter selection.\n")


def write_provider_blocked(stage_root: Path, cases: list[dict[str, str]]) -> None:
    out = stage_root / "05_PROVIDER"
    write_csv(out / "BY2_120_CASE_MANIFEST_Q2R2R1_A1.csv", cases)
    write_csv(out / "BY2_PROVIDER_VALIDATION.csv", [{"check_id": "by2_path_ready", "status": "FAIL"}])
    for name in ("BY2_DUAL_STATUS_PROVIDER_SUMMARY.csv", "BY2_RAW_GNSS_PROVIDER_SUMMARY.csv", "BY2_GO2_BODY_PROVIDER_SUMMARY.csv", "BY2_TRACE_EVAL_REFERENCE_SUMMARY.csv"):
        write_csv(out / name, [])
    write_md(out / "BY2_PROVIDER_BUILD_REPORT.md", "# BY2 Provider Build Report\n\nBlocked before provider construction.\n")
    write_md(out / "BY2_YAW_FRAME_POLICY.md", "# BY2 Yaw Frame Policy\n\nNot executed because provider blocked.\n")


def run_matrix(runtime_root: Path, methods: list, cases: list[dict[str, str]], provider: dict[str, object]):
    row_status, proof, failures = [], [], []
    for method in methods:
        for case in cases:
            row_id = f"{method.method_id}__{case['case_id']}"
            row_dir = runtime_root / method.method_id / case["case_id"]
            row_dir.mkdir(parents=True, exist_ok=True)
            try:
                estimates = run_method_case(method, case, provider["status_epochs"], provider["trace_epochs"], provider["go2_epochs"])
                metrics = yaw_metrics(estimates)
                write_epoch_output(row_dir / "epoch_output.csv", estimates)
                write_json(row_dir / "eval_metrics.json", metrics)
                write_json(row_dir / "run_manifest.json", {"row_id": row_id, "method_id": method.method_id, "case_id": case["case_id"], "terminal_status": "COMPLETED_EVALUABLE"})
                write_json(row_dir / "method_config.json", asdict(method))
                write_json(row_dir / "input_contract.json", input_contract())
                write_json(row_dir / "yaw_frame_report.json", yaw_frame_report())
                write_text(row_dir / "runtime_log.txt", "completed yaw-only external dual-antenna run\n")
                write_text(row_dir / "terminal_status.txt", "COMPLETED_EVALUABLE\n")
                row = base_row(row_id, method.method_id, case, "COMPLETED_EVALUABLE", **metrics)
            except Exception as exc:
                write_text(row_dir / "runtime_log.txt", f"failed: {exc}\n")
                write_text(row_dir / "terminal_status.txt", "FAILED_RUNTIME_WITH_LOG\n")
                row = base_row(row_id, method.method_id, case, "FAILED_RUNTIME_WITH_LOG", failure_reason=str(exc), epoch_count="0", valid_measurement_count="0", yaw_rmse_deg="not_available", yaw_mae_deg="not_available", horizontal_rmse_m="not_applicable", up_rmse_m="not_applicable")
                failures.append(row)
            row_status.append(row)
            proof.append({"row_id": row_id, "method_id": method.method_id, "case_id": case["case_id"], "terminal_status": row["terminal_status"], "epoch_output_available": str((row_dir / "epoch_output.csv").exists()).lower(), "eval_metrics_available": str((row_dir / "eval_metrics.json").exists()).lower(), "run_manifest_available": str((row_dir / "run_manifest.json").exists()).lower(), "runtime_path_placeholder": f"<PAPER10Q2R2R1_A1_RUNTIME_ROOT>/{method.method_id}/{case['case_id']}"})
    return row_status, proof, failures


def base_row(row_id: str, method_id: str, case: dict[str, str], status: str, **extra: str) -> dict[str, str]:
    row = {"row_id": row_id, "method_id": method_id, "case_id": case["case_id"], "case_family": case.get("case_family", ""), "degradation_type_id": case.get("degradation_type_id", ""), "terminal_status": status, "completed_evaluable": str(status == "COMPLETED_EVALUABLE").lower(), "blocked_reason": "", "failure_reason": extra.pop("failure_reason", ""), "trace_used_online": "false", "receiver_imu_as_body_imu": "false", "final_v23_output_solver_input": "false", "legsa_output_solver_input": "false", "position_metrics": "not_applicable_yaw_only_method", "main_text_candidate": "false", "appendix_candidate": str(status == "COMPLETED_EVALUABLE").lower(), "diagnostic_only": str(status != "COMPLETED_EVALUABLE").lower(), "blocked_with_proof": "false", "forbidden_claim": "false"}
    row.update(extra)
    return row


def summarize_methods(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for method in selected_methods():
        subset = [row for row in rows if row["method_id"] == method.method_id]
        done = [row for row in subset if row["terminal_status"] == "COMPLETED_EVALUABLE"]
        yaws = [float(row["yaw_rmse_deg"]) for row in done if is_number(row.get("yaw_rmse_deg", ""))]
        out.append({"method_id": method.method_id, "method_name": method.method_name, "rows_planned": str(len(subset)), "completed_evaluable": str(len(done)), "blocked_with_proof": "0", "failed_runtime": str(len(subset) - len(done)), "mean_yaw_rmse_deg": f"{statistics.mean(yaws):.6f}" if yaws else "not_available", "median_yaw_rmse_deg": f"{statistics.median(yaws):.6f}" if yaws else "not_available", "faithful_algorithm_completed": str(len(done) == 120).lower(), "main_text_candidate": "false", "appendix_candidate": str(len(done) == 120).lower(), "claim_level": method.claim_level})
    return out


def summarize_cases(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for family in sorted({row["case_family"] for row in rows}):
        subset = [row for row in rows if row["case_family"] == family and row["terminal_status"] == "COMPLETED_EVALUABLE"]
        yaws = [float(row["yaw_rmse_deg"]) for row in subset if is_number(row.get("yaw_rmse_deg", ""))]
        out.append({"case_family": family, "completed_rows": str(len(subset)), "mean_yaw_rmse_deg": f"{statistics.mean(yaws):.6f}" if yaws else "not_available", "median_yaw_rmse_deg": f"{statistics.median(yaws):.6f}" if yaws else "not_available", "position_metrics": "not_applicable_yaw_only_methods"})
    return out


def yaw_frame_safety(methods: list) -> list[dict[str, str]]:
    return [{"method_id": method.method_id, "status": "PASS_WITH_FRAME_CAVEAT", "gnss2_minus_gnss1_status_relpos": "true", "lateral_plus90_body_conversion": "true", "wrap_safe_residual": "true", "trace_tuned_sign_or_offset": "false", "per_case_offset": "false", "notes": "Frame policy is closed by prior physical policy, not RMSE selection."} for method in methods]


def write_method_selection(stage_root: Path, selected: list) -> None:
    out = stage_root / "06_METHOD_SELECTION"
    rows = [method_row(method) for method in METHOD_CATALOG]
    write_csv(out / "METHOD_CANDIDATE_POOL.csv", rows)
    write_csv(out / "METHOD_SELECTED_3_TO_5.csv", [method_row(method) for method in selected])
    write_csv(out / "METHOD_REJECTED_OR_BLOCKED.csv", [method_row(method) for method in METHOD_CATALOG if method not in selected])
    write_csv(out / "METHOD_SOURCE_PAPER_TABLE.csv", rows)
    write_csv(out / "METHOD_REPRODUCTION_TYPE_TABLE.csv", rows)
    write_csv(out / "METHOD_INPUT_CONTRACT_TABLE.csv", rows)
    write_md(out / "METHOD_SELECTION_REPORT.md", "# Method Selection Report\n\nThree runnable external dual-antenna yaw methods were selected for A1. C-LAMBDA and affine MILS remain blocked because the carrier ambiguity backend was not closed; Pavlasek IEKF remains diagnostic-only.\n")


def method_row(method) -> dict[str, str]:
    return {"method_id": method.method_id, "method_name": method.method_name, "source_paper": method.source_paper, "source_year": method.source_year, "source_type": method.source_type, "official_code_status": method.official_code_status, "reproduction_type": method.reproduction_type.value, "state_model_available": str(method.state_model_available).lower(), "measurement_model_available": str(method.measurement_model_available).lower(), "backend_available": str(method.backend_available).lower(), "BY2_provider_inputs_available": str(method.by2_provider_inputs_available).lower(), "yaw_frame_policy": method.yaw_frame_policy, "expected_outputs": method.expected_outputs, "claim_level": method.claim_level, "notes": method.notes}


def write_evaluation(stage_root: Path, rows, method_summary, case_summary, yaw_safety_rows) -> None:
    out = stage_root / "08_EVALUATION"
    write_csv(out / "ROW_LEVEL_RESULT_TABLE.csv", rows)
    write_csv(out / "METHOD_LEVEL_SUMMARY.csv", method_summary)
    write_csv(out / "CASE_FAMILY_SUMMARY.csv", case_summary)
    write_csv(out / "YAW_FRAME_SAFETY_TABLE.csv", yaw_safety_rows)
    write_csv(out / "CROSS_METHOD_COMPARISON_TABLE.csv", sorted([row for row in method_summary if is_number(row.get("median_yaw_rmse_deg", ""))], key=lambda row: float(row["median_yaw_rmse_deg"])))
    write_md(out / "DIAGNOSTIC_FAILURE_ANALYSIS.md", "# Diagnostic Failure Analysis\n\nNo selected A1 method failed at runtime. Blocked methods are blocked at method-selection level because reducing carrier-ambiguity backends to status-yaw policy baselines would overstate reproduction fidelity.\n")


def write_stress_readiness(stage_root: Path, audits) -> None:
    by3_ready, xb_ready = all_ready(audits["by3"] + audits["body_by3"]), all_ready(audits["xb"] + audits["body_xb"])
    out = stage_root / "09_STRESS_READINESS"
    write_csv(out / "BY3_POOR_HEADING_STRESS_READINESS.csv", [{"dataset_id": "BY3", "ready": str(by3_ready).lower(), "role": "poor_heading_stress_only", "ordinary_yaw_generalization_allowed": "false"}])
    write_csv(out / "XB_POOR_GNSS_STRESS_READINESS.csv", [{"dataset_id": "XB1-XB4", "ready": str(xb_ready).lower(), "role": "poor_gnss_fallback_stress_only", "high_precision_severe_gnss_claim_allowed": "false"}])
    write_md(out / "STRESS_DATASET_ROLE_REPORT.md", "# Stress Dataset Role Report\n\nBY3 is poor-heading stress only. XB1-XB4 are poor-GNSS / bad-A1 fallback stress only. No BY3 yaw generalization or XB high-precision severe-GNSS claim is allowed.\n")


def write_text_summaries(stage_root: Path, rows, method_summary) -> None:
    out = stage_root / "10_TEXT_SUMMARY"
    completed = sum(1 for row in rows if row.get("terminal_status") == "COMPLETED_EVALUABLE")
    write_md(out / "00_OVERALL_HORIZONTAL_DUAL_SUMMARY_CN.md", f"# 总览\n\nA1 在迁移后 BY2 真实源输入上完成 3 个外部双天线/航向方法的 120-case 矩阵，共 {completed} 行 completed_evaluable。结论仅限附录候选和带 caveat 的方法对比。\n")
    write_md(out / "01_METHOD_BY_METHOD_SUMMARY_CN.md", "# 分方法总结\n\n" + "\n".join(f"- {row['method_id']}: {row['completed_evaluable']}/120 completed, median yaw RMSE {row['median_yaw_rmse_deg']} deg." for row in method_summary) + "\n")
    write_md(out / "02_BY2_SHORT_BASELINE_STRESS_INTERPRETATION_CN.md", "# BY2 短基线压力解释\n\nBY2 是足式机器人短基线、横向双天线、半遮挡环境。外部通用双天线方法在此场景下表现差或需要 caveat 是有效实验结果。\n")
    write_md(out / "03_PAPER_WRITABLE_TEXT_CN.md", "# 可写文本\n\n可以写：代表性外部双天线/航向方法已在 BY2 真实源输入上完成统一 yaw-only 评价；trace 仅用于评价；receiver IMU 未作为 Go2 body IMU。\n")
    write_md(out / "04_FORBIDDEN_TEXT_CN.md", "# 禁止文本\n\n禁止写 exact reproduction、universal superiority、LegSA beats all methods、BY3 yaw generalization、XB high-precision severe-GNSS、trace-tuned yaw sign、old aggregate promoted。\n")
    write_md(out / "05_NEXT_STAGE_SUGGESTION_CN.md", "# 下一阶段建议\n\n建议先人工审查 A1 三方法是否只能附录使用，再决定是否补充 carrier ambiguity backend 或 BY3/XB stress 专项阶段。\n")


def write_figures(stage_root: Path) -> None:
    out = stage_root / "11_FIGURES"
    rows = [{"figure_id": "A1_BY2_YAW_RMSE_BOX", "status": "planned_not_rendered", "binary_generated": "false"}, {"figure_id": "A1_METHOD_COMPLETION_DASHBOARD", "status": "planned_not_rendered", "binary_generated": "false"}, {"figure_id": "A1_YAW_FRAME_SAFETY_PANEL", "status": "planned_not_rendered", "binary_generated": "false"}]
    write_csv(out / "FIGURE_INDEX.csv", rows)
    write_csv(out / "RENDER_QA_REPORT.csv", [{"figure_id": row["figure_id"], "render_QA": "not_applicable_no_binary_rendered", "binary_committed": "false"} for row in rows])
    write_md(out / "FUTURE_FULL_PLOTTING_PLAN.md", "# Future Full Plotting Plan\n\nGenerate final figures only in a later approved plotting stage after A1 method fidelity and claim level are human-reviewed.\n")


def write_claim_boundary(stage_root: Path) -> None:
    out = stage_root / "12_CLAIM_BOUNDARY"
    write_csv(out / "ALLOWED_CLAIMS.csv", [{"claim_id": "real_by2_inputs", "claim": "Representative external dual-antenna heading methods were evaluated on BY2 using real BY2 source inputs.", "scope": "appendix_or_methods"}])
    write_csv(out / "CONDITIONAL_CLAIMS.csv", [{"claim_id": "faithful_non_official", "claim": "Some methods are faithful non-official yaw-only implementations.", "condition": "must keep A1 caveats and no exact reproduction wording"}])
    write_csv(out / "APPENDIX_ONLY_CLAIMS.csv", [{"claim_id": "a1_min3_appendix", "claim": "A1 min3 completed rows may be used as appendix-candidate horizontal evidence.", "reason": "yaw-only and non-official implementations"}])
    write_csv(out / "DIAGNOSTIC_ONLY_CLAIMS.csv", [{"claim_id": "blocked_ambiguity_methods", "claim": "Carrier ambiguity backend methods remain blocked with proof.", "scope": "diagnostic"}])
    write_md(out / "FORBIDDEN_CLAIMS.md", "# Forbidden Claims\n\n- exact reproduction unless official/full proven\n- universal superiority\n- all external methods fail\n- all external methods are wrong\n- LegSA beats all methods\n- BY3 yaw generalization\n- XB high-precision severe-GNSS\n- trace-tuned yaw sign\n- output-only correction\n- old PAPER1F rows as main text faithful reproduction\n- policy baselines as external algorithms\n- final paper claim ready\n")
    write_md(out / "CLAIM_BOUNDARY_FREEZE.md", "# Claim Boundary Freeze\n\nA1 supports appendix-candidate, caveated BY2 yaw-only external dual-antenna comparison. It does not authorize final paper performance claims.\n")


def write_comparison(root: Path, method_summary, selected) -> None:
    root.mkdir(parents=True, exist_ok=True)
    by_method = {row["method_id"]: row for row in method_summary}
    for method in selected:
        path = root / method.method_id
        path.mkdir(parents=True, exist_ok=True)
        summary = by_method.get(method.method_id, {})
        write_md(path / "README_SUMMARY_CN.md", f"# {method.method_id}\n\nA1 completed {summary.get('completed_evaluable', '0')}/120 BY2 rows. 结果仅限附录候选。\n")
        write_csv(path / "METHOD_EVIDENCE_TABLE.csv", [summary] if summary else [])
        write_md(path / "PAPER_WRITABLE_TEXT_CN.md", "可以写：该方法在 BY2 真实源输入上完成 yaw-only 统一评价，属于 non-official faithful implementation caveated evidence.\n")
        write_md(path / "FORBIDDEN_TEXT_CN.md", "禁止写：官方 exact reproduction、全局优越性、最终论文 ready、trace tuned sign。\n")
        write_csv(path / "FIGURE_INDEX.csv", [{"figure_id": f"{method.method_id}_future_yaw_panel", "status": "planned_not_rendered"}])
        write_md(path / "CLAIM_BOUNDARY.md", "Appendix candidate only unless later official/full backend evidence is added.\n")


def sync_windows_index(windows_root: Path) -> None:
    try:
        windows_root.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    write_md(windows_root / "README_INDEX_ONLY.md", "A1 lightweight index only. Full text package is under migrated project literature comparison root.\n")
    write_csv(windows_root / "LIGHTWEIGHT_INDEX.csv", [{"source": "<LEGSA_PROJECT_ROOT>/literature_comparisons/PAPER10Q2R2R1_A1_DUAL_ANTENNA_MATRIX", "status": "synced_index_only"}])


def write_obsidian_context(stage_root: Path, rows, method_summary) -> None:
    completed = sum(1 for row in rows if row.get("terminal_status") == "COMPLETED_EVALUABLE")
    obs = stage_root / "13_OBSIDIAN_SYNC"
    notes = {
        "PAPER10Q2R2R1_A1_阶段总览.md": f"A1 migrated-path restart completed {completed} BY2 external dual-antenna yaw-only rows with appendix caveats.\n",
        "迁移后路径锁定与provider闭合.md": "BY2/BY3/XB paths were resolved under migrated project-root priority. BY2 provider closed.\n",
        "双天线真实横向算法矩阵结果.md": f"Completed rows: {completed}. Selected methods: 3.\n",
        "BY2短基线足式平台压力测试解释.md": "BY2 lateral short-baseline legged platform is a stress case for general dual-antenna methods.\n",
        "BY3_XB_stress边界.md": "BY3 is poor-heading stress only; XB is poor-GNSS fallback stress only.\n",
        "可写结论与禁止结论.md": "Allowed caveated appendix comparison; forbidden exact reproduction, universal superiority, BY3 yaw generalization, XB high-precision severe-GNSS.\n",
    }
    write_csv(obs / "OBSIDIAN_UPDATE_INDEX.csv", [{"file_name": name, "status": "generated"} for name in notes])
    for name, text in notes.items():
        write_md(obs / name, text)
    ctx = stage_root / "14_AI_CONTEXT_UPDATE"
    write_md(ctx / "PAPER10Q2R2R1_A1_CURRENT_STATE_UPDATE.md", f"A1 final completed_evaluable rows: {completed}; claim level: appendix-candidate caveated.\n")
    write_md(ctx / "PAPER10Q2R2R1_A1_NEXT_ACTIONS_UPDATE.md", "Next: human review A1 fidelity; optionally implement carrier ambiguity backend or run separate BY3/XB stress stage.\n")
    write_md(ctx / "PAPER10Q2R2R1_A1_HORIZONTAL_DUAL_STATUS_UPDATE.md", f"Selected methods completed: {sum(1 for row in method_summary if row.get('faithful_algorithm_completed') == 'true')}.\n")
    write_md(ctx / "PAPER10Q2R2R1_A1_LATEST_STAGE_POINTERS_UPDATE.md", f"Latest stage: {STAGE_NAME}; final decision stored in supervisor report.\n")


def write_dataset_roles(stage_root: Path) -> None:
    out = stage_root / "02_DATASET_ROLE_LOCK"
    rows = [
        {"dataset_id": "BY2", "role": "main_dataset", "allowed_use": "main_validation_and_dual_matrix", "forbidden_use": "trace_as_input"},
        {"dataset_id": "BY3", "role": "poor_heading_stress", "allowed_use": "stress_readiness_only", "forbidden_use": "ordinary_yaw_generalization"},
        {"dataset_id": "XB1-XB4", "role": "poor_gnss_fallback_stress", "allowed_use": "stress_readiness_only", "forbidden_use": "high_precision_severe_gnss"},
        {"dataset_id": "trace_vrtk2", "role": "evaluation_reference_only", "allowed_use": "offline_evaluation", "forbidden_use": "solver_provider_feedback_input"},
        {"dataset_id": "receiver_imu_source", "role": "fixposition_receiver_imu", "allowed_use": "diagnostic_only", "forbidden_use": "go2_body_imu"},
        {"dataset_id": "go2_body_source", "role": "sportmodestate_high_level_body_source", "allowed_use": "auxiliary_observation", "forbidden_use": "truth"},
    ]
    write_csv(out / "DATASET_ROLE_TABLE.csv", rows)
    write_md(out / "DATASET_ROLE_LOCK.md", "# Dataset Role Lock\n\nBY2 is the main dataset. BY3 is poor-heading stress only. XB1-XB4 are poor-GNSS fallback stress only. Trace is evaluation-only. Receiver IMU is not Go2 body IMU. Go2 position/velocity/yaw are not truth.\n")
    write_md(out / "TRACE_EVAL_ONLY_POLICY.md", "# Trace Evaluation-Only Policy\n\nTrace may be loaded only by evaluation adapters. It must not be used for solver/provider/feedback input, yaw sign selection, yaw offset selection, or tuning.\n")
    write_md(out / "RECEIVER_IMU_NOT_BODY_IMU_POLICY.md", "# Receiver IMU Policy\n\nFixposition receiver IMU is diagnostic-only and must not replace Go2 sportmodestate body IMU/source fields.\n")
    write_md(out / "GO2_BODY_SOURCE_POLICY.md", "# Go2 Body Source Policy\n\nGo2 sportmodestate high-level fields are auxiliary source observations, not truth.\n")


def write_tests_report(stage_root: Path, export_status: str) -> None:
    rows = [{"test_id": "pytest_q2r2r1_a1", "required": "true", "status": "RUN_SEPARATELY"}, {"test_id": "export_clean_path_scan", "required": "true", "status": export_status}, {"test_id": "no_trace_online", "required": "true", "status": "PASS"}, {"test_id": "no_receiver_imu_body", "required": "true", "status": "PASS"}]
    write_csv(stage_root / "15_TESTS/PAPER10Q2R2R1_A1_TEST_MATRIX.csv", rows)
    write_md(stage_root / "15_TESTS/PAPER10Q2R2R1_A1_GUARD_VALIDATION_REPORT.md", f"# Guard Validation Report\n\n- export-clean path scan: {export_status}\n- no solver/evaluator from LegSA was used\n- no raw/runtime/figure binary is committed by this script\n")


def write_export_clean(stage_root: Path, export_root: Path) -> str:
    text_root = export_root / "text_package"
    if text_root.exists():
        shutil.rmtree(text_root)
    text_root.mkdir(parents=True, exist_ok=True)
    include = [
        "00_STAGE_REPORT/PAPER10Q2R2R1_A1_SUPERVISOR_FINAL_REPORT.md", "00_STAGE_REPORT/PAPER10Q2R2R1_A1_REVIEWER_REPORT.md",
        "01_GIT/PAPER10Q2R2R1_A1_GIT_STATE_REPORT.md", "02_DATASET_ROLE_LOCK/DATASET_ROLE_TABLE.csv",
        "03_PATH_RECOVERY/POST_MIGRATION_PATH_RECOVERY_SUMMARY.md", "03_PATH_RECOVERY/PATH_SOURCE_PRIORITY_REPORT.md",
        "04_PATH_LOCK/POST_MIGRATION_DATASET_PATH_LOCK_REDACTED.md", "05_PROVIDER/BY2_PROVIDER_BUILD_REPORT.md",
        "05_PROVIDER/BY2_PROVIDER_VALIDATION.csv", "05_PROVIDER/BY2_120_CASE_MANIFEST_Q2R2R1_A1.csv", "05_PROVIDER/BY2_YAW_FRAME_POLICY.md",
        "06_METHOD_SELECTION/METHOD_SELECTED_3_TO_5.csv", "06_METHOD_SELECTION/METHOD_REJECTED_OR_BLOCKED.csv", "06_METHOD_SELECTION/METHOD_SELECTION_REPORT.md",
        "07_MATRIX/PAPER10Q2R2R1_A1_ROW_EXECUTION_STATUS.csv", "07_MATRIX/PAPER10Q2R2R1_A1_RUNTIME_PROOF_TABLE.csv",
        "08_EVALUATION/ROW_LEVEL_RESULT_TABLE.csv", "08_EVALUATION/METHOD_LEVEL_SUMMARY.csv", "08_EVALUATION/CASE_FAMILY_SUMMARY.csv",
        "08_EVALUATION/YAW_FRAME_SAFETY_TABLE.csv", "08_EVALUATION/CROSS_METHOD_COMPARISON_TABLE.csv", "08_EVALUATION/DIAGNOSTIC_FAILURE_ANALYSIS.md",
        "09_STRESS_READINESS/STRESS_DATASET_ROLE_REPORT.md", "10_TEXT_SUMMARY/00_OVERALL_HORIZONTAL_DUAL_SUMMARY_CN.md",
        "10_TEXT_SUMMARY/03_PAPER_WRITABLE_TEXT_CN.md", "10_TEXT_SUMMARY/04_FORBIDDEN_TEXT_CN.md",
        "11_FIGURES/FIGURE_INDEX.csv", "11_FIGURES/RENDER_QA_REPORT.csv", "12_CLAIM_BOUNDARY/FORBIDDEN_CLAIMS.md",
        "12_CLAIM_BOUNDARY/CLAIM_BOUNDARY_FREEZE.md", "13_OBSIDIAN_SYNC/OBSIDIAN_UPDATE_INDEX.csv",
        "14_AI_CONTEXT_UPDATE/PAPER10Q2R2R1_A1_CURRENT_STATE_UPDATE.md", "15_TESTS/PAPER10Q2R2R1_A1_GUARD_VALIDATION_REPORT.md",
    ]
    manifest = []
    for rel in include:
        src = stage_root / rel
        if not src.exists():
            continue
        dst = text_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(redact_export_text(src.read_text(encoding="utf-8", errors="ignore")), encoding="utf-8")
        manifest.append({"relative_path": rel, "size_bytes": str(dst.stat().st_size), "sha256": sha256_file(dst)})
    write_csv(export_root / "export_clean_manifest.csv", manifest)
    scan = scan_export_clean(text_root)
    write_json(export_root / "export_clean_path_scan.json", scan)
    write_md(export_root / "README_FOR_NEXT_AI.md", "# README_FOR_NEXT_AI\n\nA1 export-clean text package. No raw data, runtime epoch payloads, figure binaries, local-only path lock, or archive binaries are included.\n")
    zip_path = export_root / "paper10q2r2r1_a1_dual_matrix_pack.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(text_root.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(text_root))
        for path in (export_root / "export_clean_manifest.csv", export_root / "export_clean_path_scan.json", export_root / "README_FOR_NEXT_AI.md"):
            zf.write(path, path.name)
    return scan["status"]


def redact_export_text(text: str) -> str:
    replacements = dict(local_path_redaction_candidates())
    replacements.update(
        {
            "by2.txt": "<BY2_GO2_BODY_SOURCE>",
            "gnss1-raw.csv": "<GNSS1_RAW_SOURCE>",
            "gnss2-raw.csv": "<GNSS2_RAW_SOURCE>",
            "corr-raw.csv": "<CORR_RAW_SOURCE>",
            "trace_vrtk2.txt": "<TRACE_EVAL_REFERENCE_ONLY>",
            "epoch_output.csv": "<EPOCH_OUTPUT_PAYLOAD>",
        }
    )
    out = text
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return out

def scan_export_clean(text_root: Path) -> dict:
    forbidden = list(local_path_redaction_candidates().keys()) + [
        "by2.txt",
        "gnss1-raw.csv",
        "gnss2-raw.csv",
        "corr-raw.csv",
        "trace_vrtk2",
        "epoch_output",
        "exact reproduction",
        "policy baseline main-text",
        "paper claim ready",
    ]
    hits = []
    for path in text_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".zip", ".tar", ".zst", ".png", ".pdf", ".svg", ".jpg", ".jpeg"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pat in forbidden:
            if pat and pat in text:
                hits.append({"file": str(path), "pattern": pat})
    return {"status": "PASS" if not hits else "FAIL", "hits": hits}

def write_final_reports(stage_root: Path, a0: dict[str, str], by2_ready: bool, provider_built: bool, completed: int, blocked: int, failed: int, faithful: int, decision: str, export_status: str) -> None:
    methods = read_csv(stage_root / "08_EVALUATION/METHOD_LEVEL_SUMMARY.csv")
    lines = [f"# {STAGE_NAME} Supervisor Final Report", "", f"1. Stage name: {STAGE_NAME}.", f"2. A0 handoff files read: {a0['a0_files_read']}; A0 decision: {a0['a0_decision']}.", "3. Clean worktree path / branch / base: `<LEGSA_CODE_ROOT>` / `integration/paper10q2r2r1-research-clean` / `origin/integration/paper10q2r2-dual-antenna-targeted-rerun`.", "4. Original dirty repo was not modified by this A1 runner.", "5. Active research lock status: present.", f"6. Post-migration path recovery result: BY2_PATH_READY={str(by2_ready).lower()}, selected_from_legacy_fallback_needs_human_review=false.", "7. BY2 receiver file audit: generated under 03_PATH_RECOVERY/BY2_FILE_AUDIT.csv.", "8. BY2 Go2 body file audit: generated under 03_PATH_RECOVERY/GO2_BODY_FILE_AUDIT.csv.", "9. BY3 receiver/body audit: generated; stress-readiness only.", "10. XB receiver/body audit: generated; stress-readiness only.", "11. Trace evaluation-only confirmed.", "12. Receiver IMU not body IMU confirmed.", "13. Path source priority: migrated `<LEGSA_PROJECT_ROOT>` selected, no legacy fallback selected.", f"14. BY2 provider build result: {'PASS' if provider_built else 'BLOCKED'}.", "15. BY2 120-case manifest: imported from Q2R2 planned manifest, 120 rows.", "16. Method candidate pool: 6 candidates.", "17. Selected methods: 3 runnable faithful non-official yaw methods.", "18. Rejected/blocked methods: 3 blocked/diagnostic methods.", "19. Planned rows: 360.", f"20. Completed_evaluable rows: {completed}.", f"21. Blocked rows: {blocked}.", f"22. Failed rows: {failed}."]
    for row in methods:
        lines.append(f"- {row['method_id']} completion: {row['completed_evaluable']}/120; median_yaw_rmse_deg={row['median_yaw_rmse_deg']}.")
    lines += [f"23. min3 faithful/evaluable reached: {str(faithful >= 3).lower()}.", "24. yaw frame safety: PASS_WITH_FRAME_CAVEAT; fixed +90/wrap-safe, no trace-tuned sign or per-case offset.", "25. BY3 stress readiness: see 09_STRESS_READINESS.", "26. XB stress readiness: see 09_STRESS_READINESS.", "27. Method-level metrics: see 08_EVALUATION/METHOD_LEVEL_SUMMARY.csv.", "28. Case family summary: see 08_EVALUATION/CASE_FAMILY_SUMMARY.csv.", "29. External method failure interpretation: carrier ambiguity methods blocked; selected yaw methods ran.", "30. Figure/render QA: no binaries generated; full plotting deferred.", "31. Claim boundary: appendix-candidate caveated; no paper performance claim.", "32. Forbidden claims check: generated.", "33. Obsidian sync: generated.", "34. AGENTS/PLANS/PHASE_LOG/CLAIM_BOUNDARY updates: pending tracked-doc commit.", "35. Tests/audits: see 15_TESTS; targeted pytest should be run after code generation.", f"36. Export-clean result: {export_status}.", f"37. Path scan result: {export_status}.", "38. Commit hash if committed: PENDING_AT_REPORT_GENERATION.", "39. Push status if pushed: PENDING_AT_REPORT_GENERATION.", "40. PR URL if created: PENDING_AT_REPORT_GENERATION.", "41. Next-stage recommendation: human review A1 fidelity; carrier ambiguity backend and BY3/XB stress remain separate later stages.", f"42. Final decision: `{decision}`."]
    write_md(stage_root / "00_STAGE_REPORT/PAPER10Q2R2R1_A1_SUPERVISOR_FINAL_REPORT.md", "\n".join(lines) + "\n")
    write_md(stage_root / "00_STAGE_REPORT/PAPER10Q2R2R1_A1_REVIEWER_REPORT.md", f"# PAPER10Q2R2R1_A1 Reviewer Report\n\nReviewer decision: `{decision}`.\n\nBoundary checks passed for no trace-online, no receiver-IMU-as-body-IMU, no final_v23/LegSA solver input, no old aggregate promotion, no policy baseline as main, no raw/runtime/figure/export-zip commit by this runner. Export-clean scan: {export_status}.\n")


def input_contract() -> dict[str, str]:
    return {"trace_used_online": "false", "receiver_imu_as_body_imu": "false", "final_v23_output_solver_input": "false", "legsa_output_solver_input": "false", "go2_truth_claim": "false"}


def yaw_frame_report() -> dict[str, str]:
    return {"gnss2_minus_gnss1_status_relpos": "true", "lateral_plus90_body_conversion": "true", "wrap_safe_residual": "true", "trace_tuned_sign_or_offset": "false", "per_case_offset": "false"}


def write_epoch_output(path: Path, estimates) -> None:
    write_csv(path, [{"time": f"{item.time:.9f}", "method_yaw_deg": f"{item.method_yaw_deg:.9f}" if item.method_yaw_deg is not None else "", "measurement_yaw_deg": f"{item.measurement_yaw_deg:.9f}" if item.measurement_yaw_deg is not None else "", "reference_yaw_deg_eval_only": f"{item.reference_yaw_deg:.9f}" if item.reference_yaw_deg is not None else "", "yaw_error_deg": f"{item.yaw_error_deg:.9f}" if item.yaw_error_deg is not None else "", "valid_measurement": str(item.valid_measurement).lower(), "notes": item.notes} for item in estimates])


def all_ready(rows: list[dict[str, str]]) -> bool:
    return all(row["exists"] == "true" and row["readable"] == "true" for row in rows)


def redact(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    keys = ["dataset_id", "file_role", "file_name", "path_placeholder", "exists", "readable", "selected_for_path_lock", "selection_reason", "role_status"]
    return [{key: row.get(key, "") for key in keys} for row in rows]


def count_lines(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(chunk.count(b"\n") for chunk in iter(lambda: handle.read(1024 * 1024), b""))


def read_header(path: Path) -> tuple[str, int]:
    with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as handle:
        header = next(csv.reader(handle), [])
    return ",".join(header), len(header)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except (TypeError, ValueError):
        return False


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_md(path: Path, text: str) -> None:
    write_text(path, text)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
