"""N9B1C4 selected-feedback command metadata completion.

This stage is metadata cleanup only. It reads N9B1C3 ready commands and N9B1C2
selected-feedback stage2 command plans, completes runner-critical fields for
selected_feedback_EKF rows, writes runtime-only command JSONs, and refreshes WSL
bridge dry-run metadata. It never runs solvers, evaluators, figures, or case
reviews.
"""

from __future__ import annotations

import csv
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from legsa_gins.reporting.by2_degradation_runner_precheck import FORBIDDEN_EXECUTION_OUTPUT_NAMES
from legsa_gins.reporting.by2_n9b1c2_selected_feedback_same_case_mapping import (
    L_DISABLED_CASE,
    M_CLEAN_REPEAT_CASE,
    SELECTED_FEEDBACK_ALGORITHM,
)
from legsa_gins.reporting.by2_real_pilot_input_generator import AUDIT_ROOT_NAME


STAGE = "N9B1C4_SELECTED_FEEDBACK_COMMAND_FIELD_COMPLETION"
N9B1C3_STAGE = "N9B1C3_EXECUTION_MATRIX_HYGIENE_AND_DEPENDENCY_ORDER_LOCK"
N9B1C2_STAGE = "N9B1C2_SELECTED_FEEDBACK_SAME_CASE_FEEDBACK_GENERATION_MAPPING"
SELECTED_FEEDBACK_ENTRYPOINT_SUFFIX = "/LegSA-GINS/build/cpp/legsa_gins"
SELECTED_FEEDBACK_WORKING_DIRECTORY_SUFFIX = "/LegSA-GINS"
REQUIRED_SUBDIRS = [
    "command_matrix_completion",
    "wsl_dryrun_refresh",
    "reports",
    "matrix",
    "summary",
    "validation",
]
REPORT_NAMES = [
    "N9B1C4_COMMAND_FIELD_COMPLETION_REPORT.json",
    "N9B1C4_DEPENDENCY_GRAPH_CLEANUP_REPORT.json",
    "N9B1C4_WSL_DRYRUN_REFRESH_REPORT.json",
    "N9B1C4_VALIDATION_REPORT.json",
    "N9B1C4_DECISION_REPORT.json",
]
MATRIX_STEMS = [
    "N9B1C4_N9B1D_READY_COMMAND_MATRIX",
    "N9B1C4_COMMAND_FIELD_COMPLETION_DIFF",
    "N9B1C4_WSL_DRYRUN_REFRESH",
]
TRACKED_FILES_FOR_PATH_AUDIT = [
    "src/legsa_gins/reporting/by2_n9b1c4_selected_feedback_command_field_completion.py",
    "scripts/experiments/run_n9b1c4_selected_feedback_command_field_completion.py",
    "scripts/audit_n9b1c4_selected_feedback_command_field_completion.py",
    "tests/unit/test_by2_n9b1c4_selected_feedback_command_field_completion.py",
    "tests/audit/test_n9b1c4_selected_feedback_command_field_completion.py",
]
COMMAND_PATH_RE = re.compile(r"^(?P<entrypoint>/\S+)\s+--config\s+(?P<config>'[^']+'|\"[^\"]+\"|\S+)")


def default_n9b1c4_runtime_root(workspace_root: Path) -> Path:
    return workspace_root / AUDIT_ROOT_NAME / STAGE


def run_n9b1c4_selected_feedback_command_field_completion(
    workspace_root: Path,
    runtime_root: Path | None = None,
    *,
    write_outputs: bool = True,
    run_wsl_dryrun_refresh: bool = True,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root or default_n9b1c4_runtime_root(workspace_root)
    if write_outputs:
        _create_runtime_tree(runtime_root)

    c3_root = workspace_root / AUDIT_ROOT_NAME / N9B1C3_STAGE
    c2_root = workspace_root / AUDIT_ROOT_NAME / N9B1C2_STAGE
    c3_rows = _load_json_rows(c3_root / "matrix" / "N9B1C3_N9B1D_READY_COMMAND_MATRIX.json")
    dependency_rows = _load_json_rows(c3_root / "matrix" / "N9B1C3_CASE_DEPENDENCY_GRAPH.json")
    c2_plan_rows = _load_json_rows(c2_root / "matrix" / "N9B1C2_REPAIRED_COMMAND_PLAN_MATRIX.json")
    stage2_plan_by_case = {
        row.get("case_id", ""): row
        for row in c2_plan_rows
        if row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM
        and row.get("plan_stage") == "stage2_selected_feedback_ekf"
    }

    completed_rows: list[dict[str, Any]] = []
    diff_rows: list[dict[str, Any]] = []
    command_json_rows: list[dict[str, Any]] = []
    for prior in c3_rows:
        row = dict(prior)
        if _is_selected_feedback_executable(row):
            plan = stage2_plan_by_case.get(row.get("case_id", ""), {})
            before = dict(row)
            _complete_selected_feedback_row(row, plan, runtime_root)
            command_payload = _solver_command_payload(row, plan)
            command_json_rows.append(command_payload)
            if write_outputs:
                _write_json(runtime_root / row["solver_command_json"], command_payload)
            diff_rows.extend(_completion_diff(before, row))
        completed_rows.append(row)

    dryrun_rows = [_dryrun_row(row) for row in completed_rows if _is_selected_feedback_executable(row)]
    if write_outputs and run_wsl_dryrun_refresh:
        dryrun_rows = _run_wsl_dryrun_refresh(workspace_root, runtime_root, dryrun_rows)

    dependency_cleanup_report = _dependency_cleanup_report(dependency_rows)
    validation = validate_n9b1c4_result(
        workspace_root,
        runtime_root,
        completed_rows,
        diff_rows,
        dryrun_rows,
        dependency_cleanup_report,
        runtime_written=False,
    )
    selected_rows = [row for row in completed_rows if _is_selected_feedback_executable(row)]
    command_completion_report = {
        "stage": STAGE,
        "source_stage": N9B1C3_STAGE,
        "selected_feedback_executable_rows": len(selected_rows),
        "blank_entrypoint_count": sum(not row.get("entrypoint") for row in selected_rows),
        "blank_working_directory_count": sum(not row.get("working_directory") for row in selected_rows),
        "blank_solver_command_json_count": sum(not row.get("solver_command_json") for row in selected_rows),
        "runtime_solver_command_json_rows": len(command_json_rows),
        "future_solver_entry_count": sum("future_solver_entry" in row.get("command", "") for row in selected_rows),
        "solver_run": False,
        "official_evaluator_run": False,
        "figures_generated": False,
        "ready_for_N9B2_execution": False,
    }
    wsl_report = {
        "stage": STAGE,
        "bridge_script": "scripts/run_wsl_legsa.ps1",
        "dry_run_only": True,
        "dryrun_rows": len(dryrun_rows),
        "dryrun_success_count": sum(int(row.get("dryrun_returncode", 0) or 0) == 0 for row in dryrun_rows),
        "dryrun_failure_count": sum(int(row.get("dryrun_returncode", 0) or 0) != 0 for row in dryrun_rows),
        "selected_feedback_rows": len(selected_rows),
        "blank_working_directory_count": sum(not row.get("working_directory") for row in dryrun_rows),
        "executed": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "ready_for_N9B2_execution": False,
    }
    if validation["status"] == "pass":
        decision_status = "N9B1C4_selected_feedback_command_fields_complete"
        ready_for_n9b1d = True
        recommended_next_stage = "human_review_N9B1C4_then_N9B1D_solver_execution"
    else:
        decision_status = "N9B1C4_command_field_completion_failed"
        ready_for_n9b1d = False
        recommended_next_stage = "fix_command_fields"
    decision = {
        "stage": STAGE,
        "status": decision_status,
        "ready_for_N9B1D_solver_execution": ready_for_n9b1d,
        "ready_for_N9B2_execution": False,
        "ready_for_full_N9B_execution": False,
        "recommended_next_stage": recommended_next_stage,
        "solver_run": False,
        "official_evaluator_run": False,
        "figures_generated": False,
        "case_review_generated": False,
        "issues": validation["issues"],
    }
    result = {
        "command_field_completion_report": command_completion_report,
        "dependency_graph_cleanup_report": dependency_cleanup_report,
        "wsl_dryrun_refresh_report": wsl_report,
        "validation_report": validation,
        "decision_report": decision,
        "n9b1d_ready_command_matrix": completed_rows,
        "command_field_completion_diff": diff_rows,
        "wsl_dryrun_refresh": dryrun_rows,
    }
    if write_outputs:
        _write_outputs(runtime_root, result)
    return result


def validate_n9b1c4_result(
    workspace_root: Path,
    runtime_root: Path,
    ready_rows: list[dict[str, Any]] | None = None,
    diff_rows: list[dict[str, Any]] | None = None,
    dryrun_rows: list[dict[str, Any]] | None = None,
    dependency_cleanup_report: dict[str, Any] | None = None,
    *,
    runtime_written: bool = True,
) -> dict[str, Any]:
    ready_rows = ready_rows or []
    diff_rows = diff_rows or []
    dryrun_rows = dryrun_rows or []
    dependency_cleanup_report = dependency_cleanup_report or {}
    issues: list[str] = []

    if runtime_written:
        for subdir in REQUIRED_SUBDIRS:
            if not (runtime_root / subdir).is_dir():
                issues.append(f"missing required subdir: {subdir}")
        for name in REPORT_NAMES:
            if not (runtime_root / "reports" / name).is_file():
                issues.append(f"missing report: {name}")
        for stem in MATRIX_STEMS:
            if not (runtime_root / "matrix" / f"{stem}.json").is_file():
                issues.append(f"missing matrix JSON: {stem}")
            if not (runtime_root / "matrix" / f"{stem}.csv").is_file():
                issues.append(f"missing matrix CSV: {stem}")
        for path in runtime_root.rglob("*"):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix in {".png", ".jpg", ".jpeg", ".svg", ".pdf", ".npy", ".npz"}:
                issues.append(f"forbidden artifact generated: {_rel(runtime_root, path)}")
            if any(path.name.startswith(name) for name in FORBIDDEN_EXECUTION_OUTPUT_NAMES):
                issues.append(f"forbidden execution output generated: {_rel(runtime_root, path)}")
            if suffix == ".json":
                data = path.read_bytes()
                if data.startswith(b"\xef\xbb\xbf"):
                    issues.append(f"json BOM present: {_rel(runtime_root, path)}")
                try:
                    json.loads(data.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    issues.append(f"json parse failed: {_rel(runtime_root, path)}: {exc}")

    selected = [row for row in ready_rows if _is_selected_feedback_executable(row)]
    if len(selected) != 8:
        issues.append(f"selected_feedback executable rows != 8: {len(selected)}")
    for field in ["entrypoint", "working_directory", "solver_command_json", "generated_config_path", "config_path", "command"]:
        blank = [row.get("case_id", "") for row in selected if not str(row.get(field, "")).strip()]
        if blank:
            issues.append(f"blank {field} for selected_feedback executable rows: {blank}")
    for row in selected:
        case_id = row.get("case_id", "")
        if not row.get("entrypoint", "").endswith(SELECTED_FEEDBACK_ENTRYPOINT_SUFFIX):
            issues.append(f"unexpected selected_feedback entrypoint: {case_id}")
        if not row.get("working_directory", "").endswith(SELECTED_FEEDBACK_WORKING_DIRECTORY_SUFFIX):
            issues.append(f"unexpected selected_feedback working_directory: {case_id}")
        if not row.get("solver_command_json", "").startswith("command_matrix_completion/"):
            issues.append(f"solver_command_json not under N9B1C4 runtime completion root: {case_id}")
        if "future_solver_entry" in row.get("command", ""):
            issues.append(f"future_solver_entry in selected_feedback command: {case_id}")
        if row.get("block_reason") or row.get("blocked_reason"):
            issues.append(f"stale blocker in selected_feedback executable row: {case_id}")
        if row.get("selected_feedback_acceptance") == "mapped_clean_repeat" and case_id != M_CLEAN_REPEAT_CASE:
            issues.append(f"degraded selected_feedback uses clean repeat acceptance: {case_id}")
        if row.get("clean_n8j_path_used_for_degraded_case") is True:
            issues.append(f"degraded selected_feedback clean feedback marker active: {case_id}")
        for flag in ["solver_run", "official_evaluator_run", "NAV_generated", "STD_generated", "EVAL_NAV_generated", "RUN_MANIFEST_generated", "figures_generated", "case_review_generated"]:
            if row.get(flag) not in {False, 0, None}:
                issues.append(f"{flag} must be false: {case_id}")
        if _truthy(row.get("trace_solver_input")) or _truthy(row.get("final_v23_solver_input")):
            issues.append(f"trace/final_v23 solver input marker active: {case_id}")

    if [row for row in ready_rows if row.get("routing_status") == "not_selected_in_prior_plan" and row.get("run_allowed_in_N9B1D") is True]:
        issues.append("not_selected row is executable")
    if [row for row in ready_rows if row.get("n9b1d_executable") is True and (row.get("block_reason") or row.get("blocked_reason"))]:
        issues.append("stale blocker in executable row")
    if [row for row in ready_rows if row.get("n9b1d_executable") is True and "future_solver_entry" in row.get("command", "")]:
        issues.append("future_solver_entry in executable command")

    if len(dryrun_rows) != len(selected):
        issues.append(f"dry-run rows != selected_feedback executable rows: {len(dryrun_rows)} vs {len(selected)}")
    for row in dryrun_rows:
        if row.get("dry_run_only") is not True or row.get("executed") is not False:
            issues.append(f"dry-run flags invalid: {row.get('case_id')}")
        if int(row.get("dryrun_returncode", 0) or 0) != 0:
            issues.append(f"dry-run failed: {row.get('case_id')}")
        if not row.get("working_directory"):
            issues.append(f"dry-run working_directory blank: {row.get('case_id')}")
        if row.get("solver_run") is True or row.get("official_evaluator_run") is True:
            issues.append(f"dry-run row records solver/evaluator execution: {row.get('case_id')}")

    if dependency_cleanup_report.get("same_case_selected_feedback_cases") != 6:
        issues.append("same_case_selected_feedback_cases wording/count is not 6")
    if dependency_cleanup_report.get("same_case_selected_feedback_edges") != 12:
        issues.append("same_case_selected_feedback_edges wording/count is not 12")
    if dependency_cleanup_report.get("baseline_to_feedback_to_selected_edges") != 12:
        issues.append("baseline_to_feedback_to_selected_edges count is not 12")
    for row in diff_rows:
        if row.get("solver_run") is True or row.get("official_evaluator_run") is True:
            issues.append("diff row records solver/evaluator execution")
    issues.extend(_tracked_absolute_path_issues(workspace_root))
    return {
        "stage": STAGE,
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "solver_run": False,
        "official_evaluator_run": False,
        "figures_generated": False,
        "case_review_generated": False,
        "ready_for_N9B2_execution": False,
    }


def _complete_selected_feedback_row(row: dict[str, Any], plan: dict[str, Any], runtime_root: Path) -> None:
    command = plan.get("command") or row.get("command", "")
    entrypoint, config_path = _parse_entrypoint_and_config(command)
    row["entrypoint"] = entrypoint or row.get("entrypoint", "")
    row["working_directory"] = plan.get("working_directory") or row.get("working_directory") or _working_directory_from_entrypoint(row["entrypoint"])
    row["command"] = command
    row["command_preview"] = command
    row["solver_command_json"] = f"command_matrix_completion/{row['case_id']}/{SELECTED_FEEDBACK_ALGORITHM}/solver_command.json"
    row["source_solver_command_json"] = plan.get("command_plan_json", "")
    if plan.get("generated_config_path"):
        row["generated_config_path"] = plan["generated_config_path"]
    row["config_path"] = config_path or row.get("config_path") or "runtime_generated"
    row["n9b1c4_command_fields_complete"] = True
    row["n9b1c4_runtime_solver_command_json"] = str(runtime_root / row["solver_command_json"])
    row["ready_for_N9B2_execution"] = False
    for flag in ["solver_run", "official_evaluator_run", "NAV_generated", "STD_generated", "EVAL_NAV_generated", "RUN_MANIFEST_generated", "figures_generated", "case_review_generated"]:
        row[flag] = False


def _parse_entrypoint_and_config(command: str) -> tuple[str, str]:
    match = COMMAND_PATH_RE.search(command.strip())
    if not match:
        return "", ""
    config = match.group("config").strip("'\"")
    return match.group("entrypoint"), config


def _working_directory_from_entrypoint(entrypoint: str) -> str:
    suffix = SELECTED_FEEDBACK_ENTRYPOINT_SUFFIX
    if not entrypoint.endswith(suffix):
        return ""
    return entrypoint[: -len(suffix)] + SELECTED_FEEDBACK_WORKING_DIRECTORY_SUFFIX


def _solver_command_payload(row: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "case_id": row.get("case_id", ""),
        "algorithm": SELECTED_FEEDBACK_ALGORITHM,
        "command_type": row.get("command_type", ""),
        "command": row.get("command", ""),
        "entrypoint": row.get("entrypoint", ""),
        "working_directory": row.get("working_directory", ""),
        "config_path": row.get("config_path", ""),
        "generated_config_path": row.get("generated_config_path", ""),
        "source_n9b1c2_command_plan_json": plan.get("command_plan_json", ""),
        "selected_feedback_acceptance": row.get("selected_feedback_acceptance", ""),
        "dependency_order_requirement": row.get("dependency_order_requirement", ""),
        "planned_same_case_feedback_path": row.get("planned_same_case_feedback_path", ""),
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "NAV_generated": False,
        "STD_generated": False,
        "EVAL_NAV_generated": False,
        "RUN_MANIFEST_generated": False,
        "figures_generated": False,
        "case_review_generated": False,
        "dry_run_only": True,
        "executed": False,
        "ready_for_N9B2_execution": False,
    }


def _completion_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field in ["entrypoint", "working_directory", "solver_command_json", "generated_config_path", "config_path", "command"]:
        if before.get(field, "") != after.get(field, ""):
            rows.append(
                {
                    "stage": STAGE,
                    "case_id": after.get("case_id", ""),
                    "algorithm": SELECTED_FEEDBACK_ALGORITHM,
                    "field": field,
                    "before": before.get(field, ""),
                    "after": after.get(field, ""),
                    "change_reason": "selected_feedback runner-critical metadata completed for N9B1D",
                    "solver_run": False,
                    "official_evaluator_run": False,
                    "ready_for_N9B2_execution": False,
                }
            )
    return rows


def _dependency_cleanup_report(dependency_rows: list[dict[str, Any]]) -> dict[str, Any]:
    same_edges = [row for row in dependency_rows if row.get("dependency_mode") == "same_case_selected_feedback"]
    same_cases = sorted({row.get("case_id", "") for row in same_edges})
    return {
        "stage": STAGE,
        "source_stage": N9B1C3_STAGE,
        "dependency_rows": len(dependency_rows),
        "same_case_selected_feedback_cases": len(same_cases),
        "same_case_selected_feedback_edges": len(same_edges),
        "baseline_to_feedback_to_selected_edges": sum(row.get("edge_type") == "baseline_to_feedback_to_selected_feedback" for row in dependency_rows),
        "clean_repeat_cases": sum(row.get("dependency_mode") == "clean_repeat_selected_feedback" for row in dependency_rows),
        "disabled_marker_cases": sum(row.get("dependency_mode") == "disabled_marker_selected_feedback" for row in dependency_rows),
        "dependency_semantics_changed": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "ready_for_N9B2_execution": False,
    }


def _dryrun_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "case_id": row.get("case_id", ""),
        "algorithm": SELECTED_FEEDBACK_ALGORITHM,
        "command": row.get("command", ""),
        "entrypoint": row.get("entrypoint", ""),
        "working_directory": row.get("working_directory", ""),
        "solver_command_json": row.get("solver_command_json", ""),
        "bridge_script": "scripts/run_wsl_legsa.ps1",
        "dry_run_only": True,
        "executed": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "log_path": "",
        "ready_for_N9B2_execution": False,
    }


def _run_wsl_dryrun_refresh(workspace_root: Path, runtime_root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    script = workspace_root / "scripts" / "run_wsl_legsa.ps1"
    output: list[dict[str, Any]] = []
    for row in rows:
        log = runtime_root / "wsl_dryrun_refresh" / "logs" / f"{row['case_id']}__selected_feedback_EKF.json"
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-WorkingDirectory",
            row.get("working_directory", ""),
            "-Command",
            row.get("command", ""),
            "-DryRun",
            "-LogPath",
            str(log),
        ]
        completed = subprocess.run(
            cmd,
            cwd=workspace_root,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        dryrun = dict(row)
        dryrun.update(
            {
                "log_path": _rel(runtime_root, log),
                "dryrun_returncode": completed.returncode,
                "dryrun_stdout_nonempty": bool((completed.stdout or "").strip()),
                "dryrun_stderr": (completed.stderr or "").strip(),
                "executed": False,
            }
        )
        output.append(dryrun)
    return output


def _is_selected_feedback_executable(row: dict[str, Any]) -> bool:
    return (
        row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM
        and row.get("run_allowed_in_N9B1D") is True
        and row.get("mapping_status") == "mapped"
    )


def _write_outputs(runtime_root: Path, result: dict[str, Any]) -> None:
    reports = {
        "N9B1C4_COMMAND_FIELD_COMPLETION_REPORT.json": result["command_field_completion_report"],
        "N9B1C4_DEPENDENCY_GRAPH_CLEANUP_REPORT.json": result["dependency_graph_cleanup_report"],
        "N9B1C4_WSL_DRYRUN_REFRESH_REPORT.json": result["wsl_dryrun_refresh_report"],
        "N9B1C4_VALIDATION_REPORT.json": result["validation_report"],
        "N9B1C4_DECISION_REPORT.json": result["decision_report"],
    }
    for name, payload in reports.items():
        _write_json(runtime_root / "reports" / name, payload)
    matrices = {
        "N9B1C4_N9B1D_READY_COMMAND_MATRIX": result["n9b1d_ready_command_matrix"],
        "N9B1C4_COMMAND_FIELD_COMPLETION_DIFF": result["command_field_completion_diff"],
        "N9B1C4_WSL_DRYRUN_REFRESH": result["wsl_dryrun_refresh"],
    }
    for stem, rows in matrices.items():
        _write_table_pair(runtime_root / "matrix" / stem, rows)
    _write_table_pair(runtime_root / "command_matrix_completion" / "N9B1C4_N9B1D_READY_COMMAND_MATRIX", result["n9b1d_ready_command_matrix"])
    _write_table_pair(runtime_root / "wsl_dryrun_refresh" / "N9B1C4_WSL_DRYRUN_REFRESH", result["wsl_dryrun_refresh"])
    _write_json(runtime_root / "validation" / "N9B1C4_VALIDATION_REPORT.json", result["validation_report"])
    (runtime_root / "summary" / "n9b1c4_dependency_graph_cleanup.md").write_text(_dependency_summary(result), encoding="utf-8")
    (runtime_root / "summary" / "n9b1c4_next_stage_recommendation.md").write_text(_next_stage_summary(result), encoding="utf-8")


def _dependency_summary(result: dict[str, Any]) -> str:
    report = result["dependency_graph_cleanup_report"]
    return (
        "# N9B1C4 dependency graph wording cleanup\n\n"
        f"- same_case_selected_feedback_cases={report['same_case_selected_feedback_cases']}\n"
        f"- same_case_selected_feedback_edges={report['same_case_selected_feedback_edges']}\n"
        f"- baseline_to_feedback_to_selected_edges={report['baseline_to_feedback_to_selected_edges']}\n"
        "- dependency_semantics_changed=false\n"
        "- solver/evaluator/figure/case-review generation=false\n"
    )


def _next_stage_summary(result: dict[str, Any]) -> str:
    decision = result["decision_report"]
    report = result["command_field_completion_report"]
    return (
        "# N9B1C4 next stage recommendation\n\n"
        f"- status={decision['status']}\n"
        f"- ready_for_N9B1D_solver_execution={str(decision['ready_for_N9B1D_solver_execution']).lower()}\n"
        "- ready_for_N9B2_execution=false\n"
        f"- selected_feedback_executable_rows={report['selected_feedback_executable_rows']}\n"
        f"- blank_entrypoint_count={report['blank_entrypoint_count']}\n"
        f"- blank_working_directory_count={report['blank_working_directory_count']}\n"
        f"- blank_solver_command_json_count={report['blank_solver_command_json_count']}\n"
    )


def _create_runtime_tree(runtime_root: Path) -> None:
    for subdir in REQUIRED_SUBDIRS:
        path = runtime_root / subdir
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
    (runtime_root / "wsl_dryrun_refresh" / "logs").mkdir(parents=True, exist_ok=True)


def _load_json_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return [dict(row) for row in payload] if isinstance(payload, list) else []


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_table_pair(stem: Path, rows: list[dict[str, Any]]) -> None:
    _write_json(stem.with_suffix(".json"), rows)
    stem.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with stem.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key, "")) for key in fieldnames})


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _truthy(value: Any) -> bool:
    text = str(value).strip().lower()
    return text not in {"", "0", "0.0", "false", "none", "no", "nan"}


def _tracked_absolute_path_issues(workspace_root: Path) -> list[str]:
    issues: list[str] = []
    forbidden = [
        "C:" + "\\Users\\",
        "C:" + "/Users/",
        "/" + "mnt" + "/" + "c" + "/" + "Users" + "/",
        "/" + "home" + "/" + "kaiwen",
    ]
    for rel_path in TRACKED_FILES_FOR_PATH_AUDIT:
        path = workspace_root / rel_path
        if not path.is_file():
            issues.append(f"missing tracked file for path audit: {rel_path}")
            continue
        text = path.read_text(encoding="utf-8")
        if any(prefix in text for prefix in forbidden):
            issues.append(f"local absolute path in tracked file: {rel_path}")
    return issues
