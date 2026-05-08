"""Official evaluator parity lock for manually-intaken dual_final_v23 artifacts.

中文说明：本模块只锁定 evaluator 定义；dual artifacts 是仓库外 runtime evidence，
不会进入 solver input，不修改 solver output，也不做 output-only correction。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.error_series_parity import (
    compare_error_series,
    compare_summary_metrics,
    load_official_error_series,
    load_official_summary,
)
from legsa_gins.evaluation.official_case_review_reproduction import (
    parse_kfgins_nav,
    reconstruct_reference_from_error_series,
)
from legsa_gins.evaluation.yaw_evaluator_convention_policy import (
    default_yaw_convention_profiles,
    evaluate_with_yaw_profile,
)
from legsa_gins.source_audit.dual_final_v23_artifact_intake import run_dual_artifact_intake


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _diff_within(parity: dict[str, Any], metric: str, threshold: float) -> bool:
    value = (parity.get("metric_diff") or {}).get(metric)
    return isinstance(value, (int, float)) and abs(float(value)) <= threshold


def _summary_lock_passed(parity: dict[str, Any]) -> bool:
    return (
        _diff_within(parity, "horizontal_rmse_m", 0.05)
        and _diff_within(parity, "up_rmse_m", 0.05)
        and _diff_within(parity, "yaw_rmse_deg", 0.2)
    )


def _error_series_lock_passed(parity: dict[str, Any]) -> bool:
    status = parity.get("yaw_error_series_parity_status")
    if status == "evidence_missing":
        return False
    value = parity.get("yaw_error_series_rmse_diff")
    return isinstance(value, (int, float)) and float(value) <= 0.5


def _write_review(path: Path, report: dict[str, Any]) -> None:
    official = report.get("official_summary") or {}
    lines = [
        "# N4R3 dual_final_v23 official parity lock",
        "",
        "This runtime review locks evaluator parity only. It does not modify solver output.",
        "",
        "## Boundary",
        "",
        "- solver_output_changed=false",
        "- evaluator_only=true",
        "- trace_solver_input=false",
        "- output_only_correction=false",
        "- numerical_performance_claim=false",
        "",
        "## Official Summary",
        "",
        f"- horizontal_rmse_m: {official.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {official.get('up_rmse_m')}",
        f"- yaw_rmse_deg: {official.get('yaw_rmse_deg')}",
        f"- roll_rmse_deg: {official.get('roll_rmse_deg')}",
        f"- pitch_rmse_deg: {official.get('pitch_rmse_deg')}",
        "",
        "## Decision",
        "",
        f"- evaluator_profile_confirmed: {report.get('evaluator_profile_confirmed')}",
        f"- confirmed_profile_name: {report.get('confirmed_profile_name')}",
        f"- recommended_next_stage: {report.get('recommended_next_stage')}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def lock_dual_final_v23_official_parity(
    dual_root: str | Path | None,
    *,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Lock the evaluator profile against dual official summary/error_series."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    intake_report = run_dual_artifact_intake(dual_root)
    root = Path(str(intake_report.get("root_report", {}).get("root", "")))
    classification = intake_report.get("summary_classification") or {}
    if not intake_report.get("dual_final_v23_confirmed"):
        if classification.get("single_like"):
            recommended = "N4R_wrong_artifact_group"
        else:
            recommended = "N4R_manual_dual_artifact_required"
        report = {
            "phase": "N4R3",
            "intake_report": intake_report,
            "evaluator_profile_confirmed": False,
            "confirmed_profile_name": None,
            "confirmed_profile": None,
            "evidence_status": intake_report.get("evidence_status", "evidence_missing"),
            "recommended_next_stage": recommended,
            "solver_input_modified": False,
            "solver_output_changed": False,
            "evaluator_only": True,
            "trace_solver_input": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "numerical_performance_claim": False,
        }
        _write_json(out / "DUAL_FINAL_V23_OFFICIAL_PARITY_LOCK_REPORT.json", report)
        _write_review(out / "DUAL_FINAL_V23_OFFICIAL_PARITY_REVIEW.md", report)
        return report

    official_summary = load_official_summary(root / "summary.json")
    official_errors = load_official_error_series(root / "error_series.csv")
    nav_rows = parse_kfgins_nav(root / "KF_GINS_Navresult.nav")
    input_line_count = intake_report.get("validation", {}).get("line_counts", {}).get("input.gnss")
    reference_rows = reconstruct_reference_from_error_series(nav_rows, official_errors)
    profiles = default_yaw_convention_profiles()

    profile_results: dict[str, dict[str, Any]] = {}
    confirmed_profile: dict[str, Any] | None = None
    for profile in profiles:
        name = str(profile["name"])
        profile_report = evaluate_with_yaw_profile(
            nav_rows,
            reference_rows,
            profile,
            out / "profiles" / name,
        )
        recomputed_summary = profile_report["summary"]
        recomputed_errors = load_official_error_series(out / "profiles" / name / "error_series.csv")
        summary_parity = compare_summary_metrics(official_summary, recomputed_summary)
        error_parity = compare_error_series(official_errors, recomputed_errors)
        summary_passed = _summary_lock_passed(summary_parity)
        error_passed = _error_series_lock_passed(error_parity)
        profile_confirmed = bool(summary_passed and error_passed)
        profile_results[name] = {
            "profile": profile,
            "summary": recomputed_summary,
            "summary_parity": summary_parity,
            "error_series_parity": error_parity,
            "summary_lock_passed": summary_passed,
            "error_series_lock_passed": error_passed,
            "profile_confirmed": profile_confirmed,
        }
        if profile_confirmed and confirmed_profile is None:
            confirmed_profile = profile

    evaluator_confirmed = confirmed_profile is not None
    report = {
        "phase": "N4R3",
        "intake_report": intake_report,
        "official_summary": official_summary,
        "input_line_count": input_line_count,
        "reference_source": "official_error_series_reconstructed_reference",
        "profile_results": profile_results,
        "evaluator_profile_confirmed": evaluator_confirmed,
        "confirmed_profile_name": confirmed_profile.get("name") if confirmed_profile else None,
        "confirmed_profile": confirmed_profile,
        "direct_yaw_rmse_deg": (profile_results.get("direct_identity") or {}).get("summary", {}).get("yaw_rmse_deg"),
        "official_candidate_yaw_rmse_deg": (
            profile_results.get("official_candidate_ref_heading_to_math") or {}
        ).get("summary", {}).get("yaw_rmse_deg"),
        "recommended_next_stage": "N4H2C_runtime_yaw_update_config_audit"
        if evaluator_confirmed
        else "N4R_yaw_reference_schema_audit",
        "evidence_status": "official_parity_locked" if evaluator_confirmed else "profile_mismatch",
        "solver_input_modified": False,
        "solver_output_changed": False,
        "evaluator_only": True,
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "DUAL_FINAL_V23_OFFICIAL_PARITY_LOCK_REPORT.json", report)
    _write_review(out / "DUAL_FINAL_V23_OFFICIAL_PARITY_REVIEW.md", report)
    return report
