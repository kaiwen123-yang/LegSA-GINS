#!/usr/bin/env python3
"""Run N8C no-feedback FGO visual validation.

中文说明：N8C 只做 weak_yaw_smoothness_policy 的图像和贡献审查；
不回写 EKF、不替换 NAV、不使用 trace/final_v23 作为 solver input。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_factor_contribution_review import review_factor_contributions, write_factor_contribution_review
from legsa_gins.fgo.fgo_n8c_decision import make_n8c_decision, write_n8c_decision
from legsa_gins.fgo.fgo_n8c_plot_coverage import build_plot_coverage_report, write_plot_coverage_report
from legsa_gins.fgo.fgo_n8c_visual_loader import load_n8c_visual_inputs, write_visual_input_manifest
from legsa_gins.fgo.fgo_n8c_visual_plots import generate_n8c_figures
from legsa_gins.fgo.fgo_n8c_visual_sanity import build_n8c_visual_sanity_report, write_visual_sanity_report
from legsa_gins.fgo.fgo_yaw_convention_audit import write_json_report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8b-root", required=True)
    parser.add_argument("--n8a2-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--rerun-missing-timeseries", choices=["true", "false"], default="true")
    return parser.parse_args(argv)


def _write_case_review(path: Path, decision: dict[str, Any], contribution: dict[str, Any], figure_manifest: dict[str, Any]) -> None:
    lines = [
        "# N8C no-feedback FGO visual validation",
        "",
        "Runtime role aliases:",
        "",
        "- N8B_REPORT_OUTPUT_DIR",
        "- N8A2_REPORT_OUTPUT_DIR",
        "- N8C_REPORT_OUTPUT_DIR",
        "- N8C_FIGURE_OUTPUT_DIR",
        "",
        f"- decision_status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- figure_count: {figure_manifest.get('figure_count_total')}",
        f"- suspicious_no_effect_factors: {', '.join(contribution.get('suspicious_no_effect_factors', []))}",
        f"- influential_factors: {', '.join(contribution.get('influential_factors', []))}",
        "",
        "Boundaries:",
        "",
        "- FGO visual improvements are diagnostic engineering evidence only.",
        "- FGO output remains no-feedback and does not replace EKF NAV.",
        "- Trace/final_v23 are not solver inputs.",
        "- Candidate factor contribution is reviewed but not formalized.",
        "- No paper performance claim.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_figures_and_coverage(
    *,
    figure_output_dir: Path,
    ekf_rows: list[dict[str, Any]],
    rows_by_variant: dict[str, list[dict[str, Any]]],
    ablation_summary: dict[str, Any],
    factor_weight_review: dict[str, Any],
    candidate_review: dict[str, Any],
    decision_preview: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    figure_manifest, coverage_entries = generate_n8c_figures(
        figure_output_dir=figure_output_dir,
        ekf_rows=ekf_rows,
        rows_by_variant=rows_by_variant,
        ablation_summary=ablation_summary,
        factor_weight_review=factor_weight_review,
        candidate_review=candidate_review,
        decision_preview=decision_preview,
    )
    return figure_manifest, build_plot_coverage_report(coverage_entries)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.allow_run:
        raise SystemExit("--allow-run is required")
    out = Path(args.output_dir)
    figs = Path(args.figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    manifest, data = load_n8c_visual_inputs(
        n8b_root=args.n8b_root,
        n8a2_root=args.n8a2_root,
        rerun_missing_timeseries=args.rerun_missing_timeseries == "true",
    )
    write_visual_input_manifest(out / "N8C_VISUAL_INPUT_MANIFEST.json", manifest)
    reports = data["reports"]
    ekf_rows = data["ekf_rows"]
    rows_by_variant = data["rows_by_variant"]
    ablation_summary = data["ablation_summary"]
    if not ekf_rows or not rows_by_variant:
        raise SystemExit("N8C requires EKF rows and runtime-only variant time series")

    contribution = review_factor_contributions(
        ablation_summary=ablation_summary,
        factor_weight_review=reports["n8b_factor_weight_review"],
        candidate_review=reports["n8b_candidate_review"],
    )
    write_factor_contribution_review(out / "N8C_FACTOR_CONTRIBUTION_REVIEW_REPORT.json", contribution)
    preview = {
        "status": "visual_validation_pending",
        "recommended_next_stage": "pending_coverage_and_sanity",
    }
    figure_manifest, plot_coverage = _run_figures_and_coverage(
        figure_output_dir=figs,
        ekf_rows=ekf_rows,
        rows_by_variant=rows_by_variant,
        ablation_summary=ablation_summary,
        factor_weight_review=reports["n8b_factor_weight_review"],
        candidate_review=reports["n8b_candidate_review"],
        decision_preview=preview,
    )
    visual_sanity = build_n8c_visual_sanity_report(
        manifest=manifest,
        ekf_rows=ekf_rows,
        rows_by_variant=rows_by_variant,
        ablation_summary=ablation_summary,
        plot_coverage=plot_coverage,
        factor_contribution=contribution,
        figure_manifest=figure_manifest,
    )
    decision = make_n8c_decision(
        plot_coverage=plot_coverage,
        visual_sanity=visual_sanity,
        factor_contribution=contribution,
        candidate_review=reports["n8b_candidate_review"],
    )
    figure_manifest, plot_coverage = _run_figures_and_coverage(
        figure_output_dir=figs,
        ekf_rows=ekf_rows,
        rows_by_variant=rows_by_variant,
        ablation_summary=ablation_summary,
        factor_weight_review=reports["n8b_factor_weight_review"],
        candidate_review=reports["n8b_candidate_review"],
        decision_preview=decision,
    )
    visual_sanity = build_n8c_visual_sanity_report(
        manifest=manifest,
        ekf_rows=ekf_rows,
        rows_by_variant=rows_by_variant,
        ablation_summary=ablation_summary,
        plot_coverage=plot_coverage,
        factor_contribution=contribution,
        figure_manifest=figure_manifest,
    )
    decision = make_n8c_decision(
        plot_coverage=plot_coverage,
        visual_sanity=visual_sanity,
        factor_contribution=contribution,
        candidate_review=reports["n8b_candidate_review"],
    )
    write_json_report(out / "N8C_FIGURE_MANIFEST.json", figure_manifest)
    write_plot_coverage_report(out / "N8C_PLOT_DATA_COVERAGE_REPORT.json", plot_coverage)
    write_visual_sanity_report(out / "N8C_VISUAL_SANITY_REPORT.json", visual_sanity)
    write_n8c_decision(out / "N8C_NO_FEEDBACK_FGO_VISUAL_DECISION_REPORT.json", decision)
    _write_case_review(out / "n8c_visual_case_review.md", decision, contribution, figure_manifest)
    print(
        json.dumps(
            {
                "decision_status": decision.get("status"),
                "recommended_next_stage": decision.get("recommended_next_stage"),
                "figure_count_total": figure_manifest.get("figure_count_total"),
                "figures_nonempty": figure_manifest.get("required_figures_nonempty"),
                "suspicious_no_effect_factors": contribution.get("suspicious_no_effect_factors"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
