"""N9B1G case-level command rebinding with the formal LegSA runner.

This stage is command planning and dry-run precheck only. It binds the concrete
N9B1 pilot case rows from N9B1C4 to the N9B1F formal wrapper surface and keeps
selected-feedback dependencies explicit. It never executes solvers or
evaluators.
"""

from __future__ import annotations

import csv
import json
import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legsa_gins.reporting.by2_algorithm_runner import (
    ALGORITHM_SPECS,
    FORMAL_ALGORITHMS,
    build_algorithm_config_text,
    build_solver_command_record,
    load_base_config_values,
    repo_to_wsl,
)
from legsa_gins.reporting.by2_real_pilot_input_generator import AUDIT_ROOT_NAME


STAGE = "N9B1G_CASE_LEVEL_COMMAND_REBIND_WITH_FORMAL_RUNNER"
N9B1F_STAGE = "N9B1F_REAL_LEGSA_ALGORITHM_RUNNER_IMPLEMENTATION_AND_NORMAL_PARITY"
N9B1C4_STAGE = "N9B1C4_SELECTED_FEEDBACK_COMMAND_FIELD_COMPLETION"
N9B1C3_STAGE = "N9B1C3_EXECUTION_MATRIX_HYGIENE_AND_DEPENDENCY_ORDER_LOCK"
N9B1A1_STAGE = "N9B1A1_DOWNSAMPLE_CADENCE_POLICY_REPAIR"
N9B1D_STAGE = "N9B1D_PILOT_SOLVER_EXECUTION"

SINGLE_BASELINE_ALGORITHM = "single_antenna_gnss1_status_KF_GINS"
SELECTED_FEEDBACK_ALGORITHM = "selected_feedback_EKF"
BASELINE_ALGORITHM = "baseline_no_feedback_EKF"
M_CLEAN_REPEAT_CASE = "M_normal_baseline_repeat"
L_DISABLED_CASE = "L_feedback_disabled"

PILOT_CASE_IDS = [
    "M_normal_baseline_repeat",
    "A_outage_5s",
    "C_position_noise_medium",
    "D_position_spike_medium",
    "B_gnss_downsample_every2",
    "H_dual_yaw_noise_medium",
    "G_raw_doppler_disabled",
    "L_feedback_disabled",
    "I_source_aware_disabled",
    "J_go2_horizontal_velocity_missing",
]
RANDOM_CASE_IDS = {
    "C_position_noise_medium",
    "D_position_spike_medium",
    "H_dual_yaw_noise_medium",
}

REQUIRED_SUBDIRS = [
    "case_level_command_plans",
    "runtime_configs",
    "dependency_graph",
    "wsl_dryrun",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
]
REPORT_NAMES = [
    "N9B1G_COMMAND_REBIND_REPORT.json",
    "N9B1G_WSL_DRYRUN_REPORT.json",
    "N9B1G_VALIDATION_REPORT.json",
    "N9B1G_DECISION_REPORT.json",
]
MATRIX_STEMS = [
    "N9B1G_N9B1D_CASE_LEVEL_COMMAND_MATRIX",
    "N9B1G_WSL_DRYRUN_CASE_LEVEL_COMMANDS",
]
TRACKED_FILES_FOR_PATH_AUDIT = [
    "src/legsa_gins/reporting/by2_algorithm_runner.py",
    "src/legsa_gins/reporting/by2_n9b1g_case_level_command_rebind_with_formal_runner.py",
    "scripts/experiments/run_n9b1g_case_level_command_rebind_with_formal_runner.py",
    "scripts/audit_n9b1g_case_level_command_rebind_with_formal_runner.py",
    "tests/unit/test_by2_n9b1g_case_level_command_rebind_with_formal_runner.py",
    "tests/audit/test_n9b1g_case_level_command_rebind_with_formal_runner.py",
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


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_n9b1g_runtime_root(workspace_root: Path) -> Path:
    return workspace_root / AUDIT_ROOT_NAME / STAGE


def run_n9b1g_case_level_command_rebind_with_formal_runner(
    workspace_root: Path,
    runtime_root: Path | None = None,
    *,
    write_outputs: bool = True,
    run_wsl_dryrun: bool = True,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root or default_n9b1g_runtime_root(workspace_root)
    if write_outputs:
        _create_runtime_tree(runtime_root)

    c4_rows = _load_json_rows(
        workspace_root
        / AUDIT_ROOT_NAME
        / N9B1C4_STAGE
        / "matrix"
        / "N9B1C4_N9B1D_READY_COMMAND_MATRIX.json"
    )
    dependency_rows = _load_json_rows(
        workspace_root
        / AUDIT_ROOT_NAME
        / N9B1C3_STAGE
        / "matrix"
        / "N9B1C3_CASE_DEPENDENCY_GRAPH.json"
    )
    n9b1f_rows = _load_json_rows(
        workspace_root
        / AUDIT_ROOT_NAME
        / N9B1F_STAGE
        / "matrix"
        / "N9B1F_N9B1D_READY_EXECUTION_MATRIX.json"
    )
    parity_algorithms = {
        row.get("algorithm")
        for row in n9b1f_rows
        if row.get("algorithm") in FORMAL_ALGORITHMS and row.get("run_allowed_in_N9B1D") is True
    }
    dependency_by_case = _dependency_by_case(dependency_rows)
    source_rows = _selected_source_rows(c4_rows)

    command_rows: list[dict[str, Any]] = []
    for source_row in source_rows:
        algorithm = source_row.get("algorithm", "")
        if algorithm in FORMAL_ALGORITHMS:
            if algorithm not in parity_algorithms:
                command_rows.append(_blocked_row(source_row, "formal algorithm did not pass N9B1F parity"))
            elif algorithm == SELECTED_FEEDBACK_ALGORITHM:
                command_rows.extend(
                    _selected_feedback_command_rows(
                        workspace_root,
                        runtime_root,
                        source_row,
                        dependency_by_case.get(source_row.get("case_id", ""), []),
                        write_outputs=write_outputs,
                    )
                )
            else:
                command_rows.append(
                    _formal_solver_row(
                        workspace_root,
                        runtime_root,
                        source_row,
                        source_row["algorithm"],
                        "direct_solver",
                        dependency_group_id=f"{source_row['case_id']}::{source_row['algorithm']}",
                        dependency_order=1,
                        write_outputs=write_outputs,
                    )
                )
        elif algorithm == SINGLE_BASELINE_ALGORITHM:
            command_rows.append(_single_baseline_row(workspace_root, runtime_root, source_row, write_outputs=write_outputs))
        else:
            command_rows.append(_blocked_row(source_row, "not an N9B1G executable algorithm"))

    dryrun_rows = _build_wsl_dryrun_rows(workspace_root, runtime_root, command_rows)
    if write_outputs and run_wsl_dryrun:
        dryrun_rows = _run_wsl_dryrun(workspace_root, runtime_root, dryrun_rows)

    command_report = _command_rebind_report(source_rows, command_rows, parity_algorithms)
    wsl_report = _wsl_dryrun_report(dryrun_rows, run_wsl_dryrun)
    validation = validate_n9b1g_result(
        workspace_root,
        runtime_root,
        command_rows,
        dryrun_rows,
        runtime_written=False,
    )
    decision = _decision_report(validation, command_report, wsl_report)
    result = {
        "command_rebind_report": command_report,
        "wsl_dryrun_report": wsl_report,
        "validation_report": validation,
        "decision_report": decision,
        "n9b1d_case_level_command_matrix": command_rows,
        "wsl_dryrun_case_level_commands": dryrun_rows,
        "dependency_graph": dependency_rows,
    }
    if write_outputs:
        _write_outputs(runtime_root, result)
        result["validation_report"] = validate_n9b1g_result(
            workspace_root,
            runtime_root,
            command_rows,
            dryrun_rows,
            runtime_written=True,
        )
        result["decision_report"] = _decision_report(
            result["validation_report"],
            command_report,
            wsl_report,
        )
        _write_outputs(runtime_root, result)
    return result


def validate_n9b1g_result(
    workspace_root: Path,
    runtime_root: Path,
    command_rows: list[dict[str, Any]] | None = None,
    dryrun_rows: list[dict[str, Any]] | None = None,
    *,
    runtime_written: bool = True,
) -> dict[str, Any]:
    command_rows = command_rows or []
    dryrun_rows = dryrun_rows or []
    issues: list[str] = []
    executable_rows = [row for row in command_rows if row.get("run_allowed_in_N9B1D") is True]

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
        for path in runtime_root.rglob("*"):
            if path.is_file() and path.name in FORBIDDEN_RUNTIME_OUTPUT_NAMES:
                if path.parent.name != "case_level_command_plans":
                    issues.append(f"forbidden solver/evaluator output generated: {_rel(runtime_root, path)}")

    if len({(row.get("case_id"), row.get("algorithm")) for row in command_rows if row.get("source_case_algorithm_row")}) != 46:
        issues.append("expected 46 source case/algorithm rows represented")
    if any(row.get("case_id") == "B_gnss_downsample_2Hz" for row in command_rows):
        issues.append("forbidden B_gnss_downsample_2Hz was bound")

    for row in executable_rows:
        command = str(row.get("command", ""))
        if "--normal-parity-mode" in command:
            issues.append(f"normal-parity-mode present in command: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        if "future_solver_entry" in command or row.get("entrypoint") == "future_solver_entry":
            issues.append(f"future_solver_entry present: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        if "--run-filter-csv" in command:
            issues.append(f"diagnostic run-filter-csv present: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        if (
            row.get("algorithm") in FORMAL_ALGORITHMS
            and "build/cpp/legsa_gins" in command
            and row.get("stage") != "selected_feedback_stage1_feedback_generation"
        ):
            issues.append(f"formal row uses diagnostic legsa_gins: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        if row.get("algorithm") in FORMAL_ALGORITHMS and not row.get("runtime_config_path"):
            issues.append(f"missing runtime config path: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        if not row.get("solver_command_json"):
            issues.append(f"missing solver command JSON path: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        if row.get("trace_solver_input") is True:
            issues.append(f"trace solver input recorded: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        if row.get("final_v23_solver_input") is True or row.get("final_v23_output_solver_input") is True:
            issues.append(f"final_v23 solver input recorded: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        if row.get("solver_run") is True or row.get("official_evaluator_run") is True:
            issues.append(f"solver/evaluator execution recorded: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")

    for case_id, rows in _rows_by_case_algorithm(command_rows, SELECTED_FEEDBACK_ALGORITHM).items():
        stages = [row.get("stage") for row in rows if row.get("run_allowed_in_N9B1D") is True]
        if case_id == L_DISABLED_CASE:
            if "selected_feedback_stage1_feedback_generation" in stages:
                issues.append("L_feedback_disabled unexpectedly requires feedback generation")
        elif case_id == M_CLEAN_REPEAT_CASE:
            if stages != ["selected_feedback_stage2_solver"]:
                issues.append("M_normal_baseline_repeat selected-feedback command should be clean-repeat stage2 only")
        else:
            if stages != [
                "selected_feedback_stage1_baseline",
                "selected_feedback_stage1_feedback_generation",
                "selected_feedback_stage2_solver",
            ]:
                issues.append(f"selected-feedback dependency order incomplete: {case_id}: {stages}")
        for row in rows:
            feedback_path = str(row.get("feedback_input", ""))
            if case_id != M_CLEAN_REPEAT_CASE and "N8J_feedback_final_validation" in feedback_path:
                issues.append(f"clean N8J feedback reused for degraded selected-feedback case: {case_id}")

    for row in dryrun_rows:
        if row.get("dry_run") is not True:
            issues.append(f"WSL bridge row not dry-run: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        if row.get("executed_solver") is True or row.get("executed") is True:
            issues.append(f"WSL dry-run executed command: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")
        if row.get("dryrun_returncode") not in {0, None}:
            issues.append(f"WSL dry-run failed: {row.get('case_id')}/{row.get('algorithm')}/{row.get('stage')}")

    issues.extend(_tracked_path_leak_issues(workspace_root))
    return {
        "stage": STAGE,
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "runtime_written": runtime_written,
        "source_case_algorithm_rows": len({(row.get("case_id"), row.get("algorithm")) for row in command_rows if row.get("source_case_algorithm_row")}),
        "case_level_command_rows": len(command_rows),
        "run_allowed_rows": len(executable_rows),
        "selected_feedback_dependency_command_count": sum(
            row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM and row.get("run_allowed_in_N9B1D") is True
            for row in command_rows
        ),
        "no_degradation_execution": True,
        "no_N9B2": True,
        "no_solver_execution": not any(row.get("solver_run") for row in command_rows),
        "no_official_evaluator_execution": not any(row.get("official_evaluator_run") for row in command_rows),
        "no_normal_parity_mode": not any("--normal-parity-mode" in str(row.get("command", "")) for row in command_rows),
        "no_trace_solver_input": not any(row.get("trace_solver_input") for row in command_rows),
        "no_final_v23_solver_input": not any(row.get("final_v23_solver_input") for row in command_rows),
        "ready_for_N9B2_execution": False,
    }


def _selected_source_rows(c4_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        row
        for row in c4_rows
        if row.get("case_id") in PILOT_CASE_IDS
        and row.get("run_allowed_in_N9B1D") is True
        and row.get("algorithm") in set(FORMAL_ALGORITHMS + [SINGLE_BASELINE_ALGORITHM])
    ]
    return sorted(rows, key=lambda row: (PILOT_CASE_IDS.index(row["case_id"]), row.get("algorithm", "")))


def _dependency_by_case(dependency_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in dependency_rows:
        grouped.setdefault(row.get("case_id", ""), []).append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: int(row.get("order_index", 0) or 0))
    return grouped


def _formal_solver_row(
    workspace_root: Path,
    runtime_root: Path,
    source_row: dict[str, Any],
    command_algorithm: str,
    stage: str,
    *,
    dependency_group_id: str,
    dependency_order: int,
    write_outputs: bool,
    config_suffix: str = "",
    output_dir_wsl: str | None = None,
    feedback_input: str = "",
    dependency_mode: str = "direct_solver",
) -> dict[str, Any]:
    case_id = source_row["case_id"]
    algorithm = source_row["algorithm"]
    config_dir = runtime_root / "runtime_configs" / case_id / algorithm
    if config_suffix:
        config_dir = config_dir / config_suffix
    output_dir_wsl = output_dir_wsl or _future_output_root(workspace_root, case_id, algorithm)
    config_path = config_dir / "runtime_config.yaml"
    config_diff = _config_diff(source_row, command_algorithm, stage, output_dir_wsl, feedback_input)
    config_text = _runtime_config_text(workspace_root, source_row, command_algorithm, output_dir_wsl, feedback_input, stage, config_diff)
    source_role = _source_role(source_row, command_algorithm, stage, feedback_input)
    output_lineage = _output_lineage(source_row, command_algorithm, stage, config_path, output_dir_wsl, feedback_input)
    solver_command_json = runtime_root / "case_level_command_plans" / case_id / algorithm / stage / "solver_command.json"
    solver_record = build_solver_command_record(
        command_algorithm,
        config_path,
        output_dir_wsl,
        workspace_root=workspace_root,
        dry_run=True,
    )
    solver_record.update(
        {
            "case_id": case_id,
            "target_algorithm": algorithm,
            "stage": stage,
            "dependency_group_id": dependency_group_id,
            "dependency_order": dependency_order,
            "normal_parity_mode": False,
            "solver_run": False,
            "official_evaluator_run": False,
        }
    )
    if write_outputs:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config_text, encoding="utf-8")
        _write_json(config_dir / "source_role.json", source_role)
        _write_json(config_dir / "output_lineage_plan.json", output_lineage)
        _write_json(config_dir / "config_diff_from_normal.json", config_diff)
        _write_json(solver_command_json, solver_record)
    command = _formal_runner_command(source_row, command_algorithm, config_path, output_dir_wsl, feedback_input)
    return {
        "stage": stage,
        "case_id": case_id,
        "algorithm": algorithm,
        "command_algorithm": command_algorithm,
        "entrypoint": "python -m legsa_gins.reporting.by2_algorithm_runner",
        "underlying_runner": "legsa_v23_port_core_demo --config --output-dir",
        "working_directory": source_row.get("working_directory", ""),
        "command": command,
        "runtime_config_path": str(config_path),
        "runtime_config_path_wsl": repo_to_wsl(config_path),
        "solver_command_json": str(solver_command_json),
        "output_dir": output_dir_wsl,
        "degraded_input_manifest": _degraded_input_manifest(workspace_root, case_id),
        "random_manifest": _random_manifest(workspace_root, case_id),
        "dependency_group_id": dependency_group_id,
        "dependency_order": dependency_order,
        "dependency_mode": dependency_mode,
        "feedback_input": feedback_input,
        "source_case_algorithm_row": True,
        "source_case_algorithm_key": f"{case_id}::{algorithm}",
        "run_allowed_in_N9B1D": True,
        "block_reason": "",
        "command_plan_only": True,
        "dry_run_only": True,
        "solver_run": False,
        "official_evaluator_run": False,
        "NAV_generated": False,
        "STD_generated": False,
        "EVAL_NAV_generated": False,
        "RUN_MANIFEST_generated": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "ready_for_N9B2_execution": False,
    }


def _selected_feedback_command_rows(
    workspace_root: Path,
    runtime_root: Path,
    source_row: dict[str, Any],
    dependency_rows: list[dict[str, Any]],
    *,
    write_outputs: bool,
) -> list[dict[str, Any]]:
    case_id = source_row["case_id"]
    mode = dependency_rows[0].get("dependency_mode", "") if dependency_rows else ""
    group_id = f"{case_id}::{SELECTED_FEEDBACK_ALGORITHM}"
    if mode == "same_case_selected_feedback":
        feedback_rel = next((row.get("dependency_path", "") for row in dependency_rows if row.get("dependency_path")), "")
        planned_feedback = repo_to_wsl(runtime_root / feedback_rel)
        stage1_output = _dependency_output_root(workspace_root, case_id, "stage1_baseline")
        stage1 = _formal_solver_row(
            workspace_root,
            runtime_root,
            {**source_row, "algorithm": SELECTED_FEEDBACK_ALGORITHM},
            BASELINE_ALGORITHM,
            "selected_feedback_stage1_baseline",
            dependency_group_id=group_id,
            dependency_order=1,
            write_outputs=write_outputs,
            config_suffix="stage1_baseline",
            output_dir_wsl=stage1_output,
            dependency_mode=mode,
        )
        generation = _feedback_generation_row(
            workspace_root,
            runtime_root,
            source_row,
            planned_feedback,
            group_id,
            write_outputs=write_outputs,
        )
        stage2 = _formal_solver_row(
            workspace_root,
            runtime_root,
            source_row,
            SELECTED_FEEDBACK_ALGORITHM,
            "selected_feedback_stage2_solver",
            dependency_group_id=group_id,
            dependency_order=3,
            write_outputs=write_outputs,
            config_suffix="stage2_solver",
            feedback_input=planned_feedback,
            dependency_mode=mode,
        )
        return [stage1, generation, stage2]
    if mode == "disabled_marker_selected_feedback" or case_id == L_DISABLED_CASE:
        return [
            _formal_solver_row(
                workspace_root,
                runtime_root,
                source_row,
                SELECTED_FEEDBACK_ALGORITHM,
                "selected_feedback_stage2_solver",
                dependency_group_id=group_id,
                dependency_order=1,
                write_outputs=write_outputs,
                config_suffix="stage2_feedback_disabled",
                dependency_mode="disabled_marker_selected_feedback",
            )
        ]
    if mode == "clean_repeat_selected_feedback" or case_id == M_CLEAN_REPEAT_CASE:
        clean_feedback = repo_to_wsl(workspace_root / next((row.get("dependency_path", "") for row in dependency_rows), ""))
        return [
            _formal_solver_row(
                workspace_root,
                runtime_root,
                source_row,
                SELECTED_FEEDBACK_ALGORITHM,
                "selected_feedback_stage2_solver",
                dependency_group_id=group_id,
                dependency_order=1,
                write_outputs=write_outputs,
                config_suffix="stage2_clean_repeat",
                feedback_input=clean_feedback,
                dependency_mode="clean_repeat_selected_feedback",
            )
        ]
    return [_blocked_row(source_row, "selected-feedback dependency graph missing")]


def _feedback_generation_row(
    workspace_root: Path,
    runtime_root: Path,
    source_row: dict[str, Any],
    planned_feedback_wsl: str,
    group_id: str,
    *,
    write_outputs: bool,
) -> dict[str, Any]:
    case_id = source_row["case_id"]
    algorithm = source_row["algorithm"]
    config_dir = runtime_root / "runtime_configs" / case_id / algorithm / "stage1_feedback_generation"
    config_path = config_dir / "runtime_config.yaml"
    report_wsl = planned_feedback_wsl.replace("FGO_FEEDBACK_OBSERVATIONS.csv", "OBSERVATION_BUILD_REPORT.json")
    stage1_eval_nav = f"{_dependency_output_root(workspace_root, case_id, 'stage1_baseline')}/EVAL_NAV.csv"
    gnss_input = _input_value(source_row, "GNSS")
    command = " ".join(
        [
            "python",
            "scripts/experiments/run_n9b1c2_selected_feedback_same_case_mapping.py",
            "--generate-feedback-observations",
            "--case-id",
            _q(case_id),
            "--baseline-eval-nav",
            _q(stage1_eval_nav),
            "--gnss-path",
            _q(gnss_input),
            "--output-observations",
            _q(planned_feedback_wsl),
            "--output-report",
            _q(report_wsl),
        ]
    )
    solver_command_json = runtime_root / "case_level_command_plans" / case_id / algorithm / "selected_feedback_stage1_feedback_generation" / "solver_command.json"
    payload = {
        "case_id": case_id,
        "algorithm": algorithm,
        "stage": "selected_feedback_stage1_feedback_generation",
        "command": command,
        "planned_feedback_observations": planned_feedback_wsl,
        "baseline_eval_nav_dependency": stage1_eval_nav,
        "dry_run": True,
        "executed_solver": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "normal_parity_mode": False,
    }
    if write_outputs:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            "\n".join(
                [
                    "stage: selected_feedback_stage1_feedback_generation",
                    f"case_id: {_yaml_quote(case_id)}",
                    f"algorithm: {_yaml_quote(algorithm)}",
                    f"baseline_eval_nav_dependency: {_yaml_quote(stage1_eval_nav)}",
                    f"gnsspath: {_yaml_quote(gnss_input)}",
                    f"planned_feedback_observations: {_yaml_quote(planned_feedback_wsl)}",
                    "solver_run: false",
                    "official_evaluator_run: false",
                    "trace_solver_input: false",
                    "final_v23_solver_input: false",
                    "normal_parity_mode: false",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        _write_json(config_dir / "source_role.json", _source_role(source_row, algorithm, "selected_feedback_stage1_feedback_generation", planned_feedback_wsl))
        _write_json(config_dir / "output_lineage_plan.json", _output_lineage(source_row, algorithm, "selected_feedback_stage1_feedback_generation", config_path, planned_feedback_wsl, planned_feedback_wsl))
        _write_json(config_dir / "config_diff_from_normal.json", {"case_id": case_id, "stage": "selected_feedback_stage1_feedback_generation", "planned_feedback_observations": planned_feedback_wsl})
        _write_json(solver_command_json, payload)
    return {
        "stage": "selected_feedback_stage1_feedback_generation",
        "case_id": case_id,
        "algorithm": algorithm,
        "command_algorithm": algorithm,
        "entrypoint": "python scripts/experiments/run_n9b1c2_selected_feedback_same_case_mapping.py",
        "underlying_runner": "feedback_observation_generation",
        "working_directory": source_row.get("working_directory", ""),
        "command": command,
        "runtime_config_path": str(config_path),
        "runtime_config_path_wsl": repo_to_wsl(config_path),
        "solver_command_json": str(solver_command_json),
        "output_dir": planned_feedback_wsl.rsplit("/", 1)[0],
        "degraded_input_manifest": _degraded_input_manifest(workspace_root, case_id),
        "random_manifest": _random_manifest(workspace_root, case_id),
        "dependency_group_id": group_id,
        "dependency_order": 2,
        "dependency_mode": "same_case_selected_feedback",
        "feedback_input": planned_feedback_wsl,
        "source_case_algorithm_row": False,
        "source_case_algorithm_key": f"{case_id}::{algorithm}",
        "run_allowed_in_N9B1D": True,
        "block_reason": "",
        "command_plan_only": True,
        "dry_run_only": True,
        "solver_run": False,
        "official_evaluator_run": False,
        "NAV_generated": False,
        "STD_generated": False,
        "EVAL_NAV_generated": False,
        "RUN_MANIFEST_generated": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "ready_for_N9B2_execution": False,
    }


def _single_baseline_row(workspace_root: Path, runtime_root: Path, source_row: dict[str, Any], *, write_outputs: bool) -> dict[str, Any]:
    case_id = source_row["case_id"]
    algorithm = source_row["algorithm"]
    config_dir = runtime_root / "runtime_configs" / case_id / algorithm
    config_path = config_dir / "runtime_config.yaml"
    solver_command_json = runtime_root / "case_level_command_plans" / case_id / algorithm / "single_baseline_solver" / "solver_command.json"
    payload = {
        "case_id": case_id,
        "algorithm": algorithm,
        "stage": "single_baseline_solver",
        "command": source_row.get("command", ""),
        "entrypoint": source_row.get("entrypoint", ""),
        "dry_run": True,
        "executed_solver": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
    }
    if write_outputs:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            "\n".join(
                [
                    "stage: single_baseline_solver",
                    f"case_id: {_yaml_quote(case_id)}",
                    f"algorithm: {_yaml_quote(algorithm)}",
                    f"owned_runner: {_yaml_quote('KF-GINS-Baseline')}",
                    f"source_command: {_yaml_quote(source_row.get('command', ''))}",
                    "solver_run: false",
                    "official_evaluator_run: false",
                    "trace_solver_input: false",
                    "final_v23_solver_input: false",
                    "normal_parity_mode: false",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        _write_json(config_dir / "source_role.json", _source_role(source_row, algorithm, "single_baseline_solver", ""))
        _write_json(config_dir / "output_lineage_plan.json", _output_lineage(source_row, algorithm, "single_baseline_solver", config_path, source_row.get("output_dir", ""), ""))
        _write_json(config_dir / "config_diff_from_normal.json", {"case_id": case_id, "algorithm": algorithm, "runner_owner": "KF-GINS-Baseline"})
        _write_json(solver_command_json, payload)
    return {
        "stage": "single_baseline_solver",
        "case_id": case_id,
        "algorithm": algorithm,
        "command_algorithm": algorithm,
        "entrypoint": source_row.get("entrypoint", ""),
        "underlying_runner": "KF-GINS-Baseline",
        "working_directory": source_row.get("working_directory", ""),
        "command": source_row.get("command", ""),
        "runtime_config_path": str(config_path),
        "runtime_config_path_wsl": repo_to_wsl(config_path),
        "solver_command_json": str(solver_command_json),
        "output_dir": source_row.get("output_dir", source_row.get("future_output_root", "")),
        "degraded_input_manifest": _degraded_input_manifest(workspace_root, case_id),
        "random_manifest": _random_manifest(workspace_root, case_id),
        "dependency_group_id": f"{case_id}::{algorithm}",
        "dependency_order": 1,
        "dependency_mode": "single_baseline_solver",
        "feedback_input": "",
        "source_case_algorithm_row": True,
        "source_case_algorithm_key": f"{case_id}::{algorithm}",
        "run_allowed_in_N9B1D": True,
        "block_reason": "",
        "command_plan_only": True,
        "dry_run_only": True,
        "solver_run": False,
        "official_evaluator_run": False,
        "NAV_generated": False,
        "STD_generated": False,
        "EVAL_NAV_generated": False,
        "RUN_MANIFEST_generated": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "ready_for_N9B2_execution": False,
    }


def _blocked_row(source_row: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "stage": "blocked",
        "case_id": source_row.get("case_id", ""),
        "algorithm": source_row.get("algorithm", ""),
        "command": "",
        "working_directory": source_row.get("working_directory", ""),
        "entrypoint": "",
        "runtime_config_path": "",
        "solver_command_json": "",
        "output_dir": "",
        "degraded_input_manifest": "",
        "random_manifest": "",
        "dependency_group_id": f"{source_row.get('case_id', '')}::{source_row.get('algorithm', '')}",
        "dependency_order": 0,
        "run_allowed_in_N9B1D": False,
        "block_reason": reason,
        "source_case_algorithm_row": True,
        "solver_run": False,
        "official_evaluator_run": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "ready_for_N9B2_execution": False,
    }


def _runtime_config_text(
    workspace_root: Path,
    source_row: dict[str, Any],
    command_algorithm: str,
    output_dir_wsl: str,
    feedback_input: str,
    stage: str,
    config_diff: dict[str, Any],
) -> str:
    base_values, _base_config = load_base_config_values(workspace_root)
    text = build_algorithm_config_text(workspace_root, command_algorithm, Path("_n9b1g_planned_output"), base_values)
    lines = text.splitlines()
    replacements = {
        "run_label": _yaml_quote(f"n9b1g_{source_row['case_id']}_{source_row['algorithm']}_{stage}"),
        "imupath": _yaml_quote(_input_value(source_row, "IMU")),
        "gnsspath": _yaml_quote(_input_value(source_row, "GNSS")),
        "outputpath": _yaml_quote(output_dir_wsl),
        "config_policy_evidence_status": _yaml_quote("n9b1g_case_level_degraded_runtime_config"),
        "trace_solver_input": "false",
        "final_v23_output_solver_input": "false",
    }
    case_id = source_row["case_id"]
    if case_id == "G_raw_doppler_disabled":
        replacements.update({"enable_raw_doppler": "false", "raw_doppler_factor_path": _yaml_quote("")})
    if case_id == "I_source_aware_disabled":
        replacements.update(
            {
                "enable_source_aware_weighting": "false",
                "source_aware_trace_enabled": "false",
            }
        )
    if case_id == "J_go2_horizontal_velocity_missing":
        replacements.update(
            {
                "enable_go2_horizontal_velocity_prior": "false",
                "go2_horizontal_velocity_prior_path": _yaml_quote(""),
                "source_aware_go2_horizontal_velocity_enabled": "false",
                "source_aware_go2_horizontal_velocity_lsim_enabled": "false",
                "source_aware_go2_horizontal_velocity_oim_enabled": "false",
            }
        )
    if command_algorithm == SELECTED_FEEDBACK_ALGORITHM:
        if case_id == L_DISABLED_CASE:
            replacements.update(
                {
                    "enable_fgo_feedback": "false",
                    "fgo_feedback_path": _yaml_quote(""),
                    "fgo_feedback_velocity_enabled": "false",
                    "fgo_feedback_attitude_enabled": "false",
                }
            )
        else:
            replacements.update(
                {
                    "enable_fgo_feedback": "true",
                    "fgo_feedback_path": _yaml_quote(feedback_input),
                    "fgo_feedback_velocity_enabled": "true",
                    "fgo_feedback_attitude_enabled": "true",
                }
            )
    for key, value in replacements.items():
        lines = _set_yaml_key(lines, key, value)
    lines.extend(
        [
            "",
            "# N9B1G command-rebind metadata; planning only.",
            f"n9b1g_stage: {_yaml_quote(STAGE)}",
            f"case_id: {_yaml_quote(source_row['case_id'])}",
            f"formal_algorithm: {_yaml_quote(source_row['algorithm'])}",
            f"runner_command_algorithm: {_yaml_quote(command_algorithm)}",
            f"command_stage: {_yaml_quote(stage)}",
            f"degraded_input_manifest: {_yaml_quote(_degraded_input_manifest(workspace_root, source_row['case_id']))}",
            f"random_manifest: {_yaml_quote(_random_manifest(workspace_root, source_row['case_id']))}",
            f"case_policy_diff: {_yaml_quote(','.join(config_diff.get('disabled_markers', [])))}",
            "normal_parity_mode: false",
            "normal_parity_output_as_degraded_result: false",
            "solver_run: false",
            "official_evaluator_run: false",
            "ready_for_N9B2_execution: false",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _config_diff(source_row: dict[str, Any], command_algorithm: str, stage: str, output_dir_wsl: str, feedback_input: str) -> dict[str, Any]:
    case_id = source_row["case_id"]
    disabled: list[str] = []
    if case_id == "G_raw_doppler_disabled":
        disabled.append("raw_doppler")
    if case_id == "I_source_aware_disabled":
        disabled.append("source_aware_weighting")
    if case_id == "J_go2_horizontal_velocity_missing":
        disabled.append("go2_horizontal_velocity")
    if case_id == L_DISABLED_CASE:
        disabled.append("fgo_feedback")
    return {
        "stage": STAGE,
        "case_id": case_id,
        "algorithm": source_row["algorithm"],
        "command_algorithm": command_algorithm,
        "command_stage": stage,
        "gnsspath": _input_value(source_row, "GNSS"),
        "imupath": _input_value(source_row, "IMU"),
        "outputpath": output_dir_wsl,
        "feedback_input": feedback_input,
        "disabled_markers": disabled,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "normal_parity_mode": False,
    }


def _source_role(source_row: dict[str, Any], command_algorithm: str, stage: str, feedback_input: str) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "case_id": source_row.get("case_id", ""),
        "algorithm": source_row.get("algorithm", ""),
        "command_algorithm": command_algorithm,
        "command_stage": stage,
        "trace_role": "evaluation_only_not_solver_input",
        "final_v23_role": "reference_only_not_solver_input",
        "gnss_role": "degraded_or_clean_repeat_observation_input",
        "imu_role": "solver_input",
        "feedback_role": "same_case_planned_dependency" if feedback_input else "not_consumed",
        "feedback_input": feedback_input,
        "normal_parity_output_as_degraded_result": False,
    }


def _output_lineage(
    source_row: dict[str, Any],
    command_algorithm: str,
    stage: str,
    config_path: Path,
    output_dir: str,
    feedback_input: str,
) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "case_id": source_row.get("case_id", ""),
        "algorithm": source_row.get("algorithm", ""),
        "command_algorithm": command_algorithm,
        "command_stage": stage,
        "runtime_config_path": str(config_path),
        "output_dir": output_dir,
        "feedback_input": feedback_input,
        "diagnostic_generic_filter_core": False,
        "normal_parity_mode": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "solver_run": False,
        "official_evaluator_run": False,
    }


def _formal_runner_command(source_row: dict[str, Any], command_algorithm: str, config_path: Path, output_dir_wsl: str, feedback_input: str) -> str:
    parts = [
        "python",
        "-m",
        "legsa_gins.reporting.by2_algorithm_runner",
        "--algorithm",
        command_algorithm,
        "--case-id",
        source_row["case_id"],
        "--runtime-config",
        repo_to_wsl(config_path),
        "--output-dir",
        output_dir_wsl,
        "--imu-source",
        _input_value(source_row, "IMU"),
        "--gnss-input",
        _input_value(source_row, "GNSS"),
    ]
    inputs = source_row.get("inputs") or {}
    if inputs.get("yaw"):
        parts.extend(["--yaw-input", str(inputs["yaw"])])
    if inputs.get("velocity"):
        parts.extend(["--velocity-input", str(inputs["velocity"])])
    if inputs.get("go2"):
        parts.extend(["--go2-input", str(inputs["go2"])])
    if feedback_input:
        parts.extend(["--feedback-input", feedback_input])
    return shlex.join([str(part) for part in parts])


def _build_wsl_dryrun_rows(workspace_root: Path, runtime_root: Path, command_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in command_rows:
        if row.get("run_allowed_in_N9B1D") is not True:
            continue
        log_path = runtime_root / "wsl_dryrun" / _safe_name(f"{row['case_id']}__{row['algorithm']}__{row['stage']}.json")
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
                "ready_for_N9B2_execution": False,
            }
        )
    return rows


def _run_wsl_dryrun(workspace_root: Path, runtime_root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _command_rebind_report(source_rows: list[dict[str, Any]], command_rows: list[dict[str, Any]], parity_algorithms: set[str]) -> dict[str, Any]:
    formal_source = [row for row in source_rows if row.get("algorithm") in FORMAL_ALGORITHMS]
    single_source = [row for row in source_rows if row.get("algorithm") == SINGLE_BASELINE_ALGORITHM]
    selected_commands = [
        row
        for row in command_rows
        if row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM and row.get("run_allowed_in_N9B1D") is True
    ]
    return {
        "stage": STAGE,
        "created_utc": now_utc(),
        "source_stage": N9B1C4_STAGE,
        "n9b1f_parity_algorithms": sorted(parity_algorithms),
        "source_case_algorithm_rows": len(source_rows),
        "formal_legsa_source_rows": len(formal_source),
        "single_baseline_source_rows": len(single_source),
        "case_level_command_rows": len(command_rows),
        "run_allowed_command_rows": sum(row.get("run_allowed_in_N9B1D") is True for row in command_rows),
        "selected_feedback_dependency_command_count": len(selected_commands),
        "selected_feedback_source_rows": sum(row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM for row in source_rows),
        "no_normal_parity_mode": not any("--normal-parity-mode" in str(row.get("command", "")) for row in command_rows),
        "no_future_solver_entry": not any("future_solver_entry" in str(row.get("command", "")) for row in command_rows),
        "formal_runner": "python -m legsa_gins.reporting.by2_algorithm_runner",
        "underlying_runner": "legsa_v23_port_core_demo --config --output-dir",
        "single_baseline_runner_owner": "KF-GINS-Baseline",
        "solver_run": False,
        "official_evaluator_run": False,
        "ready_for_N9B2_execution": False,
    }


def _wsl_dryrun_report(rows: list[dict[str, Any]], run_wsl_dryrun: bool) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "created_utc": now_utc(),
        "bridge_script": "scripts/run_wsl_legsa.ps1",
        "dry_run_only": True,
        "wsl_dryrun_invoked": run_wsl_dryrun,
        "dryrun_rows": len(rows),
        "dryrun_success_count": sum(row.get("dryrun_returncode") == 0 for row in rows),
        "dryrun_failure_count": sum(row.get("dryrun_returncode") not in {0, None} for row in rows),
        "executed": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "ready_for_N9B2_execution": False,
    }


def _decision_report(validation: dict[str, Any], command_report: dict[str, Any], wsl_report: dict[str, Any]) -> dict[str, Any]:
    if validation["status"] == "pass" and command_report["source_case_algorithm_rows"] == 46:
        status = "N9B1G_case_level_commands_ready_for_N9B1D"
        ready_for_n9b1d = True
        recommended = "human_review_N9B1G_then_N9B1D_solver_execution"
    else:
        status = "N9B1G_safety_gate_failed"
        ready_for_n9b1d = False
        recommended = "repair_safety_violation"
    return {
        "stage": STAGE,
        "created_utc": now_utc(),
        "status": status,
        "ready_for_N9B1D_solver_execution": ready_for_n9b1d,
        "ready_for_N9B2_execution": False,
        "recommended_next_stage": recommended,
        "case_level_command_count": command_report["case_level_command_rows"],
        "selected_feedback_dependency_command_count": command_report["selected_feedback_dependency_command_count"],
        "wsl_dryrun_rows": wsl_report["dryrun_rows"],
        "validation_status": validation["status"],
        "issues": validation["issues"],
    }


def _write_outputs(runtime_root: Path, result: dict[str, Any]) -> None:
    _create_runtime_tree(runtime_root)
    reports = {
        "N9B1G_COMMAND_REBIND_REPORT.json": result["command_rebind_report"],
        "N9B1G_WSL_DRYRUN_REPORT.json": result["wsl_dryrun_report"],
        "N9B1G_VALIDATION_REPORT.json": result["validation_report"],
        "N9B1G_DECISION_REPORT.json": result["decision_report"],
    }
    for name, payload in reports.items():
        _write_json(runtime_root / "reports" / name, payload)
    matrices = {
        "N9B1G_N9B1D_CASE_LEVEL_COMMAND_MATRIX": result["n9b1d_case_level_command_matrix"],
        "N9B1G_WSL_DRYRUN_CASE_LEVEL_COMMANDS": result["wsl_dryrun_case_level_commands"],
    }
    for stem, rows in matrices.items():
        _write_table_pair(runtime_root / "matrix" / stem, rows)
    _write_table_pair(
        runtime_root / "case_level_command_plans" / "N9B1G_N9B1D_CASE_LEVEL_COMMAND_MATRIX",
        result["n9b1d_case_level_command_matrix"],
    )
    _write_table_pair(
        runtime_root / "wsl_dryrun" / "N9B1G_WSL_DRYRUN_CASE_LEVEL_COMMANDS",
        result["wsl_dryrun_case_level_commands"],
    )
    _write_table_pair(runtime_root / "dependency_graph" / "N9B1G_SELECTED_FEEDBACK_DEPENDENCY_COMMANDS", [
        row for row in result["n9b1d_case_level_command_matrix"] if row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM
    ])
    _write_json(runtime_root / "validation" / "N9B1G_VALIDATION_REPORT.json", result["validation_report"])
    (runtime_root / "summary" / "n9b1g_next_stage_recommendation.md").write_text(_summary(result), encoding="utf-8")


def _summary(result: dict[str, Any]) -> str:
    decision = result["decision_report"]
    report = result["command_rebind_report"]
    wsl = result["wsl_dryrun_report"]
    return (
        "# N9B1G next stage recommendation\n\n"
        f"- status={decision['status']}\n"
        f"- ready_for_N9B1D_solver_execution={str(decision['ready_for_N9B1D_solver_execution']).lower()}\n"
        "- ready_for_N9B2_execution=false\n"
        f"- source_case_algorithm_rows={report['source_case_algorithm_rows']}\n"
        f"- case_level_command_rows={report['case_level_command_rows']}\n"
        f"- selected_feedback_dependency_command_count={report['selected_feedback_dependency_command_count']}\n"
        f"- wsl_dryrun_rows={wsl['dryrun_rows']}\n"
        f"- recommended_next_stage={decision['recommended_next_stage']}\n"
    )


def _create_runtime_tree(runtime_root: Path) -> None:
    for subdir in REQUIRED_SUBDIRS:
        (runtime_root / subdir).mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _write_table_pair(stem_path: Path, rows: list[dict[str, Any]]) -> None:
    _write_json(stem_path.with_suffix(".json"), rows)
    stem_path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with stem_path.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key, "")) for key in keys})


def _load_json_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        rows = data.get("rows", data.get("matrix", []))
    else:
        rows = data
    return [dict(row) for row in rows] if isinstance(rows, list) else []


def _input_value(row: dict[str, Any], key: str) -> str:
    return str((row.get("inputs") or {}).get(key, ""))


def _degraded_input_manifest(workspace_root: Path, case_id: str) -> str:
    path = workspace_root / AUDIT_ROOT_NAME / N9B1A1_STAGE / "repaired_inputs" / case_id / "generated_input_manifest.json"
    return str(path) if path.exists() else ""


def _random_manifest(workspace_root: Path, case_id: str) -> str:
    if case_id not in RANDOM_CASE_IDS:
        return ""
    path = workspace_root / AUDIT_ROOT_NAME / N9B1A1_STAGE / "randomness" / case_id / "random_value_manifest.json"
    return str(path) if path.exists() else ""


def _future_output_root(workspace_root: Path, case_id: str, algorithm: str) -> str:
    return f"{repo_to_wsl(workspace_root)}/{AUDIT_ROOT_NAME}/{N9B1D_STAGE}/algorithm_outputs/{case_id}/{algorithm}"


def _dependency_output_root(workspace_root: Path, case_id: str, dependency_name: str) -> str:
    return f"{repo_to_wsl(workspace_root)}/{AUDIT_ROOT_NAME}/{N9B1D_STAGE}/selected_feedback_dependencies/{case_id}/{dependency_name}"


def _set_yaml_key(lines: list[str], key: str, value: str) -> list[str]:
    prefix = f"{key}:"
    updated = False
    out: list[str] = []
    for line in lines:
        if line.strip().startswith(prefix):
            out.append(f"{key}: {value}")
            updated = True
        else:
            out.append(line)
    if not updated:
        out.append(f"{key}: {value}")
    return out


def _yaml_quote(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _q(value: Any) -> str:
    return shlex.quote(str(value))


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _rows_by_case_algorithm(rows: list[dict[str, Any]], algorithm: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("algorithm") == algorithm:
            grouped.setdefault(row.get("case_id", ""), []).append(row)
    for values in grouped.values():
        values.sort(key=lambda row: int(row.get("dependency_order", 0) or 0))
    return grouped


def _tracked_path_leak_issues(workspace_root: Path) -> list[str]:
    issues: list[str] = []
    leak_patterns = ["C:" + "\\Users\\", "C:" + "/Users/", "/mnt/" + "c/Users/"]
    for rel in TRACKED_FILES_FOR_PATH_AUDIT:
        path = workspace_root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in leak_patterns:
            if pattern in text:
                issues.append(f"tracked local path leak in {rel}: {pattern}")
    return issues


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value
