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
from legsa_gins.evaluation.replay_official_yaw_parity import (  # noqa: E402
    apply_official_yaw_transform_to_replay,
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
    _write_markdown(out / "official_final_v23_case_review_reproduction.md", official_report, replay_report, decision)
    return decision


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-source-root", default=str(Path.home() / "KF-GINS"))
    parser.add_argument("--n4h2-artifacts-root", default=str(Path.home() / "legsa_n4h2_artifacts"))
    parser.add_argument("--recovery-report", default=None)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    decision = run(parse_args(argv))
    print(json.dumps({"recommended_next_stage": decision["recommended_next_stage"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
