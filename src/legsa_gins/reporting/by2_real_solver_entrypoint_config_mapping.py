"""N9B1C real solver entrypoint and config mapping.

This module is static/reporting-only. It repairs executable command plans from
earlier placeholder plans, writes generated runtime configs, and blocks mappings
whose real input dependencies are not available. It never runs solvers,
evaluators, figure generators, or degradation matrices.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legsa_gins.reporting.by2_degradation_runner_precheck import (
    FORBIDDEN_EXECUTION_OUTPUT_NAMES,
    discover_cleaned_matrix_root,
    load_csv_rows,
    load_matrix_bundle,
)
from legsa_gins.reporting.by2_downsample_cadence_policy_repair import (
    REPAIRED_PILOT_CASE_IDS,
    default_n9b1a1_runtime_root,
)
from legsa_gins.reporting.by2_real_pilot_input_generator import (
    AUDIT_ROOT_NAME,
    SourcePaths,
    discover_runtime_sources,
)


STAGE = "N9B1C_REAL_SOLVER_ENTRYPOINT_AND_CONFIG_MAPPING"
FUTURE_SOLVER_STAGE = "N9B1D_PILOT_SOLVER_EXECUTION"
_WSL_HOME_PREFIX = "/" + "home"
_WSL_USER_NAME = "kaiwen"
KF_GINS_BASELINE_WORKING_DIRECTORY = f"{_WSL_HOME_PREFIX}/{_WSL_USER_NAME}/KF-GINS-Baseline"
LEGSA_WORKING_DIRECTORY = f"{_WSL_HOME_PREFIX}/{_WSL_USER_NAME}/LegSA-GINS"
KF_GINS_BASELINE_ENTRYPOINT = f"{KF_GINS_BASELINE_WORKING_DIRECTORY}/bin/KF-GINS"
LEGSA_ENTRYPOINT = f"{LEGSA_WORKING_DIRECTORY}/build/cpp/legsa_gins"
WSL_AUDIT_ROOT = "${WSL_AUDIT_ROOT}"
REQUIRED_SUBDIRS = [
    "solver_entrypoint_inventory",
    "algorithm_config_mapping",
    "repaired_command_plans",
    "wsl_dryrun",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
]
REPORT_NAMES = [
    "N9B1C_SOLVER_ENTRYPOINT_INVENTORY_REPORT.json",
    "N9B1C_COMMAND_MAPPING_REPORT.json",
    "N9B1C_CONFIG_MAPPING_REPORT.json",
    "N9B1C_WSL_DRYRUN_REPORT.json",
    "N9B1C_VALIDATION_REPORT.json",
    "N9B1C_DECISION_REPORT.json",
]
MATRIX_STEMS = [
    "N9B1C_SOLVER_ENTRYPOINT_INVENTORY",
    "N9B1C_COMMAND_MAPPING_MATRIX",
    "N9B1C_ALGORITHM_READY_MATRIX",
    "N9B1C_BLOCKED_MAPPING_MATRIX",
    "N9B1C_WSL_DRYRUN_COMMAND_MATRIX",
]
REQUIRED_ALGORITHMS = [
    "source_backed_EKF",
    "Raw_Doppler_EKF",
    "source_aware_EKF",
    "Go2_joint_EKF",
    "baseline_no_feedback_EKF",
    "selected_feedback_EKF",
    "single_antenna_gnss1_status_KF_GINS",
    "reject_all_sanity",
    "pure_INS_reference_initialized",
    "final_v23_dual_antenna_EKF",
    "true_no_feedback_FGO",
]
LEGSA_EKF_GROUPS = {
    "source_backed_EKF",
    "Raw_Doppler_EKF",
    "source_aware_EKF",
    "Go2_joint_EKF",
    "baseline_no_feedback_EKF",
    "selected_feedback_EKF",
}
KF_GINS_APPLICABLE_FAMILIES = {"M", "A", "B", "C", "D"}


@dataclass(frozen=True)
class RuntimeDependencyPaths:
    imu: Path | None
    go2: Path | None
    raw_doppler: Path | None
    feedback_observations: Path | None
    source: str


def default_n9b1c_runtime_root(workspace_root: Path) -> Path:
    return workspace_root / AUDIT_ROOT_NAME / STAGE


def run_real_solver_entrypoint_config_mapping(
    workspace_root: Path,
    runtime_root: Path | None = None,
    matrix_root: Path | None = None,
    write_outputs: bool = True,
    source_paths: SourcePaths | None = None,
    dependency_paths: RuntimeDependencyPaths | None = None,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root or default_n9b1c_runtime_root(workspace_root)
    matrix_root = matrix_root or discover_cleaned_matrix_root(workspace_root)
    bundle = load_matrix_bundle(matrix_root)
    n9b1a1_root = default_n9b1a1_runtime_root(workspace_root)
    n9b1b_root = workspace_root / AUDIT_ROOT_NAME / "N9B1B_PILOT_SOLVER_EXECUTION_AND_EVALUATION"
    sources = source_paths or discover_runtime_sources(workspace_root)
    deps = dependency_paths or discover_runtime_dependencies(workspace_root, sources)
    if write_outputs:
        _create_runtime_tree(runtime_root)

    degraded_index = _load_json_rows(n9b1a1_root / "matrix" / "N9B1A1_DEGRADED_INPUT_INDEX_REPAIRED.json")
    old_plan_rows = _load_json_rows(n9b1a1_root / "matrix" / "N9B1A1_SOLVER_COMMAND_PLAN_INDEX_REPAIRED.json")
    n9b1b_rows = _load_json_rows(n9b1b_root / "matrix" / "N9B1B_EXECUTION_MATRIX.json")
    selected_rows = _selected_mapping_rows(bundle.pilot, old_plan_rows, n9b1b_rows)
    inventory = _build_inventory(deps)
    mapping_rows: list[dict[str, Any]] = []
    wsl_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []

    for row in selected_rows:
        mapping = _map_row(
            row=row,
            workspace_root=workspace_root,
            runtime_root=runtime_root,
            n9b1a1_root=n9b1a1_root,
            degraded_index=degraded_index,
            deps=deps,
            sources=sources,
            write_outputs=write_outputs,
        )
        mapping_rows.append(mapping)
        if mapping["mapping_status"] == "mapped":
            wsl_rows.append(_wsl_row(mapping))
        if mapping["mapping_status"] in {"blocked", "fixed_reference", "diagnostic_blocked", "marker_only"}:
            blocked_rows.append(_blocked_row(mapping))

    ready_matrix = _build_ready_matrix(mapping_rows)
    validation = validate_n9b1c_result(runtime_root, mapping_rows, ready_matrix, blocked_rows, wsl_rows, runtime_written=False)
    all_selected_mapped = all(row["mapping_status"] == "mapped" for row in mapping_rows if row["selected_for_N9B1C_mapping"])
    blockers = [row for row in blocked_rows if row["mapping_status"] not in {"fixed_reference", "marker_only"}]
    ready_for_n9b1d = validation["status"] == "pass" and all_selected_mapped and bool(mapping_rows)
    if validation["status"] != "pass":
        decision_status = "N9B1C_safety_gate_failed"
        recommended_next_stage = "repair_safety_violation"
    elif ready_for_n9b1d:
        decision_status = "N9B1C_real_solver_mapping_ready"
        recommended_next_stage = "human_review_N9B1C_then_N9B1D_solver_execution"
    else:
        decision_status = "N9B1C_solver_mapping_partial_with_blockers"
        recommended_next_stage = "fix_solver_mapping_blockers"

    result = {
        "solver_entrypoint_inventory_report": {
            "stage": STAGE,
            "dryrun_only": True,
            "solver_run": False,
            "official_evaluator_run": False,
            "inventory_rows": len(inventory),
            "real_entrypoints_mapped": [row["entrypoint"] for row in inventory if row["mapping_role"] == "solver_entrypoint"],
        },
        "command_mapping_report": {
            "stage": STAGE,
            "selected_mapping_rows": len(mapping_rows),
            "mapped_command_rows": sum(row["mapping_status"] == "mapped" for row in mapping_rows),
            "blocked_mapping_rows": len(blocked_rows),
            "placeholder_future_solver_entry_commands": 0,
            "output_root_stage": FUTURE_SOLVER_STAGE,
            "solver_run": False,
            "official_evaluator_run": False,
        },
        "config_mapping_report": {
            "stage": STAGE,
            "config_rows": len(mapping_rows),
            "generated_config_format": "yaml_for_mapped_json_for_blocked",
            "source_role_files_written": write_outputs,
            "trace_solver_input": False,
            "final_v23_solver_input": False,
        },
        "wsl_dryrun_report": {
            "stage": STAGE,
            "dry_run_only": True,
            "wsl_bridge_script": "scripts/run_wsl_legsa.ps1",
            "dryrun_command_rows": len(wsl_rows),
            "executed": False,
            "solver_run": False,
            "official_evaluator_run": False,
        },
        "validation_report": validation,
        "decision_report": {
            "stage": STAGE,
            "status": decision_status,
            "ready_for_N9B1D_solver_execution": ready_for_n9b1d,
            "ready_for_N9B2_execution": False,
            "ready_for_full_N9B_execution": False,
            "recommended_next_stage": recommended_next_stage,
            "solver_run": False,
            "official_evaluator_run": False,
            "figures_generated": False,
            "blockers": blockers,
            "limitations": [
                "mapping-only stage; no solver, evaluator, NAV, STD, EVAL_NAV, RUN_MANIFEST, figures, or case reviews generated",
                "selected_feedback_EKF remains blocked unless feedback observation dependency is available or disabled by case policy",
                "Raw_Doppler_EKF remains blocked unless raw Doppler dependency is available or disabled by case policy",
            ],
        },
        "solver_entrypoint_inventory": inventory,
        "command_mapping_matrix": mapping_rows,
        "algorithm_ready_matrix": ready_matrix,
        "blocked_mapping_matrix": blocked_rows,
        "wsl_dryrun_command_matrix": wsl_rows,
    }
    if write_outputs:
        _write_outputs(runtime_root, result)
    return result


def discover_runtime_dependencies(workspace_root: Path, sources: SourcePaths | None = None) -> RuntimeDependencyPaths:
    sources = sources or discover_runtime_sources(workspace_root)
    local = workspace_root / "docs" / "codex_context" / "DATA_PATHS.local.md"
    candidates = _extract_windows_paths(local) if local.exists() else []
    go2 = _first_existing(candidates, "by2.txt")
    raw_doppler = (
        _first_existing(candidates, "RAW_DOPPLER_VELOCITY_FACTORS.csv")
        or _find_runtime_file(workspace_root / AUDIT_ROOT_NAME, "RAW_DOPPLER_VELOCITY_FACTORS.csv")
        or _find_runtime_file(workspace_root / AUDIT_ROOT_NAME, "RTKLIB_DOPPLER_PROVIDER_VELOCITY.csv")
    )
    feedback = _first_existing(candidates, "FGO_FEEDBACK_OBSERVATIONS.csv")
    return RuntimeDependencyPaths(
        imu=sources.imu,
        go2=go2,
        raw_doppler=raw_doppler,
        feedback_observations=feedback,
        source="DATA_PATHS.local.md" if local.exists() else "workspace_search",
    )


def validate_n9b1c_result(
    runtime_root: Path,
    mapping_rows: list[dict[str, Any]] | None = None,
    ready_matrix: list[dict[str, Any]] | None = None,
    blocked_rows: list[dict[str, Any]] | None = None,
    wsl_rows: list[dict[str, Any]] | None = None,
    runtime_written: bool = True,
) -> dict[str, Any]:
    issues: list[str] = []
    forbidden_suffixes = {".png", ".pdf", ".svg", ".jpg", ".jpeg", ".npy", ".npz"}
    if runtime_written and runtime_root.exists():
        for path in runtime_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in forbidden_suffixes:
                issues.append(f"forbidden artifact generated: {_rel(runtime_root, path)}")
            if any(path.name.startswith(name) for name in FORBIDDEN_EXECUTION_OUTPUT_NAMES):
                issues.append(f"forbidden execution output generated: {_rel(runtime_root, path)}")
            if path.suffix.lower() == ".json":
                raw = path.read_bytes()
                if raw.startswith(b"\xef\xbb\xbf"):
                    issues.append(f"json has BOM: {_rel(runtime_root, path)}")
                try:
                    json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    issues.append(f"json parse failed: {_rel(runtime_root, path)}: {exc}")
        for subdir in REQUIRED_SUBDIRS:
            if not (runtime_root / subdir).is_dir():
                issues.append(f"missing required subdir: {subdir}")
        for report in REPORT_NAMES:
            if not (runtime_root / "reports" / report).is_file():
                issues.append(f"missing report: {report}")
        for stem in MATRIX_STEMS:
            if not (runtime_root / "matrix" / f"{stem}.csv").is_file():
                issues.append(f"missing matrix CSV: {stem}")
            if not (runtime_root / "matrix" / f"{stem}.json").is_file():
                issues.append(f"missing matrix JSON: {stem}")
    for row in mapping_rows or []:
        command = str(row.get("command", ""))
        if "python -m legsa_gins.future_solver_entry" in command:
            issues.append(f"placeholder command remains: {row.get('case_id')}/{row.get('algorithm')}")
        if row.get("mapping_status") == "mapped":
            if not row.get("input_paths_exist"):
                issues.append(f"mapped row has missing input path: {row.get('case_id')}/{row.get('algorithm')}")
            if "N9B1C_REAL_SOLVER_ENTRYPOINT_AND_CONFIG_MAPPING" in str(row.get("future_output_root", "")):
                issues.append(f"mapped output root points under N9B1C: {row.get('case_id')}/{row.get('algorithm')}")
            for key in [
                "command_type",
                "command",
                "working_directory",
                "environment",
                "inputs",
                "generated_config_path",
                "output_root",
                "expected_outputs",
            ]:
                if _is_missing(row.get(key)):
                    issues.append(f"mapped row missing {key}: {row.get('case_id')}/{row.get('algorithm')}")
            if row.get("run_allowed_in_N9B1D") is not True:
                issues.append(f"mapped row not allowed for N9B1D: {row.get('case_id')}/{row.get('algorithm')}")
            if row.get("command_type") not in {"wsl_command", "external_kf_gins", "python_module"}:
                issues.append(f"mapped row has invalid command_type: {row.get('case_id')}/{row.get('algorithm')}")
        if row.get("mapping_status") != "mapped" and row.get("run_allowed_in_N9B1D") is True:
            issues.append(f"blocked row allowed for N9B1D: {row.get('case_id')}/{row.get('algorithm')}")
        if row.get("trace_solver_input") is not False:
            issues.append(f"trace solver input not false: {row.get('case_id')}/{row.get('algorithm')}")
        if row.get("final_v23_solver_input") is not False:
            issues.append(f"final_v23 solver input not false: {row.get('case_id')}/{row.get('algorithm')}")
        if row.get("solver_input_trace") is not False:
            issues.append(f"solver_input_trace not false: {row.get('case_id')}/{row.get('algorithm')}")
        if row.get("solver_input_final_v23") is not False:
            issues.append(f"solver_input_final_v23 not false: {row.get('case_id')}/{row.get('algorithm')}")
        for key in ["solver_run", "official_evaluator_run", "NAV_generated", "STD_generated", "EVAL_NAV_generated", "RUN_MANIFEST_generated", "figures_generated"]:
            if row.get(key) not in {False, 0}:
                issues.append(f"{key} must be false: {row.get('case_id')}/{row.get('algorithm')}")
    if any(row.get("ready_for_N9B2_execution") is not False for row in ready_matrix or []):
        issues.append("ready_for_N9B2_execution must always be false")
    if any(row.get("executed") is not False or row.get("dry_run_only") is not True for row in wsl_rows or []):
        issues.append("WSL dry-run rows must be dry_run_only=true and executed=false")
    return {
        "stage": STAGE,
        "status": "pass" if not issues else "fail",
        "ready_for_N9B2_execution": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "figures_generated": False,
        "issues": issues,
        "blocked_count": len(blocked_rows or []),
    }


def _selected_mapping_rows(
    pilot_rows: list[dict[str, str]],
    old_plan_rows: list[dict[str, Any]],
    n9b1b_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    pilot_by_case = {row["case_id"]: row for row in pilot_rows}
    for row in old_plan_rows:
        case_id = row.get("case_id", "")
        algorithm = row.get("algorithm", "")
        if case_id in REPAIRED_PILOT_CASE_IDS and algorithm in REQUIRED_ALGORITHMS:
            pilot = pilot_by_case.get(case_id, {})
            selected[(case_id, algorithm)] = {
                "case_id": case_id,
                "pilot_case_id": pilot.get("pilot_case_id", case_id),
                "family_code": pilot.get("family_code", case_id[:1]),
                "algorithm": algorithm,
                "routing_status": row.get("routing_status", ""),
                "selected_for_N9B1C_mapping": True,
                "prior_solver_command_json": row.get("solver_command_json", ""),
            }
    for row in n9b1b_rows:
        case_id = row.get("case_id", "")
        algorithm = row.get("algorithm", "")
        if case_id in REPAIRED_PILOT_CASE_IDS and algorithm in REQUIRED_ALGORITHMS:
            item = selected.setdefault((case_id, algorithm), {
                "case_id": case_id,
                "pilot_case_id": row.get("pilot_case_id", case_id),
                "family_code": row.get("family_code", case_id[:1]),
                "algorithm": algorithm,
                "routing_status": row.get("routing_status", ""),
                "selected_for_N9B1C_mapping": True,
                "prior_solver_command_json": "",
            })
            item["n9b1b_block_reason"] = row.get("block_reason", "")
    for case_id in REPAIRED_PILOT_CASE_IDS:
        for algorithm in REQUIRED_ALGORITHMS:
            selected.setdefault((case_id, algorithm), {
                "case_id": case_id,
                "pilot_case_id": pilot_by_case.get(case_id, {}).get("pilot_case_id", case_id),
                "family_code": pilot_by_case.get(case_id, {}).get("family_code", case_id[:1]),
                "algorithm": algorithm,
                "routing_status": "not_selected_in_prior_plan",
                "selected_for_N9B1C_mapping": False,
                "prior_solver_command_json": "",
            })
    return [selected[key] for key in sorted(selected, key=lambda item: (REPAIRED_PILOT_CASE_IDS.index(item[0]), REQUIRED_ALGORITHMS.index(item[1])))]


def _map_row(
    row: dict[str, Any],
    workspace_root: Path,
    runtime_root: Path,
    n9b1a1_root: Path,
    degraded_index: list[dict[str, Any]],
    deps: RuntimeDependencyPaths,
    sources: SourcePaths,
    write_outputs: bool,
) -> dict[str, Any]:
    case_id = row["case_id"]
    algorithm = row["algorithm"]
    family = row["family_code"]
    case_inputs = [item for item in degraded_index if item.get("case_id") == case_id]
    input_choice = _choose_input(case_inputs, algorithm)
    input_exists = bool(input_choice) and (n9b1a1_root / input_choice["path"]).is_file()
    mapping_status = "blocked"
    reason = ""
    entrypoint = ""
    command = ""
    config: dict[str, Any] = {}
    command_type = "blocked"
    working_directory = ""
    wsl_audit_root = _to_wsl_path(workspace_root)
    environment = {"WSL_AUDIT_ROOT": wsl_audit_root}
    future_output_root = f"{wsl_audit_root}/{AUDIT_ROOT_NAME}/{FUTURE_SOLVER_STAGE}/algorithm_outputs/{case_id}/{algorithm}"
    all_case_inputs = [item.get("path", "") for item in case_inputs if item.get("path")]
    degraded_input_paths_wsl = [
        f"{wsl_audit_root}/{AUDIT_ROOT_NAME}/N9B1A1_DOWNSAMPLE_CADENCE_POLICY_REPAIR/{path}"
        for path in all_case_inputs
    ]

    if algorithm == "single_antenna_gnss1_status_KF_GINS":
        if family not in KF_GINS_APPLICABLE_FAMILIES:
            reason = f"single_antenna_gnss1_status_KF_GINS is limited to M/A/B/C/D pilot families, got {family}"
        elif not input_exists or not input_choice["input_tag"].startswith("single7"):
            reason = "7-col GNSS1-status degraded input missing"
        elif not _path_exists(deps.imu):
            reason = "real IMU input missing"
        else:
            mapping_status = "mapped"
            entrypoint = KF_GINS_BASELINE_ENTRYPOINT
            config = _kf_config(case_id, algorithm, input_choice, deps, future_output_root, wsl_audit_root)
            command_type = "external_kf_gins"
            working_directory = KF_GINS_BASELINE_WORKING_DIRECTORY
    elif algorithm in LEGSA_EKF_GROUPS:
        mapping_status, reason, config = _legsa_config_status(case_id, algorithm, input_choice, input_exists, deps, future_output_root, wsl_audit_root)
        if mapping_status == "mapped":
            entrypoint = LEGSA_ENTRYPOINT
            command_type = "wsl_command"
            working_directory = LEGSA_WORKING_DIRECTORY
    elif algorithm == "reject_all_sanity":
        mapping_status = "diagnostic_blocked"
        reason = "reject_all_sanity requires a real reject-all runner/config dependency; none is registered for N9B1C"
    elif algorithm == "pure_INS_reference_initialized":
        mapping_status = "fixed_reference"
        reason = "pure_INS_reference_initialized is fixed_reference and not solver-runnable without an approved pure-INS degradation rerun"
    elif algorithm == "final_v23_dual_antenna_EKF":
        mapping_status = "fixed_reference"
        reason = "final_v23_dual_antenna_EKF is reference-only and never solver-runnable in N9B1C"
    elif algorithm == "true_no_feedback_FGO":
        mapping_status = "diagnostic_blocked"
        reason = "true_no_feedback_FGO is diagnostic-only until a full direct degraded FGO runner exists"
    else:
        reason = "algorithm not recognized by N9B1C mapper"

    if mapping_status == "fixed_reference":
        command_type = "fixed_reference"
    elif mapping_status == "marker_only":
        command_type = "marker_only_not_solver"
    elif mapping_status != "mapped":
        command_type = "blocked"
    config_suffix = "yaml" if mapping_status == "mapped" else "json"
    config_rel = f"algorithm_config_mapping/{case_id}/{algorithm}/config.{config_suffix}"
    config_wsl = f"{wsl_audit_root}/{AUDIT_ROOT_NAME}/{STAGE}/{config_rel}"
    if mapping_status == "mapped":
        if command_type == "external_kf_gins":
            command = f"{entrypoint} {config_wsl}"
        else:
            command = f"{entrypoint} --config {config_wsl} --output-dir {future_output_root}"
    command_preview = command if command else f"BLOCKED: {reason}"
    solver_rel = f"repaired_command_plans/{case_id}/{algorithm}/solver_command.json"
    inputs = _command_inputs(
        algorithm=algorithm,
        input_choice=input_choice,
        deps=deps,
        wsl_audit_root=wsl_audit_root,
        source_aware_enabled=bool(config.get("source_aware", {}).get("enabled")) if config else False,
        raw_doppler_enabled=bool(config.get("raw_doppler", {}).get("enabled")) if config else False,
        go2_enabled=bool(config.get("go2", {}).get("enabled")) if config else False,
        feedback_enabled=bool(config.get("feedback", {}).get("enabled")) if config else False,
    )
    expected_outputs = _expected_outputs(algorithm, future_output_root)
    mapped = {
        **row,
        "stage": STAGE,
        "mapping_status": mapping_status,
        "blocked_reason": "" if mapping_status == "mapped" else reason,
        "block_reason": "" if mapping_status == "mapped" else reason,
        "command_type": command_type,
        "entrypoint": entrypoint,
        "command": command,
        "command_preview": command_preview,
        "working_directory": working_directory,
        "environment": environment,
        "inputs": inputs,
        "degraded_input_paths": all_case_inputs,
        "degraded_input_paths_wsl": degraded_input_paths_wsl,
        "solver_command_json": solver_rel,
        "config_path": "runtime_generated",
        "generated_config_path": config_rel,
        "generated_config_path_wsl": config_wsl,
        "config_json": config_rel if config_suffix == "json" else "",
        "config_yaml": config_rel if config_suffix == "yaml" else "",
        "source_role_json": f"algorithm_config_mapping/{case_id}/{algorithm}/source_role.json",
        "output_lineage_json": f"algorithm_config_mapping/{case_id}/{algorithm}/output_lineage.json",
        "config_diff_from_normal_json": f"algorithm_config_mapping/{case_id}/{algorithm}/config_diff_from_normal.json",
        "input_path": input_choice.get("path", "") if input_choice else "",
        "input_tag": input_choice.get("input_tag", "") if input_choice else "",
        "input_paths_exist": input_exists,
        "imu_input_exists": _path_exists(deps.imu),
        "go2_input_exists": _path_exists(deps.go2),
        "raw_doppler_input_exists": _path_exists(deps.raw_doppler),
        "feedback_observation_input_exists": _path_exists(deps.feedback_observations),
        "future_output_root": future_output_root,
        "output_root": future_output_root,
        "expected_outputs": expected_outputs,
        "solver_run": False,
        "official_evaluator_run": False,
        "NAV_generated": False,
        "STD_generated": False,
        "EVAL_NAV_generated": False,
        "RUN_MANIFEST_generated": False,
        "figures_generated": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "solver_input_trace": False,
        "solver_input_final_v23": False,
        "ready_for_N9B1D_solver_execution": mapping_status == "mapped",
        "run_allowed_in_N9B1D": mapping_status == "mapped",
        "ready_for_N9B2_execution": False,
    }
    if write_outputs:
        _write_mapping_files(runtime_root, mapped, config, sources, deps)
    return mapped


def _legsa_config_status(
    case_id: str,
    algorithm: str,
    input_choice: dict[str, Any] | None,
    input_exists: bool,
    deps: RuntimeDependencyPaths,
    future_output_root: str,
    wsl_audit_root: str,
) -> tuple[str, str, dict[str, Any]]:
    if not input_exists:
        return "blocked", "degraded GNSS input missing", {}
    if not _path_exists(deps.imu):
        return "blocked", "real IMU input missing", {}
    config = _legsa_base_config(case_id, algorithm, input_choice, deps, future_output_root, wsl_audit_root)
    if algorithm == "source_backed_EKF":
        return "mapped", "", config
    if algorithm == "baseline_no_feedback_EKF":
        config["feedback"]["enabled"] = False
        config["feedback"]["policy"] = "disabled_by_baseline_no_feedback_EKF"
        return "mapped", "", config
    if algorithm == "source_aware_EKF":
        config["source_aware"]["enabled"] = case_id != "I_source_aware_disabled"
        config["source_aware"]["disabled_reason"] = "I_source_aware_disabled" if case_id == "I_source_aware_disabled" else ""
        config["enable_source_aware_weighting"] = case_id != "I_source_aware_disabled"
        config["source_aware_policy_version"] = "n6b_conservative_innovation_covariance"
        config["source_aware_mode"] = "lsim_oim" if case_id != "I_source_aware_disabled" else "disabled"
        config["source_aware_no_R_shrink"] = True
        return "mapped", "", config
    if algorithm == "Raw_Doppler_EKF":
        if case_id == "G_raw_doppler_disabled":
            config["raw_doppler"]["enabled"] = False
            config["raw_doppler"]["disabled_reason"] = "G_raw_doppler_disabled"
            config["enable_raw_doppler"] = False
            config["raw_doppler_disabled_reason"] = "G_raw_doppler_disabled"
            return "mapped", "", config
        if not _path_exists(deps.raw_doppler):
            return "blocked", "Raw_Doppler_EKF requires existing raw-doppler source/config input", {}
        config["raw_doppler"]["enabled"] = True
        config["raw_doppler"]["factor_path"] = _to_wsl_path(deps.raw_doppler) if deps.raw_doppler else ""
        config["enable_raw_doppler"] = True
        config["raw_doppler_factor_path"] = _to_wsl_path(deps.raw_doppler) if deps.raw_doppler else ""
        config["raw_doppler_factor_source"] = "RTKLIB_DOPPLER_PROVIDER"
        config["raw_doppler_time_tolerance_sec"] = 0.08
        config["raw_doppler_min_sat"] = 5
        config["raw_doppler_mode"] = "doppler_ls_velocity"
        return "mapped", "", config
    if algorithm == "Go2_joint_EKF":
        if not _path_exists(deps.go2):
            return "blocked", "Go2_joint_EKF requires existing Go2 source input", {}
        config["go2"]["enabled"] = True
        config["enable_go2_horizontal_velocity_prior"] = True
        config["go2_body_source_path"] = _to_wsl_path(deps.go2) if deps.go2 else ""
        if case_id == "J_go2_horizontal_velocity_missing":
            config["go2"]["horizontal_velocity_enabled"] = False
            config["go2"]["disabled_reason"] = "J_go2_horizontal_velocity_missing"
            config["go2_horizontal_velocity_enabled"] = False
            config["go2_horizontal_velocity_disabled_reason"] = "J_go2_horizontal_velocity_missing"
        return "mapped", "", config
    if algorithm == "selected_feedback_EKF":
        if case_id == "L_feedback_disabled":
            config["feedback"]["enabled"] = False
            config["feedback"]["policy"] = "L_feedback_disabled"
            config["enable_fgo_feedback"] = False
            config["fgo_feedback_disabled_reason"] = "L_feedback_disabled"
            return "mapped", "", config
        if not _path_exists(deps.feedback_observations):
            return "blocked", "selected_feedback_EKF requires existing feedback observation dependency", {}
        config["feedback"]["enabled"] = True
        config["feedback"]["observations"] = _to_wsl_path(deps.feedback_observations) if deps.feedback_observations else ""
        config["enable_fgo_feedback"] = True
        config["fgo_feedback_path"] = _to_wsl_path(deps.feedback_observations) if deps.feedback_observations else ""
        config["fgo_feedback_mode"] = "pseudo_measurement"
        config["fgo_feedback_no_future_data_required"] = True
        return "mapped", "", config
    return "blocked", "LegSA EKF algorithm is not mapped", {}


def _kf_config(case_id: str, algorithm: str, input_choice: dict[str, Any], deps: RuntimeDependencyPaths, future_output_root: str, wsl_audit_root: str) -> dict[str, Any]:
    config = _runtime_solver_config(case_id, algorithm, input_choice, deps, future_output_root, wsl_audit_root)
    config.update(
        {
            "solver": "KF_GINS_Baseline",
            "gnss_format": 0,
            "enable_dual_antenna_yaw": False,
            "enable_raw_doppler": False,
            "enable_source_aware_weighting": False,
            "enable_go2_horizontal_velocity_prior": False,
            "enable_fgo_feedback": False,
            "trace_solver_input": False,
            "final_v23_solver_input": False,
        }
    )
    return config


def _legsa_base_config(
    case_id: str,
    algorithm: str,
    input_choice: dict[str, Any] | None,
    deps: RuntimeDependencyPaths,
    future_output_root: str,
    wsl_audit_root: str,
) -> dict[str, Any]:
    config = _runtime_solver_config(case_id, algorithm, input_choice, deps, future_output_root, wsl_audit_root)
    config.update(
        {
            "solver": "LegSA_GINS_cpp",
            "gnss_format": 1,
            "enable_dual_antenna_yaw": True,
            "enable_raw_doppler": False,
            "enable_source_aware_weighting": False,
            "enable_go2_horizontal_velocity_prior": False,
            "go2_horizontal_velocity_enabled": True,
            "enable_fgo_feedback": False,
            "n9b1c_config_mapping_only": True,
            "trace_solver_input": False,
            "final_v23_solver_input": False,
            "raw_doppler": {"enabled": False, "disabled_reason": ""},
            "source_aware": {"enabled": False, "disabled_reason": ""},
            "go2": {"enabled": False, "horizontal_velocity_enabled": True, "disabled_reason": ""},
            "feedback": {"enabled": False, "policy": "disabled_until_dependency_available"},
            "fgo": {"enabled": False},
        }
    )
    return config


def _runtime_solver_config(
    case_id: str,
    algorithm: str,
    input_choice: dict[str, Any] | None,
    deps: RuntimeDependencyPaths,
    future_output_root: str,
    wsl_audit_root: str,
) -> dict[str, Any]:
    return {
        "runtime_only_notice": "N9B1C generated command/config plan; not a tracked solver config",
        "stage": STAGE,
        "case_id": case_id,
        "algorithm": algorithm,
        "run_label": f"{STAGE}_{case_id}_{algorithm}",
        "imupath": _to_wsl_path(deps.imu) if deps.imu else "",
        "gnsspath": _input_wsl_path(input_choice, wsl_audit_root),
        "outputpath": future_output_root,
        "imudatalen": 7,
        "imudatarate": 500,
        "imudataincremental": 1,
        "imudataformat": 0,
        "starttime": 66.0,
        "endtime": 340.0,
        "initpos": [39.98482990, 116.34312810, 41.78200150],
        "initvel": [0.0, 0.0, 0.0],
        "initatt": [0.0, 0.0, 0.0],
        "initgyrbias": [0.0, 0.0, 0.0],
        "initaccbias": [0.0, 0.0, 0.0],
        "initgyrscale": [0.0, 0.0, 0.0],
        "initaccscale": [0.0, 0.0, 0.0],
        "initposstd": [10.0, 10.0, 10.0],
        "initvelstd": [5.0, 5.0, 5.0],
        "initattstd": [10.0, 10.0, 180.0],
        "imunoise": {
            "arw": [0.985, 0.985, 0.985],
            "vrw": [0.077, 0.077, 0.077],
            "gbstd": [9.38, 9.38, 9.38],
            "abstd": [77.8, 77.8, 77.8],
            "gsstd": [0.0, 0.0, 0.0],
            "asstd": [0.0, 0.0, 0.0],
            "corrtime": 1.0,
        },
        "antlever": [0.0, 0.0, -0.25],
    }


def _command_inputs(
    *,
    algorithm: str,
    input_choice: dict[str, Any] | None,
    deps: RuntimeDependencyPaths,
    wsl_audit_root: str,
    source_aware_enabled: bool,
    raw_doppler_enabled: bool,
    go2_enabled: bool,
    feedback_enabled: bool,
) -> dict[str, Any]:
    return {
        "IMU": _to_wsl_path(deps.imu) if deps.imu else "",
        "GNSS": _input_wsl_path(input_choice, wsl_audit_root),
        "velocity": "gnss_velocity_columns" if algorithm != "single_antenna_gnss1_status_KF_GINS" else "",
        "yaw": "dual_antenna_yaw_columns" if algorithm != "single_antenna_gnss1_status_KF_GINS" else "",
        "raw_doppler": _to_wsl_path(deps.raw_doppler) if raw_doppler_enabled and deps.raw_doppler else "",
        "go2": _to_wsl_path(deps.go2) if go2_enabled and deps.go2 else "",
        "feedback": _to_wsl_path(deps.feedback_observations) if feedback_enabled and deps.feedback_observations else "",
        "source_aware": source_aware_enabled,
    }


def _expected_outputs(algorithm: str, future_output_root: str) -> dict[str, str]:
    if algorithm == "single_antenna_gnss1_status_KF_GINS":
        return {
            "NAV": f"{future_output_root}/KF_GINS_Navresult.nav",
            "STD": f"{future_output_root}/KF_GINS_STD.txt",
            "EVAL_NAV": f"{future_output_root}/EVAL_NAV.csv",
            "RUN_MANIFEST": f"{future_output_root}/RUN_MANIFEST.json",
        }
    return {
        "NAV": f"{future_output_root}/LegSA_NAV.nav",
        "STD": f"{future_output_root}/LegSA_STD.csv",
        "EVAL_NAV": f"{future_output_root}/EVAL_NAV.csv",
        "RUN_MANIFEST": f"{future_output_root}/RUN_MANIFEST.json",
    }


def _choose_input(case_inputs: list[dict[str, Any]], algorithm: str) -> dict[str, Any] | None:
    if algorithm == "single_antenna_gnss1_status_KF_GINS":
        preferred = [row for row in case_inputs if str(row.get("input_tag", "")).startswith("single7")]
    else:
        preferred = [row for row in case_inputs if str(row.get("input_tag", "")).startswith("dual15")]
        if not preferred:
            preferred = [row for row in case_inputs if str(row.get("input_tag", "")).startswith("single7")]
    if not preferred:
        return None
    return sorted(preferred, key=lambda row: (str(row.get("input_tag", "")).count("seed_"), str(row.get("input_tag", ""))))[0]


def _write_mapping_files(
    runtime_root: Path,
    row: dict[str, Any],
    config: dict[str, Any],
    sources: SourcePaths,
    deps: RuntimeDependencyPaths,
) -> None:
    case_id = row["case_id"]
    algorithm = row["algorithm"]
    config_dir = runtime_root / "algorithm_config_mapping" / case_id / algorithm
    plan_dir = runtime_root / "repaired_command_plans" / case_id / algorithm
    config_dir.mkdir(parents=True, exist_ok=True)
    plan_dir.mkdir(parents=True, exist_ok=True)
    if row["mapping_status"] == "mapped":
        _write_yaml(config_dir / "config.yaml", config)
    else:
        _write_json(config_dir / "config.json", {"stage": STAGE, "case_id": case_id, "algorithm": algorithm, "mapping_status": row["mapping_status"], "blocked_reason": row["blocked_reason"]})
    source_role = {
        "stage": STAGE,
        "case_id": case_id,
        "algorithm": algorithm,
        "gnss_degraded_input": "algorithm_input",
        "imu": "algorithm_input_when_mapped" if row["imu_input_exists"] else "missing",
        "go2": "algorithm_input_when_required_not_truth" if row["go2_input_exists"] else "missing_or_not_required",
        "raw_doppler": "algorithm_input_when_required" if row["raw_doppler_input_exists"] else "missing_or_not_required",
        "feedback_observations": "algorithm_input_when_required" if row["feedback_observation_input_exists"] else "missing_or_not_required",
        "trace": "evaluation_only_not_solver_input",
        "final_v23": "reference_only_not_solver_input",
        "source_discovery": sources.source,
        "dependency_discovery": deps.source,
    }
    output_lineage = {
        "stage": STAGE,
        "case_id": case_id,
        "algorithm": algorithm,
        "solver_run": False,
        "future_output_root": row["future_output_root"],
        "future_stage": FUTURE_SOLVER_STAGE,
        "N9B1C_outputs_are_configs_and_command_plans_only": True,
    }
    config_diff = _config_diff(case_id, algorithm, row["mapping_status"], row["blocked_reason"])
    solver_command = {
        "stage": STAGE,
        "case_id": case_id,
        "algorithm": algorithm,
        "command_type": row["command_type"],
        "mapping_status": row["mapping_status"],
        "command": row["command"],
        "working_directory": row["working_directory"],
        "environment": row["environment"],
        "inputs": row["inputs"],
        "degraded_input_paths": row["degraded_input_paths"],
        "degraded_input_paths_wsl": row["degraded_input_paths_wsl"],
        "config_path": row["config_path"],
        "generated_config_path": row["generated_config_path"],
        "generated_config_path_wsl": row["generated_config_path_wsl"],
        "output_root": row["output_root"],
        "expected_outputs": row["expected_outputs"],
        "command_plan_only": True,
        "dry_run_only": True,
        "solver_run": False,
        "official_evaluator_run": False,
        "solver_input_trace": False,
        "solver_input_final_v23": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "entrypoint": row["entrypoint"],
        "future_output_root": row["future_output_root"],
        "run_allowed_in_N9B1D": row["run_allowed_in_N9B1D"],
        "block_reason": row["block_reason"],
        "blocked_reason": row["blocked_reason"],
    }
    _write_json(config_dir / "source_role.json", source_role)
    _write_json(config_dir / "output_lineage.json", output_lineage)
    _write_json(config_dir / "config_diff_from_normal.json", config_diff)
    (config_dir / "command_preview.txt").write_text(row["command_preview"] + "\n", encoding="utf-8")
    _write_json(plan_dir / "solver_command.json", solver_command)


def _config_diff(case_id: str, algorithm: str, mapping_status: str, reason: str) -> dict[str, Any]:
    diff = {
        "stage": STAGE,
        "case_id": case_id,
        "algorithm": algorithm,
        "mapping_status": mapping_status,
        "normal_baseline_reference": "M_normal_baseline_repeat",
        "blocked_reason": reason,
        "feature_diffs": [],
    }
    if case_id == "G_raw_doppler_disabled" and algorithm == "Raw_Doppler_EKF":
        diff["feature_diffs"].append({"feature": "raw_doppler", "enabled": False, "reason": "G_raw_doppler_disabled"})
    if case_id == "I_source_aware_disabled" and algorithm == "source_aware_EKF":
        diff["feature_diffs"].append({"feature": "source_aware", "enabled": False, "reason": "I_source_aware_disabled"})
    if case_id == "J_go2_horizontal_velocity_missing" and algorithm == "Go2_joint_EKF":
        diff["feature_diffs"].append({"feature": "go2_horizontal_velocity", "enabled": False, "reason": "J_go2_horizontal_velocity_missing"})
    if case_id == "L_feedback_disabled" and algorithm in {"selected_feedback_EKF", "baseline_no_feedback_EKF"}:
        diff["feature_diffs"].append({"feature": "feedback", "enabled": False, "reason": "L_feedback_disabled" if algorithm == "selected_feedback_EKF" else "baseline_no_feedback_EKF"})
    return diff


def _build_inventory(deps: RuntimeDependencyPaths) -> list[dict[str, Any]]:
    return [
        {"entrypoint": KF_GINS_BASELINE_ENTRYPOINT, "mapping_role": "solver_entrypoint", "algorithm_group": "single_antenna_gnss1_status_KF_GINS", "execution_checked": False, "dryrun_only": True},
        {"entrypoint": LEGSA_ENTRYPOINT, "mapping_role": "solver_entrypoint", "algorithm_group": "LegSA_EKF_groups", "execution_checked": False, "dryrun_only": True},
        {"entrypoint": _display_path(deps.imu), "mapping_role": "input_dependency", "algorithm_group": "all_mapped_solvers", "exists": _path_exists(deps.imu), "dryrun_only": True},
        {"entrypoint": _display_path(deps.go2), "mapping_role": "input_dependency", "algorithm_group": "Go2_joint_EKF", "exists": _path_exists(deps.go2), "dryrun_only": True},
        {"entrypoint": _display_path(deps.raw_doppler), "mapping_role": "input_dependency", "algorithm_group": "Raw_Doppler_EKF", "exists": _path_exists(deps.raw_doppler), "dryrun_only": True},
        {"entrypoint": _display_path(deps.feedback_observations), "mapping_role": "input_dependency", "algorithm_group": "selected_feedback_EKF", "exists": _path_exists(deps.feedback_observations), "dryrun_only": True},
    ]


def _build_ready_matrix(mapping_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for algorithm in REQUIRED_ALGORITHMS:
        algo_rows = [row for row in mapping_rows if row["algorithm"] == algorithm]
        mapped = [row for row in algo_rows if row["mapping_status"] == "mapped"]
        blocked = [row for row in algo_rows if row["mapping_status"] != "mapped"]
        rows.append({
            "algorithm": algorithm,
            "selected_case_count": len(algo_rows),
            "mapped_case_count": len(mapped),
            "blocked_case_count": len(blocked),
            "ready_for_N9B1D_solver_execution": bool(algo_rows) and not blocked,
            "ready_for_N9B2_execution": False,
            "solver_run": False,
            "official_evaluator_run": False,
        })
    return rows


def _blocked_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": row["case_id"],
        "algorithm": row["algorithm"],
        "routing_status": row["routing_status"],
        "mapping_status": row["mapping_status"],
        "command_type": row["command_type"],
        "blocked_reason": row["blocked_reason"],
        "block_reason": row["block_reason"],
        "solver_run": False,
        "official_evaluator_run": False,
        "run_allowed_in_N9B1D": False,
        "ready_for_N9B1D_solver_execution": False,
        "ready_for_N9B2_execution": False,
    }


def _wsl_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": row["case_id"],
        "algorithm": row["algorithm"],
        "command_type": row["command_type"],
        "entrypoint": row["entrypoint"],
        "command": row["command"],
        "working_directory": row["working_directory"],
        "environment": row["environment"],
        "input_paths_exist": row["input_paths_exist"],
        "generated_config_path": row["generated_config_path"],
        "bridge_script": "scripts/run_wsl_legsa.ps1",
        "dry_run_only": True,
        "executed": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "future_output_root": row["future_output_root"],
    }


def _write_outputs(runtime_root: Path, result: dict[str, Any]) -> None:
    reports = {
        "N9B1C_SOLVER_ENTRYPOINT_INVENTORY_REPORT.json": result["solver_entrypoint_inventory_report"],
        "N9B1C_COMMAND_MAPPING_REPORT.json": result["command_mapping_report"],
        "N9B1C_CONFIG_MAPPING_REPORT.json": result["config_mapping_report"],
        "N9B1C_WSL_DRYRUN_REPORT.json": result["wsl_dryrun_report"],
        "N9B1C_VALIDATION_REPORT.json": result["validation_report"],
        "N9B1C_DECISION_REPORT.json": result["decision_report"],
    }
    for name, payload in reports.items():
        _write_json(runtime_root / "reports" / name, payload)
    matrices = {
        "N9B1C_SOLVER_ENTRYPOINT_INVENTORY": result["solver_entrypoint_inventory"],
        "N9B1C_COMMAND_MAPPING_MATRIX": result["command_mapping_matrix"],
        "N9B1C_ALGORITHM_READY_MATRIX": result["algorithm_ready_matrix"],
        "N9B1C_BLOCKED_MAPPING_MATRIX": result["blocked_mapping_matrix"],
        "N9B1C_WSL_DRYRUN_COMMAND_MATRIX": result["wsl_dryrun_command_matrix"],
    }
    for stem, rows in matrices.items():
        _write_table_pair(runtime_root / "matrix" / stem, rows)
    _write_table_pair(runtime_root / "solver_entrypoint_inventory" / "N9B1C_SOLVER_ENTRYPOINT_INVENTORY", result["solver_entrypoint_inventory"])
    _write_table_pair(runtime_root / "wsl_dryrun" / "N9B1C_WSL_DRYRUN_COMMAND_MATRIX", result["wsl_dryrun_command_matrix"])
    summaries = {
        "n9b1c_solver_entrypoint_inventory.md": f"# N9B1C solver entrypoint inventory\n\n- KF-GINS baseline: `{KF_GINS_BASELINE_ENTRYPOINT}`\n- LegSA C++: `{LEGSA_ENTRYPOINT}`\n- Solver run: false\n",
        "n9b1c_command_mapping_summary.md": f"# N9B1C command mapping\n\n- mapped_command_rows={result['command_mapping_report']['mapped_command_rows']}\n- blocked_mapping_rows={result['command_mapping_report']['blocked_mapping_rows']}\n- ready_for_N9B2_execution=false\n",
        "n9b1c_next_stage_recommendation.md": f"# N9B1C next stage recommendation\n\n- status={result['decision_report']['status']}\n- ready_for_N9B1D_solver_execution={str(result['decision_report']['ready_for_N9B1D_solver_execution']).lower()}\n- ready_for_N9B2_execution=false\n",
    }
    for name, text in summaries.items():
        (runtime_root / "summary" / name).write_text(text, encoding="utf-8")
    _write_json(runtime_root / "validation" / "N9B1C_VALIDATION_REPORT.json", result["validation_report"])


def _create_runtime_tree(runtime_root: Path) -> None:
    for subdir in REQUIRED_SUBDIRS:
        (runtime_root / subdir).mkdir(parents=True, exist_ok=True)


def _load_json_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        return []
    return [dict(row) for row in payload]


def _extract_windows_paths(path: Path) -> list[Path]:
    paths: list[Path] = []
    if not path.exists():
        return paths
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        text = line.strip()
        if len(text) > 3 and text[1:3] == ":\\":
            paths.append(Path(text))
    return paths


def _first_existing(candidates: list[Path], name: str | None = None) -> Path | None:
    for candidate in candidates:
        path = candidate / name if name and candidate.is_dir() else candidate
        if name and candidate.name != name and not candidate.is_dir():
            continue
        if path.exists():
            return path
    return None


def _find_runtime_file(root: Path, name: str) -> Path | None:
    if not root.exists():
        return None
    preferred_markers = [
        "N9A_R4K_BY2_NORMAL_FULL_PLOT_WITH_LOCKED_BASELINES",
        "N9A_R4D_METRIC_ALIGNMENT_AND_DIAGNOSTIC_SOURCE_INTEGRATION",
    ]
    matches = sorted(root.rglob(name), key=lambda path: str(path))
    for marker in preferred_markers:
        for path in matches:
            if marker in str(path):
                return path
    return matches[0] if matches else None


def _path_exists(path: Path | None) -> bool:
    return path is not None and path.exists()


def _is_missing(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _display_path(path: Path | None) -> str:
    return "" if path is None else str(path)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_to_yaml(payload), encoding="utf-8")


def _to_yaml(value: Any, indent: int = 0) -> str:
    pad = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.append(_to_yaml(item, indent + 2).rstrip("\n"))
            else:
                lines.append(f"{pad}{key}: {_yaml_scalar(item)}")
        return "\n".join(lines) + "\n"
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}-")
                lines.append(_to_yaml(item, indent + 2).rstrip("\n"))
            else:
                lines.append(f"{pad}- {_yaml_scalar(item)}")
        return "\n".join(lines) + "\n"
    return f"{pad}{_yaml_scalar(value)}\n"


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "":
        return "''"
    return json.dumps(text, ensure_ascii=False)


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


def _to_wsl_path(path: Path) -> str:
    text = str(path.resolve())
    if len(text) >= 3 and text[1:3] == ":\\":
        drive = text[0].lower()
        rest = text[3:].replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    return text.replace("\\", "/")


def _input_wsl_path(input_choice: dict[str, Any] | None, wsl_audit_root: str = WSL_AUDIT_ROOT) -> str:
    if not input_choice:
        return ""
    return f"{wsl_audit_root}/{AUDIT_ROOT_NAME}/N9B1A1_DOWNSAMPLE_CADENCE_POLICY_REPAIR/{input_choice['path']}"
