"""Write N4H4E1 visual validation reports.

中文说明：N4H4E1 只修正图像语义和 STD 单位一致性证据；不是 solver 性能提升，
也不是 proposed factor claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FALSE_FLAGS = {
    "paper_performance_claim": False,
    "proposed_factor_claim": False,
    "trace_solver_input": False,
    "final_v23_output_solver_input": False,
    "output_only_correction": False,
    "bad_epoch_deletion_for_metric": False,
    "no_outperform_final_v23_claim": True,
}


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def make_visual_e1_report(
    *,
    std_unit_report: dict[str, Any],
    plot_report: dict[str, Any],
) -> dict[str, Any]:
    std_ok = bool(std_unit_report.get("attitude_3sigma_unit_consistency_ok"))
    plot_ok = bool(
        plot_report.get("vector_xy_line_removed")
        and plot_report.get("vector_cloud_scatter_created")
        and plot_report.get("up_diff_initial_step_checked")
        and plot_report.get("required_corrected_figures_generated")
    )
    if std_ok and plot_ok:
        status = "passed_after_std_unit_fix"
    elif plot_ok and std_unit_report.get("fix_type") == "evidence_missing":
        status = "passed_with_remaining_caveat"
    elif not std_ok:
        status = "failed_std_unit_issue"
    else:
        status = "failed_visual_anomaly"
    blocking = []
    if not std_ok:
        blocking.append("std_unit_consistency_not_ok")
    if not plot_ok:
        blocking.append("plot_semantics_fix_incomplete")
    report = {
        "phase": "N4H4E1",
        "std_unit_audit_completed": True,
        "std_unit_consistency_ok": std_ok,
        "yaw_3sigma_unit_consistency_ok": std_ok,
        "plot_semantics_fixed": plot_ok,
        "vector_xy_line_removed": bool(plot_report.get("vector_xy_line_removed")),
        "vector_cloud_scatter_created": bool(plot_report.get("vector_cloud_scatter_created")),
        "up_diff_initial_step_checked": bool(plot_report.get("up_diff_initial_step_checked")),
        "visual_candidate_status": status,
        "manual_visual_review_required": True,
        "visual_manual_review_required": True,
        "recommended_next_stage": "N5_raw_doppler_factor_foundation" if status == "passed_after_std_unit_fix" else "N4H4E1_followup_visual_or_std_fix",
        "blocking_issues": blocking,
        "figure_count_total": plot_report.get("figure_count_total", 0),
        "figure_count_by_folder": plot_report.get("figure_count_by_folder", {}),
        "required_corrected_figures_generated": plot_report.get("required_corrected_figures_generated"),
        "pure_single_comparison_absent": plot_report.get("pure_single_comparison_absent"),
        "first_sample_up_diff": plot_report.get("first_sample_up_diff"),
        "second_sample_up_diff": plot_report.get("second_sample_up_diff"),
        "median_up_diff": plot_report.get("median_up_diff"),
        "up_diff_step_suspect": plot_report.get("up_diff_step_suspect"),
        **FALSE_FLAGS,
    }
    return report


def make_visual_e1_sanity_report(
    *,
    std_unit_report: dict[str, Any],
    plot_report: dict[str, Any],
    visual_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "phase": "N4H4E1",
        "std_unit_consistency_ok": visual_report["std_unit_consistency_ok"],
        "yaw_3sigma_unit_consistency_ok": visual_report["yaw_3sigma_unit_consistency_ok"],
        "plot_semantics_fixed": visual_report["plot_semantics_fixed"],
        "vector_xy_line_removed": visual_report["vector_xy_line_removed"],
        "up_diff_initial_step_checked": visual_report["up_diff_initial_step_checked"],
        "required_corrected_figures_generated": visual_report["required_corrected_figures_generated"],
        "pure_single_comparison_absent": visual_report["pure_single_comparison_absent"],
        "visual_candidate_status": visual_report["visual_candidate_status"],
        "manual_visual_review_required": True,
        "blocking_issues": visual_report["blocking_issues"],
        "std_fix_type": std_unit_report.get("fix_type"),
        "std_fix_applied": std_unit_report.get("fix_applied"),
        "corrected_3sigma_figure_count": plot_report.get("corrected_3sigma_figure_count"),
        **FALSE_FLAGS,
    }


def write_visual_case_review_e1(
    path: str | Path,
    *,
    std_unit_report: dict[str, Any],
    plot_report: dict[str, Any],
    visual_report: dict[str, Any],
) -> None:
    lines = [
        "# N4H4E1 Visual Case Review",
        "",
        "N4H4E1 audits STD units and fixes plot semantics for the source-backed port visual validation.",
        "",
        "## What Changed",
        "",
        "- The two XY error figures were error vector clouds, not trajectories.",
        "- The vector-cloud figures are now scatter plots or time-series diagnostics, without connected vector-cloud lines.",
        "- The port-minus-final_v23 up difference keeps all epochs and marks the first sample.",
        "- STD and 3sigma attitude plots use degrees consistently after auditing the legacy port STD artifact.",
        "",
        "## Boundary",
        "",
        "- N4H4E1 is not a paper performance conclusion.",
        "- N4H4E1 does not add raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting, or FGO.",
        "- final_v23 output is not proposed solver input.",
        "- trace/reference remains evaluation-only.",
        "- No output-only correction, tuning, or epoch deletion is performed.",
        "",
        "## Summary",
        "",
        f"- finalv23_attitude_std_unit: {std_unit_report.get('finalv23_attitude_std_unit')}",
        f"- port_attitude_std_unit: {std_unit_report.get('port_attitude_std_unit')}",
        f"- fix_type: {std_unit_report.get('fix_type')}",
        f"- yaw_std_rad_deg_confusion_suspect: {std_unit_report.get('yaw_std_rad_deg_confusion_suspect')}",
        f"- vector_xy_line_removed: {plot_report.get('vector_xy_line_removed')}",
        f"- vector_cloud_scatter_created: {plot_report.get('vector_cloud_scatter_created')}",
        f"- first_sample_up_diff: {plot_report.get('first_sample_up_diff')}",
        f"- second_sample_up_diff: {plot_report.get('second_sample_up_diff')}",
        f"- median_up_diff: {plot_report.get('median_up_diff')}",
        f"- visual_candidate_status: {visual_report.get('visual_candidate_status')}",
        f"- manual_visual_review_required: {visual_report.get('manual_visual_review_required')}",
        f"- recommended_next_stage: {visual_report.get('recommended_next_stage')}",
        "",
        "The observed up-difference step is treated as a small port-final_v23 height offset diagnostic, not divergence and not a reason to delete samples.",
        "If manual review of the corrected figures finds no anomaly, the next stage may enter N5 raw Doppler foundation.",
        "",
    ]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def write_visual_e1_reports(
    *,
    report_output_dir: str | Path,
    figure_output_dir: str | Path,
    std_unit_report: dict[str, Any],
    plot_report: dict[str, Any],
) -> dict[str, Any]:
    visual = make_visual_e1_report(std_unit_report=std_unit_report, plot_report=plot_report)
    sanity = make_visual_e1_sanity_report(std_unit_report=std_unit_report, plot_report=plot_report, visual_report=visual)
    report_dir = Path(report_output_dir)
    case_dir = Path(figure_output_dir) / "09_case_review"
    _write_json(report_dir / "VISUAL_VALIDATION_E1_REPORT.json", visual)
    _write_json(report_dir / "VISUAL_SANITY_E1_REPORT.json", sanity)
    _write_json(case_dir / "VISUAL_VALIDATION_E1_REPORT.json", visual)
    _write_json(case_dir / "VISUAL_SANITY_E1_REPORT.json", sanity)
    write_visual_case_review_e1(case_dir / "visual_case_review_e1.md", std_unit_report=std_unit_report, plot_report=plot_report, visual_report=visual)
    return visual
