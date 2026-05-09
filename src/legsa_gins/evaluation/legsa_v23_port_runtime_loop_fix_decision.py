"""Decision logic for N4H4R3A runtime loop / overlap audit.

中文说明：根据 overlap、runtime trace 和 config 证据决定是否需要 source-backed
runtime loop 修复；本模块不调整门限、不删除 epoch、不做性能声明。
"""

from __future__ import annotations

from typing import Any


def make_runtime_loop_fix_decision(
    overlap_report: dict[str, Any],
    runtime_trace_report: dict[str, Any],
    config_report: dict[str, Any],
    r3_gap_report: dict[str, Any] | None = None,
    *,
    actual_update_count: int | None = None,
    runtime_loop_fix_applied: bool = False,
) -> dict[str, Any]:
    expected_min = int(overlap_report.get("expected_update_count_min", 0) or 0)
    expected_max = int(overlap_report.get("expected_update_count_max", 0) or 0)
    actual = actual_update_count
    if actual is None:
        actual = int(runtime_trace_report.get("update_applied_count", 0) or 0)
    update_count_low = expected_min > 0 and actual < 0.8 * expected_min
    matches = expected_min <= actual <= expected_max if expected_max else False
    overwritten = int(runtime_trace_report.get("overwritten_before_update_count", 0) or 0)
    blocking: list[str] = []
    if not config_report.get("config_ok", False):
        blocking.append("config_parity_issue")
    if update_count_low:
        blocking.append("update_count_low_against_overlap")
    if overwritten:
        blocking.append("gnss_overwritten_before_update")

    if matches and config_report.get("config_ok", False):
        issue = False
        recommended = "N4H4R3B_filter_residual_covariance_gap_audit"
        note = "R3 total-row expected-count rule was too naive; overlap count now matches actual updates."
    elif overwritten:
        issue = True
        recommended = "N4H4R3B_runtime_loop_gnss_queue_fix"
        note = "GNSS rows are overwritten before update."
    elif config_report.get("config_start_end_too_short") or config_report.get("config_end_before_gnss_overlap"):
        issue = True
        recommended = "N4H4R3B_config_start_end_fix"
        note = "Config start/end does not cover the effective overlap."
    elif update_count_low:
        issue = True
        recommended = "N4H4R3B_source_backed_runtime_loop_refresh_fix"
        note = "Actual updates are below effective overlap expectation."
    else:
        issue = None
        recommended = "N4H4R3A_extend_timeline_debug"
        note = "Evidence is insufficient."

    return {
        "phase": "N4H4R3A",
        "update_count_issue": issue,
        "runtime_loop_fix_applied": runtime_loop_fix_applied,
        "source_backed_runtime_loop_fix": runtime_loop_fix_applied,
        "expected_update_count_min": expected_min,
        "expected_update_count_max": expected_max,
        "actual_update_count": actual,
        "update_count_low": update_count_low,
        "gnss_rows_skipped_unexpectedly": update_count_low,
        "overwritten_before_update_count": overwritten,
        "config_ok": config_report.get("config_ok", False),
        "recommended_next_stage": recommended,
        "blocking_issues": blocking,
        "decision_note": note,
        "previous_r3_gap_blocking_issues": (r3_gap_report or {}).get("blocking_issues", []),
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
