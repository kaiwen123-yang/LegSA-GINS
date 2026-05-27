"""N9G1B Phase 1 contracts for the separate LegSA_9F_FGO_EKF candidate.

This module is deliberately limited to identity, provider/factor contract
audits, logger schemas, and safety gates. It does not implement an optimizer or
convert the existing LegSA_full_EKF runner into an active nine-factor FGO.
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from legsa_gins.reporting.by2_algorithm_runner import (
    ALGORITHM_SPECS,
    REPO_RELATIVE_REQUIRED_INPUTS,
    build_algorithm_config_text,
    load_base_config_values,
    write_json,
)


STAGE = "N9G1B_IMPLEMENT_LEGSA_9F_FGO_EKF_PHASE1_PROVIDER_FACTOR_LOGGER_AND_NORMAL_SMOKE"
LONG_STAGE = "N9G1A_TO_N9G1B_CONTEXT_LOCK_AND_LEGSA_9F_PHASE1_IMPLEMENTATION"
ALGORITHM_ID = "LegSA_9F_FGO_EKF"
LEGSA_FULL_ID = "LegSA_full_EKF"
NORMAL_CASE_ID = "FULL_normal_repeat"

RUNTIME_SUBDIRS = [
    "00_supervisor",
    "01_plan",
    "n9g1a_context_lock",
    "provider_contract_validation",
    "factor_wiring",
    "logger_schema",
    "runner_mapping",
    "dry_run",
    "normal_smoke",
    "official_eval",
    "evidence_tables",
    "context_update",
    "obsidian_sync",
    "export_clean",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
    "blocked",
]


@dataclass(frozen=True)
class Phase1Factor:
    factor_type: str
    provider: str
    intended_status_in_n9g1b: str
    residual_dim: int
    code_symbol_path: str
    required_logger_fields: tuple[str, ...]
    candidate_only: bool = False
    required_provider: str = ""


NINE_FACTORS: tuple[Phase1Factor, ...] = (
    Phase1Factor("ReceiverPositionFactor", "gnss_position", "active_target", 3, "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp", ("residual_components", "factor_rows", "cost_contribution")),
    Phase1Factor("ReceiverVelocityFactor", "gnss_velocity", "active_target", 3, "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp", ("residual_components", "factor_rows", "cost_contribution")),
    Phase1Factor("DualYawFactor", "dual_yaw", "active_target", 1, "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp", ("residual_components", "factor_rows", "cost_contribution")),
    Phase1Factor("RawDopplerVelocityFactor", "raw_doppler", "active_target", 3, "src/legsa_gins/fgo/fgo_raw_doppler_solver_injection.py", ("residual_components", "factor_rows", "jacobian_nonzero", "cost_contribution")),
    Phase1Factor("Go2ProprioceptiveJointFactor", "go2_joint", "active_target", 4, "src/legsa_gins/fgo/fgo_factor_registry.py", ("residual_components", "factor_rows", "jacobian_nonzero", "cost_contribution")),
    Phase1Factor("FootKinematicVelocityFactor", "foot_kinematic_velocity", "design_only_target", 2, "src/legsa_gins/fgo/fgo_foot_kinematic_velocity_factor.py", ("foot_kinematic_velocity", "contact_aware_weight_scale"), candidate_only=True),
    Phase1Factor("YawRateBetweenFactor", "yaw_rate", "design_only_target", 1, "src/legsa_gins/fgo/fgo_yawrate_between_factor.py", ("yaw_rate_between_residual",), candidate_only=True),
    Phase1Factor("RelativeOdometryBetweenFactor", "relative_odometry", "design_only_target", 2, "src/legsa_gins/fgo/fgo_relative_odometry_between_factor.py", ("relative_odometry_residual",), candidate_only=True),
    Phase1Factor("SmoothnessFactor", "window_smoothness", "active_target", 9, "src/legsa_gins/fgo/fgo_linear_solver.py", ("residual_components", "factor_rows", "cost_contribution"), required_provider="window_state"),
)

FGO_WINDOW_SUMMARY_FIELDS = [
    "run_id",
    "case_id",
    "seed",
    "algorithm_id",
    "window_id",
    "time_start",
    "time_end",
    "state_count",
    "factor_count",
    "total_residual_dim",
    "total_cost",
    "solver_iterations",
    "convergence_status",
]

FGO_FACTOR_RESIDUAL_FIELDS = [
    "run_id",
    "case_id",
    "seed",
    "algorithm_id",
    "window_id",
    "epoch_time",
    "factor_id",
    "factor_type",
    "measurement_type",
    "active_or_candidate",
    "residual_dim",
    "residual_components",
    "residual_norm",
    "whitened_residual_norm",
    "sigma_or_weight",
    "mahalanobis_or_nis_proxy",
    "cost_contribution",
    "factor_rows",
    "jacobian_nonzero",
    "gate_state",
    "accept_reject_state",
    "reject_reason",
    "provider_source",
    "source_role",
]

FGO_FACTOR_COVERAGE_FIELDS = [
    "case_id",
    "factor_type",
    "windows_present",
    "epochs_present",
    "rows_present",
    "residual_time_series_present",
    "cost_present",
    "status",
]

LEGGED_DIAGNOSTIC_FIELDS = [
    "case_id",
    "seed",
    "time",
    "contact_probability",
    "slip_risk",
    "foot_kinematic_velocity",
    "yaw_rate_between_residual",
    "relative_odometry_residual",
    "go2_joint_residual",
    "go2_attitude_prior_residual",
    "go2_horizontal_velocity_prior_residual",
    "contact_aware_weight_scale",
    "provider_update_count",
    "diagnostic_status",
]

FEEDBACK_TRACE_FIELDS = [
    "case_id",
    "seed",
    "time",
    "feedback_source",
    "correction_norm",
    "covariance_norm",
    "gate_state",
    "accept_reject_state",
    "reject_reason",
    "source_role",
]

LOGGER_SCHEMAS: dict[str, list[str]] = {
    "fgo_window_summary": FGO_WINDOW_SUMMARY_FIELDS,
    "fgo_factor_residual_timeseries": FGO_FACTOR_RESIDUAL_FIELDS,
    "fgo_factor_coverage": FGO_FACTOR_COVERAGE_FIELDS,
    "legged_diagnostic_timeseries": LEGGED_DIAGNOSTIC_FIELDS,
    "feedback_trace": FEEDBACK_TRACE_FIELDS,
}


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def logger_schemas() -> dict[str, list[str]]:
    return {name: list(fields) for name, fields in LOGGER_SCHEMAS.items()}


def classify_factor_evidence(evidence: Mapping[str, Any]) -> str:
    if evidence.get("provider_update_count_only") is True:
        return "blocked_provider_update_count_only"
    if evidence.get("candidate_only") is True and evidence.get("integrated_active_fgo") is not True:
        return "candidate_only"
    required = [
        "code_symbol_exists",
        "runtime_enabled",
        "instantiated",
        "contributes_rows",
        "residual_evaluated",
        "residual_dim_recorded",
        "timestamps_recorded",
        "window_ids_recorded",
    ]
    missing = [key for key in required if evidence.get(key) is not True]
    has_cost = evidence.get("cost_contribution_recorded") is True or bool(evidence.get("cost_unavailable_reason"))
    if missing:
        return "blocked_missing_" + missing[0]
    if not has_cost:
        return "blocked_missing_cost"
    return "active"


def normal_smoke_gate(
    *,
    provider_decision: str,
    static_validation_status: str,
    logger_schema_valid: bool,
    safety_violation: bool,
) -> dict[str, Any]:
    spec = ALGORITHM_SPECS[ALGORITHM_ID]
    blockers: list[str] = []
    if provider_decision not in {"provider_contracts_passed", "partial_provider_contracts_passed"}:
        blockers.append("provider_contracts_blocked")
    if static_validation_status != "pass":
        blockers.append("static_validation_not_passed")
    if not logger_schema_valid:
        blockers.append("logger_schema_invalid")
    if safety_violation:
        blockers.append("safety_violation")
    if not spec.active_fgo_backend_available:
        blockers.append("active_nine_factor_fgo_backend_unavailable")
    if not spec.solver_execution_allowed:
        blockers.append("candidate_solver_execution_disabled")
    return {
        "stage": "N9G1B_NORMAL_SMOKE_GATE",
        "algorithm_id": ALGORITHM_ID,
        "ready_for_normal_smoke": not blockers,
        "decision": "ready_for_normal_smoke" if not blockers else "normal_smoke_not_run_blocked_by_gate",
        "blockers": blockers,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_substitution": False,
        "representative_degradation": False,
        "full_matrix": False,
    }


def validate_logger_schemas() -> list[dict[str, Any]]:
    required = {
        "fgo_window_summary": FGO_WINDOW_SUMMARY_FIELDS,
        "fgo_factor_residual_timeseries": FGO_FACTOR_RESIDUAL_FIELDS,
        "fgo_factor_coverage": FGO_FACTOR_COVERAGE_FIELDS,
        "legged_diagnostic_timeseries": LEGGED_DIAGNOSTIC_FIELDS,
        "feedback_trace": FEEDBACK_TRACE_FIELDS,
    }
    rows = []
    for name, fields in required.items():
        actual = LOGGER_SCHEMAS.get(name, [])
        missing = [field for field in fields if field not in actual]
        rows.append(
            {
                "schema": name,
                "field_count": len(actual),
                "missing_fields": missing,
                "status": "pass" if not missing else "fail",
                "schema_only_no_solver_rows": True,
            }
        )
    return rows


def build_phase1_scope_rows(workspace_root: Path) -> list[dict[str, Any]]:
    spec = ALGORITHM_SPECS[ALGORITHM_ID]
    rows: list[dict[str, Any]] = []
    for factor in NINE_FACTORS:
        symbol_exists = (workspace_root / factor.code_symbol_path).exists()
        evidence_status = classify_factor_evidence(
            {
                "code_symbol_exists": symbol_exists,
                "runtime_enabled": False,
                "instantiated": False,
                "contributes_rows": False,
                "residual_evaluated": False,
                "residual_dim_recorded": False,
                "timestamps_recorded": False,
                "window_ids_recorded": False,
                "cost_unavailable_reason": "active_fgo_backend_unavailable",
                "candidate_only": factor.candidate_only,
                "integrated_active_fgo": False,
            }
        )
        rows.append(
            {
                "factor_type": factor.factor_type,
                "intended_status_in_N9G1B": factor.intended_status_in_n9g1b,
                "existing_code_symbol": symbol_exists,
                "code_symbol_path": factor.code_symbol_path,
                "provider_source": factor.provider,
                "required_code_changes": "active FGO window/backend integration" if not spec.active_fgo_backend_available else "none",
                "required_config": "LegSA_9F_FGO_EKF candidate config",
                "required_logger_fields": list(factor.required_logger_fields),
                "risk_level": "high" if factor.candidate_only else "medium",
                "can_attempt_in_N9G1B": False,
                "stop_condition": "no active FGO backend with row-level residual/Jacobian/cost logging",
                "phase1_status": evidence_status,
            }
        )
    return rows


def build_provider_contract_rows(workspace_root: Path) -> list[dict[str, Any]]:
    base_values, base_config = load_base_config_values(workspace_root)
    providers = [
        ("GNSS position", "locked_clean_replay_config", "<LOCKED_NORMAL_CONFIG>:gnsspath", ["time", "lat", "lon", "height", "std"], bool(base_values.get("gnsspath"))),
        ("GNSS velocity", "locked_clean_replay_config", "<LOCKED_NORMAL_CONFIG>:gnsspath", ["time", "vn", "ve", "vd", "std"], bool(base_values.get("gnsspath"))),
        ("dual yaw", "locked_clean_replay_config", "<LOCKED_NORMAL_CONFIG>:gnsspath", ["time", "yaw", "yaw_std"], bool(base_values.get("gnsspath"))),
        ("Raw Doppler", "repo_runtime", str(REPO_RELATIVE_REQUIRED_INPUTS["raw_doppler"]), ["time", "vn_mps", "ve_mps", "vd_mps", "std"], (workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["raw_doppler"]).exists()),
        ("Go2 joint", "repo_runtime", str(REPO_RELATIVE_REQUIRED_INPUTS["go2_joint"]), ["time", "roll", "pitch", "vn", "ve", "std"], (workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["go2_joint"]).exists()),
        ("Go2 attitude", "repo_runtime", str(REPO_RELATIVE_REQUIRED_INPUTS["go2_attitude"]), ["time", "roll", "pitch", "std"], (workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["go2_attitude"]).exists()),
        ("Go2 horizontal velocity", "repo_runtime", str(REPO_RELATIVE_REQUIRED_INPUTS["go2_horizontal_velocity"]), ["time", "vn", "ve", "std"], (workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["go2_horizontal_velocity"]).exists()),
        ("foot kinematic velocity", "candidate_provider", "N7C5_foot_kinematic_velocity_candidate", ["time", "foot_vn", "foot_ve", "contact_probability"], False),
        ("yaw-rate", "candidate_provider", "N7C5_go2_yaw_speed_candidate", ["time", "yaw_rate", "dt"], False),
        ("relative odometry", "candidate_provider", "N7C5_go2_relative_odometry_increment_candidate", ["time", "delta_n", "delta_e", "dt"], False),
        ("contact probability", "candidate_provider", "N7C5_contact_probability_candidate", ["time", "contact_probability"], False),
        ("slip risk", "candidate_provider", "N7C5_slip_risk_candidate", ["time", "slip_risk"], False),
        ("feedback observations", "repo_runtime", str(REPO_RELATIVE_REQUIRED_INPUTS["selected_feedback"]), ["time", "velocity", "attitude", "covariance"], (workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["selected_feedback"]).exists()),
    ]
    rows: list[dict[str, Any]] = []
    for name, source_root, source_path, columns, exists in providers:
        rows.append(
            {
                "provider": name,
                "source_exists": exists,
                "source_path": source_path,
                "source_root": source_root,
                "rows": "not_counted_phase1_no_solver",
                "required_columns": columns,
                "units": "provider_contract_specific",
                "frame": "provider_contract_specific",
                "timestamp": "required",
                "quality_fields": "required where available",
                "parse_status": "source_available_not_parsed" if exists else "blocked_missing_source",
                "ready_for_factor": False,
                "blocker": "" if exists else "source missing or candidate-only provider not materialized",
                "base_config": str(base_config) if base_config else "<LOCKED_NORMAL_CONFIG_MISSING>",
            }
        )
    return rows


def provider_decision(rows: list[dict[str, Any]]) -> str:
    ready = [row for row in rows if row.get("ready_for_factor") is True]
    if len(ready) == len(rows):
        return "provider_contracts_passed"
    if ready:
        return "partial_provider_contracts_passed"
    return "provider_contracts_blocked"


def build_factor_wiring_rows(workspace_root: Path) -> list[dict[str, Any]]:
    rows = []
    for scope in build_phase1_scope_rows(workspace_root):
        rows.append(
            {
                "factor_type": scope["factor_type"],
                "algorithm_id": ALGORITHM_ID,
                "code_symbol_exists": scope["existing_code_symbol"],
                "provider_source": scope["provider_source"],
                "runtime_enabled": False,
                "instantiated": False,
                "contributes_rows": False,
                "residual_rows_recorded": False,
                "cost_recorded": False,
                "jacobian_nonzero_recorded": False,
                "active_or_candidate": "candidate_only" if scope["phase1_status"] == "candidate_only" else "blocked",
                "wiring_status": scope["phase1_status"],
                "blocker": scope["stop_condition"],
            }
        )
    return rows


def build_factor_evidence_rows(workspace_root: Path) -> list[dict[str, Any]]:
    return [
        {
            "case_id": NORMAL_CASE_ID,
            "algorithm_id": ALGORITHM_ID,
            "factor_type": row["factor_type"],
            "windows_present": 0,
            "epochs_present": 0,
            "rows_present": 0,
            "residual_time_series_present": False,
            "cost_present": False,
            "status": row["wiring_status"],
            "active_factor_claim": False,
        }
        for row in build_factor_wiring_rows(workspace_root)
    ]


def build_legged_evidence_rows() -> list[dict[str, Any]]:
    names = [
        "contact_probability",
        "slip_risk",
        "foot_kinematic_velocity",
        "yaw_rate_between_residual",
        "relative_odometry_residual",
        "Go2_joint_residual",
        "Go2_attitude_prior_residual",
        "Go2_horizontal_velocity_prior_residual",
        "contact_aware_weight_scale",
    ]
    return [
        {
            "case_id": NORMAL_CASE_ID,
            "algorithm_id": ALGORITHM_ID,
            "diagnostic": name,
            "rows_present": 0,
            "time_series_present": False,
            "status": "blocked_no_normal_smoke_rows",
            "active_physical_residual_claim": False,
        }
        for name in names
    ]


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = fieldnames or []
    if not keys:
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in keys})


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_table_pair(path_stem: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    write_json(path_stem.with_suffix(".json"), rows)
    _write_csv(path_stem.with_suffix(".csv"), rows, fieldnames)


def _write_summary(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def _write_schema_tables(runtime_root: Path) -> None:
    for name, fields in LOGGER_SCHEMAS.items():
        write_json(runtime_root / "logger_schema" / f"{name}.json", [])
        _write_csv(runtime_root / "logger_schema" / f"{name}.csv", [], fields)


def prepare_runtime_tree(runtime_root: Path) -> None:
    for subdir in RUNTIME_SUBDIRS:
        (runtime_root / subdir).mkdir(parents=True, exist_ok=True)


def write_phase1_artifacts(
    workspace_root: Path,
    runtime_root: Path,
    *,
    static_validation_status: str = "not_run",
    static_validation_rows: list[dict[str, Any]] | None = None,
    context_sync_status: str = "pending",
) -> dict[str, Any]:
    prepare_runtime_tree(runtime_root)
    created = now_utc()
    spec = ALGORITHM_SPECS[ALGORITHM_ID]
    scope_rows = build_phase1_scope_rows(workspace_root)
    provider_rows = build_provider_contract_rows(workspace_root)
    provider_status = provider_decision(provider_rows)
    factor_rows = build_factor_wiring_rows(workspace_root)
    schema_rows = validate_logger_schemas()
    schema_valid = all(row["status"] == "pass" for row in schema_rows)
    static_rows = static_validation_rows or [
        {
            "check": "static_validation",
            "status": static_validation_status,
            "evidence": "provided by supervisor after py_compile/tests",
        }
    ]
    gate = normal_smoke_gate(
        provider_decision=provider_status,
        static_validation_status=static_validation_status,
        logger_schema_valid=schema_valid,
        safety_violation=False,
    )
    config_path = runtime_root / "dry_run" / "LegSA_9F_FGO_EKF_FULL_normal_repeat.runtime_config.yaml"
    base_values, _base = load_base_config_values(workspace_root)
    config_path.write_text(
        build_algorithm_config_text(workspace_root, ALGORITHM_ID, runtime_root / "normal_smoke", base_values),
        encoding="utf-8",
    )
    _write_schema_tables(runtime_root)

    reports = {
        "N9G1B_PHASE1_SCOPE_REPORT.json": {
            "stage": STAGE,
            "created_utc": created,
            "algorithm_id": ALGORITHM_ID,
            "legsa_full_relabel": False,
            "complete_nine_factor_FGO_claim": False,
            "rows": scope_rows,
        },
        "N9G1B_SOURCE_CAPABILITY_REFRESH_REPORT.json": {
            "stage": "N9G1B_SOURCE_CAPABILITY_REFRESH",
            "created_utc": created,
            "active_fgo_backend_available": spec.active_fgo_backend_available,
            "candidate_solver_execution_allowed": spec.solver_execution_allowed,
            "source_capability_decision": "active_backend_absent_phase1_contracts_only",
            "rows": provider_rows,
        },
        "N9G1B_PROVIDER_CONTRACT_VALIDATION_REPORT.json": {
            "stage": "N9G1B_PROVIDER_CONTRACT_VALIDATION",
            "created_utc": created,
            "decision": provider_status,
            "rows": provider_rows,
        },
        "N9G1B_RUNNER_CONFIG_MATERIALIZATION_REPORT.json": {
            "stage": "N9G1B_RUNNER_CONFIG_MATERIALIZATION",
            "created_utc": created,
            "algorithm_id": ALGORITHM_ID,
            "role": spec.role,
            "distinct_from_LegSA_full_EKF": ALGORITHM_ID != LEGSA_FULL_ID,
            "config_path": str(config_path),
            "trace_solver_input": False,
            "final_v23_solver_input": False,
            "output_substitution": False,
            "clean_feedback_for_degraded": False,
            "solver_execution_allowed": spec.solver_execution_allowed,
        },
        "N9G1B_FACTOR_WIRING_REPORT.json": {
            "stage": "N9G1B_FACTOR_WIRING",
            "created_utc": created,
            "algorithm_id": ALGORITHM_ID,
            "active_factors_marked": 0,
            "candidate_factors_marked_active": False,
            "rows": factor_rows,
        },
        "N9G1B_LOGGER_IMPLEMENTATION_REPORT.json": {
            "stage": "N9G1B_LOGGER_IMPLEMENTATION",
            "created_utc": created,
            "schema_only_no_solver_rows": True,
            "schemas": logger_schemas(),
            "schema_validation": schema_rows,
        },
        "N9G1B_STATIC_VALIDATION_REPORT.json": {
            "stage": "N9G1B_STATIC_VALIDATION",
            "created_utc": created,
            "status": static_validation_status,
            "rows": static_rows,
        },
        "N9G1B_NORMAL_SMOKE_GATE_REPORT.json": gate,
        "N9G1B_NORMAL_SMOKE_REPORT.json": {
            "stage": "N9G1B_NORMAL_SMOKE",
            "created_utc": created,
            "case_id": NORMAL_CASE_ID,
            "algorithm_id": ALGORITHM_ID,
            "decision": "N9G1B_normal_smoke_not_run_blocked_by_gate",
            "solver_completed": False,
            "evaluator_completed": False,
            "gate": gate,
        },
        "N9G1B_CONTEXT_OBSIDIAN_SYNC_REPORT.json": {
            "stage": "N9G1B_CONTEXT_OBSIDIAN_SYNC",
            "created_utc": created,
            "status": context_sync_status,
            "tracked_docs_updated": context_sync_status == "complete",
            "obsidian_untracked": True,
        },
        "LONG_TASK_VALIDATION_REPORT.json": {
            "stage": LONG_STAGE,
            "created_utc": created,
            "step1_passed_before_step2": True,
            "no_old_algorithm_relabeling": True,
            "no_final_v23_modification": True,
            "no_single_baseline_modification": True,
            "no_fabricated_residuals": True,
            "no_aggregate_as_timeseries": True,
            "no_candidate_as_active": True,
            "no_provider_update_as_physical_residual": True,
            "trace_solver_input": False,
            "final_v23_solver_input": False,
            "output_substitution": False,
            "representative_degradation": False,
            "full_matrix": False,
            "normal_smoke_run": False,
            "json_csv_parse": "checked_after_generation",
            "git_diff_check": "checked_after_generation",
            "changed_tracked_path_leak_scan": "checked_after_generation",
            "runtime_untracked": True,
            "obsidian_untracked": True,
            "pr_merged": False,
            "tag_created": False,
            "paper_claims": False,
        },
        "LONG_TASK_DECISION_REPORT.json": {
            "stage": LONG_STAGE,
            "created_utc": created,
            "decision": "N9G1_context_locked_provider_or_factor_blocked",
            "ready_for_N9G2_representative_validation": False,
            "ready_for_paper_claims": False,
            "ready_for_N9B2_execution": False,
            "ready_for_full_N9B_execution": False,
            "recommended_next_stage": "fix_provider_or_factor_model",
        },
    }
    for name, payload in reports.items():
        write_json(runtime_root / "reports" / name, payload)

    _write_table_pair(runtime_root / "matrix" / "N9G1B_PHASE1_SCOPE_MATRIX", scope_rows)
    _write_table_pair(runtime_root / "matrix" / "N9G1B_SOURCE_CAPABILITY_REFRESH", provider_rows)
    _write_table_pair(runtime_root / "matrix" / "N9G1B_PROVIDER_CONTRACT_VALIDATION", provider_rows)
    _write_table_pair(
        runtime_root / "matrix" / "N9G1B_CONFIG_INDEX",
        [
            {
                "algorithm_id": ALGORITHM_ID,
                "role": spec.role,
                "config_path": str(config_path),
                "trace_solver_input": False,
                "final_v23_solver_input": False,
                "output_substitution": False,
                "solver_execution_allowed": spec.solver_execution_allowed,
            }
        ],
    )
    _write_table_pair(runtime_root / "matrix" / "N9G1B_FACTOR_WIRING_STATUS", factor_rows)
    _write_table_pair(runtime_root / "matrix" / "N9G1B_LOGGER_SCHEMA_VALIDATION", schema_rows)
    _write_table_pair(runtime_root / "matrix" / "N9G1B_STATIC_VALIDATION", static_rows)
    _write_table_pair(
        runtime_root / "matrix" / "N9G1B_NORMAL_SMOKE_GATE",
        [
            {
                "algorithm_id": ALGORITHM_ID,
                "ready_for_normal_smoke": gate["ready_for_normal_smoke"],
                "decision": gate["decision"],
                "blockers": gate["blockers"],
            }
        ],
    )
    _write_table_pair(
        runtime_root / "matrix" / "N9G1B_NORMAL_SMOKE_STATUS",
        [
            {
                "case_id": NORMAL_CASE_ID,
                "algorithm_id": ALGORITHM_ID,
                "solver_completed": False,
                "evaluator_completed": False,
                "decision": "N9G1B_normal_smoke_not_run_blocked_by_gate",
            }
        ],
    )
    _write_table_pair(runtime_root / "matrix" / "N9G1B_NORMAL_METRICS", [])
    _write_table_pair(runtime_root / "matrix" / "N9G1B_FACTOR_EVIDENCE", build_factor_evidence_rows(workspace_root))
    _write_table_pair(runtime_root / "matrix" / "N9G1B_LEGGED_EVIDENCE", build_legged_evidence_rows())
    _write_table_pair(
        runtime_root / "matrix" / "N9G1B_OBSIDIAN_SYNC_INDEX",
        [
            {"path": "obsidian_knowledge/LegSA-GINS/N9G1B_legsa_9f_phase1/00_INDEX.md", "note_type": "public", "path_policy": "aliases_only", "staged": False},
            {"path": "obsidian_knowledge/LegSA-GINS/N9G1B_legsa_9f_phase1/01_CURRENT_STATE.md", "note_type": "public", "path_policy": "aliases_only", "staged": False},
            {"path": "obsidian_knowledge/LegSA-GINS/N9G1B_legsa_9f_phase1/02_PROVIDER_CONTRACT_STATUS.md", "note_type": "public", "path_policy": "aliases_only", "staged": False},
            {"path": "obsidian_knowledge/LegSA-GINS/N9G1B_legsa_9f_phase1/03_FACTOR_WIRING_STATUS.md", "note_type": "public", "path_policy": "aliases_only", "staged": False},
            {"path": "obsidian_knowledge/LegSA-GINS/N9G1B_legsa_9f_phase1/04_LOGGER_STATUS.md", "note_type": "public", "path_policy": "aliases_only", "staged": False},
            {"path": "obsidian_knowledge/LegSA-GINS/N9G1B_legsa_9f_phase1/05_NORMAL_SMOKE_RESULT.md", "note_type": "public", "path_policy": "aliases_only", "staged": False},
            {"path": "obsidian_knowledge/LegSA-GINS/N9G1B_legsa_9f_phase1/06_CLAIM_BOUNDARY.md", "note_type": "public", "path_policy": "aliases_only", "staged": False},
            {"path": "obsidian_knowledge/LegSA-GINS/N9G1B_legsa_9f_phase1/07_NEXT_STEPS.md", "note_type": "public", "path_policy": "aliases_only", "staged": False},
            {"path": "obsidian_knowledge/LegSA-GINS/N9G1B_legsa_9f_phase1/99_LOCAL_PATHS.private.md", "note_type": "private", "path_policy": "local_paths_allowed_untracked", "staged": False},
        ],
    )
    _write_table_pair(
        runtime_root / "matrix" / "LONG_TASK_STAGE_STATUS",
        [
            {"step": "N9G1A_context_lock", "status": "passed", "decision": "N9G1A_context_lock_complete"},
            {"step": "N9G1B_phase1", "status": "blocked", "decision": "N9G1_context_locked_provider_or_factor_blocked"},
            {"step": "normal_smoke", "status": "not_run", "decision": "N9G1B_normal_smoke_not_run_blocked_by_gate"},
        ],
    )

    _write_summary(runtime_root / "summary" / "n9g1b_phase1_scope.md", "N9G1B Phase 1 Scope", ["- LegSA_9F_FGO_EKF is a separate candidate algorithm ID.", "- Active FGO backend is unavailable in this phase.", "- Normal smoke is blocked rather than relabeling LegSA_full_EKF."])
    _write_summary(runtime_root / "summary" / "n9g1b_provider_contract_validation.md", "N9G1B Provider Contract Validation", [f"- Decision: {provider_status}.", "- Missing provider sources and absent active backend block factor activation."])
    _write_summary(runtime_root / "summary" / "n9g1b_runner_config_materialization.md", "N9G1B Runner Config Materialization", [f"- Config: {config_path.name}.", "- Solver execution is disabled for the candidate until active FGO backend exists."])
    _write_summary(runtime_root / "summary" / "n9g1b_normal_smoke_summary.md", "N9G1B Normal Smoke Summary", ["- Normal smoke was not run.", "- Gate decision: N9G1B_normal_smoke_not_run_blocked_by_gate."])
    _write_summary(runtime_root / "summary" / "long_task_summary.md", "N9G1 Long Task Summary", ["- Step 1 context lock passed before Step 2.", "- Step 2 created candidate identity/schema/gate support.", "- Active FGO backend and provider/factor model gaps block normal smoke."])
    _write_summary(runtime_root / "summary" / "long_task_next_stage_recommendation.md", "N9G1 Next Stage Recommendation", ["- Decision: N9G1_context_locked_provider_or_factor_blocked.", "- ready_for_N9G2_representative_validation=false.", "- ready_for_paper_claims=false.", "- Recommended next stage: fix_provider_or_factor_model."])
    return {
        "provider_decision": provider_status,
        "normal_smoke_gate": gate,
        "static_validation_status": static_validation_status,
        "runtime_root": str(runtime_root),
    }
