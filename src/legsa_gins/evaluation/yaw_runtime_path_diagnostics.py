"""Runtime yaw path issue classification for N4H2C-runtime.

中文说明：这里做的是诊断分类，不改 solver、不调参、不把 trace/reference 放入
solver input，也不做 output-only correction。
"""

from __future__ import annotations

from typing import Any


def _input_matches(report: dict[str, Any]) -> bool:
    status = (report.get("actual_input_vs_replay_input_yaw") or {}).get("input_path_parity_status")
    return status in {"input_paths_match", "input_paths_close_with_residual"}


def _input_differs(report: dict[str, Any]) -> bool:
    status = (report.get("actual_input_vs_replay_input_yaw") or {}).get("input_path_parity_status")
    return status == "input_yaw_mismatch"


def _nav_differs(report: dict[str, Any]) -> bool:
    status = (report.get("actual_nav_vs_replay_nav_yaw") or {}).get("nav_path_parity_status")
    return status in {"position_close_yaw_diverged", "nav_paths_diverged"}


def _replay_tracks_input(report: dict[str, Any]) -> bool:
    return (report.get("replay_input_vs_replay_nav_yaw") or {}).get("classification") == "nav_tracks_input_yaw"


def _actual_transformed_or_not_tracking(report: dict[str, Any]) -> bool:
    classification = (report.get("actual_input_vs_actual_nav_yaw") or {}).get("classification")
    return classification in {"nav_applies_yaw_transform", "nav_ignores_or_reinitializes_yaw"}


def _current_source_direct(source_report: dict[str, Any]) -> bool:
    current = source_report.get("current_source_audit") or source_report.get("current_yaw_update_source") or {}
    transform = str(current.get("current_yaw_measurement_transform", ""))
    return "direct" in transform or transform == "direct_gnssdata_yaw_likely"


def _source_has_variants(source_report: dict[str, Any]) -> bool:
    history = source_report.get("source_history") or source_report.get("yaw_update_source_history") or source_report
    return bool(
        history.get("possible_source_version_mismatch")
        or history.get("evidence_of_yaw_transform_variants")
        or int(history.get("candidate_commit_count") or 0) > 1
    )


def _actual_config_missing(config_report: dict[str, Any]) -> bool:
    return config_report.get("actual_config_status") == "evidence_missing" or "actual_runtime_config" in (
        config_report.get("evidence_missing") or []
    )


def _significant_config_diff(config_report: dict[str, Any]) -> bool:
    if config_report.get("significant_yaw_config_diff"):
        return True
    yaw_diff = (config_report.get("yaw_relevant_config_diff") or {}).get("initatt_yaw_diff_deg")
    return isinstance(yaw_diff, (int, float)) and abs(float(yaw_diff)) > 0.5


def classify_yaw_runtime_issue(
    actual_vs_replay_report: dict[str, Any],
    config_report: dict[str, Any],
    source_history_report: dict[str, Any],
    actual_summary: dict[str, Any] | None = None,
    replay_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify the likely yaw runtime/config/source-version issue."""

    input_matches = _input_matches(actual_vs_replay_report)
    input_differs = _input_differs(actual_vs_replay_report)
    nav_differs = _nav_differs(actual_vs_replay_report)
    source_variants = _source_has_variants(source_history_report)
    config_missing = _actual_config_missing(config_report)
    config_diff = _significant_config_diff(config_report)
    current_source_direct = _current_source_direct(source_history_report)
    actual_transformed = _actual_transformed_or_not_tracking(actual_vs_replay_report)
    replay_tracks = _replay_tracks_input(actual_vs_replay_report)
    actual_summary = actual_summary or {}
    replay_summary = replay_summary or {}
    actual_summary_yaw = actual_summary.get("yaw_rmse_deg")
    replay_summary_yaw = replay_summary.get("yaw_rmse_deg")
    nav_report = actual_vs_replay_report.get("actual_nav_vs_replay_nav_yaw") or {}
    nav_yaw_diff = nav_report.get("nav_yaw_diff_rmse_deg")
    nav_matches_summary_diverges = bool(
        input_matches
        and not nav_differs
        and isinstance(nav_yaw_diff, (int, float))
        and float(nav_yaw_diff) <= 3.0
        and isinstance(actual_summary_yaw, (int, float))
        and float(actual_summary_yaw) <= 3.0
        and isinstance(replay_summary_yaw, (int, float))
        and float(replay_summary_yaw) > 30.0
    )

    likely_source_version_mismatch = bool(input_matches and nav_differs and source_variants)
    likely_actual_runtime_used_different_yaw_update = bool(
        input_matches and current_source_direct and actual_transformed and nav_differs
    )
    likely_config_yaw_update_gate_issue = bool(input_matches and nav_differs and config_diff)
    likely_input_generation_fix = input_differs
    config_evidence_missing = config_missing

    blocking_issues: list[str] = []
    if config_missing:
        blocking_issues.append("actual_runtime_config_evidence_missing")
    if likely_input_generation_fix:
        recommended = "N4H2C_input_generation_fix"
    elif nav_matches_summary_diverges:
        recommended = "N4H2C_replay_reference_mapping_or_summary_staleness_audit"
    elif likely_config_yaw_update_gate_issue:
        recommended = "N4H2C_replay_config_parity_fix"
    elif likely_source_version_mismatch:
        recommended = "N4H2C_source_version_parity_replay"
    elif likely_actual_runtime_used_different_yaw_update:
        recommended = "N4H2C_actual_runtime_source_recovery"
    elif config_evidence_missing:
        recommended = "N4H2C_actual_config_recovery_needed"
    elif input_matches and nav_differs:
        recommended = "N4H2C_yaw_update_instrumentation_required"
    else:
        recommended = "N4H2C_runtime_yaw_evidence_inconclusive"

    if likely_source_version_mismatch:
        blocking_issues.append("source_version_or_branch_parity_not_locked")
    if nav_matches_summary_diverges:
        blocking_issues.append("replay_summary_reference_mapping_or_staleness")
    if likely_config_yaw_update_gate_issue:
        blocking_issues.append("yaw_relevant_config_diff")
    if recommended == "N4H2C_yaw_update_instrumentation_required":
        blocking_issues.append("runtime_yaw_update_needs_instrumented_replay")

    return {
        "phase": "N4H2C-runtime",
        "input_matches": input_matches,
        "nav_differs": nav_differs,
        "replay_nav_tracks_input_yaw": replay_tracks,
        "actual_nav_transformed_or_not_tracking_input": actual_transformed,
        "likely_issue_classification": {
            "likely_source_version_mismatch": likely_source_version_mismatch,
            "likely_actual_runtime_used_different_yaw_update": likely_actual_runtime_used_different_yaw_update,
            "likely_config_yaw_update_gate_issue": likely_config_yaw_update_gate_issue,
            "likely_input_generation_difference": likely_input_generation_fix,
            "config_evidence_missing": config_evidence_missing,
            "likely_replay_reference_mapping_or_summary_staleness": nav_matches_summary_diverges,
        },
        "recommended_next_stage": recommended,
        "blocking_issues": blocking_issues,
        "full_kfgins_framework_needed": True,
        "full_ekf_should_wait_until_runtime_config_parity_resolved": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }
