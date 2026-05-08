#!/usr/bin/env python3
"""Run N4H2D replay reference mapping / stale summary audit.

中文说明：runner 只读取 dual official artifacts 与 N4H2 replay artifacts 做
evaluation/reference-mapping 审计；不修改 solver output，不提交 artifacts。
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

from legsa_gins.evaluation.error_series_parity import load_official_summary  # noqa: E402
from legsa_gins.evaluation.fresh_replay_evaluator import (  # noqa: E402
    compare_fresh_replay_to_dual_summary,
    evaluate_replay_against_official_reference,
)
from legsa_gins.evaluation.official_reference_reconstruction import (  # noqa: E402
    load_official_error_series,
    load_official_nav,
    select_reference_sign_by_summary,
)
from legsa_gins.evaluation.replay_reference_mapping_audit import (  # noqa: E402
    compare_old_summary_to_fresh,
    load_old_summary,
    locate_n4h2_replay_outputs,
    make_replay_reference_mapping_audit_report,
)
from legsa_gins.evaluation.summary_staleness_audit import audit_summary_staleness  # noqa: E402


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _compact_reference_report(report: dict[str, Any]) -> dict[str, Any]:
    compact_candidates: dict[str, Any] = {}
    for name, candidate in (report.get("candidate_reports") or {}).items():
        compact_candidates[name] = {
            "summary": candidate.get("summary"),
            "summary_diff": candidate.get("summary_diff"),
            "score": candidate.get("score"),
            "reference_count": candidate.get("reference_count"),
        }
    return {
        "phase": report.get("phase", "N4H2D"),
        "selected_reference_sign": report.get("selected_reference_sign"),
        "selected_reference_profile": report.get("selected_reference_profile"),
        "actual_dual_summary_reproduced": report.get("actual_dual_summary_reproduced"),
        "actual_summary_reproduced": report.get("actual_summary_reproduced"),
        "actual_summary_reproduced_summary": report.get("actual_summary_reproduced_summary"),
        "summary_diff": report.get("summary_diff"),
        "candidate_reports": compact_candidates,
        "evidence_status": report.get("evidence_status"),
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def _write_markdown(path: Path, decision: dict[str, Any]) -> None:
    fresh = decision.get("fresh_replay_summary") or {}
    old_fresh = decision.get("old_vs_fresh_summary") or {}
    reconstruction = decision.get("official_reference_reconstruction") or {}
    lines = [
        "# N4H2D replay reference mapping audit",
        "",
        "N4H2D checks whether the old N4H2 replay yaw summary was stale or mapped to the wrong evaluation reference.",
        "",
        "## Boundary",
        "",
        "- trace_solver_input=false",
        "- output_only_correction=false",
        "- solver_output_changed=false",
        "- numerical_performance_claim=false",
        "- fresh replay metrics are baseline replay diagnostics only",
        "",
        "## Official Reference Reconstruction",
        "",
        f"- selected_reference_sign: {reconstruction.get('selected_reference_sign')}",
        f"- actual_dual_summary_reproduced: {reconstruction.get('actual_dual_summary_reproduced')}",
        f"- summary_diff: {reconstruction.get('summary_diff')}",
        "",
        "## Fresh Replay Summary",
        "",
        f"- count: {fresh.get('count')}",
        f"- horizontal_rmse_m: {fresh.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {fresh.get('up_rmse_m')}",
        f"- yaw_rmse_deg: {fresh.get('yaw_rmse_deg')}",
        f"- roll_rmse_deg: {fresh.get('roll_rmse_deg')}",
        f"- pitch_rmse_deg: {fresh.get('pitch_rmse_deg')}",
        f"- yaw_gate_pass: {fresh.get('yaw_gate_pass')}",
        "",
        "## Old vs Fresh",
        "",
        f"- old_yaw_rmse_deg: {old_fresh.get('old_yaw_rmse_deg')}",
        f"- fresh_yaw_rmse_deg: {old_fresh.get('fresh_yaw_rmse_deg')}",
        f"- stale_summary_likely: {old_fresh.get('stale_summary_likely')}",
        f"- reference_mapping_mismatch_likely: {old_fresh.get('reference_mapping_mismatch_likely')}",
        f"- old_summary_invalidated: {decision.get('old_summary_invalidated')}",
        "",
        "## Decision",
        "",
        f"- baseline_replay_parity_status: {decision.get('baseline_replay_parity_status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- blocking_issues: {decision.get('blocking_issues')}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _decide(
    reconstruction: dict[str, Any],
    fresh_summary: dict[str, Any],
    fresh_compare: dict[str, Any],
    old_vs_fresh: dict[str, Any],
) -> dict[str, Any]:
    fresh_yaw = fresh_summary.get("yaw_rmse_deg")
    fresh_close = bool(fresh_compare.get("fresh_replay_close_to_dual_final_v23"))
    yaw_pass = bool(fresh_compare.get("yaw_gate_pass"))
    near_gate = isinstance(fresh_yaw, (int, float)) and 2.0 < float(fresh_yaw) <= 2.2
    if not reconstruction.get("actual_dual_summary_reproduced"):
        recommended = "N4H2D_official_error_series_schema_fix"
        parity = "blocked_official_reference_not_reproduced"
    elif fresh_close and yaw_pass:
        recommended = "N4H3_controlled_final_v23_reference_import"
        parity = "passed"
    elif fresh_close and near_gate:
        recommended = "N4H3_reference_import_with_yaw_near_gate_caveat"
        parity = "near_gate_not_formal_pass"
    elif isinstance(fresh_yaw, (int, float)) and float(fresh_yaw) > 30.0:
        recommended = "N4H2C_runtime_yaw_update_config_audit_continue"
        parity = "failed_yaw_still_large"
    elif old_vs_fresh.get("stale_summary_or_wrong_reference_mapping"):
        recommended = "N4H3_controlled_final_v23_reference_import"
        parity = "fresh_replay_close_old_summary_invalidated" if fresh_close else "old_summary_invalidated_fresh_not_close"
    else:
        recommended = "N4H2D_replay_reference_mapping_followup"
        parity = "inconclusive"

    blocking: list[str] = []
    if not reconstruction.get("actual_dual_summary_reproduced"):
        blocking.append("official_reference_reconstruction_failed")
    if old_vs_fresh.get("stale_summary_or_wrong_reference_mapping"):
        blocking.append("old_summary_invalidated")
    if not yaw_pass and near_gate:
        blocking.append("fresh_yaw_near_gate_not_pass")
    elif not yaw_pass and isinstance(fresh_yaw, (int, float)):
        blocking.append("fresh_yaw_gate_not_pass")
    return {
        "recommended_next_stage": recommended,
        "baseline_replay_parity_status": parity,
        "blocking_issues": blocking,
        "formal_yaw_pass": yaw_pass,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    dual_root = Path(args.dual_root)
    n4h2_root = Path(args.n4h2_artifacts_root)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    dual_summary = load_official_summary(dual_root / "summary.json")
    dual_nav = load_official_nav(dual_root / "KF_GINS_Navresult.nav")
    dual_errors = load_official_error_series(dual_root / "error_series.csv")
    reconstruction = select_reference_sign_by_summary(dual_nav, dual_errors, dual_summary)
    compact_reconstruction = _compact_reference_report(reconstruction)
    _write_json(out / "OFFICIAL_REFERENCE_RECONSTRUCTION_REPORT.json", compact_reconstruction)
    _write_json(out / "ACTUAL_DUAL_SUMMARY_REPRODUCTION_REPORT.json", compact_reconstruction)

    selected_reference = reconstruction["reference_candidates"][reconstruction["selected_reference_sign"]]
    replay_locations = locate_n4h2_replay_outputs(n4h2_root)
    replay_nav_path = replay_locations.get("located_files", {}).get("replay_nav")
    if replay_nav_path is None:
        fresh_report = {
            "phase": "N4H2D",
            "fresh_summary": {},
            "evidence_status": "evidence_missing",
            "evidence_missing": ["replay_nav"],
            "trace_solver_input": False,
            "output_only_correction": False,
            "solver_output_changed": False,
            "numerical_performance_claim": False,
        }
        _write_json(out / "FRESH_REPLAY_SUMMARY.json", {})
        _write_json(out / "FRESH_REPLAY_EVALUATION_REPORT.json", fresh_report)
    else:
        fresh_report = evaluate_replay_against_official_reference(replay_nav_path, selected_reference, out)
    fresh_summary = fresh_report.get("fresh_summary") or {}
    fresh_compare = compare_fresh_replay_to_dual_summary(fresh_summary, dual_summary)

    old_summary_path = replay_locations.get("located_files", {}).get("old_summary")
    old_summary = load_old_summary(old_summary_path)
    report_paths = [
        value
        for key, value in (replay_locations.get("located_files") or {}).items()
        if key in {"replay_report_json", "replay_report_md"} and value
    ]
    staleness = audit_summary_staleness(old_summary_path, replay_nav_path, report_paths)
    _write_json(out / "SUMMARY_STALENESS_AUDIT_REPORT.json", staleness)
    old_vs_fresh = compare_old_summary_to_fresh(
        old_summary,
        fresh_summary,
        staleness_report=staleness,
        old_reference_source=replay_locations.get("old_reference_source_if_reported"),
    )
    _write_json(out / "OLD_VS_FRESH_REPLAY_SUMMARY_REPORT.json", old_vs_fresh)
    mapping_report = make_replay_reference_mapping_audit_report(
        dual_reference_report=compact_reconstruction,
        replay_locations=replay_locations,
        fresh_report=fresh_report,
        old_vs_fresh_report=old_vs_fresh,
        staleness_report=staleness,
    )

    decision_bits = _decide(compact_reconstruction, fresh_summary, fresh_compare, old_vs_fresh)
    decision = {
        "phase": "N4H2D",
        "official_reference_reconstruction": compact_reconstruction,
        "dual_official_summary": dual_summary,
        "replay_locations": replay_locations,
        "fresh_replay_summary": fresh_summary,
        "fresh_replay_vs_dual_summary": fresh_compare,
        "old_vs_fresh_summary": old_vs_fresh,
        "summary_staleness_audit": staleness,
        "mapping_audit_report": mapping_report,
        "old_summary_invalidated": bool(old_vs_fresh.get("stale_summary_or_wrong_reference_mapping")),
        "baseline_replay_parity_status": decision_bits["baseline_replay_parity_status"],
        "recommended_next_stage": decision_bits["recommended_next_stage"],
        "blocking_issues": decision_bits["blocking_issues"],
        "formal_yaw_pass": decision_bits["formal_yaw_pass"],
        "metrics_are_diagnostic_baseline_replay_parity_only": True,
        "not_proposed_solver_performance": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "N4H2D_DECISION_REPORT.json", decision)
    _write_markdown(out / "n4h2d_replay_reference_mapping_audit.md", decision)
    return decision


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dual-root", default=str(Path.home() / "legsa_external_artifacts" / "dual_final_v23_nominal"))
    parser.add_argument("--n4h2-artifacts-root", default=str(Path.home() / "legsa_n4h2_artifacts"))
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    decision = run(parse_args(argv))
    print(json.dumps({"recommended_next_stage": decision.get("recommended_next_stage")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
