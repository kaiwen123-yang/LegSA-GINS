"""N9B1C2 selected-feedback same-case generation mapping.

This stage is report and command-plan generation only. It reads the N9B1C1,
N9B1C, N9B1A, and N9B1A1 matrices, then maps selected_feedback_EKF rows onto a
dry-run-only two-stage same-case feedback plan. It never runs solvers,
evaluators, figure generation, case review generation, or degradation matrices.
"""

from __future__ import annotations

import csv
import json
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from legsa_gins.reporting.by2_degradation_runner_precheck import FORBIDDEN_EXECUTION_OUTPUT_NAMES
from legsa_gins.reporting.by2_real_pilot_input_generator import AUDIT_ROOT_NAME


STAGE = "N9B1C2_SELECTED_FEEDBACK_SAME_CASE_FEEDBACK_GENERATION_MAPPING"
N9B1C1_STAGE = "N9B1C1_ROUTING_COMMAND_CONSISTENCY_AND_SELECTED_FEEDBACK_MAPPING_FIX"
N9B1C_STAGE = "N9B1C_REAL_SOLVER_ENTRYPOINT_AND_CONFIG_MAPPING"
N9B1A_STAGE = "N9B1A_REAL_PILOT_INPUT_GENERATOR_AND_WSL_BRIDGE_PRECHECK"
N9B1A1_STAGE = "N9B1A1_DOWNSAMPLE_CADENCE_POLICY_REPAIR"
FUTURE_SOLVER_STAGE = "N9B1D_PILOT_SOLVER_EXECUTION"
SELECTED_FEEDBACK_ALGORITHM = "selected_feedback_EKF"
L_DISABLED_CASE = "L_feedback_disabled"
M_CLEAN_REPEAT_CASE = "M_normal_baseline_repeat"
DEGRADED_CLEAN_FEEDBACK_FORBIDDEN_REASON = (
    "degraded selected_feedback_EKF rows must not consume clean N8J feedback observations"
)

REQUIRED_SUBDIRS = [
    "feedback_pipeline_inventory",
    "same_case_feedback_plan",
    "repaired_command_plans",
    "wsl_dryrun",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
]
REPORT_NAMES = [
    "N9B1C2_FEEDBACK_PIPELINE_INVENTORY_REPORT.json",
    "N9B1C2_SAME_CASE_FEEDBACK_COMMAND_PLAN_REPORT.json",
    "N9B1C2_CLEAN_REPEAT_FEEDBACK_POLICY_REPORT.json",
    "N9B1C2_WSL_DRYRUN_REPORT.json",
    "N9B1C2_VALIDATION_REPORT.json",
    "N9B1C2_DECISION_REPORT.json",
]
MATRIX_STEMS = [
    "N9B1C2_FEEDBACK_PIPELINE_INVENTORY",
    "N9B1C2_SELECTED_FEEDBACK_SAME_CASE_PLAN",
    "N9B1C2_COMMAND_MAPPING_MATRIX_REPAIRED",
    "N9B1C2_SELECTED_FEEDBACK_MAPPING_DIFF",
    "N9B1C2_WSL_DRYRUN_COMMAND_MATRIX",
    "N9B1C2_INPUT_MATRIX_READINESS",
]
SELECTED_FEEDBACK_SCOPE_CASES = {
    "M_normal_baseline_repeat",
    "A_outage_5s",
    "B_gnss_downsample_every2",
    "C_position_noise_medium",
    "D_position_spike_medium",
    "H_dual_yaw_noise_medium",
    "J_go2_horizontal_velocity_missing",
    "L_feedback_disabled",
}
TRACKED_FILES_FOR_PATH_AUDIT = [
    "src/legsa_gins/reporting/by2_n9b1c2_selected_feedback_same_case_mapping.py",
    "scripts/experiments/run_n9b1c2_selected_feedback_same_case_mapping.py",
    "scripts/audit_n9b1c2_selected_feedback_same_case_mapping.py",
    "tests/unit/test_by2_n9b1c2_selected_feedback_same_case_mapping.py",
    "tests/audit/test_n9b1c2_selected_feedback_same_case_mapping.py",
]


def default_n9b1c2_runtime_root(workspace_root: Path) -> Path:
    return workspace_root / AUDIT_ROOT_NAME / STAGE


def run_n9b1c2_selected_feedback_same_case_mapping(
    workspace_root: Path,
    runtime_root: Path | None = None,
    *,
    write_outputs: bool = True,
    run_wsl_dryrun: bool = True,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root or default_n9b1c2_runtime_root(workspace_root)
    roots = _prior_roots(workspace_root)
    if write_outputs:
        _create_runtime_tree(runtime_root)

    n9b1c1_rows = _load_json_rows(roots["n9b1c1"] / "matrix" / "N9B1C1_COMMAND_MAPPING_MATRIX_REPAIRED.json")
    n9b1c1_dependency_rows = _load_json_rows(roots["n9b1c1"] / "matrix" / "N9B1C1_SELECTED_FEEDBACK_DEPENDENCY_MATRIX.json")
    n9b1c_rows = _load_json_rows(roots["n9b1c"] / "matrix" / "N9B1C_COMMAND_MAPPING_MATRIX.json")
    n9b1a_rows = _load_json_rows(roots["n9b1a"] / "matrix" / "N9B1A_SOLVER_COMMAND_PLAN_INDEX.json")
    n9b1a1_rows = _load_json_rows(roots["n9b1a1"] / "matrix" / "N9B1A1_SOLVER_COMMAND_PLAN_INDEX_REPAIRED.json")

    input_readiness = _input_readiness_matrix(
        {
            "N9B1C1_COMMAND_MAPPING_MATRIX_REPAIRED": n9b1c1_rows,
            "N9B1C1_SELECTED_FEEDBACK_DEPENDENCY_MATRIX": n9b1c1_dependency_rows,
            "N9B1C_COMMAND_MAPPING_MATRIX": n9b1c_rows,
            "N9B1A_SOLVER_COMMAND_PLAN_INDEX": n9b1a_rows,
            "N9B1A1_SOLVER_COMMAND_PLAN_INDEX_REPAIRED": n9b1a1_rows,
        }
    )
    source_rows = _selected_source_rows(n9b1c1_rows)
    command_seed_by_case = _command_seed_by_case(n9b1c1_rows, n9b1c_rows)
    dependency_by_case = {row.get("case_id", ""): row for row in n9b1c1_dependency_rows}

    inventory = _feedback_pipeline_inventory(source_rows, command_seed_by_case, dependency_by_case)
    same_case_plan_rows: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    repaired_command_rows: list[dict[str, Any]] = []
    wsl_rows: list[dict[str, Any]] = []

    for row in source_rows:
        plan = _build_case_plan(row, command_seed_by_case.get(row["case_id"], {}), dependency_by_case.get(row["case_id"], {}), runtime_root)
        same_case_plan_rows.extend(plan["plan_rows"])
        mapping_rows.append(plan["mapping_row"])
        repaired_command_rows.extend(plan["command_rows"])
        if write_outputs:
            for command_row in plan["command_rows"]:
                _write_command_plan(runtime_root, command_row)
                _write_runtime_config(workspace_root, runtime_root, command_row)
        wsl_rows.extend(_wsl_row(command_row) for command_row in plan["command_rows"] if command_row["dryrun_required"])

    if write_outputs and run_wsl_dryrun:
        wsl_rows = _run_wsl_dryruns(workspace_root, runtime_root, wsl_rows)

    command_mapping_repaired = _command_mapping_repaired(n9b1c1_rows, mapping_rows)
    mapping_diff = _selected_feedback_mapping_diff(n9b1c1_rows, mapping_rows)
    validation = validate_n9b1c2_result(
        workspace_root,
        runtime_root,
        mapping_rows,
        repaired_command_rows,
        wsl_rows,
        runtime_written=False,
    )
    mapped_rows = [row for row in mapping_rows if row["mapping_status"] == "mapped"]
    blocked_rows = [row for row in mapping_rows if row["mapping_status"] != "mapped"]
    two_stage_mapped = [
        row
        for row in mapped_rows
        if row["acceptance_mode"] == "two_stage_same_case_feedback_generation_plan"
    ]

    if validation["status"] != "pass":
        decision_status = "N9B1C2_selected_feedback_mapping_safety_gate_failed"
        recommended_next_stage = "repair_N9B1C2_mapping_validation"
        ready_for_n9b1d = False
    elif blocked_rows:
        decision_status = "N9B1C2_selected_feedback_mapping_partial_with_blockers"
        recommended_next_stage = "human_review_N9B1C2_then_decide_N9B1D_partial_scope"
        ready_for_n9b1d = False
    else:
        decision_status = "N9B1C2_selected_feedback_same_case_mapping_ready"
        recommended_next_stage = "human_review_N9B1C2_then_N9B1D_solver_execution"
        ready_for_n9b1d = True

    result = {
        "feedback_pipeline_inventory_report": {
            "stage": STAGE,
            "input_rows": len(source_rows),
            "inventory_rows": len(inventory),
            "clean_n8j_reuse_policy": "M_normal_baseline_repeat_only",
            "degraded_clean_n8j_feedback_allowed": False,
            "solver_run": False,
            "official_evaluator_run": False,
            "figures_generated": False,
            "ready_for_N9B2_execution": False,
        },
        "same_case_feedback_command_plan_report": {
            "stage": STAGE,
            "same_case_plan_rows": len(same_case_plan_rows),
            "two_stage_mapped_rows": len(two_stage_mapped),
            "stage1_dryrun_plan_count": sum(row["plan_stage"] == "stage1_feedback_generation" for row in same_case_plan_rows),
            "stage2_dryrun_plan_count": sum(row["plan_stage"] == "stage2_selected_feedback_ekf" for row in same_case_plan_rows),
            "actual_feedback_generation_run": False,
            "solver_run": False,
            "official_evaluator_run": False,
            "ready_for_N9B2_execution": False,
        },
        "clean_repeat_feedback_policy_report": {
            "stage": STAGE,
            "selected_feedback_rows": len(mapping_rows),
            "mapped_rows": len(mapped_rows),
            "blocked_rows": len(blocked_rows),
            "clean_repeat_accepted_rows": sum(row["acceptance_mode"] == "clean_repeat_feedback_reuse" for row in mapped_rows),
            "disabled_marker_rows": sum(row["acceptance_mode"] == "feedback_disabled_marker" for row in mapped_rows),
            "degraded_clean_n8j_path_count": sum(row["clean_n8j_path_used_for_degraded_case"] for row in mapping_rows),
            "future_solver_entry_count": sum("future_solver_entry" in row.get("stage2_command", "") for row in mapping_rows),
            "clean_feedback_allowed_cases": [M_CLEAN_REPEAT_CASE],
            "clean_feedback_forbidden_for_degraded_cases": True,
            "solver_run": False,
            "official_evaluator_run": False,
            "ready_for_N9B2_execution": False,
        },
        "wsl_dryrun_report": {
            "stage": STAGE,
            "dry_run_only": True,
            "wsl_bridge_script": "scripts/run_wsl_legsa.ps1",
            "dryrun_command_rows": len(wsl_rows),
            "dryrun_success_count": sum(int(row.get("dryrun_returncode", 0) or 0) == 0 for row in wsl_rows),
            "dryrun_failure_count": sum(int(row.get("dryrun_returncode", 0) or 0) != 0 for row in wsl_rows),
            "executed": False,
            "solver_run": False,
            "official_evaluator_run": False,
            "ready_for_N9B2_execution": False,
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
            "issues": validation["issues"],
            "blockers": blocked_rows,
        },
        "feedback_pipeline_inventory": inventory,
        "same_case_feedback_plan_matrix": same_case_plan_rows,
        "selected_feedback_mapping_matrix": mapping_rows,
        "command_mapping_matrix_repaired": command_mapping_repaired,
        "selected_feedback_mapping_diff": mapping_diff,
        "repaired_command_plan_matrix": repaired_command_rows,
        "wsl_dryrun_command_matrix": wsl_rows,
        "input_matrix_readiness": input_readiness,
    }
    if write_outputs:
        _write_outputs(runtime_root, result)
    return result


def validate_n9b1c2_result(
    workspace_root: Path,
    runtime_root: Path,
    mapping_rows: list[dict[str, Any]] | None = None,
    command_rows: list[dict[str, Any]] | None = None,
    wsl_rows: list[dict[str, Any]] | None = None,
    *,
    runtime_written: bool = True,
) -> dict[str, Any]:
    mapping_rows = mapping_rows or []
    command_rows = command_rows or []
    wsl_rows = wsl_rows or []
    issues: list[str] = []

    if runtime_written:
        for subdir in REQUIRED_SUBDIRS:
            if not (runtime_root / subdir).is_dir():
                issues.append(f"missing required subdir: {subdir}")
        for report_name in REPORT_NAMES:
            if not (runtime_root / "reports" / report_name).is_file():
                issues.append(f"missing report: {report_name}")
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
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    issues.append(f"json parse failed: {_rel(runtime_root, path)}: {exc}")

    for row in mapping_rows:
        case_id = row.get("case_id", "")
        status = row.get("mapping_status", "")
        acceptance = row.get("acceptance_mode", "")
        if row.get("algorithm") != SELECTED_FEEDBACK_ALGORITHM:
            issues.append(f"non-selected-feedback row in mapping: {case_id}/{row.get('algorithm')}")
        if row.get("routing_status") == "not_selected_in_prior_plan":
            issues.append(f"not-selected selected_feedback row entered N9B1C2 mapping: {case_id}")
        if case_id not in SELECTED_FEEDBACK_SCOPE_CASES:
            issues.append(f"selected_feedback row outside approved N9B1C2 scope: {case_id}")
        if case_id not in {M_CLEAN_REPEAT_CASE, L_DISABLED_CASE} and row.get("clean_n8j_path_used_for_degraded_case"):
            issues.append(f"clean N8J feedback path used for degraded selected_feedback row: {case_id}")
        if status == "mapped":
            if acceptance == "two_stage_same_case_feedback_generation_plan":
                if not row.get("stage1_plan_exists") or not row.get("stage2_plan_exists"):
                    issues.append(f"mapped degraded selected_feedback row lacks two-stage plan: {case_id}")
                if not row.get("planned_same_case_feedback_path"):
                    issues.append(f"mapped degraded selected_feedback row lacks planned same-case feedback path: {case_id}")
            elif acceptance == "clean_repeat_feedback_reuse":
                if case_id != M_CLEAN_REPEAT_CASE:
                    issues.append(f"clean repeat feedback accepted outside M case: {case_id}")
            elif acceptance == "feedback_disabled_marker":
                if case_id != L_DISABLED_CASE:
                    issues.append(f"feedback disabled marker accepted outside L case: {case_id}")
            else:
                issues.append(f"mapped selected_feedback row has invalid acceptance mode: {case_id}/{acceptance}")
        if "future_solver_entry" in row.get("stage1_command", "") or "future_solver_entry" in row.get("stage2_command", ""):
            issues.append(f"future_solver_entry command remains: {case_id}")
        if _truthy(row.get("trace_solver_input")) or _truthy(row.get("final_v23_solver_input")):
            issues.append(f"trace/final_v23 marked as solver input: {case_id}")
        if _truthy(row.get("output_substitution")) or _truthy(row.get("direct_nav_override")):
            issues.append(f"output substitution marker is active: {case_id}")
        if _has_stale_placeholder(row):
            issues.append(f"stale active placeholder blocker remains: {case_id}")
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
                issues.append(f"{flag} must be false: {case_id}")

    for row in command_rows:
        case_id = row.get("case_id", "")
        if row.get("command_plan_only") is not True or row.get("dry_run_only") is not True:
            issues.append(f"command row is not dry-run-only plan: {case_id}/{row.get('plan_stage')}")
        if row.get("executed") is not False:
            issues.append(f"command row executed marker must be false: {case_id}/{row.get('plan_stage')}")
        if any("future_solver_entry" in str(row.get(key, "")) for key in ["command", "command_preview"]):
            issues.append(f"future_solver_entry in command plan: {case_id}/{row.get('plan_stage')}")
        if "--dry-run-plan-only" in row.get("command", "") or "--plan-stage" in row.get("command", ""):
            issues.append(f"unsupported synthetic solver flag in command plan: {case_id}/{row.get('plan_stage')}")
        if _truthy(row.get("trace_solver_input")) or _truthy(row.get("final_v23_solver_input")):
            issues.append(f"trace/final_v23 command input marker active: {case_id}/{row.get('plan_stage')}")
        for flag in ["solver_run", "official_evaluator_run", "NAV_generated", "STD_generated", "EVAL_NAV_generated", "RUN_MANIFEST_generated"]:
            if row.get(flag) not in {False, 0, None}:
                issues.append(f"{flag} must be false in command plan: {case_id}/{row.get('plan_stage')}")

    if any(row.get("dry_run_only") is not True or row.get("executed") is not False for row in wsl_rows):
        issues.append("WSL rows must be dry_run_only=true and executed=false")
    for issue in _tracked_absolute_path_issues(workspace_root):
        issues.append(issue)

    return {
        "stage": STAGE,
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "ready_for_N9B2_execution": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "figures_generated": False,
    }


def generate_same_case_feedback_observations(
    *,
    case_id: str,
    baseline_eval_nav: Path,
    gnss_path: Path,
    output_observations: Path,
    output_report: Path,
    residual_proxy_p95: float = 1.0,
) -> dict[str, Any]:
    """Generate same-case feedback observations from an already-computed baseline.

    This is a future N9B1D helper. N9B1C2 only maps this command and never calls it.
    """
    from legsa_gins.fgo_feedback.feedback_state_types import FeedbackGateThresholds
    from legsa_gins.fgo_feedback.fgo_feedback_covariance_policy import apply_conservative_covariance_policy
    from legsa_gins.fgo_feedback.fgo_feedback_gate import apply_feedback_gate
    from legsa_gins.fgo_feedback.fgo_feedback_observation import build_feedback_observations, write_feedback_observations
    from legsa_gins.fgo_feedback.sliding_window_manager import build_sliding_windows, read_eval_nav_csv, read_first_column_times

    samples = read_eval_nav_csv(baseline_eval_nav)
    gnss_times = read_first_column_times(gnss_path)
    windows, window_report = build_sliding_windows(
        samples,
        candidate_feedback_times=gnss_times,
        window_duration_s=5.0,
        feedback_stride_s=1.0,
        min_epoch_count=3,
    )
    raw_obs, observation_report = build_feedback_observations(
        samples,
        windows,
        mode="horizontal_velocity_attitude_feedback",
        origin=samples[0],
        residual_proxy_p95=residual_proxy_p95,
    )
    cov_obs, covariance_report = apply_conservative_covariance_policy(raw_obs, residual_proxy_p95=residual_proxy_p95)
    gated_obs, gate_report = apply_feedback_gate(
        cov_obs,
        samples,
        origin=samples[0],
        thresholds=FeedbackGateThresholds(),
        position_enabled=False,
        velocity_enabled=True,
        attitude_enabled=True,
        reject_all=False,
    )
    write_feedback_observations(output_observations, gated_obs)
    report = {
        "stage": STAGE,
        "case_id": case_id,
        "baseline_eval_nav": str(baseline_eval_nav),
        "gnss_path": str(gnss_path),
        "output_observations": str(output_observations),
        "window_report": window_report,
        "observation_report": observation_report,
        "covariance_report": covariance_report,
        "gate_report": gate_report,
        "feedback_row_count": len(gated_obs),
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "output_substitution": False,
        "direct_nav_override": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "paper_performance_claim": False,
    }
    _write_json(output_report, report)
    return report


def _prior_roots(workspace_root: Path) -> dict[str, Path]:
    audit_root = workspace_root / AUDIT_ROOT_NAME
    return {
        "n9b1c1": audit_root / N9B1C1_STAGE,
        "n9b1c": audit_root / N9B1C_STAGE,
        "n9b1a": audit_root / N9B1A_STAGE,
        "n9b1a1": audit_root / N9B1A1_STAGE,
    }


def _selected_source_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        dict(row)
        for row in rows
        if row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM
        and row.get("case_id") in SELECTED_FEEDBACK_SCOPE_CASES
        and row.get("routing_status") in {"applicable", "diagnostic_only"}
        and row.get("selected_for_N9B1C_mapping") is not False
    ]
    return sorted(selected, key=lambda row: row.get("case_id", ""))


def _command_seed_by_case(n9b1c1_rows: list[dict[str, Any]], n9b1c_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for row in n9b1c1_rows + n9b1c_rows:
        if row.get("mapping_status") != "mapped" or not row.get("command"):
            continue
        case_id = row.get("case_id", "")
        algorithm = row.get("algorithm", "")
        if not case_id or algorithm == SELECTED_FEEDBACK_ALGORITHM:
            continue
        current = candidates.get(case_id)
        if current is None or _seed_rank(algorithm) < _seed_rank(current.get("algorithm", "")):
            candidates[case_id] = dict(row)
    return candidates


def _seed_rank(algorithm: str) -> int:
    order = {
        "baseline_no_feedback_EKF": 0,
        "source_backed_EKF": 1,
        "source_aware_EKF": 2,
        "Go2_joint_EKF": 3,
        "Raw_Doppler_EKF": 4,
        "single_antenna_gnss1_status_KF_GINS": 5,
    }
    return order.get(algorithm, 99)


def _command_mapping_repaired(n9b1c1_rows: list[dict[str, Any]], mapping_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected_by_case = {row["case_id"]: row for row in mapping_rows}
    repaired: list[dict[str, Any]] = []
    for prior in n9b1c1_rows:
        row = dict(prior)
        if row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM and row.get("case_id") in selected_by_case:
            selected = selected_by_case[row["case_id"]]
            row.update(
                {
                    "stage": STAGE,
                    "prior_stage": N9B1C1_STAGE,
                    "prior_mapping_status": prior.get("mapping_status", ""),
                    "prior_block_reason": prior.get("block_reason", prior.get("blocked_reason", "")),
                    "mapping_status": selected["mapping_status"],
                    "blocked_reason": selected["blocked_reason"],
                    "block_reason": selected["blocked_reason"],
                    "command": selected["stage2_command"] if selected["mapping_status"] == "mapped" else "",
                    "command_preview": selected["stage2_command"] if selected["mapping_status"] == "mapped" else f"BLOCKED: {selected['blocked_reason']}",
                    "command_type": "two_stage_selected_feedback_plan" if selected["mapping_status"] == "mapped" else "blocked",
                    "generated_config_path": selected["generated_config_path"],
                    "run_allowed_in_N9B1D": selected["mapping_status"] == "mapped",
                    "ready_for_N9B1D_solver_execution": selected["mapping_status"] == "mapped",
                    "ready_for_N9B2_execution": False,
                    "acceptance_mode": selected["acceptance_mode"],
                    "planned_same_case_feedback_path": selected["planned_same_case_feedback_path"],
                    "clean_n8j_path_used_for_degraded_case": selected["clean_n8j_path_used_for_degraded_case"],
                    "stage1_plan_exists": selected["stage1_plan_exists"],
                    "stage2_plan_exists": selected["stage2_plan_exists"],
                }
            )
            if selected["mapping_status"] == "mapped":
                row["n9b1c2_active_block_reason_cleaned"] = True
        repaired.append(row)
    return repaired


def _selected_feedback_mapping_diff(n9b1c1_rows: list[dict[str, Any]], mapping_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prior_by_case = {
        row.get("case_id", ""): row
        for row in n9b1c1_rows
        if row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM
    }
    rows: list[dict[str, Any]] = []
    for mapped in mapping_rows:
        prior = prior_by_case.get(mapped["case_id"], {})
        rows.append(
            {
                "stage": STAGE,
                "case_id": mapped["case_id"],
                "algorithm": SELECTED_FEEDBACK_ALGORITHM,
                "routing_status": mapped["routing_status"],
                "prior_mapping_status": prior.get("mapping_status", ""),
                "repaired_mapping_status": mapped["mapping_status"],
                "prior_block_reason": prior.get("block_reason", prior.get("blocked_reason", "")),
                "repaired_block_reason": mapped["blocked_reason"],
                "acceptance_mode": mapped["acceptance_mode"],
                "stage1_plan_exists": mapped["stage1_plan_exists"],
                "stage2_plan_exists": mapped["stage2_plan_exists"],
                "clean_n8j_path_used_for_degraded_case": mapped["clean_n8j_path_used_for_degraded_case"],
                "stale_placeholder_active_after_repair": _has_stale_placeholder(mapped),
                "solver_run": False,
                "official_evaluator_run": False,
                "ready_for_N9B2_execution": False,
            }
        )
    return rows


def _feedback_pipeline_inventory(
    selected_rows: list[dict[str, Any]],
    command_seed_by_case: dict[str, dict[str, Any]],
    dependency_by_case: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in selected_rows:
        case_id = row.get("case_id", "")
        dependency = dependency_by_case.get(case_id, {})
        rows.append(
            {
                "case_id": case_id,
                "algorithm": SELECTED_FEEDBACK_ALGORITHM,
                "routing_status": row.get("routing_status", ""),
                "prior_mapping_status": row.get("mapping_status", ""),
                "command_seed_algorithm": command_seed_by_case.get(case_id, {}).get("algorithm", ""),
                "command_seed_available": case_id in command_seed_by_case,
                "clean_feedback_candidate_source": dependency.get("candidate_source", ""),
                "clean_repeat_reuse_defensible": dependency.get("clean_repeat_reuse_defensible", False),
                "same_case_feedback_exists": dependency.get("same_case_feedback_exists", False),
                "stage1_generation_required": case_id not in {M_CLEAN_REPEAT_CASE, L_DISABLED_CASE},
                "stage2_selected_feedback_required": case_id != L_DISABLED_CASE,
                "dry_run_only": True,
                "solver_run": False,
                "official_evaluator_run": False,
            }
        )
    return rows


def _build_case_plan(
    source_row: dict[str, Any],
    seed_row: dict[str, Any],
    dependency_row: dict[str, Any],
    runtime_root: Path,
) -> dict[str, Any]:
    case_id = source_row.get("case_id", "")
    is_m_clean = case_id == M_CLEAN_REPEAT_CASE
    is_l_disabled = case_id == L_DISABLED_CASE
    is_degraded = not is_m_clean and not is_l_disabled
    plan_rows: list[dict[str, Any]] = []
    command_rows: list[dict[str, Any]] = []
    clean_feedback_path = dependency_row.get("candidate_source", "") or dependency_row.get("path", "")
    planned_feedback_rel = f"same_case_feedback_plan/{case_id}/FGO_FEEDBACK_OBSERVATIONS.csv"
    stage1_command = ""
    stage2_command = ""
    mapped = False
    acceptance_mode = "blocked"
    blocked_reason = ""

    if is_l_disabled:
        mapped = True
        acceptance_mode = "feedback_disabled_marker"
        stage2_command = source_row.get("command", "") or _disabled_marker_command(case_id)
        command_rows.append(
            _command_row(
                case_id=case_id,
                plan_stage="stage2_selected_feedback_ekf",
                command=stage2_command,
                working_directory=source_row.get("working_directory", ""),
                planned_feedback_path="",
                source_row=source_row,
                seed_row=seed_row,
                dryrun_required=True,
            )
        )
    elif is_m_clean and dependency_row.get("clean_repeat_reuse_defensible") and clean_feedback_path:
        mapped = True
        acceptance_mode = "clean_repeat_feedback_reuse"
        stage2_config_rel = _selected_feedback_config_rel(case_id)
        stage2_command = _stage2_command(case_id, seed_row, stage2_config_rel, runtime_root)
        command_rows.append(
            _command_row(
                case_id=case_id,
                plan_stage="stage2_selected_feedback_ekf",
                command=stage2_command,
                working_directory=seed_row.get("working_directory", ""),
                planned_feedback_path=clean_feedback_path,
                source_row=source_row,
                seed_row=seed_row,
                dryrun_required=True,
                generated_config_path=stage2_config_rel,
                clean_repeat=True,
            )
        )
    elif seed_row.get("command"):
        mapped = True
        acceptance_mode = "two_stage_same_case_feedback_generation_plan"
        stage2_config_rel = _selected_feedback_config_rel(case_id)
        stage1_command = _stage1_command(case_id, seed_row, planned_feedback_rel, runtime_root)
        stage2_command = _stage2_command(case_id, seed_row, stage2_config_rel, runtime_root)
        plan_rows.extend(
            [
                _plan_row(case_id, "stage1_feedback_generation", planned_feedback_rel, stage1_command, source_row, seed_row),
                _plan_row(case_id, "stage2_selected_feedback_ekf", planned_feedback_rel, stage2_command, source_row, seed_row),
            ]
        )
        command_rows.extend(
            [
                _command_row(case_id, "stage1_feedback_generation", stage1_command, seed_row.get("working_directory", ""), planned_feedback_rel, source_row, seed_row, True),
                _command_row(
                    case_id,
                    "stage2_selected_feedback_ekf",
                    stage2_command,
                    seed_row.get("working_directory", ""),
                    planned_feedback_rel,
                    source_row,
                    seed_row,
                    True,
                    generated_config_path=stage2_config_rel,
                    clean_repeat=False,
                ),
            ]
        )
    else:
        blocked_reason = "blocked: no mapped same-case command seed available for dry-run feedback generation plan"

    if mapped and not plan_rows:
        plan_rows.append(
            _plan_row(
                case_id,
                "stage2_selected_feedback_ekf",
                clean_feedback_path if is_m_clean else "",
                stage2_command,
                source_row,
                seed_row,
                acceptance_mode=acceptance_mode,
            )
        )

    mapping_row = {
        "stage": STAGE,
        "case_id": case_id,
        "algorithm": SELECTED_FEEDBACK_ALGORITHM,
        "routing_status": source_row.get("routing_status", ""),
        "prior_mapping_status": source_row.get("mapping_status", ""),
        "mapping_status": "mapped" if mapped else "blocked",
        "acceptance_mode": acceptance_mode if mapped else "blocked",
        "blocked_reason": blocked_reason,
        "stage1_plan_exists": any(row["plan_stage"] == "stage1_feedback_generation" for row in plan_rows),
        "stage2_plan_exists": any(row["plan_stage"] == "stage2_selected_feedback_ekf" for row in plan_rows),
        "planned_same_case_feedback_path": planned_feedback_rel if acceptance_mode == "two_stage_same_case_feedback_generation_plan" else "",
        "clean_feedback_candidate_source": clean_feedback_path,
        "clean_n8j_path_used_for_degraded_case": bool(is_degraded and clean_feedback_path and "N8J_feedback_final_validation" in clean_feedback_path),
        "stage1_command": stage1_command,
        "stage2_command": stage2_command,
        "command_seed_algorithm": seed_row.get("algorithm", ""),
        "command_seed_case_id": seed_row.get("case_id", ""),
        "generated_config_path": _selected_feedback_config_rel(case_id) if mapped and not is_l_disabled else source_row.get("generated_config_path", ""),
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "output_substitution": False,
        "direct_nav_override": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "NAV_generated": False,
        "STD_generated": False,
        "EVAL_NAV_generated": False,
        "RUN_MANIFEST_generated": False,
        "figures_generated": False,
        "case_review_generated": False,
        "dry_run_only": True,
        "run_allowed_in_N9B1D": mapped,
        "ready_for_N9B1D_solver_execution": mapped,
        "ready_for_N9B2_execution": False,
    }
    return {"plan_rows": plan_rows, "mapping_row": mapping_row, "command_rows": command_rows}


def _stage1_command(case_id: str, seed_row: dict[str, Any], planned_feedback_rel: str, runtime_root: Path) -> str:
    base_command = str(seed_row.get("command", ""))
    feedback_out = _to_wsl_path(runtime_root / planned_feedback_rel)
    report_out = feedback_out.replace("FGO_FEEDBACK_OBSERVATIONS.csv", "OBSERVATION_BUILD_REPORT.json")
    baseline_eval = (seed_row.get("expected_outputs") or {}).get("EVAL_NAV", "")
    gnss_path = (seed_row.get("inputs") or {}).get("GNSS", "")
    generator = "python scripts/experiments/run_n9b1c2_selected_feedback_same_case_mapping.py"
    generator_args = " ".join(
        [
            "--generate-feedback-observations",
            "--case-id",
            _q(case_id),
            "--baseline-eval-nav",
            _q(baseline_eval),
            "--gnss-path",
            _q(gnss_path),
            "--output-observations",
            _q(feedback_out),
            "--output-report",
            _q(report_out),
        ]
    )
    return (
        f"{base_command} && {generator} {generator_args}"
    )


def _stage2_command(case_id: str, seed_row: dict[str, Any], config_rel: str, runtime_root: Path) -> str:
    entrypoint = str(seed_row.get("entrypoint", ""))
    config_path = _to_wsl_path(runtime_root / config_rel)
    wsl_audit_root = _audit_root_from_runtime(runtime_root)
    output_root = f"{wsl_audit_root}/{AUDIT_ROOT_NAME}/{FUTURE_SOLVER_STAGE}/algorithm_outputs/{case_id}/{SELECTED_FEEDBACK_ALGORITHM}"
    return (
        f"{_q(entrypoint)} --config {_q(config_path)} --output-dir {_q(output_root)}"
    )


def _disabled_marker_command(case_id: str) -> str:
    return (
        "printf "
        f"'N9B1C2 dry-run marker: {case_id} selected_feedback_EKF feedback disabled; no feedback observations consumed'"
    )


def _selected_feedback_config_rel(case_id: str) -> str:
    return f"repaired_command_plans/{case_id}/{SELECTED_FEEDBACK_ALGORITHM}/config.yaml"


def _audit_root_from_runtime(runtime_root: Path) -> str:
    try:
        workspace_root = runtime_root.resolve().parents[1]
    except IndexError:
        workspace_root = runtime_root.resolve()
    return _to_wsl_path(workspace_root)


def _to_wsl_path(path: Path | str) -> str:
    value = str(path)
    if value.startswith("/"):
        return value.replace("\\", "/")
    resolved = Path(value).resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = resolved.as_posix().split(":", 1)[-1].lstrip("/")
    return f"/mnt/{drive}/{rest}" if drive else resolved.as_posix()


def _q(value: Any) -> str:
    return shlex.quote(str(value))


def _plan_row(
    case_id: str,
    plan_stage: str,
    planned_feedback_path: str,
    command: str,
    source_row: dict[str, Any],
    seed_row: dict[str, Any],
    *,
    acceptance_mode: str = "two_stage_same_case_feedback_generation_plan",
) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "case_id": case_id,
        "algorithm": SELECTED_FEEDBACK_ALGORITHM,
        "plan_stage": plan_stage,
        "acceptance_mode": acceptance_mode,
        "planned_feedback_path": planned_feedback_path,
        "command_seed_algorithm": seed_row.get("algorithm", ""),
        "routing_status": source_row.get("routing_status", ""),
        "command": command,
        "command_plan_only": True,
        "dry_run_only": True,
        "executed": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "ready_for_N9B2_execution": False,
    }


def _command_row(
    case_id: str,
    plan_stage: str,
    command: str,
    working_directory: str,
    planned_feedback_path: str,
    source_row: dict[str, Any],
    seed_row: dict[str, Any],
    dryrun_required: bool,
    *,
    generated_config_path: str = "",
    clean_repeat: bool = False,
) -> dict[str, Any]:
    rel = f"repaired_command_plans/{case_id}/{SELECTED_FEEDBACK_ALGORITHM}/{plan_stage}/command_plan.json"
    return {
        "stage": STAGE,
        "case_id": case_id,
        "algorithm": SELECTED_FEEDBACK_ALGORITHM,
        "plan_stage": plan_stage,
        "command_type": "wsl_dryrun_command_plan",
        "command": command,
        "command_preview": command,
        "working_directory": working_directory,
        "planned_feedback_path": planned_feedback_path,
        "generated_config_path": generated_config_path,
        "clean_repeat": clean_repeat,
        "seed_generated_config_path": seed_row.get("generated_config_path", ""),
        "seed_generated_config_path_wsl": seed_row.get("generated_config_path_wsl", ""),
        "future_output_root": f"{AUDIT_ROOT_NAME}/{FUTURE_SOLVER_STAGE}/algorithm_outputs/{case_id}/{SELECTED_FEEDBACK_ALGORITHM}",
        "command_seed_algorithm": seed_row.get("algorithm", ""),
        "routing_status": source_row.get("routing_status", ""),
        "command_plan_json": rel,
        "command_plan_only": True,
        "dry_run_only": True,
        "dryrun_required": dryrun_required,
        "executed": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "NAV_generated": False,
        "STD_generated": False,
        "EVAL_NAV_generated": False,
        "RUN_MANIFEST_generated": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "output_substitution": False,
        "ready_for_N9B2_execution": False,
    }


def _wsl_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": row["case_id"],
        "algorithm": row["algorithm"],
        "plan_stage": row["plan_stage"],
        "command": row["command"],
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
        dryrun = dict(row)
        dryrun.update(
            {
                "log_path": _rel(runtime_root, log),
                "dryrun_returncode": completed.returncode,
                "dryrun_stdout_nonempty": bool((completed.stdout or "").strip()),
                "dryrun_stderr": (completed.stderr or "").strip(),
            }
        )
        output.append(dryrun)
    return output


def _input_readiness_matrix(inputs: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [
        {
            "matrix_name": name,
            "row_count": len(rows),
            "read": True,
            "selected_feedback_rows": sum(row.get("algorithm") == SELECTED_FEEDBACK_ALGORITHM for row in rows),
        }
        for name, rows in inputs.items()
    ]


def _write_command_plan(runtime_root: Path, row: dict[str, Any]) -> None:
    _write_json(runtime_root / row["command_plan_json"], row)


def _write_runtime_config(workspace_root: Path, runtime_root: Path, row: dict[str, Any]) -> None:
    config_rel = row.get("generated_config_path", "")
    if not config_rel:
        return
    seed_rel = row.get("seed_generated_config_path", "")
    seed_path = workspace_root / AUDIT_ROOT_NAME / N9B1C_STAGE / seed_rel if seed_rel else None
    if seed_path is not None and seed_path.is_file():
        text = seed_path.read_text(encoding="utf-8")
    else:
        text = "runtime_only_notice: \"N9B1C2 generated selected-feedback config\"\n"
    feedback_path = row.get("planned_feedback_path", "")
    if feedback_path and not row.get("clean_repeat"):
        feedback_path = _to_wsl_path(runtime_root / feedback_path)
    output_root = _to_wsl_path(workspace_root / AUDIT_ROOT_NAME / FUTURE_SOLVER_STAGE / "algorithm_outputs" / row["case_id"] / SELECTED_FEEDBACK_ALGORITHM)
    additions = [
        "",
        "# N9B1C2 selected-feedback same-case mapping; runtime-only config.",
        f"stage: \"{STAGE}\"",
        f"algorithm: \"{SELECTED_FEEDBACK_ALGORITHM}\"",
        f"outputpath: \"{output_root}\"",
        "enable_fgo_feedback: true",
        f"fgo_feedback_path: \"{feedback_path}\"",
        "fgo_feedback_mode: pseudo_measurement",
        "fgo_feedback_position_enabled: false",
        "fgo_feedback_velocity_enabled: true",
        "fgo_feedback_attitude_enabled: true",
        "fgo_feedback_no_future_data_required: true",
        "trace_solver_input: false",
        "final_v23_solver_input: false",
        "paper_performance_claim: false",
        "n9b1c2_config_mapping_only: true",
    ]
    path = runtime_root / config_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n" + "\n".join(additions) + "\n", encoding="utf-8")


def _write_outputs(runtime_root: Path, result: dict[str, Any]) -> None:
    reports = {
        "N9B1C2_FEEDBACK_PIPELINE_INVENTORY_REPORT.json": result["feedback_pipeline_inventory_report"],
        "N9B1C2_SAME_CASE_FEEDBACK_COMMAND_PLAN_REPORT.json": result["same_case_feedback_command_plan_report"],
        "N9B1C2_CLEAN_REPEAT_FEEDBACK_POLICY_REPORT.json": result["clean_repeat_feedback_policy_report"],
        "N9B1C2_WSL_DRYRUN_REPORT.json": result["wsl_dryrun_report"],
        "N9B1C2_VALIDATION_REPORT.json": result["validation_report"],
        "N9B1C2_DECISION_REPORT.json": result["decision_report"],
    }
    for name, payload in reports.items():
        _write_json(runtime_root / "reports" / name, payload)
    matrices = {
        "N9B1C2_FEEDBACK_PIPELINE_INVENTORY": result["feedback_pipeline_inventory"],
        "N9B1C2_SELECTED_FEEDBACK_SAME_CASE_PLAN": result["same_case_feedback_plan_matrix"],
        "N9B1C2_COMMAND_MAPPING_MATRIX_REPAIRED": result["command_mapping_matrix_repaired"],
        "N9B1C2_SELECTED_FEEDBACK_MAPPING_DIFF": result["selected_feedback_mapping_diff"],
        "N9B1C2_WSL_DRYRUN_COMMAND_MATRIX": result["wsl_dryrun_command_matrix"],
        "N9B1C2_INPUT_MATRIX_READINESS": result["input_matrix_readiness"],
        "N9B1C2_SELECTED_FEEDBACK_MAPPING_MATRIX": result["selected_feedback_mapping_matrix"],
        "N9B1C2_REPAIRED_COMMAND_PLAN_MATRIX": result["repaired_command_plan_matrix"],
    }
    for stem, rows in matrices.items():
        _write_table_pair(runtime_root / "matrix" / stem, rows)
    _write_table_pair(runtime_root / "feedback_pipeline_inventory" / "N9B1C2_FEEDBACK_PIPELINE_INVENTORY", result["feedback_pipeline_inventory"])
    _write_table_pair(runtime_root / "same_case_feedback_plan" / "N9B1C2_SAME_CASE_FEEDBACK_PLAN_MATRIX", result["same_case_feedback_plan_matrix"])
    _write_table_pair(runtime_root / "repaired_command_plans" / "N9B1C2_REPAIRED_COMMAND_PLAN_MATRIX", result["repaired_command_plan_matrix"])
    _write_table_pair(runtime_root / "wsl_dryrun" / "N9B1C2_WSL_DRYRUN_COMMAND_MATRIX", result["wsl_dryrun_command_matrix"])
    _write_json(runtime_root / "validation" / "N9B1C2_VALIDATION_REPORT.json", result["validation_report"])
    (runtime_root / "summary" / "n9b1c2_selected_feedback_mapping_summary.md").write_text(_summary(result), encoding="utf-8")
    (runtime_root / "summary" / "n9b1c2_next_stage_recommendation.md").write_text(_next_stage(result), encoding="utf-8")


def _summary(result: dict[str, Any]) -> str:
    report = result["clean_repeat_feedback_policy_report"]
    return (
        "# N9B1C2 selected-feedback same-case mapping\n\n"
        f"- selected_feedback_rows={report['selected_feedback_rows']}\n"
        f"- mapped_rows={report['mapped_rows']}\n"
        f"- blocked_rows={report['blocked_rows']}\n"
        "- actual_feedback_generation_run=false\n"
        "- solver/evaluator run=false\n"
    )


def _next_stage(result: dict[str, Any]) -> str:
    decision = result["decision_report"]
    return (
        "# N9B1C2 next stage recommendation\n\n"
        f"- status={decision['status']}\n"
        f"- ready_for_N9B1D_solver_execution={str(decision['ready_for_N9B1D_solver_execution']).lower()}\n"
        "- ready_for_N9B2_execution=false\n"
        "- Stage 1 and Stage 2 remain dry-run command plans until human approval.\n"
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


def _has_stale_placeholder(row: dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key, ""))
        for key in ["blocked_reason", "block_reason", "stage1_command", "stage2_command"]
    ).lower()
    return any(token in text for token in ["placeholder solver entrypoint", "future_solver_entry", "no real executable"])


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
