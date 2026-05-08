"""N4H2 replay reference mapping / stale summary audit utilities.

中文说明：本模块只审计 evaluation/reference mapping；不修改 solver output，
不提交 artifacts，不使用 trace 作为 solver input。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.error_series_parity import load_official_summary


def _first_existing(candidates: list[Path]) -> Path | None:
    for path in candidates:
        if path.exists():
            return path
    return None


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"evidence_status": "evidence_missing"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"evidence_status": "evidence_missing", "error": str(exc)}


def _small_text(path: Path | None) -> str:
    if path is None or not path.exists() or path.stat().st_size > 2_000_000:
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def locate_n4h2_replay_outputs(n4h2_root: str | Path) -> dict[str, Any]:
    """Locate replay NAV, old summary/report, and process_data-compatible inputs."""

    root = Path(n4h2_root)
    nav_path = _first_existing(
        [
            root / "replay" / "kfgins_output" / "KF_GINS_Navresult.nav",
            root / "replay" / "standardized" / "FINAL_V23_NAV.csv",
            root / "replay" / "standardized" / "FINAL_V23_EVAL_NAV.csv",
        ]
    )
    old_summary = _first_existing(
        [
            root / "replay" / "evaluation" / "FINAL_V23_TRACE_EVAL_SUMMARY.json",
            root / "replay" / "summary.json",
            root / "summary.json",
        ]
    )
    report_json = _first_existing(
        [
            root / "replay" / "N4H2_REPLAY_REPORT.json",
            root / "replay" / "KFGINS_REPLAY_REPORT.json",
            root / "KFGINS_REPLAY_REPORT.json",
        ]
    )
    report_md = _first_existing(
        [
            root / "replay" / "N4H2_REPLAY_REPORT.md",
            root / "replay" / "KFGINS_REPLAY_CASE_REVIEW.md",
            root / "KFGINS_REPLAY_CASE_REVIEW.md",
        ]
    )
    input_gnss = _first_existing([root / "inputs" / "BY2_PROCESS_DATA_COMPAT.gnss", root / "input.gnss"])
    input_imu = _first_existing([root / "inputs" / "BY2_PROCESS_DATA_COMPAT.imu", root / "input.imu"])
    report_text = f"{json.dumps(_read_json(report_json), sort_keys=True)}\n{_small_text(report_md)}"
    lower = report_text.lower()
    if "trace" in lower:
        reference_source = "trace_reference_reported"
    elif "dual" in lower and "official" in lower:
        reference_source = "dual_official_reference_reported"
    else:
        reference_source = "evidence_missing"
    located = {
        "replay_nav": str(nav_path) if nav_path else None,
        "old_summary": str(old_summary) if old_summary else None,
        "replay_report_json": str(report_json) if report_json else None,
        "replay_report_md": str(report_md) if report_md else None,
        "input_gnss": str(input_gnss) if input_gnss else None,
        "input_imu": str(input_imu) if input_imu else None,
    }
    missing = [name for name, value in located.items() if value is None and name in {"replay_nav", "old_summary"}]
    return {
        "phase": "N4H2D",
        "root_role": "N4H2_ARTIFACTS_ROOT",
        "located_files": located,
        "old_summary_status": "parsed" if old_summary else "evidence_missing",
        "old_reference_source_if_reported": reference_source,
        "evidence_status": "located" if not missing else "evidence_missing",
        "evidence_missing": missing,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }


def _metric(summary: dict[str, Any], metric: str) -> float | None:
    value = summary.get(metric)
    return float(value) if isinstance(value, (int, float)) else None


def compare_old_summary_to_fresh(
    old_summary: dict[str, Any],
    fresh_summary: dict[str, Any],
    *,
    staleness_report: dict[str, Any] | None = None,
    old_reference_source: str | None = None,
) -> dict[str, Any]:
    """Compare old N4H2 summary to fresh dual-reference replay summary."""

    old_yaw = _metric(old_summary, "yaw_rmse_deg")
    fresh_yaw = _metric(fresh_summary, "yaw_rmse_deg")
    old_horizontal = _metric(old_summary, "horizontal_rmse_m")
    fresh_horizontal = _metric(fresh_summary, "horizontal_rmse_m")
    old_up = _metric(old_summary, "up_rmse_m")
    fresh_up = _metric(fresh_summary, "up_rmse_m")
    yaw_mapping_jump = bool(
        isinstance(old_yaw, (int, float))
        and old_yaw > 30.0
        and isinstance(fresh_yaw, (int, float))
        and 0.0 <= fresh_yaw <= 3.0
    )
    stale_summary_likely = bool((staleness_report or {}).get("summary_older_than_nav_or_report"))
    reference_mapping_mismatch = bool(
        yaw_mapping_jump
        or old_reference_source == "trace_reference_reported"
        or (staleness_report or {}).get("summary_references_different_reference_source")
    )
    reason: list[str] = []
    if yaw_mapping_jump:
        reason.append("old_yaw_around_93_fresh_yaw_around_1_to_3")
    if stale_summary_likely:
        reason.append("old_summary_older_than_nav_or_report")
    if old_reference_source == "trace_reference_reported":
        reason.append("old_report_reference_not_dual_official")
    return {
        "phase": "N4H2D",
        "old_horizontal_rmse_m": old_horizontal,
        "old_up_rmse_m": old_up,
        "old_yaw_rmse_deg": old_yaw,
        "fresh_horizontal_rmse_m": fresh_horizontal,
        "fresh_up_rmse_m": fresh_up,
        "fresh_yaw_rmse_deg": fresh_yaw,
        "horizontal_diff_old_minus_fresh": old_horizontal - fresh_horizontal
        if isinstance(old_horizontal, float) and isinstance(fresh_horizontal, float)
        else None,
        "up_diff_old_minus_fresh": old_up - fresh_up if isinstance(old_up, float) and isinstance(fresh_up, float) else None,
        "yaw_diff_old_minus_fresh": old_yaw - fresh_yaw if isinstance(old_yaw, float) and isinstance(fresh_yaw, float) else None,
        "stale_summary_likely": stale_summary_likely,
        "reference_mapping_mismatch_likely": reference_mapping_mismatch,
        "stale_summary_or_wrong_reference_mapping": bool(stale_summary_likely or reference_mapping_mismatch),
        "stale_or_mapping_reason": reason,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }


def make_replay_reference_mapping_audit_report(
    *,
    dual_reference_report: dict[str, Any],
    replay_locations: dict[str, Any],
    fresh_report: dict[str, Any],
    old_vs_fresh_report: dict[str, Any],
    staleness_report: dict[str, Any],
) -> dict[str, Any]:
    """Build the final N4H2D mapping audit report."""

    fresh_summary = fresh_report.get("fresh_summary") or {}
    return {
        "phase": "N4H2D",
        "dual_reference_confirmed": bool(dual_reference_report.get("actual_dual_summary_reproduced")),
        "old_summary_status": replay_locations.get("old_summary_status"),
        "fresh_summary_status": "parsed" if fresh_summary.get("count") else "evidence_missing",
        "old_vs_fresh_summary_diff": old_vs_fresh_report,
        "stale_summary_likely": old_vs_fresh_report.get("stale_summary_likely"),
        "reference_mapping_mismatch_likely": old_vs_fresh_report.get("reference_mapping_mismatch_likely"),
        "old_summary_invalidated": old_vs_fresh_report.get("stale_summary_or_wrong_reference_mapping"),
        "replay_recomputed_under_dual_reference": bool(fresh_report.get("replay_recomputed_under_dual_reference")),
        "fresh_summary": fresh_summary,
        "evidence_status": "fresh_replay_evaluated" if fresh_summary.get("count") else "evidence_missing",
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def load_old_summary(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {"evidence_status": "evidence_missing"}
    return load_official_summary(path)
