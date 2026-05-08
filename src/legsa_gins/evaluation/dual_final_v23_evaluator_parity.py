"""dual_final_v23 evaluator parity for N4R2.

中文说明：本模块只验证 evaluator yaw convention；official artifacts 和 trace/reference
均为 evaluation-only，不进入 solver，不修改 solver output。
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
    ARTIFACT_NAMES,
    load_trace_reference_for_case,
    parse_kfgins_nav,
)
from legsa_gins.evaluation.trajectory_metrics import write_error_series
from legsa_gins.evaluation.yaw_evaluator_convention_policy import (
    default_yaw_convention_profiles,
    evaluate_with_yaw_profile,
    get_profile,
)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _path(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    candidate = Path(path_text)
    return candidate if candidate.exists() else None


def _artifact_paths(group: dict[str, Any]) -> dict[str, Path]:
    artifacts = group.get("artifacts", {})
    return {name: path for name in ARTIFACT_NAMES if (path := _path(artifacts.get(name)))}


def _metric_diff_ok(diff: dict[str, Any], metric: str, threshold: float) -> bool:
    value = (diff.get("metric_diff") or {}).get(metric)
    return isinstance(value, (int, float)) and abs(float(value)) <= threshold


def _summary_matches_for_dual(official: dict[str, Any], recomputed: dict[str, Any]) -> bool:
    parity = compare_summary_metrics(official, recomputed)
    return (
        _metric_diff_ok(parity, "yaw_rmse_deg", 0.2)
        and _metric_diff_ok(parity, "horizontal_rmse_m", 0.05)
        and _metric_diff_ok(parity, "up_rmse_m", 0.05)
    )


def _write_review(path: Path, report: dict[str, Any]) -> None:
    official = report.get("official_summary") or {}
    profiles = report.get("profile_summaries") or {}
    lines = [
        "# N4R2 dual_final_v23 evaluator parity",
        "",
        "This runtime review is evaluator-only and does not modify solver output.",
        "",
        "## Boundary",
        "",
        "- solver_input_modified=false",
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
        "## Profile Summaries",
        "",
    ]
    for name, summary in profiles.items():
        lines.append(f"- {name}: yaw_rmse_deg={summary.get('yaw_rmse_deg')}, horizontal_rmse_m={summary.get('horizontal_rmse_m')}, up_rmse_m={summary.get('up_rmse_m')}")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- dual_evaluator_profile_confirmed: {report.get('dual_evaluator_profile_confirmed')}",
            f"- recommended_profile_name: {report.get('recommended_profile_name')}",
            f"- evaluator_profile_formal_status: {report.get('evaluator_profile_formal_status')}",
            f"- evidence_status: {report.get('evidence_status')}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def evaluate_dual_final_v23_evaluator_parity(
    dual_candidate_group: dict[str, Any] | None,
    *,
    external_source_root: str | Path,
    n4h2_artifacts_root: str | Path | None,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Evaluate dual_final_v23 artifacts against controlled yaw profiles."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    if not dual_candidate_group:
        report = {
            "phase": "N4R2",
            "evidence_status": "dual_artifact_missing",
            "dual_evaluator_profile_confirmed": False,
            "recommended_profile_name": None,
            "evaluator_profile_formal_status": "diagnostic_only",
            "solver_input_modified": False,
            "solver_output_changed": False,
            "evaluator_only": True,
            "trace_solver_input": False,
            "output_only_correction": False,
            "numerical_performance_claim": False,
        }
        _write_json(out / "DUAL_FINAL_V23_EVALUATOR_PARITY_REPORT.json", report)
        _write_json(out / "DUAL_FINAL_V23_ERROR_SERIES_PARITY_REPORT.json", {"evidence_status": "dual_artifact_missing"})
        return report

    group = dict(dual_candidate_group)
    if n4h2_artifacts_root is not None:
        group["n4h2_artifacts_root"] = str(n4h2_artifacts_root)
    group["external_source_root"] = str(external_source_root)
    artifacts = _artifact_paths(group)
    missing = [name for name in ["KF_GINS_Navresult.nav", "summary.json"] if name not in artifacts]
    if missing:
        report = {
            "phase": "N4R2",
            "evidence_status": "dual_artifact_missing",
            "evidence_missing": missing,
            "dual_evaluator_profile_confirmed": False,
            "recommended_profile_name": None,
            "evaluator_profile_formal_status": "diagnostic_only",
            "solver_input_modified": False,
            "solver_output_changed": False,
            "evaluator_only": True,
            "trace_solver_input": False,
            "output_only_correction": False,
            "numerical_performance_claim": False,
        }
        _write_json(out / "DUAL_FINAL_V23_EVALUATOR_PARITY_REPORT.json", report)
        _write_json(out / "DUAL_FINAL_V23_ERROR_SERIES_PARITY_REPORT.json", {"evidence_status": "dual_artifact_missing", "evidence_missing": missing})
        return report

    official_summary = load_official_summary(artifacts["summary.json"])
    official_error_rows = load_official_error_series(artifacts["error_series.csv"]) if "error_series.csv" in artifacts else []
    nav_rows = parse_kfgins_nav(artifacts["KF_GINS_Navresult.nav"])
    reference_bundle = load_trace_reference_for_case(group, external_source_root)
    reference_rows = reference_bundle.get("reference_rows", [])
    if not reference_rows:
        report = {
            "phase": "N4R2",
            "artifact_group_id": group.get("group_id"),
            "artifact_role_alias": group.get("role_alias"),
            "official_summary": official_summary,
            "evidence_status": "reference_missing",
            "evidence_missing": ["reference_rows"],
            "dual_evaluator_profile_confirmed": False,
            "recommended_profile_name": None,
            "evaluator_profile_formal_status": "diagnostic_only",
            "solver_input_modified": False,
            "solver_output_changed": False,
            "evaluator_only": True,
            "trace_solver_input": False,
            "output_only_correction": False,
            "numerical_performance_claim": False,
        }
        _write_json(out / "DUAL_FINAL_V23_EVALUATOR_PARITY_REPORT.json", report)
        _write_json(out / "DUAL_FINAL_V23_ERROR_SERIES_PARITY_REPORT.json", {"evidence_status": "reference_missing"})
        return report

    profiles = default_yaw_convention_profiles()
    profile_summaries: dict[str, dict[str, Any]] = {}
    profile_parity: dict[str, dict[str, Any]] = {}
    profile_error_parity: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        profile_dir = out / "profiles" / str(profile["name"])
        profile_report = evaluate_with_yaw_profile(nav_rows, reference_rows, profile, profile_dir)
        summary = profile_report["summary"]
        errors_path = profile_dir / "error_series.csv"
        errors = []
        if errors_path.exists():
            from legsa_gins.evaluation.error_series_parity import load_official_error_series as _load_rows

            errors = _load_rows(errors_path)
        profile_summaries[str(profile["name"])] = summary
        profile_parity[str(profile["name"])] = compare_summary_metrics(official_summary, summary)
        profile_error_parity[str(profile["name"])] = compare_error_series(official_error_rows, errors) if official_error_rows else {
            "yaw_error_series_parity_status": "evidence_missing",
            "evidence_missing": ["dual_error_series.csv"],
            "trace_solver_input": False,
            "output_only_correction": False,
            "numerical_performance_claim": False,
        }

    direct_summary = profile_summaries.get("direct_identity", {})
    candidate_summary = profile_summaries.get("official_candidate_ref_heading_to_math", {})
    direct_identity_matches = _summary_matches_for_dual(official_summary, direct_summary)
    official_candidate_matches = _summary_matches_for_dual(official_summary, candidate_summary)
    dual_confirmed = bool(official_candidate_matches and not direct_identity_matches)
    if direct_identity_matches:
        recommended_profile = "direct_identity"
        formal_status = "direct_identity_remains_formal"
    elif dual_confirmed:
        recommended_profile = "official_candidate_ref_heading_to_math"
        formal_status = "candidate_confirmed_by_dual_parity"
    else:
        recommended_profile = None
        formal_status = "diagnostic_only"

    selected_for_error = recommended_profile or "official_candidate_ref_heading_to_math"
    error_series_parity = profile_error_parity.get(selected_for_error, {})
    report = {
        "phase": "N4R2",
        "artifact_group_id": group.get("group_id"),
        "artifact_role_alias": group.get("role_alias"),
        "evidence_status": "dual_evaluator_parity_complete",
        "reference_source": reference_bundle.get("reference_source"),
        "official_summary": official_summary,
        "profiles": profiles,
        "profile_summaries": profile_summaries,
        "profile_summary_parity": profile_parity,
        "profile_error_series_parity": profile_error_parity,
        "direct_yaw_rmse_deg": direct_summary.get("yaw_rmse_deg"),
        "official_candidate_yaw_rmse_deg": candidate_summary.get("yaw_rmse_deg"),
        "direct_identity_matches": direct_identity_matches,
        "official_candidate_matches": official_candidate_matches,
        "dual_evaluator_profile_confirmed": dual_confirmed,
        "recommended_profile_name": recommended_profile,
        "evaluator_profile_formal_status": formal_status,
        "confirmed_profile": get_profile(recommended_profile) if recommended_profile else None,
        "solver_input_modified": False,
        "solver_output_changed": False,
        "evaluator_only": True,
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "DUAL_FINAL_V23_EVALUATOR_PARITY_REPORT.json", report)
    _write_json(out / "DUAL_FINAL_V23_ERROR_SERIES_PARITY_REPORT.json", error_series_parity)
    if selected_for_error in profile_summaries:
        selected_errors = out / "profiles" / selected_for_error / "error_series.csv"
        if selected_errors.exists():
            selected_rows = load_official_error_series(selected_errors)
            write_error_series(
                [{key: float(row[key]) for key in [
                    "timestamp",
                    "reference_timestamp",
                    "dt",
                    "north_error_m",
                    "east_error_m",
                    "up_error_m",
                    "horizontal_error_m",
                    "roll_error_deg",
                    "pitch_error_deg",
                    "yaw_error_deg",
                ]} for row in selected_rows if all(key in row for key in [
                    "timestamp",
                    "reference_timestamp",
                    "dt",
                    "north_error_m",
                    "east_error_m",
                    "up_error_m",
                    "horizontal_error_m",
                    "roll_error_deg",
                    "pitch_error_deg",
                    "yaw_error_deg",
                ])],
                out / "DUAL_FINAL_V23_SELECTED_PROFILE_ERROR_SERIES.csv",
            )
    _write_review(out / "dual_final_v23_evaluator_parity_review.md", report)
    return report
