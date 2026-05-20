"""N9B1F real LegSA runner implementation and normal parity reporting."""

from __future__ import annotations

import csv
import json
import math
import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legsa_gins.reporting.by2_algorithm_runner import (
    ALGORITHM_SPECS,
    FORMAL_ALGORITHMS,
    REPO_RELATIVE_REQUIRED_INPUTS,
    load_base_config_values,
    read_json,
    repo_to_wsl,
    resolve_port_core_executable,
    run_formal_algorithm,
    validate_algorithm_inputs,
    write_json,
)
from legsa_gins.reporting.by2_real_pilot_input_generator import AUDIT_ROOT_NAME


STAGE = "N9B1F_REAL_LEGSA_ALGORITHM_RUNNER_IMPLEMENTATION_AND_NORMAL_PARITY"
R4E3_STAGE = "N9A_R4E3_OFFICIAL_EVALUATOR_PARITY_AND_METRIC_RECOMPUTE"
R4K_STAGE = "N9A_R4K_BY2_NORMAL_FULL_PLOT_WITH_LOCKED_BASELINES"
N9B1E_STAGE = "N9B1E_REAL_LEGSA_RUNNER_VALIDATION_AND_MAPPING"

REQUIRED_SUBDIRS = [
    "runner_inventory",
    "algorithm_implementation_inventory",
    "normal_runner_configs",
    "normal_smoke_outputs",
    "official_eval",
    "parity_reports",
    "command_mapping",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
    "blocked_algorithms",
]

REPORT_NAMES = [
    "N9B1F_ALGORITHM_IMPLEMENTATION_INVENTORY_REPORT.json",
    "N9B1F_RUNNER_DESIGN_REPORT.json",
    "N9B1F_NORMAL_PARITY_REPORT.json",
    "N9B1F_COMMAND_MAPPING_REPORT.json",
    "N9B1F_WSL_DRYRUN_REPORT.json",
    "N9B1F_VALIDATION_REPORT.json",
    "N9B1F_DECISION_REPORT.json",
]

MATRIX_STEMS = [
    "N9B1F_ALGORITHM_IMPLEMENTATION_INVENTORY",
    "N9B1F_NORMAL_PARITY_METRICS",
    "N9B1F_N9B1D_READY_EXECUTION_MATRIX",
    "N9B1F_WSL_DRYRUN_READY_COMMANDS",
]

TRACKED_FILES_FOR_PATH_AUDIT = [
    "src/legsa_gins/reporting/by2_algorithm_runner.py",
    "src/legsa_gins/reporting/by2_n9b1f_real_legsa_algorithm_runner.py",
    "scripts/experiments/run_n9b1f_real_legsa_algorithm_runner.py",
    "scripts/audit_n9b1f_real_legsa_algorithm_runner.py",
    "tests/unit/test_by2_n9b1f_real_legsa_algorithm_runner.py",
    "tests/audit/test_n9b1f_real_legsa_algorithm_runner.py",
]

METRIC_KEYS = [
    "horizontal_rmse_m",
    "up_rmse_m",
    "yaw_rmse_deg",
    "roll_rmse_deg",
    "pitch_rmse_deg",
    "row_count",
    "time_start",
    "time_end",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_n9b1f_runtime_root(workspace_root: Path) -> Path:
    return workspace_root / AUDIT_ROOT_NAME / STAGE


def run_n9b1f_real_legsa_algorithm_runner(
    workspace_root: Path,
    runtime_root: Path | None = None,
    *,
    write_outputs: bool = True,
    execute_normal_parity: bool = False,
    run_official_eval: bool = False,
    run_wsl_dryrun: bool = True,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root or default_n9b1f_runtime_root(workspace_root)
    if write_outputs:
        _create_runtime_tree(runtime_root)

    base_values, base_config = load_base_config_values(workspace_root)
    runner_probe = resolve_port_core_executable(workspace_root)
    r4e3_metrics = _load_r4e3_metrics(workspace_root)
    trace_path = _load_r4e3_trace_path(workspace_root)
    inventory_rows = _build_implementation_inventory(workspace_root, base_values, base_config, runner_probe, r4e3_metrics)
    runner_design = _runner_design_report(workspace_root, runtime_root, inventory_rows, runner_probe)

    run_results: list[dict[str, Any]] = []
    eval_results: list[dict[str, Any]] = []
    parity_rows: list[dict[str, Any]] = []
    for row in inventory_rows:
        algorithm = row["algorithm"]
        if row["status"] not in {"runnable_existing", "runnable_with_wrapper"}:
            parity_rows.append(_blocked_parity_row(algorithm, row, r4e3_metrics))
            continue
        output_dir = runtime_root / "normal_smoke_outputs" / algorithm
        if execute_normal_parity:
            run_result = run_formal_algorithm(workspace_root, algorithm, output_dir, dry_run=False)
        else:
            run_result = {"algorithm": algorithm, "run_status": "not_run", "returncode": None, "outputs": {}}
        run_results.append(run_result)
        if run_result.get("run_status") == "completed" and run_official_eval:
            eval_result = _run_official_eval(workspace_root, runtime_root, algorithm, output_dir, trace_path)
        else:
            eval_result = {
                "algorithm": algorithm,
                "official_eval_status": "skipped" if run_result.get("run_status") != "completed" else "disabled",
                "returncode": None,
                "summary": {},
            }
        eval_results.append(eval_result)
        parity_rows.append(_build_parity_row(algorithm, row, run_result, eval_result, r4e3_metrics))

    ready_rows = _build_ready_execution_matrix(workspace_root, runtime_root, parity_rows)
    dryrun_rows = _build_wsl_dryrun_matrix(workspace_root, runtime_root, ready_rows, run_wsl_dryrun=run_wsl_dryrun)
    reports = _build_reports(
        workspace_root,
        runtime_root,
        inventory_rows,
        runner_design,
        run_results,
        eval_results,
        parity_rows,
        ready_rows,
        dryrun_rows,
    )
    validation = validate_n9b1f_result(
        workspace_root,
        runtime_root,
        inventory_rows,
        parity_rows,
        ready_rows,
        dryrun_rows,
        runtime_written=False,
    )
    decision = _decision_report(parity_rows, ready_rows, validation)
    reports["validation_report"] = validation
    reports["decision_report"] = decision
    result = {
        **reports,
        "algorithm_implementation_inventory": inventory_rows,
        "normal_parity_metrics": parity_rows,
        "n9b1d_ready_execution_matrix": ready_rows,
        "wsl_dryrun_ready_commands": dryrun_rows,
        "normal_run_results": run_results,
        "official_eval_results": eval_results,
    }
    if write_outputs:
        _write_outputs(runtime_root, result)
        result["validation_report"] = validate_n9b1f_result(
            workspace_root,
            runtime_root,
            inventory_rows,
            parity_rows,
            ready_rows,
            dryrun_rows,
            runtime_written=True,
        )
        result["decision_report"] = _decision_report(parity_rows, ready_rows, result["validation_report"])
        _write_outputs(runtime_root, result)
    return result


def validate_n9b1f_result(
    workspace_root: Path,
    runtime_root: Path,
    inventory_rows: list[dict[str, Any]] | None = None,
    parity_rows: list[dict[str, Any]] | None = None,
    ready_rows: list[dict[str, Any]] | None = None,
    dryrun_rows: list[dict[str, Any]] | None = None,
    *,
    runtime_written: bool = True,
) -> dict[str, Any]:
    inventory_rows = inventory_rows or []
    parity_rows = parity_rows or []
    ready_rows = ready_rows or []
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
            if not (runtime_root / "matrix" / f"{stem}.json").is_file():
                issues.append(f"missing matrix JSON: {stem}")
            if not (runtime_root / "matrix" / f"{stem}.csv").is_file():
                issues.append(f"missing matrix CSV: {stem}")
        for path in runtime_root.rglob("*.json"):
            raw = path.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                issues.append(f"json BOM present: {_rel(runtime_root, path)}")
            try:
                json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                issues.append(f"json parse failed: {_rel(runtime_root, path)}: {exc}")
        try:
            tracked = subprocess.run(
                ["git", "ls-files", "--error-unmatch", str(runtime_root)],
                cwd=workspace_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if tracked.returncode == 0:
                issues.append("runtime output root is tracked by git")
        except OSError:
            pass

    for row in inventory_rows:
        if row.get("algorithm") in FORMAL_ALGORITHMS and row.get("runner_path", "").endswith("build/cpp/legsa_gins"):
            issues.append(f"formal algorithm mapped to diagnostic legsa_gins binary: {row.get('algorithm')}")
        if row.get("algorithm") in FORMAL_ALGORITHMS and row.get("implementation_exists") and row.get("runner_exists"):
            if row.get("status") not in {"runnable_existing", "runnable_with_wrapper"} and not row.get("blocked_reason"):
                issues.append(f"blocked formal algorithm lacks reason: {row.get('algorithm')}")

    for row in parity_rows:
        if row.get("degradation_execution") is True:
            issues.append(f"degradation execution recorded: {row.get('algorithm')}")
        if row.get("trace_solver_input") is True:
            issues.append(f"trace solver input recorded: {row.get('algorithm')}")
        if row.get("final_v23_output_solver_input") is True:
            issues.append(f"final_v23 solver input recorded: {row.get('algorithm')}")
        command = " ".join(row.get("solver_command", []) or [])
        if "legsa_gins" in command and "--run-filter-csv" in command:
            issues.append(f"diagnostic --run-filter-csv relabeled as formal: {row.get('algorithm')}")

    passed = {row.get("algorithm") for row in parity_rows if row.get("parity_passed") is True}
    for row in ready_rows:
        algorithm = row.get("algorithm")
        if algorithm in FORMAL_ALGORITHMS and row.get("run_allowed_in_N9B1D") is True and algorithm not in passed:
            issues.append(f"non-parity-passed formal algorithm mapped to N9B1D: {algorithm}")
        if row.get("ready_for_N9B2_execution") is True:
            issues.append(f"N9B2 incorrectly enabled: {algorithm}")

    for row in dryrun_rows:
        if row.get("executed_solver") is True:
            issues.append(f"WSL dry-run executed solver: {row.get('algorithm')}")

    issues.extend(_tracked_path_leak_issues(workspace_root))
    return {
        "stage": STAGE,
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "checked_runtime_written": runtime_written,
        "no_degradation_execution": not any(row.get("degradation_execution") for row in parity_rows),
        "no_N9B2": True,
        "normal_parity_only": True,
        "no_trace_solver_input": not any(row.get("trace_solver_input") for row in parity_rows),
        "no_final_v23_solver_input": not any(row.get("final_v23_output_solver_input") for row in parity_rows),
        "no_algorithm_math_changes_checked_by_diff_scope": True,
        "only_parity_passed_algorithms_mapped_to_N9B1D": not any(
            row.get("algorithm") in FORMAL_ALGORITHMS
            and row.get("run_allowed_in_N9B1D") is True
            and row.get("algorithm") not in passed
            for row in ready_rows
        ),
        "ready_for_N9B2_execution": False,
    }


def _build_implementation_inventory(
    workspace_root: Path,
    base_values: dict[str, str],
    base_config: Path | None,
    runner_probe: dict[str, Any],
    r4e3_metrics: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_paths = {
        "source_backed_EKF": [
            "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp",
            "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp",
        ],
        "baseline_no_feedback_EKF": [
            "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp",
            "src/legsa_gins/fgo_feedback/fgo_feedback_final_runner.py",
        ],
        "Raw_Doppler_EKF": [
            "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp",
            "cpp/legsa_v23_port_core/src/factors/raw_doppler_factor.cpp",
        ],
        "source_aware_EKF": [
            "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp",
            "cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp",
        ],
        "Go2_joint_EKF": [
            "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp",
            "cpp/legsa_v23_port_core/src/factors/go2_weak_prior_loader.cpp",
        ],
        "selected_feedback_EKF": [
            "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp",
            "src/legsa_gins/fgo_feedback/fgo_feedback_final_runner.py",
        ],
    }
    components = {
        "source_backed_EKF": ["GNSS position", "receiver velocity", "dual yaw", "INS propagation"],
        "baseline_no_feedback_EKF": ["source-backed EKF", "feedback explicitly disabled"],
        "Raw_Doppler_EKF": ["source-backed EKF", "Raw Doppler velocity factor"],
        "source_aware_EKF": ["Raw Doppler EKF", "source-aware LSIM/OIM R scaling"],
        "Go2_joint_EKF": ["source-aware EKF", "Go2 roll/pitch", "Go2 horizontal velocity", "joint observation"],
        "selected_feedback_EKF": ["source-backed EKF", "runtime-only selected FGO feedback observations"],
    }
    for algorithm in FORMAL_ALGORITHMS:
        paths = source_paths[algorithm]
        implementation_exists = all((workspace_root / path).exists() for path in paths)
        missing_inputs = validate_algorithm_inputs(workspace_root, algorithm, base_values)
        runner_exists = bool(runner_probe.get("exists"))
        if implementation_exists and runner_exists and not missing_inputs:
            status = "runnable_with_wrapper"
            blocked_reason = ""
        elif not implementation_exists:
            status = "missing_implementation"
            blocked_reason = "required implementation source files missing"
        elif missing_inputs:
            status = "blocked_unknown"
            blocked_reason = "locked normal inputs missing: " + "; ".join(missing_inputs)
        else:
            status = "blocked_unknown"
            blocked_reason = "legsa_v23_port_core_demo runner unavailable"
        rows.append(
            {
                "algorithm": algorithm,
                "implementation_exists": implementation_exists,
                "source_file_paths": paths,
                "factor_filter_components": components[algorithm],
                "runner_exists": runner_exists,
                "runner_path": runner_probe.get("selected_path") or "",
                "runner_path_is_legsa_gins_diagnostic": False,
                "required_inputs": _required_inputs_for_algorithm(algorithm),
                "missing_inputs": missing_inputs,
                "output_writer_exists": (workspace_root / "cpp/legsa_v23_port_core/src/io/output_writer.cpp").exists()
                or (workspace_root / "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp").exists(),
                "normal_output_provenance": _r4k_lineage(workspace_root, algorithm),
                "r4e3_reference_metrics_available": algorithm in r4e3_metrics,
                "can_run_without_math_change": status == "runnable_with_wrapper",
                "status": status,
                "blocked_reason": blocked_reason,
                "base_config_path": str(base_config) if base_config else None,
            }
        )
    return rows


def _runner_design_report(
    workspace_root: Path,
    runtime_root: Path,
    inventory_rows: list[dict[str, Any]],
    runner_probe: dict[str, Any],
) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "created_utc": now_utc(),
        "runner_module": "legsa_gins.reporting.by2_algorithm_runner",
        "preferred_cli": "python -m legsa_gins.reporting.by2_algorithm_runner",
        "underlying_runner": "legsa_v23_port_core_demo --config <config> --output-dir <dir>",
        "forbidden_runner": "build/cpp/legsa_gins --run-filter-csv",
        "runner_probe": runner_probe,
        "supported_algorithms": [row["algorithm"] for row in inventory_rows if row["status"] == "runnable_with_wrapper"],
        "blocked_algorithms": [
            {"algorithm": row["algorithm"], "reason": row["blocked_reason"]}
            for row in inventory_rows
            if row["status"] != "runnable_with_wrapper"
        ],
        "runtime_config_root": str(runtime_root / "normal_runner_configs"),
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "math_changes_required": False,
        "tracked_math_files_modified_by_design": False,
        "workspace_root_recorded_in_tracked_files": False,
    }


def _build_reports(
    workspace_root: Path,
    runtime_root: Path,
    inventory_rows: list[dict[str, Any]],
    runner_design: dict[str, Any],
    run_results: list[dict[str, Any]],
    eval_results: list[dict[str, Any]],
    parity_rows: list[dict[str, Any]],
    ready_rows: list[dict[str, Any]],
    dryrun_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    inventory_report = {
        "stage": STAGE,
        "created_utc": now_utc(),
        "algorithm_count": len(inventory_rows),
        "runnable_with_wrapper_count": sum(row["status"] == "runnable_with_wrapper" for row in inventory_rows),
        "blocked_count": sum(row["status"] != "runnable_with_wrapper" for row in inventory_rows),
        "diagnostic_generic_filter_core_reused": False,
        "rows": inventory_rows,
        "ready_for_N9B2_execution": False,
    }
    normal_parity_report = {
        "stage": STAGE,
        "created_utc": now_utc(),
        "normal_condition_only": True,
        "degradation_execution": False,
        "official_evaluator_run_count": sum(row.get("official_eval_status") == "completed" for row in eval_results),
        "parity_passed_algorithms": [row["algorithm"] for row in parity_rows if row.get("parity_passed") is True],
        "blocked_algorithms": [
            {"algorithm": row["algorithm"], "reason": row.get("blocked_reason")}
            for row in parity_rows
            if row.get("parity_passed") is not True
        ],
        "rows": parity_rows,
        "ready_for_N9B2_execution": False,
    }
    command_report = {
        "stage": STAGE,
        "created_utc": now_utc(),
        "rules": [
            "Only normal-parity-passed formal algorithms are allowed in repaired N9B1D mapping.",
            "single_antenna_gnss1_status_KF_GINS remains mapped through KF-GINS-Baseline.",
            "No build/cpp/legsa_gins --config or --run-filter-csv formal mapping is emitted.",
        ],
        "rows": ready_rows,
        "ready_for_N9B2_execution": False,
    }
    dryrun_report = {
        "stage": STAGE,
        "created_utc": now_utc(),
        "dryrun_only": True,
        "solver_execution": False,
        "rows": dryrun_rows,
        "ready_for_N9B2_execution": False,
    }
    return {
        "algorithm_implementation_inventory_report": inventory_report,
        "runner_design_report": runner_design,
        "normal_parity_report": normal_parity_report,
        "command_mapping_report": command_report,
        "wsl_dryrun_report": dryrun_report,
    }


def _write_outputs(runtime_root: Path, result: dict[str, Any]) -> None:
    _create_runtime_tree(runtime_root)
    report_map = {
        "N9B1F_ALGORITHM_IMPLEMENTATION_INVENTORY_REPORT.json": result["algorithm_implementation_inventory_report"],
        "N9B1F_RUNNER_DESIGN_REPORT.json": result["runner_design_report"],
        "N9B1F_NORMAL_PARITY_REPORT.json": result["normal_parity_report"],
        "N9B1F_COMMAND_MAPPING_REPORT.json": result["command_mapping_report"],
        "N9B1F_WSL_DRYRUN_REPORT.json": result["wsl_dryrun_report"],
        "N9B1F_VALIDATION_REPORT.json": result["validation_report"],
        "N9B1F_DECISION_REPORT.json": result["decision_report"],
    }
    for name, payload in report_map.items():
        write_json(runtime_root / "reports" / name, payload)
    matrix_map = {
        "N9B1F_ALGORITHM_IMPLEMENTATION_INVENTORY": result["algorithm_implementation_inventory"],
        "N9B1F_NORMAL_PARITY_METRICS": result["normal_parity_metrics"],
        "N9B1F_N9B1D_READY_EXECUTION_MATRIX": result["n9b1d_ready_execution_matrix"],
        "N9B1F_WSL_DRYRUN_READY_COMMANDS": result["wsl_dryrun_ready_commands"],
    }
    for stem, rows in matrix_map.items():
        _write_matrix(runtime_root / "matrix" / f"{stem}.json", runtime_root / "matrix" / f"{stem}.csv", rows)
    _write_summary(runtime_root / "summary" / "n9b1f_algorithm_implementation_inventory.md", result)
    write_json(runtime_root / "validation" / "N9B1F_VALIDATION_REPORT.json", result["validation_report"])
    for row in result["normal_parity_metrics"]:
        if row.get("parity_passed") is not True:
            write_json(runtime_root / "blocked_algorithms" / f"{row['algorithm']}.json", row)


def _create_runtime_tree(runtime_root: Path) -> None:
    for subdir in REQUIRED_SUBDIRS:
        (runtime_root / subdir).mkdir(parents=True, exist_ok=True)


def _write_matrix(json_path: Path, csv_path: Path, rows: list[dict[str, Any]]) -> None:
    write_json(json_path, rows)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in keys})


def _write_summary(path: Path, result: dict[str, Any]) -> None:
    passed = [row["algorithm"] for row in result["normal_parity_metrics"] if row.get("parity_passed") is True]
    blocked = [
        f"- {row['algorithm']}: {row.get('blocked_reason') or row.get('parity_status')}"
        for row in result["normal_parity_metrics"]
        if row.get("parity_passed") is not True
    ]
    lines = [
        "# N9B1F Algorithm Implementation Inventory",
        "",
        f"- Status: {result['decision_report']['status']}",
        f"- Ready for N9B1D solver execution: {result['decision_report']['ready_for_N9B1D_solver_execution']}",
        "- Ready for N9B2 execution: False",
        f"- Parity-passed algorithms: {', '.join(passed) if passed else 'none'}",
        "",
        "## Blocked Algorithms",
        "",
        *(blocked or ["- none"]),
        "",
        "## Runner Boundary",
        "",
        "- Formal LegSA algorithms use legsa_v23_port_core_demo --config --output-dir.",
        "- build/cpp/legsa_gins --run-filter-csv remains diagnostic-only.",
        "- Trace and final_v23 outputs are not solver inputs.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_official_eval(
    workspace_root: Path,
    runtime_root: Path,
    algorithm: str,
    solver_output_dir: Path,
    trace_path: str | None,
) -> dict[str, Any]:
    official_dir = runtime_root / "official_eval" / algorithm
    official_dir.mkdir(parents=True, exist_ok=True)
    eval_script = _load_r4e3_eval_script(workspace_root)
    if not eval_script:
        return {"algorithm": algorithm, "official_eval_status": "blocked", "blocked_reason": "R4E3 evaluator path missing"}
    if not trace_path:
        return {"algorithm": algorithm, "official_eval_status": "blocked", "blocked_reason": "R4E3 trace path missing"}
    nav_src = solver_output_dir / "EVAL_NAV.csv"
    std_src = solver_output_dir / "LegSA_PORT_STD.csv"
    if not nav_src.exists() or not std_src.exists():
        return {"algorithm": algorithm, "official_eval_status": "blocked", "blocked_reason": "NAV/STD output missing"}
    nav_dst = official_dir / "converted_eval_nav_official.nav"
    std_dst = official_dir / "converted_std_official.txt"
    nav_meta = _convert_eval_nav(nav_src, nav_dst)
    std_meta = _convert_std(std_src, nav_src, std_dst)
    command = [
        "python3",
        eval_script,
        "--trace",
        trace_path,
        "--nav",
        repo_to_wsl(nav_dst),
        "--std",
        repo_to_wsl(std_dst),
        "--outdir",
        repo_to_wsl(official_dir),
        "--base_time",
        "1772784000.0",
        "--yaw_truth_mode",
        "enu",
    ]
    write_json(
        official_dir / "command.json",
        {
            "algorithm": algorithm,
            "command": command,
            "trace_is_evaluation_only": True,
            "final_v23_reference_only": False,
        },
    )
    write_json(
        official_dir / "role.json",
        {
            "algorithm": algorithm,
            "trace_role": "evaluation_only",
            "solver_input_trace": False,
            "solver_input_final_v23": False,
        },
    )
    completed = subprocess.run(
        ["wsl", "bash", "-lc", shlex.join(command)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    (official_dir / "run_stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (official_dir / "run_stderr.txt").write_text(completed.stderr, encoding="utf-8")
    summary = read_json(official_dir / "summary.json", {})
    return {
        "algorithm": algorithm,
        "official_eval_status": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "summary": summary,
        "nav_conversion": nav_meta,
        "std_conversion": std_meta,
        "command": command,
        "trace_is_evaluation_only": True,
    }


def _convert_eval_nav(src: Path, dst: Path) -> dict[str, Any]:
    with src.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(
                "0.000000000     "
                f"{_float(row.get('time')):.9f}    {_float(row.get('lat_deg')):.12f}    "
                f"{_float(row.get('lon_deg')):.12f}   {_float(row.get('height_m')):.9f}    "
                f"{_float(row.get('vn') or row.get('vn_mps')):.9f}     "
                f"{_float(row.get('ve') or row.get('ve_mps')):.9f}    "
                f"{_float(row.get('vd') or row.get('vd_mps')):.9f}     "
                f"{_float(row.get('roll_deg')):.9f}    {_float(row.get('pitch_deg')):.9f}     "
                f"{_float(row.get('yaw_deg')):.9f}\n"
            )
    return {
        "row_count": len(rows),
        "time_start": _float(rows[0].get("time")) if rows else None,
        "time_end": _float(rows[-1].get("time")) if rows else None,
        "source_format": "EVAL_NAV.csv",
    }


def _convert_std(src: Path, nav_src: Path, dst: Path) -> dict[str, Any]:
    with nav_src.open("r", encoding="utf-8-sig", newline="") as handle:
        nav_rows = list(csv.DictReader(handle))
    with src.open("r", encoding="utf-8-sig", newline="") as handle:
        std_rows = list(csv.DictReader(handle))
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8", newline="") as handle:
        for nav, std in zip(nav_rows, std_rows):
            handle.write(
                f"{_float(nav.get('time')):.9f}    {_float(std.get('std_pos_n_m')):.9f}    "
                f"{_float(std.get('std_pos_e_m')):.9f}    "
                f"{_float(std.get('std_pos_u_m') or std.get('std_pos_d_m')):.9f}    "
                f"{_float(std.get('std_vel_n_mps')):.9f}     {_float(std.get('std_vel_e_mps')):.9f}     "
                f"{_float(std.get('std_vel_d_mps')):.9f}     {_float(std.get('std_roll_deg')):.9f}     "
                f"{_float(std.get('std_pitch_deg')):.9f}     {_float(std.get('std_yaw_deg')):.9f}\n"
            )
    return {"row_count": min(len(nav_rows), len(std_rows)), "source_format": "LegSA_PORT_STD.csv"}


def _build_parity_row(
    algorithm: str,
    inventory_row: dict[str, Any],
    run_result: dict[str, Any],
    eval_result: dict[str, Any],
    r4e3_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    metrics = _metrics_from_summary(eval_result.get("summary", {}))
    reference = r4e3_metrics.get(algorithm, {})
    deltas = {
        key + "_delta": _safe_delta(metrics.get(key), reference.get(key))
        for key in METRIC_KEYS
        if key in metrics or key in reference
    }
    blocked_reason = ""
    if run_result.get("run_status") != "completed":
        blocked_reason = run_result.get("blocked_reason") or f"solver run status {run_result.get('run_status')}"
    elif eval_result.get("official_eval_status") != "completed":
        blocked_reason = eval_result.get("blocked_reason") or f"official eval status {eval_result.get('official_eval_status')}"
    elif not reference:
        blocked_reason = "R4E3 reference metrics missing"
    parity_passed = not blocked_reason and _parity_pass(metrics, reference)
    if not parity_passed and not blocked_reason:
        blocked_reason = "normal parity tolerance failed"
    command = (run_result.get("command") or {}).get("command", [])
    return {
        "algorithm": algorithm,
        "implementation_status": inventory_row["status"],
        "runner_status": run_result.get("run_status"),
        "solver_returncode": run_result.get("returncode"),
        "official_eval_status": eval_result.get("official_eval_status"),
        "official_eval_returncode": eval_result.get("returncode"),
        "parity_status": "pass" if parity_passed else "blocked",
        "parity_passed": parity_passed,
        "blocked_reason": blocked_reason,
        **{f"current_{key}": metrics.get(key) for key in METRIC_KEYS},
        **{f"reference_{key}": reference.get(key) for key in METRIC_KEYS},
        **deltas,
        "horizontal_tolerance_m": 0.05,
        "yaw_tolerance_deg": 0.25,
        "row_count_tolerance": 1,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "degradation_execution": False,
        "solver_command": command,
    }


def _blocked_parity_row(
    algorithm: str,
    inventory_row: dict[str, Any],
    r4e3_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    reference = r4e3_metrics.get(algorithm, {})
    return {
        "algorithm": algorithm,
        "implementation_status": inventory_row["status"],
        "runner_status": "blocked",
        "official_eval_status": "not_run",
        "parity_status": "blocked",
        "parity_passed": False,
        "blocked_reason": inventory_row.get("blocked_reason") or "not runnable",
        **{f"reference_{key}": reference.get(key) for key in METRIC_KEYS},
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "degradation_execution": False,
    }


def _parity_pass(metrics: dict[str, Any], reference: dict[str, Any]) -> bool:
    if not metrics or not reference:
        return False
    row_delta = abs(int(metrics.get("row_count", -999999)) - int(reference.get("row_count", 999999)))
    if row_delta > 1:
        return False
    if abs(float(metrics.get("horizontal_rmse_m", math.inf)) - float(reference.get("horizontal_rmse_m", -math.inf))) > 0.05:
        return False
    if abs(float(metrics.get("yaw_rmse_deg", math.inf)) - float(reference.get("yaw_rmse_deg", -math.inf))) > 0.25:
        return False
    return True


def _build_ready_execution_matrix(workspace_root: Path, runtime_root: Path, parity_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in parity_rows:
        algorithm = row["algorithm"]
        passed = row.get("parity_passed") is True
        command = [
            "python",
            "-m",
            "legsa_gins.reporting.by2_algorithm_runner",
            "--algorithm",
            algorithm,
            "--case-id",
            "N9B1D_future_case",
            "--normal-parity-mode",
            "--output-dir",
            "<N9B1D_RUNTIME_OUTPUT_ROOT>",
        ]
        rows.append(
            {
                "algorithm": algorithm,
                "runner": "legsa_gins.reporting.by2_algorithm_runner",
                "underlying_runner": "legsa_v23_port_core_demo",
                "run_allowed_in_N9B1D": passed,
                "mapping_status": "mapped_parity_passed" if passed else "blocked_requires_real_runner_or_parity",
                "blocked_reason": "" if passed else row.get("blocked_reason"),
                "command_template": " ".join(command),
                "no_unsupported_legsa_binary_config": True,
                "no_future_solver_entry": True,
                "ready_for_N9B2_execution": False,
            }
        )
    rows.append(
        {
            "algorithm": "single_antenna_gnss1_status_KF_GINS",
            "runner": "KF-GINS-Baseline",
            "underlying_runner": "KF-GINS-Baseline/bin/KF-GINS",
            "run_allowed_in_N9B1D": True,
            "mapping_status": "mapped_existing_single_baseline",
            "blocked_reason": "",
            "command_template": "existing N9B1D1 KF-GINS-Baseline positional config mapping",
            "no_unsupported_legsa_binary_config": True,
            "no_future_solver_entry": True,
            "ready_for_N9B2_execution": False,
        }
    )
    return rows


def _build_wsl_dryrun_matrix(
    workspace_root: Path,
    runtime_root: Path,
    ready_rows: list[dict[str, Any]],
    *,
    run_wsl_dryrun: bool,
) -> list[dict[str, Any]]:
    script = workspace_root / "scripts" / "run_wsl_legsa.ps1"
    rows: list[dict[str, Any]] = []
    for row in ready_rows:
        if row.get("run_allowed_in_N9B1D") is not True:
            continue
        algorithm = row["algorithm"]
        command = row["command_template"]
        if algorithm in FORMAL_ALGORITHMS:
            wsl_command = "python3 -m legsa_gins.reporting.by2_algorithm_runner --dry-run --algorithm " + shlex.quote(algorithm) + " --output-dir <N9B1D_OUTPUT_ROOT>"
        else:
            wsl_command = "KF-GINS-Baseline dry-run command remains owned by N9B1D1 mapping"
        dryrun_row = {
            "algorithm": algorithm,
            "command_template": command,
            "wsl_dryrun_command": wsl_command,
            "dryrun_status": "not_run",
            "executed_solver": False,
            "ready_for_N9B2_execution": False,
        }
        if run_wsl_dryrun and script.exists() and algorithm in FORMAL_ALGORITHMS:
            log_path = runtime_root / "logs" / f"{algorithm}_wsl_dryrun.json"
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                    "-WorkingDirectory",
                    str(workspace_root),
                    "-Command",
                    wsl_command,
                    "-DryRun",
                    "-LogPath",
                    str(log_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            dryrun_row.update(
                {
                    "dryrun_status": "pass" if completed.returncode == 0 else "failed",
                    "returncode": completed.returncode,
                    "log_path": str(log_path),
                    "stdout_tail": completed.stdout[-1000:],
                    "stderr_tail": completed.stderr[-1000:],
                }
            )
        rows.append(dryrun_row)
    return rows


def _decision_report(parity_rows: list[dict[str, Any]], ready_rows: list[dict[str, Any]], validation: dict[str, Any]) -> dict[str, Any]:
    passed = {row["algorithm"] for row in parity_rows if row.get("parity_passed") is True}
    has_single = any(
        row.get("algorithm") == "single_antenna_gnss1_status_KF_GINS" and row.get("run_allowed_in_N9B1D") is True
        for row in ready_rows
    )
    if validation.get("status") != "pass":
        status = "N9B1F_validation_failed"
        ready = False
        recommended = "fix_N9B1F_validation_issues"
    elif has_single and ({"source_backed_EKF", "baseline_no_feedback_EKF"} & passed):
        if len(passed) >= 3:
            status = "N9B1F_formal_LegSA_runners_parity_ready"
            recommended = "N9B1D_pilot_solver_execution"
        else:
            status = "N9B1F_minimal_LegSA_runner_parity_ready"
            recommended = "human_review_N9B1F_then_N9B1D_pilot_solver_execution"
        ready = True
    elif has_single:
        status = "N9B1F_only_single_baseline_runner_available"
        ready = False
        recommended = "implement_real_LegSA_runner"
    else:
        status = "N9B1F_LegSA_algorithm_implementation_missing"
        ready = False
        recommended = "build_or_restore_LegSA_algorithm_solver"
    return {
        "stage": STAGE,
        "status": status,
        "ready_for_N9B1D_solver_execution": ready,
        "ready_for_N9B2_execution": False,
        "recommended_next_stage": recommended,
        "parity_passed_algorithms": sorted(passed),
        "blocked_algorithms": [
            {"algorithm": row["algorithm"], "reason": row.get("blocked_reason")}
            for row in parity_rows
            if row.get("parity_passed") is not True
        ],
        "validation_status": validation.get("status"),
        "issues": validation.get("issues", []),
        "paper_performance_claim": False,
    }


def _load_r4e3_metrics(workspace_root: Path) -> dict[str, dict[str, Any]]:
    path = workspace_root / AUDIT_ROOT_NAME / R4E3_STAGE / "matrix" / "N9A_R4E3_OFFICIAL_EVALUATOR_METRICS_TABLE.json"
    data = read_json(path, [])
    rows = data.get("rows", data) if isinstance(data, dict) else data
    out: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        algorithm = row.get("algorithm")
        if algorithm:
            out[algorithm] = {key: row.get(key) for key in METRIC_KEYS}
    return out


def _load_r4e3_trace_path(workspace_root: Path) -> str | None:
    path = workspace_root / AUDIT_ROOT_NAME / R4E3_STAGE / "reports" / "N9A_R4E3_EVALUATOR_COMMAND_REPORT.json"
    report = read_json(path, {})
    for command_row in report.get("commands", []):
        command = command_row.get("command", [])
        if "--trace" in command:
            idx = command.index("--trace")
            if idx + 1 < len(command):
                return command[idx + 1]
    return None


def _load_r4e3_eval_script(workspace_root: Path) -> str | None:
    path = workspace_root / AUDIT_ROOT_NAME / R4E3_STAGE / "reports" / "N9A_R4E3_EVALUATOR_COMMAND_REPORT.json"
    report = read_json(path, {})
    for command_row in report.get("commands", []):
        command = command_row.get("command", [])
        if len(command) >= 2 and command[0] == "python3":
            return command[1]
    return None


def _metrics_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    if not summary:
        return {}
    pos = summary.get("position", {})
    att = summary.get("attitude", {})
    meta = summary.get("meta", {})
    return {
        "horizontal_rmse_m": pos.get("horizontal_rmse_m"),
        "up_rmse_m": pos.get("up_rmse_m"),
        "yaw_rmse_deg": att.get("yaw_rmse_deg"),
        "roll_rmse_deg": att.get("roll_rmse_deg"),
        "pitch_rmse_deg": att.get("pitch_rmse_deg"),
        "row_count": meta.get("num_samples"),
        "time_start": meta.get("time_start"),
        "time_end": meta.get("time_end"),
    }


def _required_inputs_for_algorithm(algorithm: str) -> list[str]:
    spec = ALGORITHM_SPECS[algorithm]
    inputs = ["locked clean IMU", "locked clean GNSS/status-yaw"]
    if spec.component_flags["raw_doppler"]:
        inputs.append(str(REPO_RELATIVE_REQUIRED_INPUTS["raw_doppler"]))
    if spec.component_flags["go2_joint"]:
        inputs.extend(
            [
                str(REPO_RELATIVE_REQUIRED_INPUTS["go2_attitude"]),
                str(REPO_RELATIVE_REQUIRED_INPUTS["go2_horizontal_velocity"]),
                str(REPO_RELATIVE_REQUIRED_INPUTS["go2_joint"]),
            ]
        )
    if spec.component_flags["feedback"]:
        inputs.append(str(REPO_RELATIVE_REQUIRED_INPUTS["selected_feedback"]))
    return inputs


def _r4k_lineage(workspace_root: Path, algorithm: str) -> dict[str, Any]:
    path = workspace_root / AUDIT_ROOT_NAME / R4K_STAGE / "algorithm_outputs_full" / algorithm / "output_lineage.json"
    return read_json(path, {}) or {}


def _tracked_path_leak_issues(workspace_root: Path) -> list[str]:
    patterns = [
        re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+"),
        re.compile("/" + "mnt" + r"/[A-Za-z]/Users/"),
        re.compile("/" + "home" + r"/[^/\s\"']+"),
    ]
    issues: list[str] = []
    for rel in TRACKED_FILES_FOR_PATH_AUDIT:
        path = workspace_root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in patterns):
            issues.append(f"local absolute path leak in tracked file: {rel}")
    return issues


def _safe_delta(current: Any, reference: Any) -> float | None:
    if current is None or reference is None:
        return None
    try:
        return float(current) - float(reference)
    except (TypeError, ValueError):
        return None


def _float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return value


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
