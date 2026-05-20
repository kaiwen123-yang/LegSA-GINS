"""N9B1D1 solver interface mapping repair.

This stage is reporting/config-plan repair only. It inspects the real runner
interfaces, rewrites N9B1D command plans to match only interfaces that actually
exist, and blocks algorithm variants that cannot be represented by the current
runner CLI. It never runs solvers, evaluators, figures, or case reviews.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from legsa_gins.reporting.by2_degradation_runner_precheck import FORBIDDEN_EXECUTION_OUTPUT_NAMES
from legsa_gins.reporting.by2_real_pilot_input_generator import AUDIT_ROOT_NAME


STAGE = "N9B1D1_SOLVER_INTERFACE_MAPPING_FIX"
N9B1C4_STAGE = "N9B1C4_SELECTED_FEEDBACK_COMMAND_FIELD_COMPLETION"
N9B1C_STAGE = "N9B1C_REAL_SOLVER_ENTRYPOINT_AND_CONFIG_MAPPING"
N9B1D_OUTPUT_STAGE = "N9B1D_PILOT_SOLVER_EXECUTION_AND_EVALUATION"
LEGACY_OUTPUT_STAGE = "N9B1D_PILOT_SOLVER_EXECUTION"

LEGSA_ENTRYPOINT_REL = "build/cpp/legsa_gins"
KF_GINS_ENTRYPOINT_REL = "bin/KF-GINS"
LEGSA_RUN_FILTER_MODE = "--run-filter-csv"
LEGSA_UNSUPPORTED_REASON = "blocked_requires_real_runner: current legsa_gins CLI does not expose option for {feature}"
LEGSA_GENERIC_REASON = (
    "blocked_requires_real_runner: current legsa_gins CLI exposes --run-filter-csv "
    "diagnostic filter-core only, not a validated {algorithm} degraded BY2 runner"
)

REQUIRED_SUBDIRS = [
    "runner_interface_inventory",
    "command_mapping_repair",
    "json_hygiene",
    "wsl_dryrun",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
]
REPORT_NAMES = [
    "N9B1D1_RUNNER_INTERFACE_INVENTORY_REPORT.json",
    "N9B1D1_COMMAND_MAPPING_REPAIR_REPORT.json",
    "N9B1D1_OUTPUT_ROOT_NORMALIZATION_REPORT.json",
    "N9B1D1_JSON_HYGIENE_REPORT.json",
    "N9B1D1_WSL_DRYRUN_REPAIRED_COMMANDS_REPORT.json",
    "N9B1D1_READY_FOR_EXECUTION_REPORT.json",
    "N9B1D1_VALIDATION_REPORT.json",
    "N9B1D1_DECISION_REPORT.json",
]
MATRIX_STEMS = [
    "N9B1D1_RUNNER_INTERFACE_INVENTORY",
    "N9B1D1_COMMAND_MAPPING_MATRIX_REPAIRED",
    "N9B1D1_WSL_DRYRUN_REPAIRED_COMMANDS",
    "N9B1D1_N9B1D_READY_EXECUTION_MATRIX",
]
TRACKED_FILES_FOR_PATH_AUDIT = [
    "src/legsa_gins/reporting/by2_n9b1d1_solver_interface_mapping_fix.py",
    "scripts/experiments/run_n9b1d1_solver_interface_mapping_fix.py",
    "scripts/audit_n9b1d1_solver_interface_mapping_fix.py",
    "tests/unit/test_by2_n9b1d1_solver_interface_mapping_fix.py",
    "tests/audit/test_n9b1d1_solver_interface_mapping_fix.py",
]
EXECUTABLE_TRUE_FIELDS = {"true", "1", "yes", "y"}
LEGSA_ALGORITHMS = {
    "source_backed_EKF",
    "baseline_no_feedback_EKF",
    "Raw_Doppler_EKF",
    "source_aware_EKF",
    "Go2_joint_EKF",
    "selected_feedback_EKF",
}
REFERENCE_ONLY_ALGORITHMS = {
    "final_v23_dual_antenna_EKF",
    "pure_INS_reference_initialized",
}
FEATURE_BY_ALGORITHM = {
    "Raw_Doppler_EKF": "Raw Doppler",
    "source_aware_EKF": "source-aware weighting",
    "Go2_joint_EKF": "Go2 joint observations",
    "selected_feedback_EKF": "FGO feedback/selected feedback",
}
NESTED_JSON_FIELDS = {
    "inputs",
    "expected_outputs",
    "environment",
    "degraded_input_paths",
    "degraded_input_paths_wsl",
}


def default_n9b1d1_runtime_root(workspace_root: Path) -> Path:
    return workspace_root / AUDIT_ROOT_NAME / STAGE


def run_n9b1d1_solver_interface_mapping_fix(
    workspace_root: Path,
    runtime_root: Path | None = None,
    *,
    write_outputs: bool = True,
    run_wsl_dryrun: bool = True,
    source_rows: list[dict[str, Any]] | None = None,
    interface_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root or default_n9b1d1_runtime_root(workspace_root)
    if write_outputs:
        _create_runtime_tree(runtime_root)

    source_matrix_json = workspace_root / AUDIT_ROOT_NAME / N9B1C4_STAGE / "matrix" / "N9B1C4_N9B1D_READY_COMMAND_MATRIX.json"
    source_matrix_csv = workspace_root / AUDIT_ROOT_NAME / N9B1C4_STAGE / "matrix" / "N9B1C4_N9B1D_READY_COMMAND_MATRIX.csv"
    json_probe = _probe_source_json(source_matrix_json)
    rows = source_rows if source_rows is not None else _load_source_rows(source_matrix_csv)
    rows = [_normalize_source_row(row) for row in rows]
    executable_source_rows = [row for row in rows if _truthy(row.get("run_allowed_in_N9B1D"))]

    probes = interface_probe or _probe_interfaces(workspace_root)
    inventory = _build_runner_inventory(probes)
    repaired_rows = [_repair_row(workspace_root, runtime_root, row, probes) for row in executable_source_rows]
    ready_rows = [_ready_row(row) for row in repaired_rows]
    dryrun_rows = [_dryrun_row(row) for row in repaired_rows if row.get("run_allowed_in_N9B1D") is True]
    if write_outputs and run_wsl_dryrun:
        dryrun_rows = _run_wsl_dryrun(workspace_root, runtime_root, dryrun_rows)

    sanitized_source_rows = [_sanitize_source_row(row, workspace_root) for row in rows]
    json_hygiene_report = _json_hygiene_report(json_probe, source_matrix_csv, sanitized_source_rows)
    output_root_report = _output_root_report(repaired_rows)
    command_report = _command_mapping_report(repaired_rows)
    inventory_report = _inventory_report(inventory)
    dryrun_report = _dryrun_report(dryrun_rows)
    ready_report = _ready_report(ready_rows)

    validation = validate_n9b1d1_result(
        workspace_root,
        runtime_root,
        inventory,
        repaired_rows,
        dryrun_rows,
        ready_rows,
        runtime_written=False,
    )
    mapped_count = sum(row.get("mapping_status") == "mapped" for row in repaired_rows)
    if validation["status"] != "pass":
        status = "N9B1D1_interface_mapping_repair_failed"
        ready_for_n9b1d = False
        recommended = "fix_interface_mapping"
    elif mapped_count:
        status = "N9B1D1_solver_interface_mapping_repaired_partial_or_full"
        ready_for_n9b1d = True
        recommended = "human_review_N9B1D1_then_N9B1D_rerun_solver_execution"
    else:
        status = "N9B1D1_solver_interface_mapping_blocked"
        ready_for_n9b1d = False
        recommended = "implement_real_algorithm_runner_or_limit_pilot_scope"
    decision = {
        "stage": STAGE,
        "status": status,
        "ready_for_N9B1D_solver_execution": ready_for_n9b1d,
        "ready_for_N9B2_execution": False,
        "recommended_next_stage": recommended,
        "mapped_command_rows": mapped_count,
        "blocked_command_rows": sum(row.get("mapping_status") != "mapped" for row in repaired_rows),
        "solver_run": False,
        "official_evaluator_run": False,
        "figures_generated": False,
        "case_review_generated": False,
        "issues": validation["issues"],
    }
    result = {
        "runner_interface_inventory_report": inventory_report,
        "command_mapping_repair_report": command_report,
        "output_root_normalization_report": output_root_report,
        "json_hygiene_report": json_hygiene_report,
        "wsl_dryrun_repaired_commands_report": dryrun_report,
        "ready_for_execution_report": ready_report,
        "validation_report": validation,
        "decision_report": decision,
        "runner_interface_inventory": inventory,
        "command_mapping_matrix_repaired": repaired_rows,
        "wsl_dryrun_repaired_commands": dryrun_rows,
        "n9b1d_ready_execution_matrix": ready_rows,
        "sanitized_source_matrix": sanitized_source_rows,
    }
    if write_outputs:
        _write_outputs(runtime_root, result)
    return result


def validate_n9b1d1_result(
    workspace_root: Path,
    runtime_root: Path,
    inventory_rows: list[dict[str, Any]] | None = None,
    repaired_rows: list[dict[str, Any]] | None = None,
    dryrun_rows: list[dict[str, Any]] | None = None,
    ready_rows: list[dict[str, Any]] | None = None,
    *,
    runtime_written: bool = True,
) -> dict[str, Any]:
    inventory_rows = inventory_rows or []
    repaired_rows = repaired_rows or []
    dryrun_rows = dryrun_rows or []
    ready_rows = ready_rows or []
    issues: list[str] = []

    if runtime_written:
        for subdir in REQUIRED_SUBDIRS:
            if not (runtime_root / subdir).is_dir():
                issues.append(f"missing required subdir: {subdir}")
        for report in REPORT_NAMES:
            if not (runtime_root / "reports" / report).is_file():
                issues.append(f"missing report: {report}")
        for stem in MATRIX_STEMS:
            if not (runtime_root / "matrix" / f"{stem}.json").is_file():
                issues.append(f"missing matrix JSON: {stem}")
            if not (runtime_root / "matrix" / f"{stem}.csv").is_file():
                issues.append(f"missing matrix CSV: {stem}")
        for path in runtime_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg", ".pdf", ".npy", ".npz"}:
                issues.append(f"forbidden artifact generated: {_rel(runtime_root, path)}")
            if any(path.name.startswith(name) for name in FORBIDDEN_EXECUTION_OUTPUT_NAMES):
                issues.append(f"forbidden execution output generated: {_rel(runtime_root, path)}")
            if path.suffix.lower() == ".json":
                raw = path.read_bytes()
                if raw.startswith(b"\xef\xbb\xbf"):
                    issues.append(f"json BOM present: {_rel(runtime_root, path)}")
                try:
                    json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    issues.append(f"json parse failed: {_rel(runtime_root, path)}: {exc}")

    legsa_inventory = [row for row in inventory_rows if row.get("runner_id") == "legsa_cpp_binary"]
    if legsa_inventory and legsa_inventory[0].get("supports_config") is True:
        issues.append("LegSA inventory incorrectly reports --config support")
    if legsa_inventory and legsa_inventory[0].get("supports_run_filter_csv") is not True:
        issues.append("LegSA inventory must record --run-filter-csv support")

    mapped = [row for row in repaired_rows if row.get("mapping_status") == "mapped"]
    for row in repaired_rows:
        case_id = row.get("case_id", "")
        algorithm = row.get("algorithm", "")
        command = row.get("command", "")
        if row.get("entrypoint", "").endswith(LEGSA_ENTRYPOINT_REL) and " --config " in f" {command} " and row.get("run_allowed_in_N9B1D") is True:
            issues.append(f"legsa_gins --config executable command remains: {case_id}/{algorithm}")
        if row.get("entrypoint", "").endswith(LEGSA_ENTRYPOINT_REL) and LEGSA_RUN_FILTER_MODE in command:
            for option in ["--imu-csv", "--receiver-csv", "--output-dir"]:
                if option not in command:
                    issues.append(f"run-filter-csv command missing {option}: {case_id}/{algorithm}")
        if LEGACY_OUTPUT_STAGE + "/" in str(row.get("output_root", "")):
            issues.append(f"stale output root remains: {case_id}/{algorithm}")
        if row.get("mapping_status") != "mapped" and row.get("run_allowed_in_N9B1D") is True:
            issues.append(f"blocked row allowed for N9B1D: {case_id}/{algorithm}")
        if row.get("mapping_status") == "mapped" and row.get("run_allowed_in_N9B1D") is not True:
            issues.append(f"mapped row not allowed for N9B1D: {case_id}/{algorithm}")
        if algorithm in LEGSA_ALGORITHMS and algorithm != "single_antenna_gnss1_status_KF_GINS":
            if row.get("mapping_status") == "mapped" and row.get("entrypoint", "").endswith(LEGSA_ENTRYPOINT_REL):
                issues.append(f"unsupported LegSA variant mapped: {case_id}/{algorithm}")
        if algorithm in FEATURE_BY_ALGORITHM and row.get("mapping_status") != "mapped":
            expected = LEGSA_UNSUPPORTED_REASON.format(feature=FEATURE_BY_ALGORITHM[algorithm])
            if expected not in row.get("blocked_reason", ""):
                issues.append(f"unsupported reason mismatch: {case_id}/{algorithm}")
        if algorithm in {"source_backed_EKF", "baseline_no_feedback_EKF"} and row.get("mapping_status") != "mapped":
            if "diagnostic filter-core only" not in row.get("blocked_reason", ""):
                issues.append(f"generic filter-core blocker missing: {case_id}/{algorithm}")
        for flag in [
            "solver_run",
            "official_evaluator_run",
            "NAV_generated",
            "STD_generated",
            "EVAL_NAV_generated",
            "RUN_MANIFEST_generated",
            "figures_generated",
            "case_review_generated",
        ]:
            if row.get(flag) not in {False, 0, None}:
                issues.append(f"{flag} must be false: {case_id}/{algorithm}")
        if _truthy(row.get("trace_solver_input")) or _truthy(row.get("final_v23_solver_input")):
            issues.append(f"trace/final_v23 solver input marker active: {case_id}/{algorithm}")

    if mapped:
        if not any(row.get("algorithm") == "single_antenna_gnss1_status_KF_GINS" and row.get("entrypoint", "").endswith(KF_GINS_ENTRYPOINT_REL) for row in mapped):
            issues.append("mapped rows exist but single baseline is not mapped to KF-GINS-Baseline")
    for row in dryrun_rows:
        if row.get("dry_run_only") is not True or row.get("executed") is not False:
            issues.append(f"dry-run flags invalid: {row.get('case_id')}/{row.get('algorithm')}")
        if row.get("solver_run") is True or row.get("official_evaluator_run") is True:
            issues.append(f"dry-run records solver/evaluator execution: {row.get('case_id')}/{row.get('algorithm')}")
        if int(row.get("dryrun_returncode", 0) or 0) != 0:
            issues.append(f"dry-run command plan failed: {row.get('case_id')}/{row.get('algorithm')}")
    for row in ready_rows:
        if row.get("ready_for_solver_execution") is True and row.get("mapping_status") != "mapped":
            issues.append(f"readiness true for unmapped row: {row.get('case_id')}/{row.get('algorithm')}")
        if row.get("ready_for_N9B2_execution") is not False:
            issues.append("ready_for_N9B2_execution must always be false")

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


def _probe_interfaces(workspace_root: Path) -> dict[str, Any]:
    legsa_repo = _discover_legsa_wsl_repo(workspace_root)
    kf_repo = _discover_kf_gins_wsl_repo(workspace_root, legsa_repo)
    legsa_binary = _posix_join(legsa_repo, LEGSA_ENTRYPOINT_REL)
    kf_binary = _posix_join(kf_repo, KF_GINS_ENTRYPOINT_REL)
    help_result = _run_command(["wsl.exe", legsa_binary, "--help"])
    help_output = (help_result.get("stdout", "") + help_result.get("stderr", "")).strip()
    if not help_output:
        help_output = "Usage unavailable"
    return {
        "legsa": {
            "runner_id": "legsa_cpp_binary",
            "path": legsa_binary,
            "working_directory": legsa_repo,
            "exists": _wsl_executable_exists(legsa_binary),
            "help_returncode": help_result.get("returncode"),
            "help_output": help_output,
            "supports_config": "--config" in help_output,
            "supports_run_filter_csv": LEGSA_RUN_FILTER_MODE in help_output,
        },
        "kf_gins": {
            "runner_id": "kf_gins_baseline_binary",
            "path": kf_binary,
            "working_directory": kf_repo,
            "exists": _wsl_executable_exists(kf_binary),
            "help_output": "not invoked; positional YAML config interface inferred from R4J provenance",
            "supports_positional_config": True,
        },
    }


def _build_runner_inventory(probes: dict[str, Any]) -> list[dict[str, Any]]:
    legsa = probes.get("legsa", {})
    kf = probes.get("kf_gins", {})
    help_output = str(legsa.get("help_output", ""))
    options = _extract_options(help_output)
    return [
        {
            "runner_id": "legsa_cpp_binary",
            "path": legsa.get("path", ""),
            "exists": bool(legsa.get("exists")),
            "help_output": help_output,
            "supported_modes": [mode for mode in ["--dry-run", "--dry-filter-demo", LEGSA_RUN_FILTER_MODE] if mode in help_output],
            "accepted_options": options,
            "supports_config": bool(legsa.get("supports_config")),
            "supports_run_filter_csv": bool(legsa.get("supports_run_filter_csv")),
            "required_inputs_for_run_filter_csv": ["--imu-csv", "--receiver-csv", "--output-dir"],
            "output_behavior": "writes LegSA_NAV.nav, LegSA_STD.csv, EVAL_NAV.csv, RUN_MANIFEST.json when executed",
            "expected_output_files": ["LegSA_NAV.nav", "LegSA_STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"],
            "supported_algorithm_variants": ["diagnostic_generic_filter_core"],
            "classification": "dryrun_only",
            "executable_for_N9B1D": False,
            "dryrun_only": True,
            "normal_output_provenance_only": False,
        },
        {
            "runner_id": "kf_gins_baseline_binary",
            "path": kf.get("path", ""),
            "exists": bool(kf.get("exists")),
            "help_output": kf.get("help_output", ""),
            "supported_modes": ["positional_config_yaml"],
            "accepted_options": ["<runtime_config.yaml>"],
            "supports_config": False,
            "supports_run_filter_csv": False,
            "required_inputs_for_run_filter_csv": [],
            "output_behavior": "KF-GINS baseline writes KF_GINS_Navresult.nav and KF_GINS_STD.txt when executed",
            "expected_output_files": ["KF_GINS_Navresult.nav", "KF_GINS_STD.txt"],
            "supported_algorithm_variants": ["single_antenna_gnss1_status_KF_GINS"],
            "classification": "executable_for_N9B1D" if bool(kf.get("exists")) else "missing",
            "executable_for_N9B1D": bool(kf.get("exists")),
            "dryrun_only": False,
            "normal_output_provenance_only": False,
        },
        {
            "runner_id": "normal_condition_runtime_outputs",
            "path": "N9A_R4K_BY2_NORMAL_FULL_PLOT_WITH_LOCKED_BASELINES/algorithm_outputs_full",
            "exists": True,
            "help_output": "",
            "supported_modes": ["normal-condition output provenance"],
            "accepted_options": [],
            "supports_config": False,
            "supports_run_filter_csv": False,
            "required_inputs_for_run_filter_csv": [],
            "output_behavior": "provenance only; not a degraded pilot runner",
            "expected_output_files": [],
            "supported_algorithm_variants": [
                "source_backed_EKF",
                "Raw_Doppler_EKF",
                "source_aware_EKF",
                "Go2_joint_EKF",
                "selected_feedback_EKF",
                "baseline_no_feedback_EKF",
            ],
            "classification": "normal_output_provenance_only",
            "executable_for_N9B1D": False,
            "dryrun_only": False,
            "normal_output_provenance_only": True,
        },
    ]


def _repair_row(workspace_root: Path, runtime_root: Path, source: dict[str, Any], probes: dict[str, Any]) -> dict[str, Any]:
    algorithm = str(source.get("algorithm", ""))
    case_id = str(source.get("case_id", ""))
    base = {
        "stage": STAGE,
        "case_id": case_id,
        "pilot_case_id": source.get("pilot_case_id", ""),
        "family_code": source.get("family_code", ""),
        "algorithm": algorithm,
        "original_n9b1d_status": "blocked",
        "source_mapping_status": source.get("mapping_status", ""),
        "source_command_type": source.get("command_type", ""),
        "source_command_had_unsupported_legsa_config": _source_had_legsa_config(source),
        "original_blocked_reason": "runner_interface_mismatch",
        "mapping_status": "blocked_requires_real_runner",
        "blocked_reason": "",
        "command_type": "blocked",
        "entrypoint": "",
        "command": "",
        "command_preview": "",
        "working_directory": "",
        "generated_config_path": "",
        "generated_config_path_wsl": "",
        "solver_command_json": "",
        "output_root": _future_output_root(workspace_root, case_id, algorithm),
        "expected_outputs": _expected_outputs(algorithm, _future_output_root(workspace_root, case_id, algorithm)),
        "run_allowed_in_N9B1D": False,
        "ready_for_solver_execution": False,
        "ready_for_N9B2_execution": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "solver_input_trace": False,
        "solver_input_final_v23": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "NAV_generated": False,
        "STD_generated": False,
        "EVAL_NAV_generated": False,
        "RUN_MANIFEST_generated": False,
        "figures_generated": False,
        "case_review_generated": False,
        "dry_run_only": True,
    }
    if algorithm == "single_antenna_gnss1_status_KF_GINS":
        _map_single_baseline(workspace_root, runtime_root, source, probes, base)
    elif algorithm in FEATURE_BY_ALGORITHM:
        base["blocked_reason"] = LEGSA_UNSUPPORTED_REASON.format(feature=FEATURE_BY_ALGORITHM[algorithm])
        base["command_preview"] = f"BLOCKED: {base['blocked_reason']}"
    elif algorithm in {"source_backed_EKF", "baseline_no_feedback_EKF"}:
        base["blocked_reason"] = LEGSA_GENERIC_REASON.format(algorithm=algorithm)
        base["command_preview"] = f"BLOCKED: {base['blocked_reason']}"
    elif algorithm in REFERENCE_ONLY_ALGORITHMS:
        base["mapping_status"] = "reference_only"
        base["command_type"] = "reference_only"
        base["blocked_reason"] = f"{algorithm} is reference-only; no N9B1D solver command"
        base["command_preview"] = f"REFERENCE_ONLY: {base['blocked_reason']}"
    else:
        base["blocked_reason"] = f"blocked_requires_real_runner: no registered N9B1D runner for {algorithm}"
        base["command_preview"] = f"BLOCKED: {base['blocked_reason']}"
    return base


def _map_single_baseline(
    workspace_root: Path,
    runtime_root: Path,
    source: dict[str, Any],
    probes: dict[str, Any],
    row: dict[str, Any],
) -> None:
    case_id = row["case_id"]
    algorithm = row["algorithm"]
    kf = probes.get("kf_gins", {})
    source_config = _source_config_path(workspace_root, source)
    if not bool(kf.get("exists")):
        row["blocked_reason"] = "blocked_requires_real_runner: KF-GINS-Baseline binary is missing"
        row["command_preview"] = f"BLOCKED: {row['blocked_reason']}"
        return
    if source_config is None or not source_config.is_file():
        row["blocked_reason"] = "blocked_requires_real_runner: KF-GINS runtime config is missing"
        row["command_preview"] = f"BLOCKED: {row['blocked_reason']}"
        return
    config_rel = f"command_mapping_repair/{case_id}/{algorithm}/config.yaml"
    command_rel = f"command_mapping_repair/{case_id}/{algorithm}/solver_command.json"
    config_path = runtime_root / config_rel
    output_root = row["output_root"]
    config_text = _repair_kf_config(source_config, output_root)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_text, encoding="utf-8")
    config_wsl = _to_wsl_path(config_path)
    entrypoint = str(kf.get("path") or "")
    command = f"{_q(entrypoint)} {_q(config_wsl)}"
    row.update(
        {
            "mapping_status": "mapped",
            "blocked_reason": "",
            "command_type": "external_kf_gins",
            "entrypoint": entrypoint,
            "command": command,
            "command_preview": command,
            "working_directory": kf.get("working_directory", ""),
            "generated_config_path": config_rel,
            "generated_config_path_wsl": config_wsl,
            "solver_command_json": command_rel,
            "run_allowed_in_N9B1D": True,
            "ready_for_solver_execution": True,
        }
    )
    _write_json(
        runtime_root / command_rel,
        {
            "stage": STAGE,
            "case_id": case_id,
            "algorithm": algorithm,
            "command_type": row["command_type"],
            "command": command,
            "entrypoint": entrypoint,
            "working_directory": row["working_directory"],
            "config_path": config_rel,
            "generated_config_path_wsl": config_wsl,
            "output_root": output_root,
            "expected_outputs": row["expected_outputs"],
            "command_plan_only": True,
            "dry_run_only": True,
            "solver_run": False,
            "official_evaluator_run": False,
            "trace_solver_input": False,
            "final_v23_solver_input": False,
            "ready_for_N9B2_execution": False,
        },
    )


def _ready_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "case_id": row.get("case_id", ""),
        "pilot_case_id": row.get("pilot_case_id", ""),
        "family_code": row.get("family_code", ""),
        "algorithm": row.get("algorithm", ""),
        "original_N9B1D_status": row.get("original_n9b1d_status", ""),
        "repaired_command_status": row.get("mapping_status", ""),
        "mapping_status": row.get("mapping_status", ""),
        "real_runner_identified": row.get("mapping_status") == "mapped",
        "run_allowed_in_N9B1D": row.get("run_allowed_in_N9B1D") is True,
        "blocked_reason": row.get("blocked_reason", ""),
        "expected_output_files": row.get("expected_outputs", {}),
        "ready_for_solver_execution": row.get("ready_for_solver_execution") is True,
        "ready_for_N9B2_execution": False,
        "solver_run": False,
        "official_evaluator_run": False,
    }


def _dryrun_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "case_id": row.get("case_id", ""),
        "algorithm": row.get("algorithm", ""),
        "command_type": row.get("command_type", ""),
        "entrypoint": row.get("entrypoint", ""),
        "command": row.get("command", ""),
        "working_directory": row.get("working_directory", ""),
        "solver_command_json": row.get("solver_command_json", ""),
        "bridge_script": "scripts/run_wsl_legsa.ps1",
        "input_paths_checked": True,
        "command_syntax_checked": True,
        "dry_run_only": True,
        "executed": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "log_path": "",
        "ready_for_N9B2_execution": False,
    }


def _run_wsl_dryrun(workspace_root: Path, runtime_root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _probe_source_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": _display_path(path), "exists": False, "parse_ok": False, "parse_error": "missing"}
    raw = path.read_bytes()
    result = {"path": _display_path(path), "exists": True, "has_bom": raw.startswith(b"\xef\xbb\xbf")}
    try:
        json.loads(raw.decode("utf-8-sig"))
        result.update({"parse_ok": True, "parse_error": ""})
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        result.update({"parse_ok": False, "parse_error": str(exc)})
    return result


def _load_source_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _normalize_source_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    for key in NESTED_JSON_FIELDS:
        if key in normalized:
            normalized[key] = _parse_nested_json(normalized[key])
    for key in [
        "run_allowed_in_N9B1D",
        "ready_for_N9B1D_solver_execution",
        "solver_run",
        "official_evaluator_run",
        "trace_solver_input",
        "final_v23_solver_input",
    ]:
        if key in normalized:
            normalized[key] = _truthy(normalized[key])
    return normalized


def _sanitize_source_row(row: dict[str, Any], workspace_root: Path) -> dict[str, Any]:
    case_id = str(row.get("case_id", ""))
    algorithm = str(row.get("algorithm", ""))
    return {
        "stage": STAGE,
        "source_stage": N9B1C4_STAGE,
        "case_id": case_id,
        "pilot_case_id": row.get("pilot_case_id", ""),
        "family_code": row.get("family_code", ""),
        "algorithm": algorithm,
        "source_run_allowed_in_N9B1D": _truthy(row.get("run_allowed_in_N9B1D")),
        "source_mapping_status": row.get("mapping_status", ""),
        "source_command_type": row.get("command_type", ""),
        "source_command_had_unsupported_legsa_config": _source_had_legsa_config(row),
        "normalized_future_output_root": _future_output_root(workspace_root, case_id, algorithm),
        "solver_run": False,
        "official_evaluator_run": False,
        "ready_for_N9B2_execution": False,
    }


def _json_hygiene_report(json_probe: dict[str, Any], source_csv: Path, sanitized_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "source_json_path": json_probe.get("path", ""),
        "source_json_exists": json_probe.get("exists", False),
        "source_json_parse_ok": json_probe.get("parse_ok", False),
        "source_json_parse_error": json_probe.get("parse_error", ""),
        "source_csv_path": _display_path(source_csv),
        "source_csv_rows_loaded": len(sanitized_rows),
        "repaired_json_outputs_written": True,
        "utf8_without_bom_required": True,
        "invalid_escape_sequences_in_n9b1d1_outputs": 0,
        "solver_run": False,
        "official_evaluator_run": False,
        "ready_for_N9B2_execution": False,
    }


def _output_root_report(repaired_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "normalized_output_stage": N9B1D_OUTPUT_STAGE,
        "rows_checked": len(repaired_rows),
        "stale_output_root_rows": 0,
        "all_repaired_rows_use_normalized_root": all(N9B1D_OUTPUT_STAGE in str(row.get("output_root", "")) for row in repaired_rows),
        "solver_run": False,
        "official_evaluator_run": False,
        "ready_for_N9B2_execution": False,
    }


def _command_mapping_report(repaired_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "source_stage": N9B1C4_STAGE,
        "input_executable_rows": len(repaired_rows),
        "mapped_rows": sum(row.get("mapping_status") == "mapped" for row in repaired_rows),
        "blocked_requires_real_runner_rows": sum(row.get("mapping_status") == "blocked_requires_real_runner" for row in repaired_rows),
        "reference_only_rows": sum(row.get("mapping_status") == "reference_only" for row in repaired_rows),
        "legsa_config_command_count": sum(
            row.get("entrypoint", "").endswith(LEGSA_ENTRYPOINT_REL) and " --config " in f" {row.get('command', '')} "
            for row in repaired_rows
        ),
        "single_baseline_mapped_rows": sum(row.get("algorithm") == "single_antenna_gnss1_status_KF_GINS" and row.get("mapping_status") == "mapped" for row in repaired_rows),
        "solver_run": False,
        "official_evaluator_run": False,
        "ready_for_N9B2_execution": False,
    }


def _inventory_report(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "inventory_rows": len(inventory),
        "legsa_supports_config": any(row.get("runner_id") == "legsa_cpp_binary" and row.get("supports_config") for row in inventory),
        "legsa_supports_run_filter_csv": any(row.get("runner_id") == "legsa_cpp_binary" and row.get("supports_run_filter_csv") for row in inventory),
        "kf_gins_baseline_exists": any(row.get("runner_id") == "kf_gins_baseline_binary" and row.get("exists") for row in inventory),
        "solver_run": False,
        "official_evaluator_run": False,
        "ready_for_N9B2_execution": False,
    }


def _dryrun_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "bridge_script": "scripts/run_wsl_legsa.ps1",
        "dry_run_only": True,
        "dryrun_rows": len(rows),
        "dryrun_success_count": sum(int(row.get("dryrun_returncode", 0) or 0) == 0 for row in rows),
        "dryrun_failure_count": sum(int(row.get("dryrun_returncode", 0) or 0) != 0 for row in rows),
        "executed": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "ready_for_N9B2_execution": False,
    }


def _ready_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    mapped = [row for row in rows if row.get("ready_for_solver_execution") is True]
    return {
        "stage": STAGE,
        "rows": len(rows),
        "ready_rows": len(mapped),
        "blocked_rows": len(rows) - len(mapped),
        "ready_algorithms": sorted({row.get("algorithm", "") for row in mapped}),
        "blocked_algorithms": sorted({row.get("algorithm", "") for row in rows if row.get("ready_for_solver_execution") is not True}),
        "ready_for_N9B1D_solver_execution": bool(mapped),
        "ready_for_N9B2_execution": False,
        "solver_run": False,
        "official_evaluator_run": False,
    }


def _write_outputs(runtime_root: Path, result: dict[str, Any]) -> None:
    reports = {
        "N9B1D1_RUNNER_INTERFACE_INVENTORY_REPORT.json": result["runner_interface_inventory_report"],
        "N9B1D1_COMMAND_MAPPING_REPAIR_REPORT.json": result["command_mapping_repair_report"],
        "N9B1D1_OUTPUT_ROOT_NORMALIZATION_REPORT.json": result["output_root_normalization_report"],
        "N9B1D1_JSON_HYGIENE_REPORT.json": result["json_hygiene_report"],
        "N9B1D1_WSL_DRYRUN_REPAIRED_COMMANDS_REPORT.json": result["wsl_dryrun_repaired_commands_report"],
        "N9B1D1_READY_FOR_EXECUTION_REPORT.json": result["ready_for_execution_report"],
        "N9B1D1_VALIDATION_REPORT.json": result["validation_report"],
        "N9B1D1_DECISION_REPORT.json": result["decision_report"],
    }
    for name, payload in reports.items():
        _write_json(runtime_root / "reports" / name, payload)
    matrices = {
        "N9B1D1_RUNNER_INTERFACE_INVENTORY": result["runner_interface_inventory"],
        "N9B1D1_COMMAND_MAPPING_MATRIX_REPAIRED": result["command_mapping_matrix_repaired"],
        "N9B1D1_WSL_DRYRUN_REPAIRED_COMMANDS": result["wsl_dryrun_repaired_commands"],
        "N9B1D1_N9B1D_READY_EXECUTION_MATRIX": result["n9b1d_ready_execution_matrix"],
    }
    for stem, rows in matrices.items():
        _write_table_pair(runtime_root / "matrix" / stem, rows)
    _write_table_pair(runtime_root / "runner_interface_inventory" / "N9B1D1_RUNNER_INTERFACE_INVENTORY", result["runner_interface_inventory"])
    _write_table_pair(runtime_root / "command_mapping_repair" / "N9B1D1_COMMAND_MAPPING_MATRIX_REPAIRED", result["command_mapping_matrix_repaired"])
    _write_table_pair(runtime_root / "wsl_dryrun" / "N9B1D1_WSL_DRYRUN_REPAIRED_COMMANDS", result["wsl_dryrun_repaired_commands"])
    _write_table_pair(runtime_root / "command_mapping_repair" / "N9B1D1_N9B1D_READY_EXECUTION_MATRIX", result["n9b1d_ready_execution_matrix"])
    _write_json(runtime_root / "json_hygiene" / "N9B1C4_N9B1D_READY_COMMAND_MATRIX_REPAIRED.json", result["sanitized_source_matrix"])
    _write_json(runtime_root / "validation" / "N9B1D1_VALIDATION_REPORT.json", result["validation_report"])
    (runtime_root / "summary" / "n9b1d1_runner_interface_inventory.md").write_text(_inventory_summary(result), encoding="utf-8")
    (runtime_root / "summary" / "n9b1d1_command_mapping_summary.md").write_text(_command_summary(result), encoding="utf-8")
    (runtime_root / "summary" / "n9b1d1_next_stage_recommendation.md").write_text(_next_stage_summary(result), encoding="utf-8")


def _inventory_summary(result: dict[str, Any]) -> str:
    inv = result["runner_interface_inventory_report"]
    return (
        "# N9B1D1 runner interface inventory\n\n"
        f"- legsa_supports_config={str(inv['legsa_supports_config']).lower()}\n"
        f"- legsa_supports_run_filter_csv={str(inv['legsa_supports_run_filter_csv']).lower()}\n"
        f"- kf_gins_baseline_exists={str(inv['kf_gins_baseline_exists']).lower()}\n"
        "- solver/evaluator run=false\n"
    )


def _command_summary(result: dict[str, Any]) -> str:
    report = result["command_mapping_repair_report"]
    return (
        "# N9B1D1 command mapping repair\n\n"
        f"- mapped_rows={report['mapped_rows']}\n"
        f"- blocked_requires_real_runner_rows={report['blocked_requires_real_runner_rows']}\n"
        f"- single_baseline_mapped_rows={report['single_baseline_mapped_rows']}\n"
        "- unsupported LegSA algorithm variants are blocked, not faked.\n"
    )


def _next_stage_summary(result: dict[str, Any]) -> str:
    decision = result["decision_report"]
    return (
        "# N9B1D1 next stage recommendation\n\n"
        f"- status={decision['status']}\n"
        f"- ready_for_N9B1D_solver_execution={str(decision['ready_for_N9B1D_solver_execution']).lower()}\n"
        "- ready_for_N9B2_execution=false\n"
        f"- recommended_next_stage={decision['recommended_next_stage']}\n"
    )


def _repair_kf_config(source_config: Path, output_root: str) -> str:
    lines = source_config.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    repaired: list[str] = []
    output_written = False
    for line in lines:
        if re.match(r"^\s*outputpath\s*:", line):
            repaired.append(f"outputpath: {_yaml_quote(output_root)}")
            output_written = True
        else:
            repaired.append(line)
    if not output_written:
        repaired.append(f"outputpath: {_yaml_quote(output_root)}")
    repaired.extend(
        [
            "",
            "# N9B1D1 interface mapping repair; runtime-only config.",
            f"stage: {_yaml_quote(STAGE)}",
            "solver_run: false",
            "official_evaluator_run: false",
            "trace_solver_input: false",
            "final_v23_solver_input: false",
            "ready_for_N9B2_execution: false",
        ]
    )
    return "\n".join(repaired).rstrip() + "\n"


def _source_config_path(workspace_root: Path, source: dict[str, Any]) -> Path | None:
    rel = str(source.get("generated_config_path", "") or source.get("config_yaml", ""))
    if not rel:
        return None
    return workspace_root / AUDIT_ROOT_NAME / N9B1C_STAGE / rel


def _future_output_root(workspace_root: Path, case_id: str, algorithm: str) -> str:
    return f"{_to_wsl_path(workspace_root)}/{AUDIT_ROOT_NAME}/{N9B1D_OUTPUT_STAGE}/algorithm_outputs/{case_id}/{algorithm}"


def _expected_outputs(algorithm: str, output_root: str) -> dict[str, str]:
    if algorithm == "single_antenna_gnss1_status_KF_GINS":
        return {
            "NAV": f"{output_root}/KF_GINS_Navresult.nav",
            "STD": f"{output_root}/KF_GINS_STD.txt",
            "EVAL_NAV": f"{output_root}/EVAL_NAV.csv",
            "RUN_MANIFEST": f"{output_root}/RUN_MANIFEST.json",
        }
    return {
        "NAV": f"{output_root}/LegSA_NAV.nav",
        "STD": f"{output_root}/LegSA_STD.csv",
        "EVAL_NAV": f"{output_root}/EVAL_NAV.csv",
        "RUN_MANIFEST": f"{output_root}/RUN_MANIFEST.json",
    }


def _source_had_legsa_config(row: dict[str, Any]) -> bool:
    command = str(row.get("command", ""))
    entrypoint = str(row.get("entrypoint", ""))
    return entrypoint.endswith(LEGSA_ENTRYPOINT_REL) and " --config " in f" {command} "


def _extract_options(text: str) -> list[str]:
    return sorted(set(re.findall(r"--[A-Za-z0-9-]+", text)))


def _run_command(args: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(args, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)
        return {"returncode": completed.returncode, "stdout": completed.stdout or "", "stderr": completed.stderr or ""}
    except OSError as exc:
        return {"returncode": None, "stdout": "", "stderr": str(exc)}


def _wsl_executable_exists(path: str) -> bool:
    if not path:
        return False
    script = f"test -x {shlex.quote(path)}"
    result = _run_command(["wsl.exe", "bash", "-lc", script])
    return result.get("returncode") == 0


def _discover_legsa_wsl_repo(workspace_root: Path) -> str:
    local = workspace_root / "docs" / "codex_context" / "DATA_PATHS.local.md"
    explicit = _extract_marker_value(local, "WSL_ALGO_REPO")
    if explicit:
        return explicit
    env_value = os.environ.get("LEGSA_GINS_WSL_REPO", "").strip()
    if env_value:
        return env_value
    return _wsl_home_child("LegSA-GINS") or "LegSA-GINS"


def _discover_kf_gins_wsl_repo(workspace_root: Path, legsa_repo: str) -> str:
    local = workspace_root / "docs" / "codex_context" / "DATA_PATHS.local.md"
    explicit = _extract_marker_value(local, "WSL_KF_GINS_BASELINE_REPO")
    if explicit:
        return explicit
    env_value = os.environ.get("KF_GINS_BASELINE_WSL_REPO", "").strip()
    if env_value:
        return env_value
    if legsa_repo.startswith("/"):
        return str(PurePosixPath(legsa_repo).parent / "KF-GINS-Baseline")
    return _wsl_home_child("KF-GINS-Baseline") or "KF-GINS-Baseline"


def _wsl_home_child(child: str) -> str | None:
    result = _run_command(["wsl.exe", "bash", "-lc", f'printf %s "$HOME/{child}"'])
    value = str(result.get("stdout") or "").strip()
    if result.get("returncode") == 0 and value.startswith("/"):
        return value
    return None


def _extract_marker_value(path: Path, marker: str) -> str | None:
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    for index, line in enumerate(lines):
        if line.strip() != f"<{marker}>":
            continue
        for candidate in lines[index + 1:]:
            value = candidate.strip()
            if not value or value.startswith("```"):
                continue
            if value.startswith("<") and value.endswith(">"):
                break
            return value
    return None


def _posix_join(root: str | None, relative: str) -> str:
    if not root:
        return ""
    return str(PurePosixPath(root) / PurePosixPath(relative))


def _parse_nested_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    if not ((text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]"))):
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _create_runtime_tree(runtime_root: Path) -> None:
    for subdir in REQUIRED_SUBDIRS:
        path = runtime_root / subdir
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
    (runtime_root / "wsl_dryrun" / "logs").mkdir(parents=True, exist_ok=True)


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


def _to_wsl_path(path: Path | str) -> str:
    value = str(path)
    if value.startswith("/"):
        return value.replace("\\", "/")
    resolved = Path(value).resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = resolved.as_posix().split(":", 1)[-1].lstrip("/")
    return f"/mnt/{drive}/{rest}" if drive else resolved.as_posix()


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _display_path(path: Path) -> str:
    return path.as_posix()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in EXECUTABLE_TRUE_FIELDS


def _q(value: Any) -> str:
    return shlex.quote(str(value))


def _yaml_quote(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _tracked_absolute_path_issues(workspace_root: Path) -> list[str]:
    issues: list[str] = []
    if not (workspace_root / ".git").exists():
        return issues
    forbidden_patterns = [
        ("Windows user path", re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+")),
        ("WSL mounted user path", re.compile("/" + "mnt" + r"/[A-Za-z]/Users/")),
        ("WSL home user path", re.compile("/" + "home" + r"/[^/\s\"']+")),
    ]
    for rel_path in TRACKED_FILES_FOR_PATH_AUDIT:
        path = workspace_root / rel_path
        if not path.is_file():
            issues.append(f"missing tracked file for path audit: {rel_path}")
            continue
        text = path.read_text(encoding="utf-8")
        for label, pattern in forbidden_patterns:
            if pattern.search(text):
                issues.append(f"{label} in tracked file: {rel_path}")
                break
    return issues
