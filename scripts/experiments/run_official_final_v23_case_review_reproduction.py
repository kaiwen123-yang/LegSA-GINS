#!/usr/bin/env python3
"""Run N4R official final_v23 case-review reproduction and yaw parity.

中文说明：runner 只读 runtime artifacts 与 evaluation-only reference；不提交
raw data，不复制外部源码，不使用 trace 作为 solver input。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.official_case_review_reproduction import (  # noqa: E402
    load_trace_reference_for_case,
    locate_actual_final_v23_artifact_group,
    reproduce_official_case_review,
)
from legsa_gins.evaluation.dual_final_v23_evaluator_parity import (  # noqa: E402
    evaluate_dual_final_v23_evaluator_parity,
)
from legsa_gins.evaluation.dual_final_v23_official_parity_lock import (  # noqa: E402
    lock_dual_final_v23_official_parity,
)
from legsa_gins.evaluation.n4h2_replay_profile_revaluation import (  # noqa: E402
    reevaluate_n4h2_replay_profiles,
)
from legsa_gins.evaluation.replay_official_yaw_parity import (  # noqa: E402
    apply_official_yaw_transform_to_replay,
)
from legsa_gins.evaluation.yaw_evaluator_convention_policy import (  # noqa: E402
    write_yaw_convention_policy_report,
)
from legsa_gins.source_audit.dual_final_v23_artifact_recovery import (  # noqa: E402
    recover_dual_final_v23_artifacts,
)
from legsa_gins.source_audit.dual_final_v23_artifact_intake import (  # noqa: E402
    run_dual_artifact_intake,
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


def _metric(report: dict[str, Any], section: str, metric: str) -> float | None:
    value = (report.get(section) or {}).get(metric)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _decide(
    *,
    official_report: dict[str, Any],
    replay_report: dict[str, Any],
    error_series_parse_status: str,
) -> dict[str, Any]:
    if not official_report.get("artifact_located"):
        recommended = "N4R_artifact_recovery_fix"
    elif error_series_parse_status == "evidence_missing":
        recommended = "N4R_error_series_schema_audit"
    elif replay_report.get("likely_evaluator_convention_issue"):
        recommended = "N4R_apply_evaluator_convention_patch_then_N4H3"
    elif (
        official_report.get("evaluator_yaw_transform_needed")
        and _metric(official_report, "direct_recompute_summary", "yaw_rmse_deg") is not None
    ):
        recommended = "N4R_fix_yaw_evaluator_convention"
    elif official_report.get("evaluator_direct_parity_passed") and replay_report.get(
        "likely_runtime_yaw_or_config_issue"
    ):
        recommended = "N4H2C_runtime_yaw_update_config_audit"
    elif replay_report.get("likely_runtime_yaw_or_config_issue"):
        recommended = "N4H2C_runtime_yaw_update_config_audit"
    else:
        recommended = "N4R_artifact_recovery_fix"

    official_yaw = _metric(official_report, "official_summary", "yaw_rmse_deg")
    direct_yaw = _metric(official_report, "direct_recompute_summary", "yaw_rmse_deg")
    replay_yaw = (replay_report.get("replay_summary") or {}).get("yaw_rmse_deg")
    return {
        "phase": "N4R",
        "official_summary_yaw_rmse_deg": official_yaw,
        "direct_recompute_yaw_rmse_deg": direct_yaw,
        "replay_with_official_yaw_rmse_deg": replay_yaw,
        "evaluator_direct_parity_passed": official_report.get("evaluator_direct_parity_passed"),
        "evaluator_yaw_transform_needed": official_report.get("evaluator_yaw_transform_needed"),
        "official_yaw_error_definition_identified": official_report.get(
            "official_yaw_error_definition_identified"
        ),
        "likely_issue_classification": {
            "evaluator_yaw_convention_issue": bool(
                official_report.get("evaluator_yaw_transform_needed")
                or replay_report.get("likely_evaluator_convention_issue")
            ),
            "runtime_yaw_update_or_config_issue": bool(replay_report.get("likely_runtime_yaw_or_config_issue")),
            "artifact_or_reference_mismatch": bool(
                official_report.get("evaluator_reference_source_mismatch")
                or replay_report.get("likely_artifact_or_reference_mismatch")
            ),
        },
        "recommended_next_stage": recommended,
        "blocking_issues": []
        if recommended
        not in {"N4R_artifact_recovery_fix", "N4R_error_series_schema_audit"}
        else [recommended],
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def _n4r2_decide(
    *,
    official_report: dict[str, Any],
    recovery_report: dict[str, Any],
    dual_report: dict[str, Any] | None,
    replay_profile_report: dict[str, Any],
) -> dict[str, Any]:
    dual_report = dual_report or {}
    candidate_yaw = replay_profile_report.get("official_candidate_yaw_rmse_deg")
    confirmed_yaw = replay_profile_report.get("confirmed_profile_yaw_rmse_deg")
    yaw_replay_gate_pass_candidate = bool(replay_profile_report.get("yaw_replay_gate_pass_candidate"))
    dual_confirmed = bool(dual_report.get("dual_evaluator_profile_confirmed"))
    direct_identity_works = bool(dual_report.get("direct_identity_matches"))
    dual_found = bool(recovery_report.get("dual_artifact_found"))

    if dual_confirmed:
        recommended = "N4R_apply_confirmed_evaluator_profile_then_N4H3"
    elif not dual_found:
        recommended = "N4R_dual_artifact_recovery_needed"
    elif direct_identity_works:
        recommended = "N4R_keep_direct_evaluator_then_runtime_yaw_audit"
    elif official_report.get("evaluator_yaw_transform_needed") and isinstance(candidate_yaw, (int, float)):
        recommended = "N4R_yaw_reference_schema_audit"
    else:
        recommended = "N4R_yaw_reference_schema_audit"

    formal_yaw_pass = bool(
        dual_confirmed
        and (
            (isinstance(confirmed_yaw, (int, float)) and float(confirmed_yaw) <= 2.0)
            or (confirmed_yaw is None and yaw_replay_gate_pass_candidate)
        )
    )
    blocking: list[str] = []
    if recommended == "N4R_dual_artifact_recovery_needed":
        blocking.append("dual_final_v23_artifact_missing_or_unconfirmed")
    elif recommended == "N4R_yaw_reference_schema_audit":
        blocking.append("dual_profile_not_confirmed")
    if isinstance(candidate_yaw, (int, float)) and float(candidate_yaw) > 2.0:
        blocking.append("candidate_yaw_above_strict_gate")

    return {
        "phase": "N4R2",
        "dual_artifact_found": dual_found,
        "dual_evaluator_profile_confirmed": dual_confirmed,
        "dual_direct_identity_works": direct_identity_works,
        "dual_official_candidate_matches": bool(dual_report.get("official_candidate_matches")),
        "official_candidate_replay_yaw_rmse_deg": candidate_yaw,
        "confirmed_profile_replay_yaw_rmse_deg": confirmed_yaw,
        "yaw_replay_gate_pass_candidate": yaw_replay_gate_pass_candidate,
        "formal_yaw_pass": formal_yaw_pass,
        "evaluator_profile_formal_status": dual_report.get("evaluator_profile_formal_status", "diagnostic_only"),
        "recommended_next_stage": recommended,
        "blocking_issues": blocking,
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "solver_input_modified": False,
        "solver_output_changed": False,
        "evaluator_only": True,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def _n4r3_decide(
    *,
    intake_report: dict[str, Any],
    parity_lock_report: dict[str, Any] | None,
    replay_profile_report: dict[str, Any],
) -> dict[str, Any]:
    classification = intake_report.get("summary_classification") or {}
    confirmed_artifact = bool(intake_report.get("dual_final_v23_confirmed"))
    single_like = bool(classification.get("single_like"))
    parity_lock_report = parity_lock_report or {}
    evaluator_confirmed = bool(parity_lock_report.get("evaluator_profile_confirmed"))
    confirmed_profile_name = parity_lock_report.get("confirmed_profile_name")
    confirmed_yaw = replay_profile_report.get("confirmed_profile_yaw_rmse_deg")
    candidate_yaw = replay_profile_report.get("official_candidate_yaw_rmse_deg")
    formal_yaw_pass = bool(evaluator_confirmed and isinstance(confirmed_yaw, (int, float)) and float(confirmed_yaw) <= 2.0)
    confirmed_near_gate = bool(evaluator_confirmed and isinstance(confirmed_yaw, (int, float)) and 2.0 < float(confirmed_yaw) <= 2.2)

    if single_like:
        recommended = "N4R_wrong_artifact_group"
    elif not confirmed_artifact:
        recommended = "N4R_manual_dual_artifact_required"
    elif not evaluator_confirmed:
        recommended = "N4R_yaw_reference_schema_audit"
    elif formal_yaw_pass:
        recommended = "N4H3_controlled_final_v23_reference_import"
    elif confirmed_near_gate:
        recommended = "N4H3_reference_import_with_yaw_near_gate_caveat"
    else:
        recommended = "N4H2C_runtime_yaw_update_config_audit"

    blocking: list[str] = []
    if recommended == "N4R_wrong_artifact_group":
        blocking.append("manual_artifact_single_antenna_like")
    elif recommended == "N4R_manual_dual_artifact_required":
        blocking.append("manual_dual_artifact_missing_or_incomplete")
    elif recommended == "N4R_yaw_reference_schema_audit":
        blocking.append("official_profile_not_confirmed")
    elif recommended == "N4H2C_runtime_yaw_update_config_audit":
        blocking.append("confirmed_profile_replay_yaw_above_gate")
    if isinstance(candidate_yaw, (int, float)) and float(candidate_yaw) > 2.0:
        blocking.append("diagnostic_candidate_yaw_above_strict_gate")

    return {
        "phase": "N4R3",
        "dual_final_v23_confirmed": confirmed_artifact,
        "manual_artifact_required": bool(intake_report.get("manual_artifact_required")),
        "single_like": single_like,
        "evaluator_profile_confirmed": evaluator_confirmed,
        "confirmed_profile_name": confirmed_profile_name,
        "official_candidate_replay_yaw_rmse_deg": candidate_yaw,
        "confirmed_profile_replay_yaw_rmse_deg": confirmed_yaw,
        "formal_yaw_pass": formal_yaw_pass,
        "near_gate_status": replay_profile_report.get("near_gate_status", {}),
        "recommended_next_stage": recommended,
        "blocking_issues": blocking,
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "solver_input_modified": False,
        "solver_output_changed": False,
        "evaluator_only": True,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def _write_markdown(path: Path, official_report: dict[str, Any], replay_report: dict[str, Any], decision: dict[str, Any]) -> None:
    official = official_report.get("official_summary", {})
    direct = official_report.get("direct_recompute_summary", {})
    best = official_report.get("best_yaw_transform_candidate") or {}
    replay_summary = replay_report.get("replay_summary") or {}
    lines = [
        "# N4R official final_v23 case-review reproduction",
        "",
        "## Boundary",
        "",
        "- trace_solver_input=false",
        "- output_only_correction=false",
        "- bad_epoch_deletion_for_metric=false",
        "- numerical_performance_claim=false",
        "- official artifacts are evaluator/reference context only",
        "- yaw transform candidates are diagnostic evaluator conventions, not solver tuning",
        "",
        "## Official Summary",
        "",
        f"- horizontal_rmse_m: {official.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {official.get('up_rmse_m')}",
        f"- yaw_rmse_deg: {official.get('yaw_rmse_deg')}",
        f"- roll_rmse_deg: {official.get('roll_rmse_deg')}",
        f"- pitch_rmse_deg: {official.get('pitch_rmse_deg')}",
        "",
        "## Direct Recompute",
        "",
        f"- horizontal_rmse_m: {direct.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {direct.get('up_rmse_m')}",
        f"- yaw_rmse_deg: {direct.get('yaw_rmse_deg')}",
        f"- roll_rmse_deg: {direct.get('roll_rmse_deg')}",
        f"- pitch_rmse_deg: {direct.get('pitch_rmse_deg')}",
        "",
        "## Yaw Evaluator Parity",
        "",
        f"- best_candidate: {best.get('candidate_id')}",
        f"- est_transform: {best.get('est_transform')}",
        f"- ref_transform: {best.get('ref_transform')}",
        f"- direct_parity_passed: {official_report.get('evaluator_direct_parity_passed')}",
        f"- official_error_series_status: {(official_report.get('official_error_series_parity') or {}).get('yaw_error_series_parity_status')}",
        "",
        "## Replay With Official Transform",
        "",
        f"- horizontal_rmse_m: {replay_summary.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {replay_summary.get('up_rmse_m')}",
        f"- yaw_rmse_deg: {replay_summary.get('yaw_rmse_deg')}",
        "",
        "## Decision",
        "",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- blocking_issues: {decision.get('blocking_issues')}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    external_root = Path(args.external_source_root)
    n4h2_root = Path(args.n4h2_artifacts_root)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    artifact_group = locate_actual_final_v23_artifact_group(
        recovery_report_path=args.recovery_report,
        artifact_root=external_root,
    )
    artifact_group["external_source_root"] = str(external_root)
    artifact_group["n4h2_artifacts_root"] = str(n4h2_root)

    official_report = reproduce_official_case_review(artifact_group, output_dir=out)
    policy_report = write_yaw_convention_policy_report(out)
    reference_bundle = load_trace_reference_for_case(artifact_group, external_root)
    replay_nav = _find_replay_nav(n4h2_root)
    transform_report = {
        "best_yaw_transform_candidate": official_report.get("best_yaw_transform_candidate") or {}
    }
    if replay_nav and reference_bundle.get("reference_rows"):
        replay_report = apply_official_yaw_transform_to_replay(
            replay_nav,
            reference_bundle["reference_rows"],
            transform_report,
            out,
        )
    else:
        replay_report = {
            "phase": "N4R",
            "evidence_status": "evidence_missing",
            "evidence_missing": ["replay_nav_or_reference"],
            "replay_summary": {},
            "likely_evaluator_convention_issue": False,
            "likely_runtime_yaw_or_config_issue": False,
            "likely_artifact_or_reference_mismatch": True,
            "trace_solver_input": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "numerical_performance_claim": False,
        }
        _write_json(out / "REPLAY_OFFICIAL_YAW_PARITY_REPORT.json", replay_report)

    error_status = (official_report.get("official_error_series_parity") or {}).get(
        "yaw_error_series_parity_status",
        "evidence_missing",
    )
    decision = _decide(
        official_report=official_report,
        replay_report=replay_report,
        error_series_parse_status=error_status,
    )
    _write_json(out / "N4R_DECISION_REPORT.json", decision)

    dual_roots = {
        "EXTERNAL_KFGINS_ROOT": external_root,
        "HOME_ROOT": Path.home(),
        "WINDOWS_YKW_ROOT": Path("/mnt") / "c" / "Users" / "ykw",
        "WINDOWS_86187_ROOT": Path("/mnt") / "c" / "Users" / "86187",
    }
    dual_recovery = recover_dual_final_v23_artifacts(dual_roots)
    _write_json(out / "DUAL_FINAL_V23_ARTIFACT_RECOVERY_REPORT.json", dual_recovery)
    dual_report = evaluate_dual_final_v23_evaluator_parity(
        dual_recovery.get("best_dual_candidate_group") if dual_recovery.get("dual_artifact_found") else None,
        external_source_root=external_root,
        n4h2_artifacts_root=n4h2_root,
        output_dir=out,
    )
    confirmed_profile = (
        dual_report.get("confirmed_profile")
        if dual_report.get("dual_evaluator_profile_confirmed")
        else None
    )
    replay_profile_report = reevaluate_n4h2_replay_profiles(
        n4h2_root,
        output_dir=out,
        confirmed_dual_profile=confirmed_profile,
    )
    n4r2_decision = _n4r2_decide(
        official_report=official_report,
        recovery_report=dual_recovery,
        dual_report=dual_report,
        replay_profile_report=replay_profile_report,
    )
    n4r2_decision["policy_formal_profile_patch_allowed"] = policy_report.get("formal_profile_patch_allowed")
    _write_json(out / "N4R2_DECISION_REPORT.json", n4r2_decision)

    intake_report = run_dual_artifact_intake(args.dual_root, output_dir=out)
    parity_lock_report: dict[str, Any] | None = None
    if intake_report.get("dual_final_v23_confirmed"):
        parity_lock_report = lock_dual_final_v23_official_parity(args.dual_root, output_dir=out)
    confirmed_lock_profile = (
        parity_lock_report.get("confirmed_profile")
        if parity_lock_report and parity_lock_report.get("evaluator_profile_confirmed")
        else None
    )
    replay_profile_report = reevaluate_n4h2_replay_profiles(
        n4h2_root,
        output_dir=out,
        confirmed_dual_profile=confirmed_lock_profile,
    )
    n4r3_decision = _n4r3_decide(
        intake_report=intake_report,
        parity_lock_report=parity_lock_report,
        replay_profile_report=replay_profile_report,
    )
    _write_json(out / "N4R3_DECISION_REPORT.json", n4r3_decision)
    _write_markdown(out / "official_final_v23_case_review_reproduction.md", official_report, replay_report, decision)
    return n4r3_decision


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-source-root", default=str(Path.home() / "KF-GINS"))
    parser.add_argument("--n4h2-artifacts-root", default=str(Path.home() / "legsa_n4h2_artifacts"))
    parser.add_argument("--dual-root", default=None)
    parser.add_argument("--recovery-report", default=None)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    decision = run(parse_args(argv))
    print(json.dumps({"recommended_next_stage": decision["recommended_next_stage"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
