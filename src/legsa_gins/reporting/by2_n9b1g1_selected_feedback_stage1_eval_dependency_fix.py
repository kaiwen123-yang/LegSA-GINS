"""N9B1G1 selected-feedback stage1 official-eval dependency repair.

This stage is command planning and audit reporting only. It reuses the N9B1G
case-level command matrix, inserts the missing same-case selected-feedback
stage1 official evaluator dependency, and normalizes future N9B1D output roots.
It never executes solvers or evaluators.
"""

from __future__ import annotations

import csv
import json
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legsa_gins.reporting.by2_n9b1g_case_level_command_rebind_with_formal_runner import (
    L_DISABLED_CASE,
    M_CLEAN_REPEAT_CASE,
    SELECTED_FEEDBACK_ALGORITHM,
    SINGLE_BASELINE_ALGORITHM,
    _build_wsl_dryrun_rows,
    _rel,
    _safe_name,
    _write_table_pair,
    repo_to_wsl,
    run_n9b1g_case_level_command_rebind_with_formal_runner,
)
from legsa_gins.reporting.by2_n9b1f_real_legsa_algorithm_runner import _load_r4e3_trace_path
from legsa_gins.reporting.by2_real_pilot_input_generator import AUDIT_ROOT_NAME


STAGE = "N9B1G1_SELECTED_FEEDBACK_STAGE1_EVAL_DEPENDENCY_FIX_AND_SINGLE_POSITION_NOISE_GUARD"
SOURCE_STAGE = "N9B1G_CASE_LEVEL_COMMAND_REBIND_WITH_FORMAL_RUNNER"
N9B1D_STAGE = "N9B1D_PILOT_SOLVER_EXECUTION_AND_EVALUATION"
LEGACY_N9B1D_STAGE = "N9B1D_PILOT_SOLVER_EXECUTION"
N9B0A1_STAGE = "N9B0A1_MATRIX_SCHEMA_CLEANUP"
N9B1_STAGE = "N9B1_REAL_PILOT_INPUT_GENERATOR"
N9B1A_STAGE = "N9B1A_REAL_PILOT_INPUT_GENERATOR_AND_WSL_BRIDGE_PRECHECK"
N9B1A1_STAGE = "N9B1A1_DOWNSAMPLE_CADENCE_POLICY_REPAIR"

SAME_CASE_SELECTED_FEEDBACK_CASES = {
    "A_outage_5s",
    "C_position_noise_medium",
    "D_position_spike_medium",
    "B_gnss_downsample_every2",
    "H_dual_yaw_noise_medium",
    "J_go2_horizontal_velocity_missing",
}
POSITION_NOISE_CASES = {
    "C_position_noise_mild",
    "C_position_noise_medium",
    "C_position_noise_strong",
}

REQUIRED_SUBDIRS = [
    "dependency_graph_fix",
    "command_matrix_fix",
    "output_root_normalization",
    "single_position_noise_guard",
    "wsl_dryrun",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
]
REPORT_NAMES = [
    "N9B1G1_SELECTED_FEEDBACK_STAGE1_EVAL_DEPENDENCY_REPORT.json",
    "N9B1G1_FEEDBACK_GENERATION_COMMAND_REPAIR_REPORT.json",
    "N9B1G1_SINGLE_POSITION_NOISE_GUARD_REPORT.json",
    "N9B1G1_OUTPUT_ROOT_NORMALIZATION_REPORT.json",
    "N9B1G1_COMMAND_MATRIX_REPAIR_REPORT.json",
    "N9B1G1_WSL_DRYRUN_REPORT.json",
    "N9B1G1_VALIDATION_REPORT.json",
    "N9B1G1_DECISION_REPORT.json",
]
MATRIX_STEMS = [
    "N9B1G1_SELECTED_FEEDBACK_DEPENDENCY_GRAPH",
    "N9B1G1_FEEDBACK_GENERATION_COMMANDS",
    "N9B1G1_SINGLE_POSITION_NOISE_GUARD_MATRIX",
    "N9B1G1_OUTPUT_ROOT_DIFF",
    "N9B1G1_N9B1D_READY_COMMAND_MATRIX",
    "N9B1G1_N9B1D_DEPENDENCY_ORDER_MATRIX",
    "N9B1G1_WSL_DRYRUN_COMMANDS",
]
FORBIDDEN_RUNTIME_OUTPUT_NAMES = {
    "LegSA_NAV.nav",
    "LegSA_PORT_NAV.nav",
    "LegSA_STD.csv",
    "LegSA_PORT_STD.csv",
    "KF_GINS_Navresult.nav",
    "KF_GINS_STD.txt",
    "EVAL_NAV.csv",
    "RUN_MANIFEST.json",
}
COMMAND_CONFIG_SUBDIR = Path("command_matrix_fix") / "cfg"
COMMAND_PLAN_SUBDIR = Path("command_matrix_fix") / "cmd"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_n9b1g1_runtime_root(workspace_root: Path) -> Path:
    return workspace_root / AUDIT_ROOT_NAME / STAGE


def run_n9b1g1_selected_feedback_stage1_eval_dependency_fix(
    workspace_root: Path,
    runtime_root: Path | None = None,
    *,
    write_outputs: bool = True,
    run_wsl_dryrun: bool = True,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root or default_n9b1g1_runtime_root(workspace_root)
    if write_outputs:
        _reset_runtime_tree(runtime_root)

    base = run_n9b1g_case_level_command_rebind_with_formal_runner(
        workspace_root,
        runtime_root=workspace_root / AUDIT_ROOT_NAME / SOURCE_STAGE,
        write_outputs=False,
        run_wsl_dryrun=False,
    )
    normalized_source = _materialize_inherited_command_plan_files(
        runtime_root,
        base["n9b1d_case_level_command_matrix"],
        write_outputs=write_outputs,
    )
    command_rows = _insert_stage1_official_eval_rows(workspace_root, runtime_root, normalized_source)
    command_rows = _rewrite_generation_eval_dependencies(command_rows)
    dependency_rows = _dependency_order_rows(command_rows)
    feedback_rows = [row for row in command_rows if row.get("stage") == "selected_feedback_stage1_feedback_generation"]
    output_root_diff = _output_root_diff(normalized_source, command_rows)
    guard_rows = _single_position_noise_guard_rows(workspace_root, command_rows)
    dryrun_rows = _build_wsl_dryrun_rows(workspace_root, runtime_root, command_rows)
    if write_outputs and run_wsl_dryrun:
        dryrun_rows = _run_wsl_dryrun(workspace_root, dryrun_rows)

    reports = {
        "stage1_eval_dependency_report": _stage1_eval_dependency_report(command_rows),
        "feedback_generation_command_repair_report": _feedback_generation_command_repair_report(feedback_rows),
        "single_position_noise_guard_report": _single_position_noise_guard_report(guard_rows),
        "output_root_normalization_report": _output_root_normalization_report(command_rows, output_root_diff),
        "command_matrix_repair_report": _command_matrix_repair_report(command_rows),
        "wsl_dryrun_report": _wsl_dryrun_report(dryrun_rows, run_wsl_dryrun),
    }
    validation = validate_n9b1g1_result(
        workspace_root,
        runtime_root,
        command_rows,
        dryrun_rows,
        guard_rows,
        runtime_written=False,
    )
    decision = _decision_report(validation, reports)
    result = {
        **reports,
        "validation_report": validation,
        "decision_report": decision,
        "selected_feedback_dependency_graph": dependency_rows,
        "feedback_generation_commands": feedback_rows,
        "single_position_noise_guard_matrix": guard_rows,
        "output_root_diff": output_root_diff,
        "n9b1d_ready_command_matrix": command_rows,
        "n9b1d_dependency_order_matrix": dependency_rows,
        "wsl_dryrun_commands": dryrun_rows,
    }
    if write_outputs:
        _write_outputs(runtime_root, result)
        result["validation_report"] = validate_n9b1g1_result(
            workspace_root,
            runtime_root,
            command_rows,
            dryrun_rows,
            guard_rows,
            runtime_written=True,
        )
        result["decision_report"] = _decision_report(result["validation_report"], reports)
        _write_outputs(runtime_root, result)
    return result


def validate_n9b1g1_result(
    workspace_root: Path,
    runtime_root: Path,
    command_rows: list[dict[str, Any]] | None = None,
    dryrun_rows: list[dict[str, Any]] | None = None,
    guard_rows: list[dict[str, Any]] | None = None,
    *,
    runtime_written: bool = True,
) -> dict[str, Any]:
    command_rows = command_rows or []
    dryrun_rows = dryrun_rows or []
    guard_rows = guard_rows or []
    issues: list[str] = []
    active_rows = [row for row in command_rows if row.get("run_allowed_in_N9B1D") is True]

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
                issues.append(f"forbidden solver/evaluator output generated: {_rel(runtime_root, path)}")
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg", ".pdf"}:
                issues.append(f"forbidden figure/artifact generated: {_rel(runtime_root, path)}")
            if path.suffix.lower() == ".json":
                raw = path.read_bytes()
                if raw.startswith(b"\xef\xbb\xbf"):
                    issues.append(f"json BOM present: {_rel(runtime_root, path)}")
                try:
                    json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    issues.append(f"json parse failed: {_rel(runtime_root, path)}: {exc}")

    by_case = _selected_feedback_rows_by_case(command_rows)
    for case_id in SAME_CASE_SELECTED_FEEDBACK_CASES:
        stages = [row.get("stage") for row in sorted(by_case.get(case_id, []), key=lambda row: int(row.get("dependency_order", 0)))]
        if stages != [
            "selected_feedback_stage1_baseline_solver",
            "selected_feedback_stage1_official_eval",
            "selected_feedback_stage1_feedback_generation",
            "selected_feedback_stage2_solver",
        ]:
            issues.append(f"same-case dependency order incorrect: {case_id}: {stages}")
    for case_id, expected in {
        M_CLEAN_REPEAT_CASE: ["selected_feedback_stage2_solver"],
        L_DISABLED_CASE: ["selected_feedback_stage2_solver"],
    }.items():
        stages = [row.get("stage") for row in sorted(by_case.get(case_id, []), key=lambda row: int(row.get("dependency_order", 0)))]
        if stages != expected:
            issues.append(f"{case_id} selected-feedback stage policy incorrect: {stages}")

    for row in active_rows:
        haystack = json.dumps(row, ensure_ascii=False)
        if "_n9b1g_source_not_written" in haystack:
            issues.append(f"non-materialized source path remains: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        if _has_stale_n9b1d_root(haystack):
            issues.append(f"stale output root remains: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        if N9B1D_STAGE not in haystack and row.get("stage") != "single_baseline_solver":
            issues.append(f"new output root absent from active command row: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        for flag in ["solver_run", "official_evaluator_run", "NAV_generated", "STD_generated", "EVAL_NAV_generated", "RUN_MANIFEST_generated"]:
            if row.get(flag) is True:
                issues.append(f"{flag} must be false: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        if row.get("dry_run_only") is not True:
            issues.append(f"row is not dry-run only: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        if runtime_written:
            runtime_config = str(row.get("runtime_config_path", ""))
            if runtime_config and not Path(runtime_config).is_file():
                issues.append(f"missing runtime config: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}: {runtime_config}")
            solver_command_json = str(row.get("solver_command_json", ""))
            if solver_command_json and not Path(solver_command_json).is_file():
                issues.append(f"missing solver command json: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}: {solver_command_json}")

    for case_id in SAME_CASE_SELECTED_FEEDBACK_CASES:
        generation = [row for row in by_case.get(case_id, []) if row.get("stage") == "selected_feedback_stage1_feedback_generation"]
        if not generation:
            continue
        eval_nav = str(generation[0].get("baseline_eval_nav_dependency", ""))
        if "/stage1_baseline_official_eval/EVAL_NAV.csv" not in eval_nav:
            issues.append(f"feedback generation does not use official-eval EVAL_NAV: {case_id}")

    c_guard = [row for row in guard_rows if row.get("case_id") == "C_position_noise_medium" and row.get("algorithm") == SINGLE_BASELINE_ALGORITHM]
    if not c_guard or c_guard[0].get("guard_status") != "pass":
        issues.append("single position-noise guard did not pass C_position_noise_medium single baseline")
    if not all(row.get("n9b0a1_applicable") is True for row in guard_rows if row.get("case_id") in POSITION_NOISE_CASES):
        issues.append("N9B0A1 single position-noise applicability guard failed")
    single_medium = [row for row in active_rows if row.get("case_id") == "C_position_noise_medium" and row.get("algorithm") == SINGLE_BASELINE_ALGORITHM]
    if not single_medium:
        issues.append("C_position_noise_medium single baseline was removed from command matrix")
    elif single_medium[0].get("underlying_runner") != "KF-GINS-Baseline":
        issues.append("C_position_noise_medium single baseline is not mapped via KF-GINS-Baseline")

    for row in dryrun_rows:
        if row.get("dry_run") is not True:
            issues.append(f"WSL row is not dry-run: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        if row.get("executed") is True or row.get("executed_solver") is True:
            issues.append(f"WSL dry-run executed command: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")

    stale_root_count = sum(_has_stale_n9b1d_root(json.dumps(row, ensure_ascii=False)) for row in active_rows)
    new_root_count = sum(N9B1D_STAGE in json.dumps(row, ensure_ascii=False) for row in active_rows)
    if stale_root_count:
        issues.append(f"active command stale root count nonzero: {stale_root_count}")
    if new_root_count <= 0:
        issues.append("active command new root count is zero")

    return {
        "stage": STAGE,
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "runtime_written": runtime_written,
        "case_level_command_rows": len(command_rows),
        "run_allowed_rows": len(active_rows),
        "same_case_selected_feedback_cases": sorted(SAME_CASE_SELECTED_FEEDBACK_CASES),
        "selected_feedback_stage1_official_eval_rows": sum(row.get("stage") == "selected_feedback_stage1_official_eval" for row in command_rows),
        "stale_root_count_active_command_fields": stale_root_count,
        "new_root_count_active_command_fields": new_root_count,
        "single_position_noise_guard_status": "pass" if not [row for row in guard_rows if row.get("guard_status") != "pass"] else "fail",
        "solver_run": False,
        "official_evaluator_run": False,
        "figures_generated": False,
        "ready_for_N9B2_execution": False,
    }


def _insert_stage1_official_eval_rows(workspace_root: Path, runtime_root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    trace_path = _load_r4e3_trace_path(workspace_root) or "<trace path>"
    for row in rows:
        normalized = dict(row)
        if normalized.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM and normalized.get("stage") == "selected_feedback_stage1_baseline":
            normalized["stage"] = "selected_feedback_stage1_baseline_solver"
        out.append(normalized)
        if (
            normalized.get("case_id") in SAME_CASE_SELECTED_FEEDBACK_CASES
            and normalized.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM
            and normalized.get("stage") == "selected_feedback_stage1_baseline_solver"
        ):
            out.append(_official_eval_row(workspace_root, runtime_root, normalized, trace_path))
    return _renumber_selected_feedback(out)


def _official_eval_row(workspace_root: Path, runtime_root: Path, stage1_row: dict[str, Any], trace_path: str) -> dict[str, Any]:
    case_id = stage1_row["case_id"]
    eval_root = _stage1_official_eval_root(workspace_root, case_id)
    baseline_root = str(stage1_row.get("output_dir", ""))
    nav = f"{baseline_root}/LegSA_PORT_NAV.nav"
    std = f"{baseline_root}/LegSA_PORT_STD.csv"
    command_parts = [
        "python3",
        "/home/kaiwen/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py",
        "--trace",
        trace_path,
        "--nav",
        nav,
        "--std",
        std,
        "--outdir",
        eval_root,
        "--base_time",
        "1772784000.0",
        "--yaw_truth_mode",
        "enu",
    ]
    solver_command_json = runtime_root / COMMAND_PLAN_SUBDIR / f"eval_{_safe_name(case_id)}.json"
    payload = {
        "stage": "selected_feedback_stage1_official_eval",
        "case_id": case_id,
        "algorithm": SELECTED_FEEDBACK_ALGORITHM,
        "command": shlex.join(command_parts),
        "baseline_stage1_nav": nav,
        "baseline_stage1_std": std,
        "official_eval_outdir": eval_root,
        "planned_eval_nav": f"{eval_root}/EVAL_NAV.csv",
        "dry_run": True,
        "dry_run_only": True,
        "executed_solver": False,
        "solver_run": False,
        "official_evaluator_run": False,
    }
    return {
        **stage1_row,
        "stage": "selected_feedback_stage1_official_eval",
        "command_algorithm": "official_evaluator",
        "entrypoint": "python3 /home/kaiwen/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py",
        "underlying_runner": "planned_official_evaluator_not_executed",
        "command": payload["command"],
        "runtime_config_path": "",
        "runtime_config_path_wsl": "",
        "solver_command_json": str(solver_command_json),
        "output_dir": eval_root,
        "dependency_order": 2,
        "dependency_mode": "same_case_selected_feedback_stage1_official_eval",
        "baseline_stage1_nav": nav,
        "baseline_stage1_std": std,
        "planned_eval_nav": payload["planned_eval_nav"],
        "source_case_algorithm_row": False,
        "dry_run_only": True,
        "solver_run": False,
        "official_evaluator_run": False,
        "NAV_generated": False,
        "STD_generated": False,
        "EVAL_NAV_generated": False,
        "RUN_MANIFEST_generated": False,
        "_solver_payload": payload,
    }


def _rewrite_generation_eval_dependencies(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        updated = dict(row)
        if updated.get("case_id") in SAME_CASE_SELECTED_FEEDBACK_CASES and updated.get("stage") == "selected_feedback_stage1_feedback_generation":
            eval_nav = f"{_stage1_official_eval_root_from_row(updated)}/EVAL_NAV.csv"
            old = str(updated.get("baseline_eval_nav_dependency", ""))
            updated["baseline_eval_nav_dependency_before_n9b1g1"] = old
            updated["baseline_eval_nav_dependency"] = eval_nav
            updated["command"] = _replace_option_value(str(updated.get("command", "")), "--baseline-eval-nav", eval_nav)
        out.append(updated)
    return out


def _renumber_selected_feedback(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {
        "selected_feedback_stage1_baseline_solver": 1,
        "selected_feedback_stage1_official_eval": 2,
        "selected_feedback_stage1_feedback_generation": 3,
        "selected_feedback_stage2_solver": 4,
    }
    out: list[dict[str, Any]] = []
    for row in rows:
        updated = dict(row)
        if updated.get("case_id") in SAME_CASE_SELECTED_FEEDBACK_CASES and updated.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM:
            updated["dependency_order"] = order.get(str(updated.get("stage")), updated.get("dependency_order", 0))
        out.append(updated)
    return out


def _normalize_roots(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_roots(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_roots(item) for item in value]
    if isinstance(value, str):
        return value.replace(LEGACY_N9B1D_STAGE, N9B1D_STAGE).replace(SOURCE_STAGE, STAGE)
    return value


def _materialize_inherited_command_plan_files(
    runtime_root: Path,
    rows: list[dict[str, Any]],
    *,
    write_outputs: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        updated = _normalize_roots(dict(row))
        config_path = runtime_root / COMMAND_CONFIG_SUBDIR / f"{index:03d}.yaml"
        command_json = runtime_root / COMMAND_PLAN_SUBDIR / f"{index:03d}.json"
        source_config = Path(str(row.get("runtime_config_path", ""))) if row.get("runtime_config_path") else None
        if source_config is not None and source_config.is_file():
            updated["runtime_config_path"] = str(config_path)
            updated["runtime_config_path_wsl"] = repo_to_wsl(config_path)
            updated["command"] = _replace_option_value(str(updated.get("command", "")), "--runtime-config", repo_to_wsl(config_path))
            if write_outputs:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                config_path.write_text(_normalize_stage_text(source_config.read_text(encoding="utf-8", errors="ignore")), encoding="utf-8")
        updated["solver_command_json"] = str(command_json)
        if write_outputs:
            _write_json(
                command_json,
                {
                    "stage": updated.get("stage", ""),
                    "case_id": updated.get("case_id", ""),
                    "algorithm": updated.get("algorithm", ""),
                    "command": updated.get("command", ""),
                    "entrypoint": updated.get("entrypoint", ""),
                    "working_directory": updated.get("working_directory", ""),
                    "runtime_config_path": updated.get("runtime_config_path", ""),
                    "runtime_config_path_wsl": updated.get("runtime_config_path_wsl", ""),
                    "output_dir": updated.get("output_dir", ""),
                    "dependency_group_id": updated.get("dependency_group_id", ""),
                    "dependency_order": updated.get("dependency_order", ""),
                    "dry_run": True,
                    "dry_run_only": True,
                    "executed_solver": False,
                    "solver_run": False,
                    "official_evaluator_run": False,
                    "trace_solver_input": False,
                    "final_v23_solver_input": False,
                },
            )
        out.append(updated)
    return out


def _normalize_stage_text(text: str) -> str:
    return text.replace(LEGACY_N9B1D_STAGE, N9B1D_STAGE).replace(SOURCE_STAGE, STAGE)


def _stage1_official_eval_root(workspace_root: Path, case_id: str) -> str:
    return f"{repo_to_wsl(workspace_root)}/{AUDIT_ROOT_NAME}/{N9B1D_STAGE}/selected_feedback_dependencies/{case_id}/stage1_baseline_official_eval"


def _stage1_official_eval_root_from_row(row: dict[str, Any]) -> str:
    output_dir = str(row.get("output_dir", ""))
    marker = f"/{AUDIT_ROOT_NAME}/{STAGE}/"
    if marker in output_dir:
        prefix = output_dir.split(f"/{AUDIT_ROOT_NAME}/", 1)[0]
        return f"{prefix}/{AUDIT_ROOT_NAME}/{N9B1D_STAGE}/selected_feedback_dependencies/{row['case_id']}/stage1_baseline_official_eval"
    if f"/{AUDIT_ROOT_NAME}/" in output_dir:
        prefix = output_dir.split(f"/{AUDIT_ROOT_NAME}/", 1)[0]
        return f"{prefix}/{AUDIT_ROOT_NAME}/{N9B1D_STAGE}/selected_feedback_dependencies/{row['case_id']}/stage1_baseline_official_eval"
    return f"{N9B1D_STAGE}/selected_feedback_dependencies/{row['case_id']}/stage1_baseline_official_eval"


def _replace_option_value(command: str, option: str, value: str) -> str:
    try:
        parts = shlex.split(command)
    except ValueError:
        return command
    if option in parts:
        idx = parts.index(option)
        if idx + 1 < len(parts):
            parts[idx + 1] = value
            return shlex.join(parts)
    return command


def _selected_feedback_rows_by_case(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM and row.get("run_allowed_in_N9B1D") is True:
            grouped.setdefault(str(row.get("case_id", "")), []).append(row)
    return grouped


def _dependency_order_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "case_id": row.get("case_id", ""),
            "algorithm": row.get("algorithm", ""),
            "stage": row.get("stage", ""),
            "dependency_group_id": row.get("dependency_group_id", ""),
            "dependency_order": row.get("dependency_order", ""),
            "dependency_mode": row.get("dependency_mode", ""),
            "command_plan_only": True,
            "solver_run": False,
            "official_evaluator_run": False,
        }
        for row in rows
        if row.get("run_allowed_in_N9B1D") is True
    ]


def _output_root_diff(before_rows: list[dict[str, Any]], after_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for before, after in zip(before_rows, [row for row in after_rows if row.get("stage") != "selected_feedback_stage1_official_eval"]):
        before_blob = json.dumps(before, ensure_ascii=False)
        after_blob = json.dumps(after, ensure_ascii=False)
        rows.append(
            {
                "case_id": after.get("case_id", ""),
                "algorithm": after.get("algorithm", ""),
                "stage": after.get("stage", ""),
                "legacy_root_before": _has_stale_n9b1d_root(before_blob),
                "legacy_root_after": _has_stale_n9b1d_root(after_blob),
                "new_root_after": N9B1D_STAGE in after_blob,
            }
        )
    return rows


def _single_position_noise_guard_rows(workspace_root: Path, command_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    applicability = _load_rows(workspace_root / AUDIT_ROOT_NAME / N9B0A1_STAGE / "cleaned_matrix" / "N9B0A_ALGORITHM_APPLICABILITY_MATRIX_CLEANED.json")
    c4_rows = _load_rows(workspace_root / AUDIT_ROOT_NAME / "N9B1C4_SELECTED_FEEDBACK_COMMAND_FIELD_COMPLETION" / "matrix" / "N9B1C4_N9B1D_READY_COMMAND_MATRIX.json")
    command_keys = {(row.get("case_id"), row.get("algorithm")): row for row in command_rows}
    c4_keys = {(row.get("case_id"), row.get("algorithm")) for row in c4_rows if row.get("run_allowed_in_N9B1D") is True}
    out: list[dict[str, Any]] = []
    for case_id in sorted(POSITION_NOISE_CASES):
        app = next(
            (
                row
                for row in applicability
                if row.get("case_id") == case_id and row.get("algorithm_group") == SINGLE_BASELINE_ALGORITHM
            ),
            {},
        )
        key = (case_id, SINGLE_BASELINE_ALGORITHM)
        command_row = command_keys.get(key, {})
        row = {
            "case_id": case_id,
            "algorithm": SINGLE_BASELINE_ALGORITHM,
            "n9b0a1_applicability": app.get("applicability", ""),
            "n9b0a1_applicable": app.get("applicability") == "applicable",
            "n9b1_or_c4_pilot_includes_medium_single": key in c4_keys if case_id == "C_position_noise_medium" else "",
            "n9b1a1_single7_seed_inputs_present": _case_has_single_seed_inputs(workspace_root, case_id),
            "n9b1a1_random_seed_manifest_present": (workspace_root / AUDIT_ROOT_NAME / N9B1A1_STAGE / "randomness" / case_id / "random_seed_manifest.json").is_file(),
            "n9b1a1_random_value_manifest_present": (workspace_root / AUDIT_ROOT_NAME / N9B1A1_STAGE / "randomness" / case_id / "random_value_manifest.json").is_file(),
            "n9b1a1_hash_manifest_present": (workspace_root / AUDIT_ROOT_NAME / N9B1A1_STAGE / "randomness" / case_id / "hashes.json").is_file(),
            "n9b1g1_command_matrix_includes_medium_single": key in command_keys if case_id == "C_position_noise_medium" else "",
            "n9b1g1_medium_single_runner": command_row.get("underlying_runner", "") if case_id == "C_position_noise_medium" else "",
            "n9b1g1_medium_single_not_legsa_formal_runner": "by2_algorithm_runner" not in str(command_row.get("command", "")) if case_id == "C_position_noise_medium" else "",
        }
        checks = [row["n9b0a1_applicable"]]
        if case_id == "C_position_noise_medium":
            checks.extend(
                [
                    row["n9b1a1_single7_seed_inputs_present"],
                    row["n9b1a1_random_seed_manifest_present"],
                    row["n9b1a1_random_value_manifest_present"],
                    row["n9b1a1_hash_manifest_present"],
                    row["n9b1_or_c4_pilot_includes_medium_single"],
                    row["n9b1g1_command_matrix_includes_medium_single"],
                    row["n9b1g1_medium_single_runner"] == "KF-GINS-Baseline",
                    row["n9b1g1_medium_single_not_legsa_formal_runner"],
                ]
            )
        row["guard_status"] = "pass" if all(checks) else "fail"
        out.append(row)
    return out


def _case_has_single_seed_inputs(workspace_root: Path, case_id: str) -> bool:
    root = workspace_root / AUDIT_ROOT_NAME / N9B1A1_STAGE
    return bool(list((root / "repaired_inputs" / case_id).glob("*single7_seed*"))) or bool(
        list((root / "randomness" / case_id / "random_values").glob("*single7*"))
    )


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


def _stage1_eval_dependency_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "created_utc": now_utc(),
        "same_case_selected_feedback_cases": sorted(SAME_CASE_SELECTED_FEEDBACK_CASES),
        "stage1_official_eval_rows": sum(row.get("stage") == "selected_feedback_stage1_official_eval" for row in rows),
        "dependency_sequence_by_case": {
            case_id: [row.get("stage") for row in sorted(case_rows, key=lambda row: int(row.get("dependency_order", 0)))]
            for case_id, case_rows in _selected_feedback_rows_by_case(rows).items()
        },
        "planned_official_evaluator_command_only": True,
        "solver_run": False,
        "official_evaluator_run": False,
    }


def _feedback_generation_command_repair_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    repaired = [row for row in rows if "/stage1_baseline_official_eval/EVAL_NAV.csv" in str(row.get("baseline_eval_nav_dependency", ""))]
    return {
        "stage": STAGE,
        "created_utc": now_utc(),
        "feedback_generation_command_rows": len(rows),
        "baseline_eval_nav_repaired_rows": len(repaired),
        "baseline_eval_nav_points_to_stage1_official_eval": len(repaired) == len(SAME_CASE_SELECTED_FEEDBACK_CASES),
        "solver_run": False,
        "official_evaluator_run": False,
    }


def _single_position_noise_guard_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "created_utc": now_utc(),
        "guard_rows": len(rows),
        "pass_rows": sum(row.get("guard_status") == "pass" for row in rows),
        "fail_rows": sum(row.get("guard_status") != "pass" for row in rows),
        "single_antenna_gnss1_status_KF_GINS_not_removed": any(
            row.get("case_id") == "C_position_noise_medium" and row.get("guard_status") == "pass" for row in rows
        ),
    }


def _output_root_normalization_report(rows: list[dict[str, Any]], diff_rows: list[dict[str, Any]]) -> dict[str, Any]:
    active = [row for row in rows if row.get("run_allowed_in_N9B1D") is True]
    return {
        "stage": STAGE,
        "created_utc": now_utc(),
        "active_command_rows": len(active),
        "stale_root_count_active_command_fields": sum(_has_stale_n9b1d_root(json.dumps(row, ensure_ascii=False)) for row in active),
        "new_root_count_active_command_fields": sum(N9B1D_STAGE in json.dumps(row, ensure_ascii=False) for row in active),
        "diff_rows": len(diff_rows),
    }


def _command_matrix_repair_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "created_utc": now_utc(),
        "source_stage": SOURCE_STAGE,
        "command_rows": len(rows),
        "run_allowed_rows": sum(row.get("run_allowed_in_N9B1D") is True for row in rows),
        "same_case_selected_feedback_cases": sorted(SAME_CASE_SELECTED_FEEDBACK_CASES),
        "M_normal_baseline_repeat_policy": "clean-repeat stage2 only",
        "L_feedback_disabled_policy": "disabled marker stage2 only",
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
        "solver_run": False,
        "official_evaluator_run": False,
    }


def _decision_report(validation: dict[str, Any], reports: dict[str, Any]) -> dict[str, Any]:
    status = (
        "N9B1G1_selected_feedback_eval_dependency_fixed_single_position_noise_preserved"
        if validation["status"] == "pass"
        else "N9B1G1_validation_failed"
    )
    return {
        "stage": STAGE,
        "created_utc": now_utc(),
        "status": status,
        "ready_for_N9B1D_solver_execution": validation["status"] == "pass",
        "ready_for_N9B2_execution": False,
        "recommended_next_stage": "human_review_N9B1G1_then_N9B1D_solver_execution" if validation["status"] == "pass" else "repair_N9B1G1_validation_issues",
        "validation_status": validation["status"],
        "issues": validation["issues"],
        "solver_run": False,
        "official_evaluator_run": False,
        "figures_generated": False,
    }


def _write_outputs(runtime_root: Path, result: dict[str, Any]) -> None:
    _create_runtime_tree(runtime_root)
    reports = {
        "N9B1G1_SELECTED_FEEDBACK_STAGE1_EVAL_DEPENDENCY_REPORT.json": result["stage1_eval_dependency_report"],
        "N9B1G1_FEEDBACK_GENERATION_COMMAND_REPAIR_REPORT.json": result["feedback_generation_command_repair_report"],
        "N9B1G1_SINGLE_POSITION_NOISE_GUARD_REPORT.json": result["single_position_noise_guard_report"],
        "N9B1G1_OUTPUT_ROOT_NORMALIZATION_REPORT.json": result["output_root_normalization_report"],
        "N9B1G1_COMMAND_MATRIX_REPAIR_REPORT.json": result["command_matrix_repair_report"],
        "N9B1G1_WSL_DRYRUN_REPORT.json": result["wsl_dryrun_report"],
        "N9B1G1_VALIDATION_REPORT.json": result["validation_report"],
        "N9B1G1_DECISION_REPORT.json": result["decision_report"],
    }
    for name, payload in reports.items():
        _write_json(runtime_root / "reports" / name, payload)
    matrices = {
        "N9B1G1_SELECTED_FEEDBACK_DEPENDENCY_GRAPH": result["selected_feedback_dependency_graph"],
        "N9B1G1_FEEDBACK_GENERATION_COMMANDS": result["feedback_generation_commands"],
        "N9B1G1_SINGLE_POSITION_NOISE_GUARD_MATRIX": result["single_position_noise_guard_matrix"],
        "N9B1G1_OUTPUT_ROOT_DIFF": result["output_root_diff"],
        "N9B1G1_N9B1D_READY_COMMAND_MATRIX": result["n9b1d_ready_command_matrix"],
        "N9B1G1_N9B1D_DEPENDENCY_ORDER_MATRIX": result["n9b1d_dependency_order_matrix"],
        "N9B1G1_WSL_DRYRUN_COMMANDS": result["wsl_dryrun_commands"],
    }
    for stem, rows in matrices.items():
        _write_table_pair(runtime_root / "matrix" / stem, rows)
    _write_table_pair(runtime_root / "dependency_graph_fix" / "N9B1G1_SELECTED_FEEDBACK_DEPENDENCY_GRAPH", result["selected_feedback_dependency_graph"])
    _write_table_pair(runtime_root / "command_matrix_fix" / "N9B1G1_N9B1D_READY_COMMAND_MATRIX", result["n9b1d_ready_command_matrix"])
    _write_table_pair(runtime_root / "output_root_normalization" / "N9B1G1_OUTPUT_ROOT_DIFF", result["output_root_diff"])
    _write_table_pair(runtime_root / "single_position_noise_guard" / "N9B1G1_SINGLE_POSITION_NOISE_GUARD_MATRIX", result["single_position_noise_guard_matrix"])
    _write_table_pair(runtime_root / "wsl_dryrun" / "N9B1G1_WSL_DRYRUN_COMMANDS", result["wsl_dryrun_commands"])
    for row in result["n9b1d_ready_command_matrix"]:
        payload = row.get("_solver_payload")
        if payload:
            _write_json(Path(row["solver_command_json"]), payload)
    _write_json(runtime_root / "validation" / "N9B1G1_VALIDATION_REPORT.json", result["validation_report"])
    _write_json(runtime_root / "logs" / "N9B1G1_OPERATION_LOG.json", {"stage": STAGE, "created_utc": now_utc(), "solver_run": False})
    (runtime_root / "single_position_noise_guard" / "n9b1g1_single_position_noise_guard.md").write_text(_guard_markdown(result), encoding="utf-8")
    (runtime_root / "summary" / "n9b1g1_next_stage_recommendation.md").write_text(_summary_markdown(result), encoding="utf-8")


def _guard_markdown(result: dict[str, Any]) -> str:
    report = result["single_position_noise_guard_report"]
    return (
        "# N9B1G1 single position-noise guard\n\n"
        f"- guard_rows={report['guard_rows']}\n"
        f"- pass_rows={report['pass_rows']}\n"
        f"- fail_rows={report['fail_rows']}\n"
        f"- single_antenna_gnss1_status_KF_GINS_not_removed={str(report['single_antenna_gnss1_status_KF_GINS_not_removed']).lower()}\n"
    )


def _summary_markdown(result: dict[str, Any]) -> str:
    decision = result["decision_report"]
    validation = result["validation_report"]
    return (
        "# N9B1G1 next stage recommendation\n\n"
        f"- status={decision['status']}\n"
        f"- ready_for_N9B1D_solver_execution={str(decision['ready_for_N9B1D_solver_execution']).lower()}\n"
        "- ready_for_N9B2_execution=false\n"
        f"- validation_status={validation['status']}\n"
        f"- selected_feedback_stage1_official_eval_rows={validation['selected_feedback_stage1_official_eval_rows']}\n"
        f"- stale_root_count_active_command_fields={validation['stale_root_count_active_command_fields']}\n"
        f"- new_root_count_active_command_fields={validation['new_root_count_active_command_fields']}\n"
    )


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = data.get("rows", data) if isinstance(data, dict) else data
    return [row for row in rows if isinstance(row, dict)]


def _has_stale_n9b1d_root(text: str) -> bool:
    return (
        f"{LEGACY_N9B1D_STAGE}/" in text
        or f"{LEGACY_N9B1D_STAGE}\\\\" in text
        or f"{LEGACY_N9B1D_STAGE}\\\\/" in text
    )


def _create_runtime_tree(runtime_root: Path) -> None:
    for subdir in REQUIRED_SUBDIRS:
        (runtime_root / subdir).mkdir(parents=True, exist_ok=True)


def _reset_runtime_tree(runtime_root: Path) -> None:
    for subdir in REQUIRED_SUBDIRS:
        path = runtime_root / subdir
        if path.exists():
            shutil.rmtree(path)
    _create_runtime_tree(runtime_root)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
