"""Write N4H4E visual validation reports.

中文说明：N4H4E visual report 只记录工程图像验证结果；不写 paper
performance claim，不 claim outperform final_v23，不引入 proposed factor。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def make_visual_validation_report(
    *,
    sanity: dict[str, Any],
    figure_manifest: dict[str, Any],
    input_manifest: dict[str, Any],
) -> dict[str, Any]:
    passed = bool(sanity.get("visual_candidate_passed"))
    return {
        "phase": "N4H4E",
        "source_backed_port_visual_validation": True,
        "engineering_backbone_visual_candidate": passed,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "raw_doppler": False,
        "go2_prior": False,
        "lsim_oim": False,
        "fgo": False,
        "no_outperform_final_v23_claim": True,
        "figure_count_total": figure_manifest.get("figure_count_total", 0),
        "figure_count_by_folder": figure_manifest.get("figure_count_by_folder", {}),
        "required_figures_generated": sanity.get("required_figures_generated"),
        "pure_single_comparison_absent": sanity.get("pure_single_comparison_absent"),
        "visual_candidate_passed": passed,
        "manual_visual_review_required": True,
        "visual_manual_review_required": True,
        "recommended_next_stage": "N5_raw_doppler_factor_foundation" if passed else "N4H4E_visual_anomaly_debug",
        "blocking_issues": sanity.get("blocking_issues", []),
        "input_manifest_status": {
            "port_nav_found": input_manifest.get("port_nav_found"),
            "port_std_found": input_manifest.get("port_std_found"),
            "final_v23_nav_found": input_manifest.get("final_v23_nav_found"),
            "final_v23_std_found": input_manifest.get("final_v23_std_found"),
            "trace_found": input_manifest.get("trace_found"),
            "r3c_all_reports_found": input_manifest.get("r3c_all_reports_found"),
        },
    }


def write_visual_case_review(
    path: str | Path,
    *,
    report: dict[str, Any],
    sanity: dict[str, Any],
    figure_manifest: dict[str, Any],
) -> None:
    lines = [
        "# N4H4E Source-Backed Port Visual Case Review",
        "",
        "N4H4R3C split the metric namespace before this visual review.",
        "N4H4E only validates whether the source-backed port-core backbone parity looks visually reasonable.",
        "",
        "## Boundary",
        "",
        "- pure INS and single antenna comparison plots are not included.",
        "- visual validation is not a paper performance claim.",
        "- ported backbone is not a proposed novelty.",
        "- final_v23 output is not proposed solver input.",
        "- trace/reference remains evaluation-only.",
        "- no output-only correction, tuning, or epoch deletion is performed.",
        "",
        "## Summary",
        "",
        f"- figure_count_total: {figure_manifest.get('figure_count_total')}",
        f"- visual_candidate_passed: {report.get('visual_candidate_passed')}",
        f"- manual_visual_review_required: {report.get('manual_visual_review_required')}",
        f"- recommended_next_stage: {report.get('recommended_next_stage')}",
        f"- blocking_issues: {', '.join(report.get('blocking_issues') or []) or 'none'}",
        "",
        "If the manual figure review finds no anomaly, the next stage may start raw Doppler foundation work.",
        "That future stage remains separate from N4H4E and requires its own boundary checks.",
        "",
        "## Sanity Snapshot",
        "",
        f"- time_monotonic: {sanity.get('time_monotonic')}",
        f"- no_nan_inf: {sanity.get('no_nan_inf')}",
        f"- aligned_count: {sanity.get('aligned_count')}",
        f"- yaw_wrap_spike_detected: {sanity.get('yaw_wrap_spike_detected')}",
        f"- horizontal_error_max_reasonable: {sanity.get('horizontal_error_max_reasonable')}",
        f"- up_error_max_reasonable: {sanity.get('up_error_max_reasonable')}",
        f"- yaw_error_abs_max_reasonable: {sanity.get('yaw_error_abs_max_reasonable')}",
        "",
    ]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def write_visual_reports(
    *,
    output_dir: str | Path,
    figure_output_dir: str | Path,
    sanity: dict[str, Any],
    figure_manifest: dict[str, Any],
    input_manifest: dict[str, Any],
) -> dict[str, Any]:
    report = make_visual_validation_report(
        sanity=sanity,
        figure_manifest=figure_manifest,
        input_manifest=input_manifest,
    )
    out = Path(output_dir)
    fig_case = Path(figure_output_dir) / "09_case_review"
    write_json(out / "VISUAL_VALIDATION_REPORT.json", report)
    write_json(out / "VISUAL_SANITY_REPORT.json", sanity)
    write_json(fig_case / "VISUAL_VALIDATION_REPORT.json", report)
    write_json(fig_case / "VISUAL_SANITY_REPORT.json", sanity)
    write_visual_case_review(fig_case / "visual_case_review.md", report=report, sanity=sanity, figure_manifest=figure_manifest)
    return report
