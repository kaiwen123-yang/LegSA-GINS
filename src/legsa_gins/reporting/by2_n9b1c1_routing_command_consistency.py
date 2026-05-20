"""N9B1C1 routing-command consistency and selected-feedback repair.

This stage is reporting and command-plan repair only. It reads the N9B1C
mapping output plus repaired N9B1A1/N9B1B pilot context, blocks rows that must
not be executable, and writes dry-run-only command plans for allowed mapped
rows. It never runs solvers, evaluators, figures, case reviews, or degradation
matrices.
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from legsa_gins.reporting.by2_degradation_runner_precheck import FORBIDDEN_EXECUTION_OUTPUT_NAMES
from legsa_gins.reporting.by2_real_pilot_input_generator import AUDIT_ROOT_NAME


STAGE = "N9B1C1_ROUTING_COMMAND_CONSISTENCY_AND_SELECTED_FEEDBACK_MAPPING_FIX"
PRIOR_STAGE = "N9B1C_REAL_SOLVER_ENTRYPOINT_AND_CONFIG_MAPPING"
N9B1A1_STAGE = "N9B1A1_DOWNSAMPLE_CADENCE_POLICY_REPAIR"
N9B1B_STAGE = "N9B1B_PILOT_SOLVER_EXECUTION_AND_EVALUATION"
FUTURE_SOLVER_STAGE = "N9B1D_PILOT_SOLVER_EXECUTION"
RUN_RESULTS_ROOT = "运行结果"

REQUIRED_SUBDIRS = [
    "routing_consistency",
    "selected_feedback_dependency_audit",
    "repaired_command_plans",
    "wsl_dryrun",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
]
REPORT_NAMES = [
    "N9B1C1_ROUTING_COMMAND_CONSISTENCY_REPORT.json",
    "N9B1C1_SELECTED_FEEDBACK_DEPENDENCY_AUDIT_REPORT.json",
    "N9B1C1_SELECTED_FEEDBACK_COMMAND_REPAIR_REPORT.json",
    "N9B1C1_WSL_DRYRUN_REPORT.json",
    "N9B1C1_VALIDATION_REPORT.json",
    "N9B1C1_DECISION_REPORT.json",
]
MATRIX_STEMS = [
    "N9B1C1_COMMAND_MAPPING_MATRIX_REPAIRED",
    "N9B1C1_ROUTING_COMMAND_DIFF",
    "N9B1C1_SELECTED_FEEDBACK_DEPENDENCY_MATRIX",
    "N9B1C1_SELECTED_FEEDBACK_COMMAND_MATRIX",
    "N9B1C1_WSL_DRYRUN_COMMAND_MATRIX",
]
FIXED_REFERENCE_ALGORITHMS = {"final_v23_dual_antenna_EKF", "pure_INS_reference_initialized"}
DIAGNOSTIC_BLOCKED_ALGORITHMS = {"reject_all_sanity", "true_no_feedback_FGO"}
SELECTED_FEEDBACK_ALGORITHM = "selected_feedback_EKF"


def default_n9b1c1_runtime_root(workspace_root: Path) -> Path:
    return workspace_root / AUDIT_ROOT_NAME / STAGE


def run_n9b1c1_routing_command_consistency_fix(
    workspace_root: Path,
    runtime_root: Path | None = None,
    *,
    write_outputs: bool = True,
    run_wsl_dryrun: bool = True,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root or default_n9b1c1_runtime_root(workspace_root)
    prior_root = workspace_root / AUDIT_ROOT_NAME / PRIOR_STAGE
    n9b1a1_root = workspace_root / AUDIT_ROOT_NAME / N9B1A1_STAGE
    n9b1b_root = workspace_root / AUDIT_ROOT_NAME / N9B1B_STAGE
    if write_outputs:
        _create_runtime_tree(runtime_root)

    prior_rows = _load_json_rows(prior_root / "matrix" / "N9B1C_COMMAND_MAPPING_MATRIX.json")
    n9b1a1_plan = _load_json_rows(n9b1a1_root / "matrix" / "N9B1A1_SOLVER_COMMAND_PLAN_INDEX_REPAIRED.json")
    n9b1b_rows = _load_json_rows(n9b1b_root / "matrix" / "N9B1B_EXECUTION_MATRIX.json")
    feedback_matrix, feedback_report = _audit_selected_feedback_candidates(workspace_root)
    feedback_by_case = {row["case_id"]: row for row in feedback_matrix}

    repaired_rows: list[dict[str, Any]] = []
    diff_rows: list[dict[str, Any]] = []
    feedback_command_rows: list[dict[str, Any]] = []
    wsl_rows: list[dict[str, Any]] = []
    selected_prior = _selected_pairs(n9b1a1_plan, n9b1b_rows)

    for prior in prior_rows:
        repaired = _repair_row(prior, selected_prior, feedback_by_case, runtime_root)
        repaired_rows.append(repaired)
        diff_rows.append(_diff_row(prior, repaired))
        if repaired["algorithm"] == SELECTED_FEEDBACK_ALGORITHM:
            feedback_command_rows.append(_feedback_command_row(repaired))
        if repaired["mapping_status"] == "mapped":
            if write_outputs:
                _write_solver_command(runtime_root, repaired)
            wsl_rows.append(_wsl_row(repaired))

    if write_outputs and run_wsl_dryrun:
        wsl_rows = _run_wsl_dryruns(workspace_root, runtime_root, wsl_rows)

    routing_report = {
        "stage": STAGE,
        "prior_stage": PRIOR_STAGE,
        "input_rows": len(prior_rows),
        "not_selected_mapped_count": sum(1 for row in repaired_rows if row["routing_status"] == "not_selected_in_prior_plan" and row["mapping_status"] == "mapped"),
        "not_selected_run_allowed_count": sum(1 for row in repaired_rows if row["routing_status"] == "not_selected_in_prior_plan" and row["run_allowed_in_N9B1D"]),
        "fixed_reference_command_count": sum(1 for row in repaired_rows if row["mapping_status"] == "fixed_reference" and row["command"]),
        "mapped_rows": sum(1 for row in repaired_rows if row["mapping_status"] == "mapped"),
        "blocked_rows": sum(1 for row in repaired_rows if row["mapping_status"] != "mapped"),
        "solver_run": False,
        "official_evaluator_run": False,
    }
    repair_report = {
        "stage": STAGE,
        "allowed_command_plan_rows": sum(1 for row in repaired_rows if row["mapping_status"] == "mapped"),
        "selected_feedback_mapped_rows": sum(1 for row in repaired_rows if row["algorithm"] == SELECTED_FEEDBACK_ALGORITHM and row["mapping_status"] == "mapped"),
        "selected_feedback_blocked_rows": sum(1 for row in repaired_rows if row["algorithm"] == SELECTED_FEEDBACK_ALGORITHM and row["mapping_status"] != "mapped"),
        "future_solver_entry_commands": sum("future_solver_entry" in row.get("command", "") for row in repaired_rows if row["mapping_status"] == "mapped"),
        "solver_run": False,
        "official_evaluator_run": False,
    }
    wsl_report = {
        "stage": STAGE,
        "dry_run_only": True,
        "dryrun_command_rows": len(wsl_rows),
        "dryrun_success_count": sum(1 for row in wsl_rows if int(row.get("dryrun_returncode", 0) or 0) == 0),
        "dryrun_failure_count": sum(1 for row in wsl_rows if int(row.get("dryrun_returncode", 0) or 0) != 0),
        "executed": False,
        "solver_run": False,
        "official_evaluator_run": False,
    }
    validation = validate_n9b1c1_result(runtime_root, repaired_rows, wsl_rows, runtime_written=False)
    selected_feedback_blocked = any(
        row["algorithm"] == SELECTED_FEEDBACK_ALGORITHM
        and row["case_id"] != "L_feedback_disabled"
        and row["mapping_status"] != "mapped"
        for row in repaired_rows
    )
    feedback_dependency_unsafe = any(
        row["acceptance"].startswith("accepted") and not row["safe_candidate"]
        for row in feedback_matrix
    )
    if validation["status"] != "pass":
        decision_status = "N9B1C1_routing_command_consistency_failed"
        ready_for_n9b1d = False
        recommended_next_stage = "fix_mapping_consistency"
    elif feedback_dependency_unsafe:
        decision_status = "N9B1C1_selected_feedback_dependency_unsafe"
        ready_for_n9b1d = False
        recommended_next_stage = "repair_feedback_dependency_or_exclude_selected_feedback"
    elif selected_feedback_blocked:
        decision_status = "N9B1C1_partial_safe_mapping_ready_selected_feedback_blocked"
        ready_for_n9b1d = False
        recommended_next_stage = "human_decision_run_partial_N9B1D_or_fix_selected_feedback"
    else:
        decision_status = "N9B1C1_full_safe_mapping_ready"
        ready_for_n9b1d = True
        recommended_next_stage = "human_review_N9B1C1_then_N9B1D_solver_execution"
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
        "issues": validation["issues"],
    }
    result = {
        "routing_consistency_report": routing_report,
        "selected_feedback_dependency_audit_report": feedback_report,
        "selected_feedback_command_repair_report": repair_report,
        "wsl_dryrun_report": wsl_report,
        "validation_report": validation,
        "decision_report": decision,
        "command_mapping_matrix_repaired": repaired_rows,
        "routing_command_diff": diff_rows,
        "selected_feedback_dependency_matrix": feedback_matrix,
        "selected_feedback_command_matrix": feedback_command_rows,
        "wsl_dryrun_command_matrix": wsl_rows,
    }
    if write_outputs:
        _write_outputs(runtime_root, result)
    return result


def validate_n9b1c1_result(
    runtime_root: Path,
    repaired_rows: list[dict[str, Any]] | None = None,
    wsl_rows: list[dict[str, Any]] | None = None,
    *,
    runtime_written: bool = True,
) -> dict[str, Any]:
    rows = repaired_rows or []
    issues: list[str] = []
    if runtime_written and runtime_root.exists():
        for subdir in REQUIRED_SUBDIRS:
            if not (runtime_root / subdir).is_dir():
                issues.append(f"missing required subdir: {subdir}")
        for name in REPORT_NAMES:
            if not (runtime_root / "reports" / name).is_file():
                issues.append(f"missing report: {name}")
        for stem in MATRIX_STEMS:
            if not (runtime_root / "matrix" / f"{stem}.csv").is_file():
                issues.append(f"missing matrix CSV: {stem}")
            if not (runtime_root / "matrix" / f"{stem}.json").is_file():
                issues.append(f"missing matrix JSON: {stem}")
        for path in runtime_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in {".png", ".pdf", ".svg", ".jpg", ".jpeg", ".npy", ".npz"}:
                issues.append(f"forbidden artifact generated: {_rel(runtime_root, path)}")
            if any(path.name.startswith(name) for name in FORBIDDEN_EXECUTION_OUTPUT_NAMES):
                issues.append(f"forbidden execution output generated: {_rel(runtime_root, path)}")
            if path.suffix.lower() == ".json":
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    issues.append(f"json parse failed: {_rel(runtime_root, path)}: {exc}")
    for row in rows:
        case_id = row.get("case_id", "")
        algorithm = row.get("algorithm", "")
        command = row.get("command", "")
        if row.get("routing_status") == "not_selected_in_prior_plan":
            if row.get("mapping_status") == "mapped" or row.get("run_allowed_in_N9B1D") or command:
                issues.append(f"not-selected row is executable: {case_id}/{algorithm}")
        if row.get("mapping_status") == "fixed_reference":
            if command or row.get("run_allowed_in_N9B1D"):
                issues.append(f"fixed_reference row is executable: {case_id}/{algorithm}")
        if row.get("mapping_status") != "mapped" and (command or row.get("run_allowed_in_N9B1D")):
            issues.append(f"blocked row has command/run permission: {case_id}/{algorithm}")
        if row.get("mapping_status") == "mapped":
            if row.get("run_allowed_in_N9B1D") is not True:
                issues.append(f"mapped row is not run-allowed: {case_id}/{algorithm}")
            if not command:
                issues.append(f"mapped row has empty command: {case_id}/{algorithm}")
            if row.get("command_type") in {"", "blocked", "fixed_reference", "diagnostic_blocked", "not_selected", "not_applicable"}:
                issues.append(f"mapped row has non-executable command_type: {case_id}/{algorithm}")
            if not row.get("entrypoint"):
                issues.append(f"mapped row has no real entrypoint: {case_id}/{algorithm}")
            if row.get("input_paths_exist") is not True:
                issues.append(f"mapped row input paths are not confirmed: {case_id}/{algorithm}")
        if "future_solver_entry" in command:
            issues.append(f"future_solver_entry command remains: {case_id}/{algorithm}")
        if algorithm == SELECTED_FEEDBACK_ALGORITHM and row.get("selected_feedback_acceptance") == "accepted":
            if row.get("selected_feedback_safe_candidate") is not True:
                issues.append(f"selected_feedback accepted without safe candidate: {case_id}/{algorithm}")
        if algorithm == SELECTED_FEEDBACK_ALGORITHM and case_id not in {"M_normal_baseline_repeat", "L_feedback_disabled"}:
            if row.get("mapping_status") == "mapped":
                issues.append(f"degraded selected_feedback mapped without same-case feedback: {case_id}/{algorithm}")
        for flag in ["solver_run", "official_evaluator_run", "NAV_generated", "STD_generated", "EVAL_NAV_generated", "RUN_MANIFEST_generated", "figures_generated"]:
            if row.get(flag) not in {False, 0}:
                issues.append(f"{flag} must be false: {case_id}/{algorithm}")
    if any(row.get("dry_run_only") is not True or row.get("executed") is not False for row in wsl_rows or []):
        issues.append("WSL dry-run rows must be dry_run_only=true and executed=false")
    return {
        "stage": STAGE,
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "ready_for_N9B2_execution": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "figures_generated": False,
    }


def _repair_row(
    prior: dict[str, Any],
    selected_prior: set[tuple[str, str]],
    feedback_by_case: dict[str, dict[str, Any]],
    runtime_root: Path,
) -> dict[str, Any]:
    row = dict(prior)
    case_id = row.get("case_id", "")
    algorithm = row.get("algorithm", "")
    selected = (case_id, algorithm) in selected_prior and row.get("selected_for_N9B1C_mapping") is not False
    reason = ""

    if not selected or row.get("routing_status") == "not_selected_in_prior_plan":
        status = "not_selected"
        reason = "not selected in N9B1A1/N9B1B repaired pilot command plan"
    elif algorithm in FIXED_REFERENCE_ALGORITHMS:
        status = "fixed_reference"
        reason = f"{algorithm} is reference-only for this stage"
    elif algorithm in DIAGNOSTIC_BLOCKED_ALGORITHMS:
        status = "diagnostic_blocked"
        reason = f"{algorithm} is diagnostic-only and has no approved N9B1D solver command"
    elif algorithm == SELECTED_FEEDBACK_ALGORITHM:
        status, reason = _selected_feedback_status(case_id, row, feedback_by_case)
    elif row.get("mapping_status") == "mapped" and row.get("command"):
        status = "mapped"
    else:
        status = row.get("mapping_status") or "blocked"
        reason = row.get("blocked_reason") or row.get("block_reason") or "prior N9B1C row was not safely mapped"

    row["stage"] = STAGE
    row["prior_stage"] = PRIOR_STAGE
    row["prior_mapping_status"] = prior.get("mapping_status", "")
    row["prior_command"] = prior.get("command", "")
    row["mapping_status"] = status
    row["run_allowed_in_N9B1D"] = status == "mapped"
    row["ready_for_N9B1D_solver_execution"] = status == "mapped"
    row["ready_for_N9B2_execution"] = False
    row["solver_run"] = False
    row["official_evaluator_run"] = False
    row["NAV_generated"] = False
    row["STD_generated"] = False
    row["EVAL_NAV_generated"] = False
    row["RUN_MANIFEST_generated"] = False
    row["figures_generated"] = False
    row["dry_run_only"] = True
    row["blocked_reason"] = "" if status == "mapped" else reason
    row["block_reason"] = "" if status == "mapped" else reason
    row["solver_command_json"] = f"repaired_command_plans/{case_id}/{algorithm}/solver_command.json" if status == "mapped" else ""
    row["generated_config_path"] = row.get("generated_config_path", "")
    row["generated_config_path_wsl"] = row.get("generated_config_path_wsl", "")
    row["command"] = _repaired_command(row, prior, runtime_root) if status == "mapped" else ""
    row["command_preview"] = row["command"] if status == "mapped" else f"BLOCKED: {reason}"
    if status != "mapped":
        row["command_type"] = "fixed_reference" if status == "fixed_reference" else status
        row["entrypoint"] = ""
        row["working_directory"] = "" if status == "fixed_reference" else row.get("working_directory", "")
    feedback = feedback_by_case.get(case_id, {})
    if algorithm == SELECTED_FEEDBACK_ALGORITHM:
        row["selected_feedback_acceptance"] = "mapped_disabled_marker" if case_id == "L_feedback_disabled" and status == "mapped" else ("accepted" if status == "mapped" else "blocked")
        row["selected_feedback_safe_candidate"] = status == "mapped" and bool(feedback.get("safe_candidate"))
        row["selected_feedback_candidate_source"] = feedback.get("candidate_source", "")
        row["selected_feedback_block_reason"] = "" if status == "mapped" else reason
    return row


def _selected_feedback_status(case_id: str, row: dict[str, Any], feedback_by_case: dict[str, dict[str, Any]]) -> tuple[str, str]:
    if case_id == "L_feedback_disabled":
        return "mapped", ""
    if not row.get("command"):
        return "blocked", "selected_feedback_EKF blocked: N9B1C did not provide a real executable selected-feedback command/config seed"
    feedback = feedback_by_case.get(case_id, {})
    if feedback.get("same_case_feedback_exists") and feedback.get("safe_candidate"):
        return "mapped", ""
    if case_id == "M_normal_baseline_repeat" and feedback.get("clean_repeat_reuse_defensible"):
        return "mapped", ""
    return "blocked", "selected_feedback_EKF blocked: no safe same-case feedback observations; clean feedback reuse allowed only for M_normal_baseline_repeat"


def _repaired_command(row: dict[str, Any], prior: dict[str, Any], runtime_root: Path) -> str:
    return str(prior.get("command", "") or "")


def _audit_selected_feedback_candidates(workspace_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    search_roots = [
        workspace_root / RUN_RESULTS_ROOT / "N8J_feedback_final_validation",
        workspace_root / RUN_RESULTS_ROOT / "N8I_feedback_ablation_gate_covariance",
        workspace_root / RUN_RESULTS_ROOT / "N8H_fgo_feedback_visual_validation",
        workspace_root / AUDIT_ROOT_NAME / "N9A_R4D_METRIC_ALIGNMENT_AND_DIAGNOSTIC_SOURCE_INTEGRATION" / "diagnostic_sources",
        workspace_root / AUDIT_ROOT_NAME / "N9A_R4K_BY2_NORMAL_FULL_PLOT_WITH_LOCKED_BASELINES" / "diagnostic_sources",
    ]
    candidates = sorted(
        {
            path
            for root in search_roots
            if root.exists()
            for pattern in ("FGO_FEEDBACK_OBSERVATIONS.csv", "FGO_FEEDBACK_UPDATE_TRACE.csv")
            for path in root.rglob(pattern)
        }
    )
    rows: list[dict[str, Any]] = []
    clean_candidate = _choose_clean_feedback_candidate(candidates)
    clean_summary = _feedback_safety(clean_candidate, workspace_root)
    for case_id in _case_ids(workspace_root):
        same_case = _choose_case_feedback_candidate(candidates, case_id)
        use_clean = case_id == "M_normal_baseline_repeat" and same_case is None and clean_summary["accepted"]
        candidate = same_case or (clean_candidate if use_clean else None)
        summary = _feedback_safety(candidate, workspace_root)
        accepted = summary["accepted"] and (same_case is not None or use_clean)
        if candidate is None:
            reason = "blocked: no same-case feedback observations found"
        elif accepted and use_clean:
            reason = "accepted clean normal feedback only for M_normal_baseline_repeat"
        elif accepted:
            reason = "accepted same-case feedback observations"
        else:
            reason = summary["reason"]
        rows.append(
            {
                "case_id": case_id,
                "path": summary["path"],
                "candidate_source": summary["path"],
                "exists": summary["exists"],
                "row_count": summary["row_count"],
                "columns": summary["columns"],
                "trace_path": summary["trace_path"],
                "trace_row_count": summary["trace_row_count"],
                "trace_columns": summary["trace_columns"],
                "role": "selected feedback observation/config dependency",
                "normal_or_pilot_applicability": "clean_normal_repeat_only" if use_clean else ("same_case_pilot" if same_case is not None else "none"),
                "can_be_used_as_solver_input": accepted,
                "is_output_substitution": summary["is_output_substitution"],
                "is_future_data_safe": summary["is_future_data_safe"],
                "source_stage": summary["source_stage"],
                "accepted": accepted,
                "same_case_feedback_exists": same_case is not None,
                "clean_normal_feedback_exists": clean_candidate is not None,
                "clean_repeat_reuse_defensible": use_clean and accepted,
                "safe_candidate": accepted,
                "trace_solver_input": summary["trace_solver_input"],
                "final_v23_solver_input": summary["final_v23_solver_input"],
                "output_substitution": summary["output_substitution"],
                "direct_nav_override": summary["direct_nav_override"],
                "rejects_trace_solver_input": not summary["trace_solver_input"],
                "rejects_final_v23_solver_input": not summary["final_v23_solver_input"],
                "rejects_output_substitution": not summary["output_substitution"],
                "rejects_direct_nav_override": not summary["direct_nav_override"],
                "rejects_future_data_violation": summary["is_future_data_safe"],
                "not_final_v23_output": not summary["final_v23_path"],
                "acceptance": "accepted_for_clean_repeat" if accepted and use_clean else ("accepted_same_case" if accepted else "blocked"),
                "reason": reason,
            }
        )
    report = {
        "stage": STAGE,
        "candidate_count": len(candidates),
        "safe_candidate_count": sum(1 for row in rows if row["safe_candidate"]),
        "clean_normal_candidate_found": clean_candidate is not None,
        "clean_normal_candidate_path": _display_rel(workspace_root, clean_candidate),
        "accepted_cases": [row["case_id"] for row in rows if row["safe_candidate"]],
        "blocked_cases": [row["case_id"] for row in rows if not row["safe_candidate"]],
        "policy": "degraded selected-feedback rows require same-case feedback; M_normal_baseline_repeat may reuse clean N8J/R4K feedback if safe",
        "candidate_paths": [_display_rel(workspace_root, path) for path in candidates],
        "solver_run": False,
        "official_evaluator_run": False,
    }
    return rows, report


def _selected_pairs(n9b1a1_plan: list[dict[str, Any]], n9b1b_rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    pairs = {
        (row.get("case_id", ""), row.get("algorithm", ""))
        for row in n9b1a1_plan
        if row.get("routing_status") in {"applicable", "diagnostic_only"}
    }
    pairs.update(
        (row.get("case_id", ""), row.get("algorithm", row.get("algorithm_group", "")))
        for row in n9b1b_rows
        if row.get("routing_status") in {"applicable", "diagnostic_only"}
    )
    return {(case_id, algorithm) for case_id, algorithm in pairs if case_id and algorithm}


def _case_ids(workspace_root: Path) -> list[str]:
    prior = _load_json_rows(workspace_root / AUDIT_ROOT_NAME / PRIOR_STAGE / "matrix" / "N9B1C_COMMAND_MAPPING_MATRIX.json")
    return sorted({row.get("case_id", "") for row in prior if row.get("case_id")})


def _unsafe_feedback_path(path: Path) -> bool:
    text = str(path).lower()
    return "final_v23" in text or "trace" in path.name.lower()


def _choose_clean_feedback_candidate(candidates: list[Path]) -> Path | None:
    preferred = [
        path
        for path in candidates
        if path.name == "FGO_FEEDBACK_OBSERVATIONS.csv"
        and "N8J_feedback_final_validation" in str(path)
        and "n8j_selected_conservative_feedback" in str(path)
    ]
    if preferred:
        return preferred[0]
    fallback = [
        path
        for path in candidates
        if path.name == "FGO_FEEDBACK_OBSERVATIONS.csv" and "N8J_feedback_final_validation" in str(path)
    ]
    return fallback[0] if fallback else None


def _choose_case_feedback_candidate(candidates: list[Path], case_id: str) -> Path | None:
    matches = [path for path in candidates if case_id in str(path)]
    observations = [path for path in matches if path.name == "FGO_FEEDBACK_OBSERVATIONS.csv"]
    return observations[0] if observations else (matches[0] if matches else None)


def _feedback_safety(path: Path | None, workspace_root: Path) -> dict[str, Any]:
    if path is None:
        return {
            "path": "",
            "exists": False,
            "row_count": 0,
            "columns": [],
            "trace_path": "",
            "trace_row_count": 0,
            "trace_columns": [],
            "trace_solver_input": False,
            "final_v23_solver_input": False,
            "output_substitution": False,
            "direct_nav_override": False,
            "final_v23_path": False,
            "is_output_substitution": False,
            "is_future_data_safe": False,
            "source_stage": "",
            "accepted": False,
            "reason": "blocked: no feedback dependency candidate",
        }
    summary = _read_csv_summary(path)
    trace = _matching_feedback_trace(path)
    trace_summary = _read_csv_summary(trace)
    trace_solver_input = _csv_column_any_truthy(trace, "trace_solver_input") or _unsafe_feedback_path(path)
    final_v23_solver_input = (
        _csv_column_any_truthy(trace, "final_v23_output_solver_input")
        or _csv_column_any_truthy(trace, "final_v23_solver_input")
        or "final_v23" in str(path).lower()
    )
    output_substitution = _csv_column_any_truthy(trace, "output_substitution")
    direct_nav_override = _csv_column_any_truthy(trace, "direct_nav_override")
    future_data_safe = _future_data_safe(path) and (trace is None or _future_data_safe(trace))
    issues = []
    if not summary["exists"]:
        issues.append("candidate path missing")
    if summary["row_count"] <= 0:
        issues.append("candidate has no rows")
    if trace is None:
        issues.append("matching feedback update trace missing")
    if trace_solver_input:
        issues.append("trace marked as solver input")
    if final_v23_solver_input:
        issues.append("final_v23 marked as solver input")
    if output_substitution:
        issues.append("output substitution marker is true")
    if direct_nav_override:
        issues.append("direct NAV override marker is true")
    if not future_data_safe:
        issues.append("source window is not future-data safe")
    accepted = not issues
    return {
        "path": _display_rel(workspace_root, path),
        "exists": summary["exists"],
        "row_count": summary["row_count"],
        "columns": summary["columns"],
        "trace_path": _display_rel(workspace_root, trace),
        "trace_row_count": trace_summary["row_count"],
        "trace_columns": trace_summary["columns"],
        "trace_solver_input": trace_solver_input,
        "final_v23_solver_input": final_v23_solver_input,
        "output_substitution": output_substitution,
        "direct_nav_override": direct_nav_override,
        "final_v23_path": "final_v23" in str(path).lower(),
        "is_output_substitution": output_substitution or direct_nav_override,
        "is_future_data_safe": future_data_safe,
        "source_stage": _source_stage(path),
        "accepted": accepted,
        "reason": "accepted" if accepted else "blocked: " + "; ".join(issues),
    }


def _matching_feedback_trace(path: Path) -> Path | None:
    if path.name == "FGO_FEEDBACK_UPDATE_TRACE.csv":
        return path
    direct = path.parent / "run" / "FGO_FEEDBACK_UPDATE_TRACE.csv"
    if direct.is_file():
        return direct
    for root in [path.parent, path.parent.parent]:
        if root.exists():
            matches = sorted(root.rglob("FGO_FEEDBACK_UPDATE_TRACE.csv"))
            if matches:
                return matches[0]
    return None


def _read_csv_summary(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {"exists": False, "row_count": 0, "columns": []}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        row_count = sum(1 for _ in reader)
    return {"exists": True, "row_count": row_count, "columns": columns}


def _csv_column_any_truthy(path: Path | None, column: str) -> bool:
    if path is None or not path.is_file():
        return False
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if column not in (reader.fieldnames or []):
            return False
        return any(_is_truthy(row.get(column, "")) for row in reader)


def _future_data_safe(path: Path | None) -> bool:
    if path is None or not path.is_file():
        return False
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        if "source_window_end" not in fields:
            return False
        time_columns = [name for name in ("time", "observation_time", "update_time") if name in fields]
        if not time_columns:
            return False
        for row in reader:
            try:
                source_end = float(row["source_window_end"])
            except (TypeError, ValueError):
                return False
            for time_column in time_columns:
                try:
                    if source_end > float(row[time_column]) + 1e-6:
                        return False
                except (TypeError, ValueError):
                    return False
    return True


def _is_truthy(value: Any) -> bool:
    text = str(value).strip().lower()
    if text in {"", "0", "0.0", "false", "no", "none", "nan"}:
        return False
    if text in {"1", "1.0", "true", "yes", "y", "t"}:
        return True
    try:
        return float(text) != 0.0
    except ValueError:
        return True


def _source_stage(path: Path) -> str:
    for name in [
        "N8J_feedback_final_validation",
        "N8I_feedback_ablation_gate_covariance",
        "N8H_fgo_feedback_visual_validation",
        "N9A_R4D_METRIC_ALIGNMENT_AND_DIAGNOSTIC_SOURCE_INTEGRATION",
        "N9A_R4K_BY2_NORMAL_FULL_PLOT_WITH_LOCKED_BASELINES",
    ]:
        if name in str(path):
            return name
    return ""


def _wsl_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": row["case_id"],
        "algorithm": row["algorithm"],
        "command": row["command"],
        "command_type": row.get("command_type", ""),
        "working_directory": row.get("working_directory", ""),
        "bridge_script": "scripts/run_wsl_legsa.ps1",
        "dry_run_only": True,
        "executed": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "log_path": "",
    }


def _run_wsl_dryruns(workspace_root: Path, runtime_root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    script = workspace_root / "scripts" / "run_wsl_legsa.ps1"
    output: list[dict[str, Any]] = []
    for row in rows:
        log = runtime_root / "wsl_dryrun" / "logs" / f"{row['case_id']}__{row['algorithm']}.json"
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
            row["command"],
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
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        dryrun = dict(row)
        dryrun.update(
            {
                "log_path": _rel(runtime_root, log),
                "dryrun_returncode": completed.returncode,
                "dryrun_stdout_nonempty": bool(stdout.strip()),
                "dryrun_stderr": stderr.strip(),
            }
        )
        output.append(dryrun)
    return output


def _feedback_command_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": row["case_id"],
        "algorithm": row["algorithm"],
        "mapping_status": row["mapping_status"],
        "run_allowed_in_N9B1D": row["run_allowed_in_N9B1D"],
        "selected_feedback_acceptance": row.get("selected_feedback_acceptance", ""),
        "selected_feedback_candidate_source": row.get("selected_feedback_candidate_source", ""),
        "selected_feedback_block_reason": row.get("selected_feedback_block_reason", ""),
        "command": row["command"],
    }


def _diff_row(prior: dict[str, Any], repaired: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": repaired.get("case_id", ""),
        "algorithm": repaired.get("algorithm", ""),
        "routing_status": repaired.get("routing_status", ""),
        "prior_mapping_status": prior.get("mapping_status", ""),
        "repaired_mapping_status": repaired.get("mapping_status", ""),
        "prior_run_allowed_in_N9B1D": prior.get("run_allowed_in_N9B1D", ""),
        "repaired_run_allowed_in_N9B1D": repaired.get("run_allowed_in_N9B1D", ""),
        "prior_command_nonempty": bool(prior.get("command", "")),
        "repaired_command_nonempty": bool(repaired.get("command", "")),
        "repair_reason": repaired.get("blocked_reason", "") or "mapped",
    }


def _write_solver_command(runtime_root: Path, row: dict[str, Any]) -> None:
    path = runtime_root / row["solver_command_json"]
    payload = {
        key: row.get(key, "")
        for key in [
            "stage",
            "case_id",
            "algorithm",
            "routing_status",
            "mapping_status",
            "command_type",
            "command",
            "working_directory",
            "environment",
            "inputs",
            "degraded_input_paths",
            "degraded_input_paths_wsl",
            "generated_config_path",
            "generated_config_path_wsl",
            "output_root",
            "expected_outputs",
            "entrypoint",
            "run_allowed_in_N9B1D",
        ]
    }
    payload.update(
        {
            "command_plan_only": True,
            "dry_run_only": True,
            "solver_run": False,
            "official_evaluator_run": False,
            "trace_solver_input": False,
            "final_v23_solver_input": False,
        }
    )
    _write_json(path, payload)


def _write_outputs(runtime_root: Path, result: dict[str, Any]) -> None:
    reports = {
        "N9B1C1_ROUTING_COMMAND_CONSISTENCY_REPORT.json": result["routing_consistency_report"],
        "N9B1C1_SELECTED_FEEDBACK_DEPENDENCY_AUDIT_REPORT.json": result["selected_feedback_dependency_audit_report"],
        "N9B1C1_SELECTED_FEEDBACK_COMMAND_REPAIR_REPORT.json": result["selected_feedback_command_repair_report"],
        "N9B1C1_WSL_DRYRUN_REPORT.json": result["wsl_dryrun_report"],
        "N9B1C1_VALIDATION_REPORT.json": result["validation_report"],
        "N9B1C1_DECISION_REPORT.json": result["decision_report"],
    }
    for name, payload in reports.items():
        _write_json(runtime_root / "reports" / name, payload)
    matrices = {
        "N9B1C1_COMMAND_MAPPING_MATRIX_REPAIRED": result["command_mapping_matrix_repaired"],
        "N9B1C1_ROUTING_COMMAND_DIFF": result["routing_command_diff"],
        "N9B1C1_SELECTED_FEEDBACK_DEPENDENCY_MATRIX": result["selected_feedback_dependency_matrix"],
        "N9B1C1_SELECTED_FEEDBACK_COMMAND_MATRIX": result["selected_feedback_command_matrix"],
        "N9B1C1_WSL_DRYRUN_COMMAND_MATRIX": result["wsl_dryrun_command_matrix"],
    }
    for stem, rows in matrices.items():
        _write_table_pair(runtime_root / "matrix" / stem, rows)
    _write_table_pair(runtime_root / "routing_consistency" / "N9B1C1_ROUTING_COMMAND_DIFF", result["routing_command_diff"])
    _write_table_pair(runtime_root / "selected_feedback_dependency_audit" / "N9B1C1_SELECTED_FEEDBACK_DEPENDENCY_MATRIX", result["selected_feedback_dependency_matrix"])
    _write_table_pair(runtime_root / "wsl_dryrun" / "N9B1C1_WSL_DRYRUN_COMMAND_MATRIX", result["wsl_dryrun_command_matrix"])
    _write_json(runtime_root / "validation" / "N9B1C1_VALIDATION_REPORT.json", result["validation_report"])
    summaries = {
        "n9b1c1_selected_feedback_dependency_audit.md": _feedback_summary(result),
        "n9b1c1_next_stage_recommendation.md": _next_stage_summary(result),
    }
    for name, text in summaries.items():
        (runtime_root / "summary" / name).write_text(text, encoding="utf-8")


def _feedback_summary(result: dict[str, Any]) -> str:
    report = result["selected_feedback_dependency_audit_report"]
    return (
        "# N9B1C1 selected feedback dependency audit\n\n"
        f"- Candidate count: {report['candidate_count']}.\n"
        f"- Clean normal candidate found: {str(report['clean_normal_candidate_found']).lower()}.\n"
        "- Degraded selected-feedback cases remain blocked unless same-case feedback exists.\n"
        "- Solver/evaluator run: false.\n"
    )


def _next_stage_summary(result: dict[str, Any]) -> str:
    decision = result["decision_report"]
    return (
        "# N9B1C1 next stage recommendation\n\n"
        f"- status={decision['status']}\n"
        f"- ready_for_N9B1D_solver_execution={str(decision['ready_for_N9B1D_solver_execution']).lower()}\n"
        "- ready_for_N9B2_execution=false\n"
        "- N9B1D should consume only mapped rows from repaired command plans after human review.\n"
    )


def _create_runtime_tree(runtime_root: Path) -> None:
    for subdir in REQUIRED_SUBDIRS:
        path = runtime_root / subdir
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def _load_json_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return [dict(row) for row in payload] if isinstance(payload, list) else []


def _stage_replace(value: Any) -> str:
    return str(value or "").replace(PRIOR_STAGE, STAGE)


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


def _display_rel(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    return _rel(root, path)
