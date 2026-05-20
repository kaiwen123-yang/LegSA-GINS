"""N9B1C3 execution matrix hygiene and dependency-order lock.

This stage is reporting and audit metadata only. It reads N9B1C2 outputs,
cleans stale executable blockers, locks selected-feedback acceptance metadata,
records dependency ordering for N9B1D, and refreshes WSL dry-run plans. It does
not run solvers, evaluators, figure generation, or case reviews.
"""

from __future__ import annotations

import csv
import json
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from legsa_gins.reporting.by2_degradation_runner_precheck import FORBIDDEN_EXECUTION_OUTPUT_NAMES
from legsa_gins.reporting.by2_n9b1c2_selected_feedback_same_case_mapping import (
    L_DISABLED_CASE,
    M_CLEAN_REPEAT_CASE,
    SELECTED_FEEDBACK_ALGORITHM,
)
from legsa_gins.reporting.by2_real_pilot_input_generator import AUDIT_ROOT_NAME


STAGE = "N9B1C3_EXECUTION_MATRIX_HYGIENE_AND_DEPENDENCY_ORDER_LOCK"
N9B1C2_STAGE = "N9B1C2_SELECTED_FEEDBACK_SAME_CASE_FEEDBACK_GENERATION_MAPPING"
N9B1D_STAGE = "N9B1D_PILOT_SOLVER_EXECUTION"
BASELINE_ALGORITHM = "baseline_no_feedback_EKF"
PATH_RE = re.compile(r"(?P<quote>['\"]?)(/mnt/[^\s'\";]+|/home/[^\s'\";]+)(?P=quote)")

REQUIRED_SUBDIRS = [
    "matrix_hygiene",
    "dependency_graph",
    "path_preflight",
    "n9b1d_ready_commands",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
    "wsl_dryrun",
]
REPORT_NAMES = [
    "N9B1C3_MATRIX_HYGIENE_REPORT.json",
    "N9B1C3_DEPENDENCY_GRAPH_REPORT.json",
    "N9B1C3_WSL_PATH_PREFLIGHT_REPORT.json",
    "N9B1C3_WSL_DRYRUN_REFRESH_REPORT.json",
    "N9B1C3_VALIDATION_REPORT.json",
    "N9B1C3_DECISION_REPORT.json",
]
MATRIX_STEMS = [
    "N9B1C3_N9B1D_READY_COMMAND_MATRIX",
    "N9B1C3_STALE_FIELD_DIFF",
    "N9B1C3_CASE_DEPENDENCY_GRAPH",
    "N9B1C3_WSL_PATH_PREFLIGHT",
    "N9B1C3_WSL_DRYRUN_REFRESH",
]
TRACKED_FILES_FOR_PATH_AUDIT = [
    "src/legsa_gins/reporting/by2_n9b1c3_execution_matrix_hygiene_dependency_order.py",
    "scripts/experiments/run_n9b1c3_execution_matrix_hygiene_dependency_order.py",
    "scripts/audit_n9b1c3_execution_matrix_hygiene_dependency_order.py",
    "tests/unit/test_by2_n9b1c3_execution_matrix_hygiene_dependency_order.py",
    "tests/audit/test_n9b1c3_execution_matrix_hygiene_dependency_order.py",
]

ACCEPTANCE_MAP = {
    "two_stage_same_case_feedback_generation_plan": "mapped_same_case_plan",
    "clean_repeat_feedback_reuse": "mapped_clean_repeat",
    "feedback_disabled_marker": "mapped_disabled_marker",
}


def default_n9b1c3_runtime_root(workspace_root: Path) -> Path:
    return workspace_root / AUDIT_ROOT_NAME / STAGE


def run_n9b1c3_execution_matrix_hygiene_dependency_order(
    workspace_root: Path,
    runtime_root: Path | None = None,
    *,
    write_outputs: bool = True,
    run_wsl_path_preflight: bool = True,
    run_wsl_dryrun_refresh: bool = True,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root or default_n9b1c3_runtime_root(workspace_root)
    if write_outputs:
        _create_runtime_tree(runtime_root)

    c2_root = workspace_root / AUDIT_ROOT_NAME / N9B1C2_STAGE
    c2_command_rows = _load_json_rows(c2_root / "matrix" / "N9B1C2_COMMAND_MAPPING_MATRIX_REPAIRED.json")
    c2_selected_rows = _load_json_rows(c2_root / "matrix" / "N9B1C2_SELECTED_FEEDBACK_MAPPING_MATRIX.json")
    c2_plan_rows = _load_json_rows(c2_root / "matrix" / "N9B1C2_REPAIRED_COMMAND_PLAN_MATRIX.json")
    selected_by_case = {row.get("case_id", ""): row for row in c2_selected_rows}
    plan_rows_by_case = _rows_by_case(c2_plan_rows)

    ready_rows: list[dict[str, Any]] = []
    stale_diff_rows: list[dict[str, Any]] = []
    for prior in c2_command_rows:
        row = _ready_row(prior, selected_by_case.get(prior.get("case_id", "")))
        ready_rows.append(row)
        stale_diff_rows.extend(_stale_field_diff(prior, row))

    dependency_rows = _dependency_graph(c2_selected_rows, plan_rows_by_case)
    preflight_rows = _wsl_path_preflight_rows(workspace_root, ready_rows, c2_plan_rows, dependency_rows)
    if write_outputs and run_wsl_path_preflight:
        preflight_rows = _run_wsl_path_preflight(preflight_rows)
    dryrun_rows = _wsl_dryrun_refresh_rows(c2_plan_rows)
    if write_outputs and run_wsl_dryrun_refresh:
        dryrun_rows = _run_wsl_dryrun_refresh(workspace_root, runtime_root, dryrun_rows)

    validation = validate_n9b1c3_result(
        workspace_root,
        runtime_root,
        ready_rows,
        stale_diff_rows,
        dependency_rows,
        preflight_rows,
        dryrun_rows,
        runtime_written=False,
    )
    executable_rows = [row for row in ready_rows if row.get("n9b1d_executable") is True]
    selected_mapped = [
        row
        for row in ready_rows
        if row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM and row.get("mapping_status") == "mapped"
    ]
    reports = {
        "matrix_hygiene_report": {
            "stage": STAGE,
            "source_stage": N9B1C2_STAGE,
            "input_command_rows": len(c2_command_rows),
            "ready_command_rows": len(ready_rows),
            "n9b1d_executable_rows": len(executable_rows),
            "stale_field_diff_rows": len(stale_diff_rows),
            "stale_executable_blocker_count": sum(row.get("stale_executable_blocker") for row in ready_rows),
            "selected_feedback_mapped_rows": len(selected_mapped),
            "selected_feedback_safe_candidate_rows": sum(row.get("selected_feedback_safe_candidate") for row in selected_mapped),
            "solver_run": False,
            "official_evaluator_run": False,
            "figures_generated": False,
            "ready_for_N9B1D_solver_execution": validation["status"] == "pass",
            "ready_for_N9B2_execution": False,
        },
        "dependency_graph_report": {
            "stage": STAGE,
            "dependency_rows": len(dependency_rows),
            "same_case_selected_feedback_cases": sum(row.get("dependency_mode") == "same_case_selected_feedback" for row in dependency_rows),
            "clean_repeat_cases": sum(row.get("dependency_mode") == "clean_repeat_selected_feedback" for row in dependency_rows),
            "disabled_marker_cases": sum(row.get("dependency_mode") == "disabled_marker_selected_feedback" for row in dependency_rows),
            "baseline_to_feedback_to_selected_edges": sum(row.get("edge_type") == "baseline_to_feedback_to_selected_feedback" for row in dependency_rows),
            "solver_run": False,
            "official_evaluator_run": False,
            "ready_for_N9B2_execution": False,
        },
        "wsl_path_preflight_report": {
            "stage": STAGE,
            "preflight_rows": len(preflight_rows),
            "checked_rows": sum(row.get("preflight_checked") for row in preflight_rows),
            "exists_true_count": sum(row.get("exists") is True for row in preflight_rows),
            "planned_output_dependency_count": sum(row.get("classification") == "planned_output_dependency" for row in preflight_rows),
            "missing_count": sum(row.get("classification") == "missing" for row in preflight_rows),
            "mojibake_display_only_count": sum(row.get("mojibake_classification") == "display_only" for row in preflight_rows),
            "non_ascii_verified_by_wsl_count": sum(row.get("path_encoding_status") == "non_ascii_path_verified_by_wsl" for row in preflight_rows),
            "solver_run": False,
            "official_evaluator_run": False,
            "ready_for_N9B2_execution": False,
        },
        "wsl_dryrun_refresh_report": {
            "stage": STAGE,
            "bridge_script": "scripts/run_wsl_legsa.ps1",
            "dry_run_only": True,
            "dryrun_rows": len(dryrun_rows),
            "dryrun_success_count": sum(int(row.get("dryrun_returncode", 0) or 0) == 0 for row in dryrun_rows),
            "dryrun_failure_count": sum(int(row.get("dryrun_returncode", 0) or 0) != 0 for row in dryrun_rows),
            "executed": False,
            "solver_run": False,
            "official_evaluator_run": False,
            "ready_for_N9B2_execution": False,
        },
        "validation_report": validation,
    }
    decision_status, recommended_next_stage, ready_for_n9b1d = _decision_from_validation(validation["issues"])
    reports["decision_report"] = {
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
        **reports,
        "n9b1d_ready_command_matrix": ready_rows,
        "stale_field_diff": stale_diff_rows,
        "case_dependency_graph": dependency_rows,
        "wsl_path_preflight": preflight_rows,
        "wsl_dryrun_refresh": dryrun_rows,
    }
    if write_outputs:
        _write_outputs(runtime_root, result)
    return result


def validate_n9b1c3_result(
    workspace_root: Path,
    runtime_root: Path,
    ready_rows: list[dict[str, Any]] | None = None,
    stale_diff_rows: list[dict[str, Any]] | None = None,
    dependency_rows: list[dict[str, Any]] | None = None,
    preflight_rows: list[dict[str, Any]] | None = None,
    dryrun_rows: list[dict[str, Any]] | None = None,
    *,
    runtime_written: bool = True,
) -> dict[str, Any]:
    ready_rows = ready_rows or []
    stale_diff_rows = stale_diff_rows or []
    dependency_rows = dependency_rows or []
    preflight_rows = preflight_rows or []
    dryrun_rows = dryrun_rows or []
    issues: list[str] = []

    if runtime_written:
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
                    issues.append(f"json UTF-8 parse failed: {_rel(runtime_root, path)}: {exc}")

    for row in ready_rows:
        case_id = row.get("case_id", "")
        algorithm = row.get("algorithm", "")
        command_text = " ".join(str(row.get(key, "")) for key in ["command", "command_preview"])
        if row.get("routing_status") == "not_selected_in_prior_plan" and row.get("n9b1d_executable") is True:
            issues.append(f"not-selected row became executable: {case_id}/{algorithm}")
        if row.get("command_type") in {"diagnostic_blocked", "fixed_reference"} and row.get("n9b1d_executable") is True:
            issues.append(f"diagnostic/fixed row became executable: {case_id}/{algorithm}")
        if row.get("n9b1d_executable") is True:
            if row.get("block_reason") not in {"", None} or row.get("blocked_reason") not in {"", None}:
                issues.append(f"stale executable blocker remains: {case_id}/{algorithm}")
            if _truthy(row.get("n9b1b_block_reason")) and row.get("n9b1b_block_reason") != "superseded_by_N9B1C3":
                issues.append(f"n9b1b_block_reason not superseded: {case_id}/{algorithm}")
        if "future_solver_entry" in command_text:
            issues.append(f"future_solver_entry in executable command fields: {case_id}/{algorithm}")
        if algorithm == SELECTED_FEEDBACK_ALGORITHM and row.get("mapping_status") == "mapped":
            if row.get("selected_feedback_safe_candidate") is not True:
                issues.append(f"mapped selected_feedback not marked safe: {case_id}")
            if row.get("selected_feedback_block_reason") != "none":
                issues.append(f"mapped selected_feedback has block reason: {case_id}")
            if row.get("selected_feedback_acceptance") == "blocked":
                issues.append(f"mapped selected_feedback acceptance remains blocked: {case_id}")
            if row.get("selected_feedback_acceptance") == "mapped_clean_repeat" and case_id != M_CLEAN_REPEAT_CASE:
                issues.append(f"degraded selected_feedback uses clean feedback acceptance: {case_id}")
            if row.get("clean_n8j_path_used_for_degraded_case") is True:
                issues.append(f"degraded selected_feedback clean feedback use: {case_id}")
        for flag in ["solver_run", "official_evaluator_run", "NAV_generated", "STD_generated", "EVAL_NAV_generated", "RUN_MANIFEST_generated", "figures_generated", "case_review_generated"]:
            if row.get(flag) not in {False, 0, None}:
                issues.append(f"{flag} must be false: {case_id}/{algorithm}")

    for diff in stale_diff_rows:
        if diff.get("field") in {"block_reason", "blocked_reason"} and diff.get("after") not in {"", None} and diff.get("n9b1d_executable") is True:
            issues.append(f"stale diff leaves executable blocker: {diff.get('case_id')}/{diff.get('algorithm')}")

    graph_by_case = _rows_by_case(dependency_rows)
    for row in ready_rows:
        if row.get("algorithm") != SELECTED_FEEDBACK_ALGORITHM or row.get("mapping_status") != "mapped":
            continue
        modes = {edge.get("dependency_mode") for edge in graph_by_case.get(row["case_id"], [])}
        if row["case_id"] == M_CLEAN_REPEAT_CASE:
            if "clean_repeat_selected_feedback" not in modes:
                issues.append("M clean repeat dependency edge missing")
        elif row["case_id"] == L_DISABLED_CASE:
            if "disabled_marker_selected_feedback" not in modes:
                issues.append("L disabled marker dependency edge missing")
        elif "same_case_selected_feedback" not in modes:
            issues.append(f"same-case selected_feedback dependency chain missing: {row['case_id']}")

    for row in preflight_rows:
        if row.get("classification") == "missing" and row.get("planned_output_dependency") is not True:
            issues.append(f"required WSL path missing: {row.get('path')}")
        if row.get("classification") == "wsl_unavailable":
            issues.append(f"WSL path preflight unavailable: {row.get('path')}")
        if row.get("classification") == "missing" and row.get("planned_output_dependency") is True:
            issues.append(f"planned output dependency classified missing: {row.get('path')}")
        if row.get("mojibake_classification") == "display_only" and row.get("exists") is not True:
            issues.append(f"mojibake classified display-only without proven existence: {row.get('path')}")
        if row.get("solver_run") is True or row.get("official_evaluator_run") is True:
            issues.append(f"preflight row records solver/evaluator execution: {row.get('path')}")

    for row in dryrun_rows:
        if row.get("bridge_script") != "scripts/run_wsl_legsa.ps1":
            issues.append(f"dry-run refresh did not use bridge script: {row.get('case_id')}/{row.get('plan_stage')}")
        if row.get("dry_run_only") is not True or row.get("executed") is not False:
            issues.append(f"dry-run refresh execution flags invalid: {row.get('case_id')}/{row.get('plan_stage')}")
        if row.get("solver_run") is True or row.get("official_evaluator_run") is True:
            issues.append(f"dry-run refresh records solver/evaluator execution: {row.get('case_id')}/{row.get('plan_stage')}")

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


def _decision_from_validation(issues: list[str]) -> tuple[str, str, bool]:
    if not issues:
        return (
            "N9B1C3_execution_matrix_clean_and_order_locked",
            "human_review_N9B1C3_then_N9B1D_solver_execution",
            True,
        )
    issue_text = "\n".join(issues).lower()
    if any(token in issue_text for token in ["wsl path", "mojibake", "path preflight"]):
        return ("N9B1C3_path_preflight_failed", "fix_path_encoding", False)
    if "dependency" in issue_text:
        return ("N9B1C3_dependency_order_failed", "fix_dependency_order", False)
    if any(token in issue_text for token in ["stale", "blocker", "acceptance"]):
        return ("N9B1C3_matrix_hygiene_failed", "fix_matrix_hygiene", False)
    return ("N9B1C3_safety_gate_failed", "repair_safety_violation", False)


def _ready_row(prior: dict[str, Any], selected: dict[str, Any] | None) -> dict[str, Any]:
    row = dict(prior)
    row["stage"] = STAGE
    row["source_stage"] = prior.get("stage", N9B1C2_STAGE)
    row["prior_stage"] = prior.get("stage", "")
    row["prior_block_reason"] = prior.get("block_reason", prior.get("blocked_reason", ""))
    executable = _is_executable_candidate(prior)
    row["n9b1d_executable"] = executable
    row["ready_for_N9B1D_solver_execution"] = executable
    row["run_allowed_in_N9B1D"] = executable
    row["ready_for_N9B2_execution"] = False
    row["solver_run"] = False
    row["official_evaluator_run"] = False
    row["NAV_generated"] = False
    row["STD_generated"] = False
    row["EVAL_NAV_generated"] = False
    row["RUN_MANIFEST_generated"] = False
    row["figures_generated"] = False
    row["case_review_generated"] = False
    row["command_plan_only"] = True
    row["execution_matrix_hygiene_locked"] = True
    row["n9b1c3_dependency_order_locked"] = True
    row["n9b1b_block_reason"] = "superseded_by_N9B1C3" if executable and _truthy(row.get("n9b1b_block_reason")) else "none"
    if executable:
        row["block_reason"] = ""
        row["blocked_reason"] = ""
    else:
        row["n9b1d_non_executable_reason"] = row.get("blocked_reason") or row.get("block_reason") or _non_executable_reason(row)
    row["stale_executable_blocker"] = bool(executable and (row.get("block_reason") or row.get("blocked_reason")))

    if row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM:
        if selected and selected.get("mapping_status") == "mapped":
            acceptance = ACCEPTANCE_MAP.get(selected.get("acceptance_mode", ""), "blocked")
            row.update(
                {
                    "mapping_status": "mapped",
                    "selected_feedback_safe_candidate": True,
                    "selected_feedback_block_reason": "none",
                    "selected_feedback_acceptance": acceptance,
                    "acceptance_mode": selected.get("acceptance_mode", ""),
                    "planned_same_case_feedback_path": selected.get("planned_same_case_feedback_path", ""),
                    "clean_n8j_path_used_for_degraded_case": selected.get("clean_n8j_path_used_for_degraded_case", False),
                    "stage1_plan_exists": selected.get("stage1_plan_exists", False),
                    "stage2_plan_exists": selected.get("stage2_plan_exists", False),
                    "dependency_order_requirement": _selected_dependency_requirement(row.get("case_id", ""), acceptance),
                }
            )
        else:
            row["selected_feedback_safe_candidate"] = False
            row["selected_feedback_block_reason"] = row.get("blocked_reason") or row.get("block_reason") or "not_mapped_by_N9B1C2"
            row["selected_feedback_acceptance"] = "blocked"
    return row


def _is_executable_candidate(row: dict[str, Any]) -> bool:
    if row.get("mapping_status") != "mapped":
        return False
    if row.get("routing_status") == "not_selected_in_prior_plan":
        return False
    if row.get("command_type") in {"diagnostic_blocked", "fixed_reference"}:
        return False
    if not row.get("command"):
        return False
    if "future_solver_entry" in str(row.get("command", "")):
        return False
    return True


def _non_executable_reason(row: dict[str, Any]) -> str:
    if row.get("routing_status") == "not_selected_in_prior_plan":
        return "not_selected_in_prior_plan"
    if row.get("command_type") in {"diagnostic_blocked", "fixed_reference"}:
        return row.get("command_type", "")
    if row.get("mapping_status") != "mapped":
        return "mapping_status_not_mapped"
    if not row.get("command"):
        return "missing_command"
    return "non_executable_by_N9B1C3_policy"


def _selected_dependency_requirement(case_id: str, acceptance: str) -> str:
    if acceptance == "mapped_same_case_plan":
        return f"{BASELINE_ALGORITHM} solver output -> feedback observations generation -> {SELECTED_FEEDBACK_ALGORITHM}"
    if acceptance == "mapped_clean_repeat":
        return f"{M_CLEAN_REPEAT_CASE} clean feedback repeat -> {SELECTED_FEEDBACK_ALGORITHM}"
    if acceptance == "mapped_disabled_marker":
        return f"{L_DISABLED_CASE} feedback disabled marker; no feedback observations consumed"
    return f"{case_id} blocked"


def _stale_field_diff(prior: dict[str, Any], row: dict[str, Any]) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    fields = [
        "block_reason",
        "blocked_reason",
        "n9b1b_block_reason",
        "mapping_status",
        "selected_feedback_acceptance",
        "selected_feedback_block_reason",
        "ready_for_N9B1D_solver_execution",
        "run_allowed_in_N9B1D",
    ]
    for field in fields:
        before = prior.get(field, "")
        after = row.get(field, "")
        if before != after:
            diffs.append(
                {
                    "stage": STAGE,
                    "case_id": row.get("case_id", ""),
                    "algorithm": row.get("algorithm", ""),
                    "field": field,
                    "before": before,
                    "after": after,
                    "n9b1d_executable": row.get("n9b1d_executable", False),
                    "change_reason": _change_reason(field, row),
                    "solver_run": False,
                    "official_evaluator_run": False,
                    "ready_for_N9B2_execution": False,
                }
            )
    return diffs


def _change_reason(field: str, row: dict[str, Any]) -> str:
    if field in {"block_reason", "blocked_reason", "n9b1b_block_reason"}:
        return "stale executable blocker superseded by N9B1C3 hygiene lock"
    if row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM:
        return "selected_feedback acceptance locked from N9B1C2"
    return "N9B1D readiness metadata normalized"


def _dependency_graph(selected_rows: list[dict[str, Any]], plan_rows_by_case: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for selected in selected_rows:
        case_id = selected.get("case_id", "")
        acceptance = ACCEPTANCE_MAP.get(selected.get("acceptance_mode", ""), "blocked")
        plans = {row.get("plan_stage", ""): row for row in plan_rows_by_case.get(case_id, [])}
        if acceptance == "mapped_same_case_plan":
            rows.append(
                _edge(
                    case_id,
                    "same_case_selected_feedback",
                    "baseline_solver_output",
                    "feedback_observation_generation",
                    "baseline_to_feedback_to_selected_feedback",
                    1,
                    BASELINE_ALGORITHM,
                    SELECTED_FEEDBACK_ALGORITHM,
                    plans.get("stage1_feedback_generation", {}).get("command", ""),
                    plans.get("stage1_feedback_generation", {}).get("planned_feedback_path", ""),
                )
            )
            rows.append(
                _edge(
                    case_id,
                    "same_case_selected_feedback",
                    "feedback_observation_generation",
                    "selected_feedback_EKF",
                    "baseline_to_feedback_to_selected_feedback",
                    2,
                    BASELINE_ALGORITHM,
                    SELECTED_FEEDBACK_ALGORITHM,
                    plans.get("stage2_selected_feedback_ekf", {}).get("command", ""),
                    plans.get("stage2_selected_feedback_ekf", {}).get("planned_feedback_path", ""),
                )
            )
        elif acceptance == "mapped_clean_repeat":
            rows.append(
                _edge(
                    case_id,
                    "clean_repeat_selected_feedback",
                    "M_clean_repeat_existing_feedback",
                    "selected_feedback_EKF",
                    "clean_repeat_feedback_to_selected_feedback",
                    1,
                    "clean_repeat_feedback",
                    SELECTED_FEEDBACK_ALGORITHM,
                    plans.get("stage2_selected_feedback_ekf", {}).get("command", ""),
                    plans.get("stage2_selected_feedback_ekf", {}).get("planned_feedback_path", ""),
                )
            )
        elif acceptance == "mapped_disabled_marker":
            rows.append(
                _edge(
                    case_id,
                    "disabled_marker_selected_feedback",
                    "feedback_disabled_marker",
                    "selected_feedback_EKF_marker",
                    "disabled_marker_no_feedback_dependency",
                    1,
                    "none",
                    SELECTED_FEEDBACK_ALGORITHM,
                    plans.get("stage2_selected_feedback_ekf", {}).get("command", ""),
                    "",
                )
            )
    return rows


def _edge(
    case_id: str,
    mode: str,
    source_node: str,
    target_node: str,
    edge_type: str,
    order_index: int,
    source_algorithm: str,
    target_algorithm: str,
    command: str,
    dependency_path: str,
) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "case_id": case_id,
        "dependency_mode": mode,
        "source_node": source_node,
        "target_node": target_node,
        "edge_type": edge_type,
        "order_index": order_index,
        "source_algorithm": source_algorithm,
        "target_algorithm": target_algorithm,
        "dependency_path": dependency_path,
        "command_preview": command,
        "command_plan_only": True,
        "solver_run": False,
        "official_evaluator_run": False,
        "ready_for_N9B2_execution": False,
    }


def _wsl_path_preflight_rows(
    workspace_root: Path,
    ready_rows: list[dict[str, Any]],
    plan_rows: list[dict[str, Any]],
    dependency_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    path_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for row in ready_rows:
        context = f"{row.get('case_id', '')}/{row.get('algorithm', '')}"
        for role, path in _paths_from_ready_row(row):
            _add_path_row(path_rows, context, role, path)
    for row in plan_rows:
        context = f"{row.get('case_id', '')}/{row.get('algorithm', '')}/{row.get('plan_stage', '')}"
        for path in _extract_wsl_paths(row.get("command", "")):
            role = "planned_output_dependency" if _is_planned_output_path(path) else "command_path"
            _add_path_row(path_rows, context, role, path)
        if row.get("planned_feedback_path"):
            if row.get("clean_repeat") is True:
                _add_path_row(
                    path_rows,
                    context,
                    "feedback_input_dependency",
                    _to_wsl_path(workspace_root / row["planned_feedback_path"]),
                )
            else:
                _add_path_row(path_rows, context, "planned_output_dependency", row["planned_feedback_path"])
    for row in dependency_rows:
        if row.get("dependency_path"):
            if row.get("dependency_mode") == "clean_repeat_selected_feedback":
                _add_path_row(
                    path_rows,
                    row.get("case_id", ""),
                    "feedback_input_dependency",
                    _to_wsl_path(workspace_root / row["dependency_path"]),
                )
            else:
                _add_path_row(path_rows, row.get("case_id", ""), "planned_output_dependency", row["dependency_path"])
    return sorted(path_rows.values(), key=lambda row: (row["context"], row["role"], row["path"]))


def _paths_from_ready_row(row: dict[str, Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for path in _extract_wsl_paths(row.get("command", "")):
        role = "planned_output_dependency" if _is_planned_output_path(path) else "command_path"
        pairs.append((role, path))
    for key, value in (row.get("inputs") or {}).items():
        if isinstance(value, str) and (value.startswith("/") or value.endswith((".imu", ".gnss", ".csv", ".txt"))):
            pairs.append((f"input_dependency:{key}", value))
    for key, value in (row.get("expected_outputs") or {}).items():
        if isinstance(value, str) and value:
            pairs.append((f"planned_output_dependency:{key}", value))
    config = row.get("generated_config_path_wsl") or ""
    if config:
        pairs.append(("config_dependency", config))
    return pairs


def _add_path_row(path_rows: dict[tuple[str, str], dict[str, Any]], context: str, role: str, path: str) -> None:
    if not path or path in {"gnss_velocity_columns", "dual_antenna_yaw_columns"}:
        return
    planned = role.startswith("planned_output_dependency") or _is_planned_output_path(path)
    normalized = str(path).replace("\\", "/")
    key = (role, normalized)
    if key in path_rows:
        row = path_rows[key]
        contexts = row.setdefault("contexts", [])
        if context not in contexts:
            contexts.append(context)
        row["context_count"] = len(contexts)
        row["context"] = contexts[0]
        return
    path_rows[key] = {
        "stage": STAGE,
        "context": context,
        "contexts": [context],
        "context_count": 1,
        "role": role,
        "path": normalized,
        "planned_output_dependency": planned,
        "preflight_command": "" if planned else f"test -e {_q(normalized)}",
        "preflight_checked": False,
        "exists": None,
        "classification": "planned_output_dependency" if planned else "unchecked",
        "non_ascii_path": _has_non_ascii(normalized),
        "mojibake_suspect": _has_mojibake_suspect(normalized),
        "mojibake_classification": "not_applicable",
        "path_encoding_status": "planned_output_dependency" if planned else "unchecked",
        "solver_run": False,
        "official_evaluator_run": False,
        "ready_for_N9B2_execution": False,
    }


def _run_wsl_path_preflight(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = [dict(row) for row in rows]
    check_indices = [index for index, row in enumerate(output) if not row.get("planned_output_dependency")]
    if not check_indices:
        return output
    paths = [output[index]["path"] for index in check_indices]
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write("\n".join(paths) + "\n")
        list_path = _to_wsl_path(temp_path)
        completed = subprocess.run(
            [
                "wsl.exe",
                "python3",
                "-c",
                (
                    "from pathlib import Path\n"
                    "import sys\n"
                    "for line in Path(sys.argv[1]).read_text(encoding='utf-8').splitlines():\n"
                    "    print(0 if Path(line).exists() else 1)\n"
                ),
                list_path,
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        status_lines = (completed.stdout or "").splitlines()
        for offset, index in enumerate(check_indices):
            checked = output[index]
            returncode = int(status_lines[offset]) if offset < len(status_lines) and status_lines[offset] in {"0", "1"} else 1
            exists = returncode == 0
            checked.update(
                {
                    "preflight_checked": True,
                    "exists": exists,
                    "preflight_returncode": returncode,
                    "preflight_stderr": (completed.stderr or "").strip(),
                    "classification": "exists" if exists else "missing",
                    "path_encoding_status": _path_encoding_status(checked, exists),
                }
            )
            if checked.get("mojibake_suspect"):
                checked["mojibake_classification"] = "display_only" if exists else "unproven"
    except OSError as exc:
        for index in check_indices:
            output[index].update(
                {
                    "preflight_checked": False,
                    "exists": None,
                    "preflight_error": str(exc),
                    "classification": "wsl_unavailable",
                }
            )
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass
    return output


def _wsl_dryrun_refresh_rows(plan_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in plan_rows:
        rows.append(
            {
                "stage": STAGE,
                "case_id": row.get("case_id", ""),
                "algorithm": row.get("algorithm", ""),
                "plan_stage": row.get("plan_stage", ""),
                "command": row.get("command", ""),
                "working_directory": row.get("working_directory", ""),
                "bridge_script": "scripts/run_wsl_legsa.ps1",
                "dry_run_only": True,
                "executed": False,
                "solver_run": False,
                "official_evaluator_run": False,
                "log_path": "",
                "ready_for_N9B2_execution": False,
            }
        )
    return rows


def _run_wsl_dryrun_refresh(workspace_root: Path, runtime_root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    script = workspace_root / "scripts" / "run_wsl_legsa.ps1"
    output: list[dict[str, Any]] = []
    for row in rows:
        log = runtime_root / "wsl_dryrun" / "logs" / f"{row['case_id']}__{row['plan_stage']}.json"
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


def _extract_wsl_paths(text: Any) -> list[str]:
    return [match.group(2).rstrip(",") for match in PATH_RE.finditer(str(text))]


def _to_wsl_path(path: Path | str) -> str:
    value = str(path)
    if value.startswith("/"):
        return value.replace("\\", "/")
    resolved = Path(value).resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = resolved.as_posix().split(":", 1)[-1].lstrip("/")
    return f"/mnt/{drive}/{rest}" if drive else resolved.as_posix()


def _has_non_ascii(value: str) -> bool:
    return any(ord(char) > 127 for char in value)


def _has_mojibake_suspect(value: str) -> bool:
    return any(token in value for token in ["??", "\ufffd", "鈥", "�"])


def _path_encoding_status(row: dict[str, Any], exists: bool) -> str:
    if row.get("mojibake_suspect"):
        return "display_only_mojibake_verified_by_wsl" if exists else "mojibake_unproven"
    if row.get("non_ascii_path"):
        return "non_ascii_path_verified_by_wsl" if exists else "non_ascii_path_missing"
    return "ascii_path_exists" if exists else "ascii_path_missing"


def _is_planned_output_path(path: str) -> bool:
    text = str(path)
    return any(
        token in text
        for token in [
            f"{N9B1D_STAGE}/algorithm_outputs",
            "same_case_feedback_plan/",
            "FGO_FEEDBACK_OBSERVATIONS.csv",
            "OBSERVATION_BUILD_REPORT.json",
            "EVAL_NAV.csv",
            "NAV.csv",
            "STD.csv",
            "RUN_MANIFEST",
        ]
    )


def _rows_by_case(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row.get("case_id", ""), []).append(row)
    return grouped


def _write_outputs(runtime_root: Path, result: dict[str, Any]) -> None:
    reports = {
        "N9B1C3_MATRIX_HYGIENE_REPORT.json": result["matrix_hygiene_report"],
        "N9B1C3_DEPENDENCY_GRAPH_REPORT.json": result["dependency_graph_report"],
        "N9B1C3_WSL_PATH_PREFLIGHT_REPORT.json": result["wsl_path_preflight_report"],
        "N9B1C3_WSL_DRYRUN_REFRESH_REPORT.json": result["wsl_dryrun_refresh_report"],
        "N9B1C3_VALIDATION_REPORT.json": result["validation_report"],
        "N9B1C3_DECISION_REPORT.json": result["decision_report"],
    }
    for name, payload in reports.items():
        _write_json(runtime_root / "reports" / name, payload)
    matrices = {
        "N9B1C3_N9B1D_READY_COMMAND_MATRIX": result["n9b1d_ready_command_matrix"],
        "N9B1C3_STALE_FIELD_DIFF": result["stale_field_diff"],
        "N9B1C3_CASE_DEPENDENCY_GRAPH": result["case_dependency_graph"],
        "N9B1C3_WSL_PATH_PREFLIGHT": result["wsl_path_preflight"],
        "N9B1C3_WSL_DRYRUN_REFRESH": result["wsl_dryrun_refresh"],
    }
    for stem, rows in matrices.items():
        _write_table_pair(runtime_root / "matrix" / stem, rows)
    _write_table_pair(runtime_root / "matrix_hygiene" / "N9B1C3_N9B1D_READY_COMMAND_MATRIX", result["n9b1d_ready_command_matrix"])
    _write_table_pair(runtime_root / "matrix_hygiene" / "N9B1C3_STALE_FIELD_DIFF", result["stale_field_diff"])
    _write_table_pair(runtime_root / "dependency_graph" / "N9B1C3_CASE_DEPENDENCY_GRAPH", result["case_dependency_graph"])
    _write_table_pair(runtime_root / "path_preflight" / "N9B1C3_WSL_PATH_PREFLIGHT", result["wsl_path_preflight"])
    _write_table_pair(runtime_root / "n9b1d_ready_commands" / "N9B1C3_N9B1D_READY_COMMAND_MATRIX", result["n9b1d_ready_command_matrix"])
    _write_table_pair(runtime_root / "n9b1d_ready_commands" / "N9B1C3_WSL_DRYRUN_REFRESH", result["wsl_dryrun_refresh"])
    _write_json(runtime_root / "validation" / "N9B1C3_VALIDATION_REPORT.json", result["validation_report"])
    (runtime_root / "summary" / "n9b1c3_dependency_order.md").write_text(_dependency_summary(result), encoding="utf-8")
    (runtime_root / "summary" / "n9b1c3_next_stage_recommendation.md").write_text(_next_stage_summary(result), encoding="utf-8")


def _dependency_summary(result: dict[str, Any]) -> str:
    report = result["dependency_graph_report"]
    hygiene = result["matrix_hygiene_report"]
    return (
        "# N9B1C3 dependency order lock\n\n"
        f"- ready_command_rows={hygiene['ready_command_rows']}\n"
        f"- n9b1d_executable_rows={hygiene['n9b1d_executable_rows']}\n"
        f"- dependency_rows={report['dependency_rows']}\n"
        f"- same_case_selected_feedback_cases={report['same_case_selected_feedback_cases']}\n"
        f"- clean_repeat_cases={report['clean_repeat_cases']}\n"
        f"- disabled_marker_cases={report['disabled_marker_cases']}\n"
        "- same-case selected_feedback order=baseline_no_feedback_EKF solver output -> feedback observations generation -> selected_feedback_EKF\n"
        "- solver/evaluator/figure/case-review generation=false\n"
    )


def _next_stage_summary(result: dict[str, Any]) -> str:
    decision = result["decision_report"]
    return (
        "# N9B1C3 next stage recommendation\n\n"
        f"- status={decision['status']}\n"
        f"- ready_for_N9B1D_solver_execution={str(decision['ready_for_N9B1D_solver_execution']).lower()}\n"
        "- ready_for_N9B2_execution=false\n"
        "- N9B1D remains a future human-approved solver execution stage.\n"
    )


def _create_runtime_tree(runtime_root: Path) -> None:
    for subdir in REQUIRED_SUBDIRS:
        path = runtime_root / subdir
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
    (runtime_root / "wsl_dryrun" / "logs").mkdir(parents=True, exist_ok=True)


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


def _q(value: Any) -> str:
    return shlex.quote(str(value))


def _tracked_absolute_path_issues(workspace_root: Path) -> list[str]:
    issues: list[str] = []
    forbidden = ["C:" + "\\Users\\", "C:" + "/Users/"]
    for rel_path in TRACKED_FILES_FOR_PATH_AUDIT:
        path = workspace_root / rel_path
        if not path.is_file():
            issues.append(f"missing tracked file for path audit: {rel_path}")
            continue
        text = path.read_text(encoding="utf-8")
        if any(prefix in text for prefix in forbidden):
            issues.append(f"local absolute path in tracked file: {rel_path}")
    return issues
