"""N4H2 replay re-evaluation under controlled yaw profiles.

中文说明：本模块只重算 evaluator metrics；不修改 replay NAV，不写回 solver，
不把 trace/reference 作为 solver input。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.error_series_parity import load_official_error_series
from legsa_gins.evaluation.official_case_review_reproduction import (
    load_eval_nav_csv,
    parse_kfgins_nav,
    reconstruct_reference_from_error_series,
)
from legsa_gins.evaluation.yaw_evaluator_convention_policy import (
    default_yaw_convention_profiles,
    evaluate_with_yaw_profile,
)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _find_replay_nav(root: Path) -> Path | None:
    candidates = [
        root / "replay" / "standardized" / "FINAL_V23_EVAL_NAV.csv",
        root / "replay" / "standardized" / "FINAL_V23_NAV.csv",
        root / "replay" / "kfgins_output" / "KF_GINS_Navresult.nav",
    ]
    for path in candidates:
        if path.exists():
            return path
    if root.exists():
        found = sorted(root.rglob("FINAL_V23_EVAL_NAV.csv"))
        if found:
            return found[0]
    return None


def _find_replay_errors(root: Path) -> Path | None:
    candidates = [
        root / "replay" / "evaluation" / "FINAL_V23_TRACE_ERROR_SERIES.csv",
        root / "replay" / "evaluation" / "error_series.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    if root.exists():
        found = sorted(root.rglob("FINAL_V23_TRACE_ERROR_SERIES.csv"))
        if found:
            return found[0]
    return None


def _load_replay_nav(path: str | Path) -> list[dict[str, float]]:
    nav_path = Path(path)
    if nav_path.suffix.lower() == ".csv":
        return load_eval_nav_csv(nav_path)
    return parse_kfgins_nav(nav_path)


def _select_profiles(confirmed_dual_profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    profiles = [
        profile
        for profile in default_yaw_convention_profiles()
        if profile["name"] in {"direct_identity", "official_candidate_ref_heading_to_math"}
    ]
    if confirmed_dual_profile:
        confirmed = dict(confirmed_dual_profile)
        confirmed["name"] = "confirmed_dual_profile"
        profiles.append(confirmed)
    return profiles


def _yaw_gate(summary: dict[str, Any]) -> bool:
    yaw = summary.get("yaw_rmse_deg")
    return isinstance(yaw, (int, float)) and float(yaw) <= 2.0


def _write_review(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# N4R2 N4H2 replay profile re-evaluation",
        "",
        "This runtime review only changes evaluator yaw profile selection.",
        "",
        "## Boundary",
        "",
        "- solver_output_changed=false",
        "- evaluator_only=true",
        "- trace_solver_input=false",
        "- output_only_correction=false",
        "- numerical_performance_claim=false",
        "",
        "## Metrics",
        "",
        f"- direct_yaw_rmse_deg: {report.get('direct_yaw_rmse_deg')}",
        f"- official_candidate_yaw_rmse_deg: {report.get('official_candidate_yaw_rmse_deg')}",
        f"- confirmed_profile_yaw_rmse_deg: {report.get('confirmed_profile_yaw_rmse_deg')}",
        f"- horizontal_rmse_m: {report.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {report.get('up_rmse_m')}",
        f"- yaw_gate_pass_for_each_profile: {report.get('yaw_gate_pass_for_each_profile')}",
        f"- recommended_profile_status: {report.get('recommended_profile_status')}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def reevaluate_n4h2_replay_profiles(
    n4h2_artifacts_root: str | Path,
    *,
    output_dir: str | Path,
    confirmed_dual_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate N4H2 replay NAV under direct/candidate/confirmed profiles."""

    root = Path(n4h2_artifacts_root)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    replay_nav = _find_replay_nav(root)
    replay_errors = _find_replay_errors(root)
    if replay_nav is None or replay_errors is None:
        report = {
            "phase": "N4R2",
            "evidence_status": "evidence_missing",
            "evidence_missing": ["n4h2_replay_nav_or_error_series"],
            "direct_yaw_rmse_deg": None,
            "official_candidate_yaw_rmse_deg": None,
            "confirmed_profile_yaw_rmse_deg": None,
            "yaw_gate_pass_for_each_profile": {},
            "recommended_profile_status": "evidence_missing",
            "solver_output_changed": False,
            "evaluator_only": True,
            "trace_solver_input": False,
            "output_only_correction": False,
            "numerical_performance_claim": False,
        }
        _write_json(out / "N4H2_REPLAY_PROFILE_REEVALUATION_REPORT.json", report)
        return report

    replay_rows = _load_replay_nav(replay_nav)
    error_rows = load_official_error_series(replay_errors)
    reference_rows = reconstruct_reference_from_error_series(replay_rows, error_rows)
    if not reference_rows:
        report = {
            "phase": "N4R2",
            "evidence_status": "reference_missing",
            "evidence_missing": ["reconstructed_reference_rows"],
            "direct_yaw_rmse_deg": None,
            "official_candidate_yaw_rmse_deg": None,
            "confirmed_profile_yaw_rmse_deg": None,
            "yaw_gate_pass_for_each_profile": {},
            "recommended_profile_status": "evidence_missing",
            "solver_output_changed": False,
            "evaluator_only": True,
            "trace_solver_input": False,
            "output_only_correction": False,
            "numerical_performance_claim": False,
        }
        _write_json(out / "N4H2_REPLAY_PROFILE_REEVALUATION_REPORT.json", report)
        return report

    profile_summaries: dict[str, dict[str, Any]] = {}
    for profile in _select_profiles(confirmed_dual_profile):
        profile_report = evaluate_with_yaw_profile(
            replay_rows,
            reference_rows,
            profile,
            out / "profiles" / str(profile["name"]),
        )
        profile_summaries[str(profile["name"])] = profile_report["summary"]

    direct = profile_summaries.get("direct_identity", {})
    candidate = profile_summaries.get("official_candidate_ref_heading_to_math", {})
    confirmed = profile_summaries.get("confirmed_dual_profile")
    yaw_gate_pass = {name: _yaw_gate(summary) for name, summary in profile_summaries.items()}
    candidate_yaw = candidate.get("yaw_rmse_deg")
    if confirmed is not None:
        recommended_status = "confirmed_profile_available"
    elif isinstance(candidate_yaw, (int, float)) and float(candidate_yaw) <= 2.0:
        recommended_status = "candidate_gate_pass_but_unconfirmed"
    elif isinstance(candidate_yaw, (int, float)) and float(candidate_yaw) <= 3.0:
        recommended_status = "near_gate_candidate_only"
    else:
        recommended_status = "diagnostic_only"

    base_summary = candidate or direct
    report = {
        "phase": "N4R2",
        "evidence_status": "n4h2_replay_profile_reevaluated",
        "profile_summaries": profile_summaries,
        "direct_yaw_rmse_deg": direct.get("yaw_rmse_deg"),
        "official_candidate_yaw_rmse_deg": candidate.get("yaw_rmse_deg"),
        "confirmed_profile_yaw_rmse_deg": confirmed.get("yaw_rmse_deg") if confirmed else None,
        "horizontal_rmse_m": base_summary.get("horizontal_rmse_m"),
        "up_rmse_m": base_summary.get("up_rmse_m"),
        "yaw_gate_pass_for_each_profile": yaw_gate_pass,
        "yaw_replay_gate_pass_candidate": bool(yaw_gate_pass.get("official_candidate_ref_heading_to_math", False)),
        "recommended_profile_status": recommended_status,
        "solver_output_changed": False,
        "evaluator_only": True,
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "N4H2_REPLAY_PROFILE_REEVALUATION_REPORT.json", report)
    _write_review(out / "n4h2_replay_profile_revaluation_review.md", report)
    return report
