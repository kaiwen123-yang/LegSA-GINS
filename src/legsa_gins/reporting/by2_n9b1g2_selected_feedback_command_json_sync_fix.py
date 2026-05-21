"""N9B1G2 selected-feedback command JSON synchronization fix.

This stage is a command-plan synchronization and audit stage only. It reads the
repaired N9B1G1 command matrix, rewrites active command JSON files into the
N9B1G2 runtime tree, and validates selected-feedback safety boundaries before
N9B1D solver execution. It never runs solvers, evaluators, figure generation, or
case review generation.
"""

from __future__ import annotations

import ast
import csv
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legsa_gins.reporting.by2_n9b1g_case_level_command_rebind_with_formal_runner import (
    SELECTED_FEEDBACK_ALGORITHM,
    SINGLE_BASELINE_ALGORITHM,
    _rel,
    _safe_name,
    _write_table_pair,
    repo_to_wsl,
)
from legsa_gins.reporting.by2_real_pilot_input_generator import AUDIT_ROOT_NAME


STAGE = "N9B1G2_SELECTED_FEEDBACK_COMMAND_JSON_SYNC_FIX"
SOURCE_STAGE = "N9B1G1_SELECTED_FEEDBACK_STAGE1_EVAL_DEPENDENCY_FIX_AND_SINGLE_POSITION_NOISE_GUARD"
N9B1D_STAGE = "N9B1D_PILOT_SOLVER_EXECUTION_AND_EVALUATION"
FEEDBACK_SCRIPT = "scripts/experiments/run_n9b1c2_selected_feedback_same_case_mapping.py"
FEEDBACK_MODULE = "src/legsa_gins/reporting/by2_n9b1c2_selected_feedback_same_case_mapping.py"
SLIDING_WINDOW_MODULE = "src/legsa_gins/fgo_feedback/sliding_window_manager.py"

COMMAND_JSON_SUBDIR = Path("command_json_sync") / "cmd"
REQUIRED_SUBDIRS = [
    "command_json_sync",
    "matrix_consistency",
    "feedback_eval_nav_safety",
    "wsl_dryrun",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
]
REPORT_NAMES = [
    "N9B1G2_COMMAND_JSON_SYNC_REPORT.json",
    "N9B1G2_READY_COMMAND_MATRIX_REPORT.json",
    "N9B1G2_FEEDBACK_EVAL_NAV_SAFETY_AUDIT_REPORT.json",
    "N9B1G2_WSL_DRYRUN_REPORT.json",
    "N9B1G2_VALIDATION_REPORT.json",
    "N9B1G2_DECISION_REPORT.json",
]
MATRIX_STEMS = [
    "N9B1G2_COMMAND_JSON_SYNC_MATRIX",
    "N9B1G2_N9B1D_READY_COMMAND_MATRIX",
    "N9B1G2_WSL_DRYRUN_COMMANDS",
]
FORBIDDEN_COMMAND_TOKENS = ["future_solver_entry", "--normal-parity-mode", "--run-filter-csv"]
FORBIDDEN_RUNTIME_OUTPUT_NAMES = {
    "LegSA_NAV.nav",
    "LegSA_PORT_NAV.nav",
    "LegSA_STD.csv",
    "LegSA_PORT_STD.csv",
    "KF_GINS_Navresult.nav",
    "KF_GINS_STD.txt",
    "EVAL_NAV.csv",
    "RUN_MANIFEST.json",
    "FGO_FEEDBACK_OBSERVATIONS.csv",
    "FGO_SMOOTHED_NAV.csv",
    "FGO_FACTOR_TABLE.csv",
}
ESTIMATE_EVAL_NAV_COLUMNS = {
    "time",
    "lat_deg",
    "lon_deg",
    "height_m",
    "vn",
    "ve",
    "vd",
    "roll_deg",
    "pitch_deg",
    "yaw_deg",
}
TRACE_OR_ERROR_COLUMN_PATTERNS = (
    "trace",
    "truth",
    "ref_",
    "reference",
    "error",
    "err_",
    "horizontal_error",
    "north_error",
    "east_error",
    "up_error",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_n9b1g2_runtime_root(workspace_root: Path) -> Path:
    return workspace_root / AUDIT_ROOT_NAME / STAGE


def run_n9b1g2_selected_feedback_command_json_sync_fix(
    workspace_root: Path,
    runtime_root: Path | None = None,
    *,
    write_outputs: bool = True,
    run_wsl_dryrun: bool = True,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root or default_n9b1g2_runtime_root(workspace_root)
    if write_outputs:
        _reset_runtime_tree(runtime_root)

    source_rows, source_path = _load_n9b1g1_rows(workspace_root)
    command_rows, sync_rows = _sync_command_json_rows(runtime_root, source_rows, write_outputs=write_outputs)
    dryrun_rows = _build_wsl_dryrun_rows(workspace_root, runtime_root, command_rows)
    if write_outputs and run_wsl_dryrun:
        dryrun_rows = _run_wsl_dryrun(workspace_root, dryrun_rows)
    safety_report = audit_feedback_eval_nav_safety(workspace_root)
    sync_report = _command_json_sync_report(command_rows, sync_rows, source_path)
    ready_report = _ready_command_matrix_report(command_rows)
    wsl_report = _wsl_dryrun_report(dryrun_rows, run_wsl_dryrun)
    validation = validate_n9b1g2_result(
        workspace_root,
        runtime_root,
        command_rows,
        sync_rows,
        dryrun_rows,
        safety_report,
        runtime_written=False,
    )
    decision = _decision_report(validation, sync_report, safety_report)
    result = {
        "command_json_sync_report": sync_report,
        "ready_command_matrix_report": ready_report,
        "feedback_eval_nav_safety_audit_report": safety_report,
        "wsl_dryrun_report": wsl_report,
        "validation_report": validation,
        "decision_report": decision,
        "command_json_sync_matrix": sync_rows,
        "n9b1d_ready_command_matrix": command_rows,
        "wsl_dryrun_commands": dryrun_rows,
    }
    if write_outputs:
        _write_outputs(runtime_root, result)
        result["validation_report"] = validate_n9b1g2_result(
            workspace_root,
            runtime_root,
            command_rows,
            sync_rows,
            dryrun_rows,
            safety_report,
            runtime_written=True,
        )
        result["decision_report"] = _decision_report(result["validation_report"], sync_report, safety_report)
        _write_outputs(runtime_root, result)
    return result


def validate_n9b1g2_result(
    workspace_root: Path,
    runtime_root: Path,
    command_rows: list[dict[str, Any]] | None = None,
    sync_rows: list[dict[str, Any]] | None = None,
    dryrun_rows: list[dict[str, Any]] | None = None,
    safety_report: dict[str, Any] | None = None,
    *,
    runtime_written: bool = True,
) -> dict[str, Any]:
    command_rows = command_rows or []
    sync_rows = sync_rows or []
    dryrun_rows = dryrun_rows or []
    safety_report = safety_report or {}
    active_rows = [row for row in command_rows if row.get("run_allowed_in_N9B1D") is True]
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
            if path.name in FORBIDDEN_RUNTIME_OUTPUT_NAMES:
                issues.append(f"forbidden runtime output generated: {_rel(runtime_root, path)}")
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg", ".pdf"}:
                issues.append(f"forbidden figure/case artifact generated: {_rel(runtime_root, path)}")
            if path.suffix.lower() == ".json":
                raw = path.read_bytes()
                if raw.startswith(b"\xef\xbb\xbf"):
                    issues.append(f"json BOM present: {_rel(runtime_root, path)}")
                try:
                    json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    issues.append(f"json parse failed: {_rel(runtime_root, path)}: {exc}")

    if len(active_rows) != 64:
        issues.append(f"expected 64 active command rows, found {len(active_rows)}")
    if len(sync_rows) != len(active_rows):
        issues.append(f"sync row count mismatch: sync={len(sync_rows)} active={len(active_rows)}")
    if len(dryrun_rows) != len(active_rows):
        issues.append(f"expected {len(active_rows)} WSL dry-run rows, found {len(dryrun_rows)}")
    if safety_report.get("status") not in {"pass", "conditional_pass_with_note"}:
        issues.append(f"feedback EVAL_NAV safety audit did not pass: {safety_report.get('status', '')}")

    by_json = {row.get("command_json_path"): row for row in sync_rows}
    command_json_payload_mismatch_count = 0
    command_json_stale_eval_nav_count = 0
    command_json_official_eval_count = 0
    command_json_forbidden_token_count = 0
    for row in active_rows:
        row_id = _row_id(row)
        command_json_path = str(row.get("solver_command_json", ""))
        if command_json_path not in by_json:
            issues.append(f"matrix row not represented in sync matrix: {row_id}")
        if "command_json_sync" not in command_json_path:
            issues.append(f"solver_command_json not synchronized to N9B1G2 runtime: {row_id}")
        if runtime_written and command_json_path:
            path = Path(command_json_path)
            if not path.is_file():
                issues.append(f"missing synchronized command JSON: {row_id}: {command_json_path}")
            else:
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload_blob = json.dumps(payload, ensure_ascii=False)
                for key in ["command", "case_id", "algorithm", "stage", "solver_command_json"]:
                    if payload.get(key) != row.get(key):
                        command_json_payload_mismatch_count += 1
                        issues.append(f"command JSON payload mismatch for {key}: {row_id}")
                if _contains_stale_stage1_baseline_eval_nav(payload_blob):
                    command_json_stale_eval_nav_count += 1
                    issues.append(f"stale stage1_baseline/EVAL_NAV path remains in command JSON: {row_id}")
                if row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM and row.get("stage") == "selected_feedback_stage1_feedback_generation":
                    if "/stage1_baseline_official_eval/EVAL_NAV.csv" in payload_blob:
                        command_json_official_eval_count += 1
                    else:
                        issues.append(f"feedback generation command JSON does not use official eval EVAL_NAV: {row_id}")
                for token in FORBIDDEN_COMMAND_TOKENS:
                    if token in payload_blob:
                        command_json_forbidden_token_count += 1
                        issues.append(f"forbidden command token remains in command JSON: {token}: {row_id}")
        haystack = json.dumps(row, ensure_ascii=False)
        for token in FORBIDDEN_COMMAND_TOKENS:
            if token in haystack:
                issues.append(f"forbidden command token remains in row: {token}: {row_id}")
        if _contains_stale_stage1_baseline_eval_nav(haystack):
            issues.append(f"stale stage1_baseline/EVAL_NAV path remains in row: {row_id}")
        if _contains_stale_n9b1d_root(haystack):
            issues.append(f"stale N9B1D output root remains in row: {row_id}")
        if N9B1D_STAGE not in haystack:
            issues.append(f"N9B1D execution/evaluation output root absent from row: {row_id}")
        for flag in ["solver_run", "official_evaluator_run", "NAV_generated", "STD_generated", "EVAL_NAV_generated", "RUN_MANIFEST_generated"]:
            if row.get(flag) is True:
                issues.append(f"{flag} must be false: {row_id}")

    for row in active_rows:
        if row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM and row.get("stage") == "selected_feedback_stage1_feedback_generation":
            blob = json.dumps(row, ensure_ascii=False)
            if "--baseline-eval-nav" not in str(row.get("command", "")):
                issues.append(f"feedback generation missing --baseline-eval-nav: {_row_id(row)}")
            if "/stage1_baseline_official_eval/EVAL_NAV.csv" not in blob:
                issues.append(f"feedback generation does not use official eval EVAL_NAV: {_row_id(row)}")

    by_case = _selected_feedback_stage_sequence(command_rows)
    for case_id, stages in by_case.items():
        if case_id in {"M_normal_baseline_repeat", "L_feedback_disabled"}:
            expected = ["selected_feedback_stage2_solver"]
        else:
            expected = [
                "selected_feedback_stage1_baseline_solver",
                "selected_feedback_stage1_official_eval",
                "selected_feedback_stage1_feedback_generation",
                "selected_feedback_stage2_solver",
            ]
        if stages != expected:
            issues.append(f"selected-feedback dependency order incorrect: {case_id}: {stages}")

    medium_single = [
        row
        for row in active_rows
        if row.get("case_id") == "C_position_noise_medium" and row.get("algorithm") == SINGLE_BASELINE_ALGORITHM
    ]
    if not medium_single:
        issues.append("C_position_noise_medium single_antenna_gnss1_status_KF_GINS row missing")
    elif medium_single[0].get("underlying_runner") != "KF-GINS-Baseline":
        issues.append("C_position_noise_medium single_antenna_gnss1_status_KF_GINS row not mapped to KF-GINS-Baseline")

    for row in dryrun_rows:
        if row.get("dry_run") is not True:
            issues.append(f"WSL row is not dry-run: {_row_id(row)}")
        if row.get("executed") is True or row.get("executed_solver") is True:
            issues.append(f"WSL dry-run row marked executed: {_row_id(row)}")

    return {
        "stage": STAGE,
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "runtime_written": runtime_written,
        "command_rows": len(command_rows),
        "active_command_rows": len(active_rows),
        "command_json_sync_rows": len(sync_rows),
        "wsl_dryrun_rows": len(dryrun_rows),
        "feedback_eval_nav_safety_status": safety_report.get("status", ""),
        "official_eval_feedback_generation_rows": sum(
            row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM
            and row.get("stage") == "selected_feedback_stage1_feedback_generation"
            and "/stage1_baseline_official_eval/EVAL_NAV.csv" in json.dumps(row, ensure_ascii=False)
            for row in active_rows
        ),
        "stale_stage1_baseline_eval_nav_count": sum(
            _contains_stale_stage1_baseline_eval_nav(json.dumps(row, ensure_ascii=False)) for row in active_rows
        ),
        "command_json_stale_stage1_baseline_eval_nav_count": command_json_stale_eval_nav_count,
        "command_json_official_eval_feedback_generation_rows": command_json_official_eval_count,
        "command_json_payload_mismatch_count": command_json_payload_mismatch_count,
        "stale_output_root_count": sum(_contains_stale_n9b1d_root(json.dumps(row, ensure_ascii=False)) for row in active_rows),
        "forbidden_command_token_count": sum(
            token in json.dumps(row, ensure_ascii=False) for row in active_rows for token in FORBIDDEN_COMMAND_TOKENS
        ),
        "command_json_forbidden_token_count": command_json_forbidden_token_count,
        "solver_run": False,
        "official_evaluator_run": False,
        "figures_generated": False,
        "ready_for_N9B2_execution": False,
    }


def audit_feedback_eval_nav_safety(workspace_root: Path) -> dict[str, Any]:
    read_columns = sorted(_static_eval_nav_columns(workspace_root))
    status, reason = classify_eval_nav_safety(read_columns)
    files_scanned = [
        FEEDBACK_SCRIPT,
        FEEDBACK_MODULE,
        SLIDING_WINDOW_MODULE,
        "src/legsa_gins/fgo_feedback/fgo_feedback_observation.py",
        "src/legsa_gins/fgo_feedback/fgo_feedback_gate.py",
        "src/legsa_gins/fgo_feedback/fgo_feedback_covariance_policy.py",
    ]
    return {
        "stage": STAGE,
        "created_utc": now_utc(),
        "status": status,
        "reason": reason,
        "entrypoint": FEEDBACK_SCRIPT,
        "files_scanned": files_scanned,
        "eval_nav_columns_read": read_columns,
        "allowed_estimate_state_columns": sorted(ESTIMATE_EVAL_NAV_COLUMNS),
        "trace_or_error_columns_used_for_corrections": [
            column for column in read_columns if _is_trace_or_error_column(column)
        ],
        "safety_policy": "pass if only estimate/state columns are read; fail if trace/error columns are used for corrections",
        "solver_run": False,
        "official_evaluator_run": False,
        "figures_generated": False,
        "ready_for_N9B2_execution": False,
    }


def classify_eval_nav_safety(columns: list[str] | set[str]) -> tuple[str, str]:
    observed = {column for column in columns if column}
    forbidden = sorted(column for column in observed if _is_trace_or_error_column(column))
    unknown = sorted(observed - ESTIMATE_EVAL_NAV_COLUMNS - set(forbidden))
    if forbidden:
        return "fail", "trace/error columns are read from EVAL_NAV"
    if unknown:
        return "conditional_pass_with_note", "unknown EVAL_NAV columns are read and require review"
    return "pass", "only estimate/state columns are read from EVAL_NAV"


def _load_n9b1g1_rows(workspace_root: Path) -> tuple[list[dict[str, Any]], Path]:
    source_root = workspace_root / AUDIT_ROOT_NAME / SOURCE_STAGE
    candidates = [
        source_root / "matrix" / "N9B1G1_N9B1D_READY_COMMAND_MATRIX.json",
        source_root / "command_matrix_fix" / "N9B1G1_N9B1D_READY_COMMAND_MATRIX.json",
    ]
    for path in candidates:
        rows = _load_rows(path)
        if rows:
            return rows, path
    raise FileNotFoundError("N9B1G1 ready command matrix was not found")


def _sync_command_json_rows(
    runtime_root: Path,
    source_rows: list[dict[str, Any]],
    *,
    write_outputs: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    out: list[dict[str, Any]] = []
    sync_rows: list[dict[str, Any]] = []
    for index, row in enumerate(source_rows, start=1):
        updated = dict(row)
        if updated.get("run_allowed_in_N9B1D") is True:
            command_json = runtime_root / COMMAND_JSON_SUBDIR / f"{index:03d}_{_safe_name(_row_id(updated))}.json"
            updated["solver_command_json_before_n9b1g2"] = str(updated.get("solver_command_json", ""))
            updated["solver_command_json"] = str(command_json)
            payload = _command_json_payload(updated)
            if write_outputs:
                _write_json(command_json, payload)
            payload_blob = json.dumps(payload, ensure_ascii=False)
            sync_rows.append(
                {
                    "row_index": index,
                    "case_id": updated.get("case_id", ""),
                    "algorithm": updated.get("algorithm", ""),
                    "stage": updated.get("stage", ""),
                    "dependency_group_id": updated.get("dependency_group_id", ""),
                    "dependency_order": updated.get("dependency_order", ""),
                    "command_json_path": str(command_json),
                    "matrix_solver_command_json": updated["solver_command_json"],
                    "json_matches_matrix": True,
                    "uses_stage1_baseline_official_eval": "/stage1_baseline_official_eval/EVAL_NAV.csv" in payload_blob,
                    "uses_stale_stage1_baseline_eval_nav": _contains_stale_stage1_baseline_eval_nav(payload_blob),
                    "forbidden_command_token_present": any(token in payload_blob for token in FORBIDDEN_COMMAND_TOKENS),
                    "dry_run_only": True,
                    "executed": False,
                    "solver_run": False,
                    "official_evaluator_run": False,
                }
            )
        out.append(updated)
    return out, sync_rows


def _command_json_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": row.get("stage", ""),
        "case_id": row.get("case_id", ""),
        "algorithm": row.get("algorithm", ""),
        "command_algorithm": row.get("command_algorithm", ""),
        "entrypoint": row.get("entrypoint", ""),
        "underlying_runner": row.get("underlying_runner", ""),
        "working_directory": row.get("working_directory", ""),
        "command": row.get("command", ""),
        "runtime_config_path": row.get("runtime_config_path", ""),
        "runtime_config_path_wsl": row.get("runtime_config_path_wsl", ""),
        "solver_command_json": row.get("solver_command_json", ""),
        "output_dir": row.get("output_dir", ""),
        "dependency_group_id": row.get("dependency_group_id", ""),
        "dependency_order": row.get("dependency_order", ""),
        "dependency_mode": row.get("dependency_mode", ""),
        "baseline_eval_nav_dependency": row.get("baseline_eval_nav_dependency", ""),
        "planned_eval_nav": row.get("planned_eval_nav", ""),
        "dry_run": True,
        "dry_run_only": True,
        "executed": False,
        "executed_solver": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "NAV_generated": False,
        "STD_generated": False,
        "EVAL_NAV_generated": False,
        "RUN_MANIFEST_generated": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "output_substitution": False,
        "direct_nav_override": False,
        "ready_for_N9B2_execution": False,
    }


def _build_wsl_dryrun_rows(workspace_root: Path, runtime_root: Path, command_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in command_rows:
        if row.get("run_allowed_in_N9B1D") is not True:
            continue
        log_path = runtime_root / "logs" / "wsl_dryrun" / f"{_safe_name(_row_id(row))}.json"
        rows.append(
            {
                "stage": row.get("stage", ""),
                "case_id": row.get("case_id", ""),
                "algorithm": row.get("algorithm", ""),
                "command": row.get("command", ""),
                "working_directory": row.get("working_directory", ""),
                "runtime_config_path": row.get("runtime_config_path", ""),
                "solver_command_json": row.get("solver_command_json", ""),
                "output_dir": row.get("output_dir", ""),
                "dependency_group_id": row.get("dependency_group_id", ""),
                "dependency_order": row.get("dependency_order", ""),
                "log_path": str(log_path),
                "bridge_script": str(workspace_root / "scripts" / "run_wsl_legsa.ps1"),
                "dry_run": True,
                "executed": False,
                "executed_solver": False,
                "dryrun_returncode": None,
                "stdout": "",
                "stderr": "",
                "solver_run": False,
                "official_evaluator_run": False,
                "ready_for_N9B2_execution": False,
            }
        )
    return rows


def _run_wsl_dryrun(workspace_root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    script = workspace_root / "scripts" / "run_wsl_legsa.ps1"
    refreshed: list[dict[str, Any]] = []
    for row in rows:
        args = [
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
            row.get("log_path", ""),
        ]
        try:
            completed = subprocess.run(
                args,
                cwd=workspace_root,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            updated = dict(row)
            updated.update(
                {
                    "dryrun_returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                    "dryrun_success": completed.returncode == 0,
                    "executed": False,
                    "executed_solver": False,
                }
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            updated = dict(row)
            updated.update(
                {
                    "dryrun_returncode": None,
                    "stdout": "",
                    "stderr": str(exc),
                    "dryrun_success": False,
                    "executed": False,
                    "executed_solver": False,
                }
            )
        refreshed.append(updated)
    return refreshed


def _static_eval_nav_columns(workspace_root: Path) -> set[str]:
    columns: set[str] = set()
    path = workspace_root / SLIDING_WINDOW_MODULE
    if path.exists():
        text = path.read_text(encoding="utf-8", errors="ignore")
        columns.update(_function_dict_subscript_columns(text, "read_eval_nav_csv"))
    return columns


def _function_dict_subscript_columns(text: str, function_name: str) -> set[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return _dict_subscript_columns(ast.unparse(node))
    return set()


def _dict_subscript_columns(text: str) -> set[str]:
    columns: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return columns
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            key = _literal_slice_value(node.slice)
            if isinstance(key, str):
                columns.add(key)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get" and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                columns.add(arg.value)
    return columns


def _literal_slice_value(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    return None


def _is_trace_or_error_column(column: str) -> bool:
    normalized = column.lower()
    return any(pattern in normalized for pattern in TRACE_OR_ERROR_COLUMN_PATTERNS)


def _selected_feedback_stage_sequence(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM and row.get("run_allowed_in_N9B1D") is True:
            grouped.setdefault(str(row.get("case_id", "")), []).append(row)
    return {
        case_id: [row.get("stage", "") for row in sorted(case_rows, key=lambda item: int(item.get("dependency_order", 0)))]
        for case_id, case_rows in grouped.items()
    }


def _contains_stale_stage1_baseline_eval_nav(text: str) -> bool:
    return bool(re.search(r"[/\\]stage1_baseline[/\\]EVAL_NAV\.csv", text))


def _contains_stale_n9b1d_root(text: str) -> bool:
    return bool(re.search(r"N9B1D_PILOT_SOLVER_EXECUTION(?!_AND_EVALUATION)([/\\]|$)", text))


def _command_json_sync_report(command_rows: list[dict[str, Any]], sync_rows: list[dict[str, Any]], source_path: Path) -> dict[str, Any]:
    active_rows = [row for row in command_rows if row.get("run_allowed_in_N9B1D") is True]
    return {
        "stage": STAGE,
        "created_utc": now_utc(),
        "source_stage": SOURCE_STAGE,
        "source_matrix": str(source_path),
        "active_command_rows": len(active_rows),
        "synchronized_command_json_rows": len(sync_rows),
        "all_active_rows_synchronized": len(active_rows) == len(sync_rows),
        "stale_stage1_baseline_eval_nav_count": sum(row["uses_stale_stage1_baseline_eval_nav"] for row in sync_rows),
        "stale_output_root_count": sum(_contains_stale_n9b1d_root(json.dumps(row, ensure_ascii=False)) for row in active_rows),
        "forbidden_command_token_count": sum(row["forbidden_command_token_present"] for row in sync_rows),
        "solver_run": False,
        "official_evaluator_run": False,
        "figures_generated": False,
        "ready_for_N9B2_execution": False,
    }


def _ready_command_matrix_report(command_rows: list[dict[str, Any]]) -> dict[str, Any]:
    active = [row for row in command_rows if row.get("run_allowed_in_N9B1D") is True]
    return {
        "stage": STAGE,
        "created_utc": now_utc(),
        "ready_matrix_rows": len(command_rows),
        "active_rows": len(active),
        "output_root": N9B1D_STAGE,
        "stale_output_root_count": sum(_contains_stale_n9b1d_root(json.dumps(row, ensure_ascii=False)) for row in active),
        "selected_feedback_stage1_feedback_generation_rows": sum(
            row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM and row.get("stage") == "selected_feedback_stage1_feedback_generation"
            for row in active
        ),
        "feedback_generation_uses_stage1_baseline_official_eval": all(
            "/stage1_baseline_official_eval/EVAL_NAV.csv" in json.dumps(row, ensure_ascii=False)
            for row in active
            if row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM and row.get("stage") == "selected_feedback_stage1_feedback_generation"
        ),
        "single_position_noise_medium_single_baseline_preserved": any(
            row.get("case_id") == "C_position_noise_medium"
            and row.get("algorithm") == SINGLE_BASELINE_ALGORITHM
            and row.get("underlying_runner") == "KF-GINS-Baseline"
            for row in active
        ),
        "solver_run": False,
        "official_evaluator_run": False,
        "ready_for_N9B2_execution": False,
    }


def _wsl_dryrun_report(rows: list[dict[str, Any]], invoked: bool) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "created_utc": now_utc(),
        "wsl_dryrun_invoked": invoked,
        "bridge_script": "scripts/run_wsl_legsa.ps1",
        "dry_run_only": True,
        "dryrun_rows": len(rows),
        "dryrun_success_count": sum(row.get("dryrun_returncode") == 0 for row in rows),
        "dryrun_failure_count": sum(row.get("dryrun_returncode") not in {0, None} for row in rows),
        "executed": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "ready_for_N9B2_execution": False,
    }


def _decision_report(validation: dict[str, Any], sync_report: dict[str, Any], safety_report: dict[str, Any]) -> dict[str, Any]:
    passed = validation.get("status") == "pass" and safety_report.get("status") == "pass" and sync_report.get("all_active_rows_synchronized") is True
    return {
        "stage": STAGE,
        "created_utc": now_utc(),
        "status": "N9B1G2_command_json_sync_complete" if passed else "N9B1G2_command_json_sync_safety_gate_failed",
        "ready_for_N9B1D_solver_execution": passed,
        "ready_for_N9B2_execution": False,
        "recommended_next_stage": "human_review_N9B1G2_then_N9B1D_solver_execution" if passed else "repair_N9B1G2_validation_issues",
        "validation_status": validation.get("status", ""),
        "feedback_eval_nav_safety_status": safety_report.get("status", ""),
        "issues": validation.get("issues", []),
        "solver_run": False,
        "official_evaluator_run": False,
        "figures_generated": False,
    }


def _write_outputs(runtime_root: Path, result: dict[str, Any]) -> None:
    _create_runtime_tree(runtime_root)
    reports = {
        "N9B1G2_COMMAND_JSON_SYNC_REPORT.json": result["command_json_sync_report"],
        "N9B1G2_READY_COMMAND_MATRIX_REPORT.json": result["ready_command_matrix_report"],
        "N9B1G2_FEEDBACK_EVAL_NAV_SAFETY_AUDIT_REPORT.json": result["feedback_eval_nav_safety_audit_report"],
        "N9B1G2_WSL_DRYRUN_REPORT.json": result["wsl_dryrun_report"],
        "N9B1G2_VALIDATION_REPORT.json": result["validation_report"],
        "N9B1G2_DECISION_REPORT.json": result["decision_report"],
    }
    for name, payload in reports.items():
        _write_json(runtime_root / "reports" / name, payload)
    matrices = {
        "N9B1G2_COMMAND_JSON_SYNC_MATRIX": result["command_json_sync_matrix"],
        "N9B1G2_N9B1D_READY_COMMAND_MATRIX": result["n9b1d_ready_command_matrix"],
        "N9B1G2_WSL_DRYRUN_COMMANDS": result["wsl_dryrun_commands"],
    }
    for stem, rows in matrices.items():
        _write_table_pair(runtime_root / "matrix" / stem, rows)
    _write_table_pair(runtime_root / "command_json_sync" / "N9B1G2_COMMAND_JSON_SYNC_MATRIX", result["command_json_sync_matrix"])
    _write_table_pair(runtime_root / "matrix_consistency" / "N9B1G2_N9B1D_READY_COMMAND_MATRIX", result["n9b1d_ready_command_matrix"])
    _write_table_pair(runtime_root / "wsl_dryrun" / "N9B1G2_WSL_DRYRUN_COMMANDS", result["wsl_dryrun_commands"])
    _write_json(
        runtime_root / "feedback_eval_nav_safety" / "N9B1G2_FEEDBACK_EVAL_NAV_SAFETY_AUDIT_REPORT.json",
        result["feedback_eval_nav_safety_audit_report"],
    )
    _write_json(runtime_root / "validation" / "N9B1G2_VALIDATION_REPORT.json", result["validation_report"])
    _write_json(runtime_root / "logs" / "N9B1G2_OPERATION_LOG.json", {"stage": STAGE, "created_utc": now_utc(), "solver_run": False})
    (runtime_root / "summary" / "n9b1g2_feedback_eval_nav_safety_audit.md").write_text(_safety_markdown(result), encoding="utf-8")
    (runtime_root / "feedback_eval_nav_safety" / "n9b1g2_feedback_eval_nav_safety_audit.md").write_text(_safety_markdown(result), encoding="utf-8")
    (runtime_root / "summary" / "n9b1g2_next_stage_recommendation.md").write_text(_summary_markdown(result), encoding="utf-8")


def _safety_markdown(result: dict[str, Any]) -> str:
    report = result["feedback_eval_nav_safety_audit_report"]
    columns = ", ".join(report.get("eval_nav_columns_read", []))
    return (
        "# N9B1G2 feedback EVAL_NAV safety audit\n\n"
        f"- status={report['status']}\n"
        f"- reason={report['reason']}\n"
        f"- eval_nav_columns_read={columns}\n"
        "- solver_run=false\n"
        "- official_evaluator_run=false\n"
    )


def _summary_markdown(result: dict[str, Any]) -> str:
    decision = result["decision_report"]
    validation = result["validation_report"]
    return (
        "# N9B1G2 next stage recommendation\n\n"
        f"- status={decision['status']}\n"
        f"- ready_for_N9B1D_solver_execution={str(decision['ready_for_N9B1D_solver_execution']).lower()}\n"
        "- ready_for_N9B2_execution=false\n"
        f"- validation_status={validation['status']}\n"
        f"- command_json_sync_rows={validation['command_json_sync_rows']}\n"
        f"- wsl_dryrun_rows={validation['wsl_dryrun_rows']}\n"
        f"- feedback_eval_nav_safety_status={validation['feedback_eval_nav_safety_status']}\n"
    )


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = data.get("rows", data.get("matrix", [])) if isinstance(data, dict) else data
    return [dict(row) for row in rows] if isinstance(rows, list) else []


def _create_runtime_tree(runtime_root: Path) -> None:
    for subdir in REQUIRED_SUBDIRS:
        (runtime_root / subdir).mkdir(parents=True, exist_ok=True)
    (runtime_root / COMMAND_JSON_SUBDIR).mkdir(parents=True, exist_ok=True)
    (runtime_root / "logs" / "wsl_dryrun").mkdir(parents=True, exist_ok=True)


def _reset_runtime_tree(runtime_root: Path) -> None:
    for subdir in REQUIRED_SUBDIRS:
        path = runtime_root / subdir
        if path.exists():
            shutil.rmtree(path)
    _create_runtime_tree(runtime_root)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _row_id(row: dict[str, Any]) -> str:
    return f"{row.get('case_id', '')}__{row.get('algorithm', '')}__{row.get('stage', '')}"
