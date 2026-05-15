#!/usr/bin/env python3
"""Run N8K2 BY2 formal ablation real plot fix.

Runtime paths are command-line inputs only. Tracked code stores role aliases.
"""

# 中文说明：N8K2 只重画真实审计图，不改算法、不调参、不运行退化矩阵。

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json
from legsa_gins.reporting.by2_placeholder_plot_detector import detect_placeholder_plots, write_placeholder_detection_report
from legsa_gins.reporting.by2_real_plot_coverage import build_real_plot_coverage, write_real_plot_coverage
from legsa_gins.reporting.by2_real_plot_data_loader import load_real_plot_data, write_real_plot_data_load_report
from legsa_gins.reporting.by2_real_plot_decision import build_real_plot_decision, write_real_plot_decision
from legsa_gins.reporting.by2_real_plot_materializer import materialize_real_plots, write_real_plot_materialization_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8k-root", required=True)
    parser.add_argument("--n8k-figure-root", required=True)
    parser.add_argument("--n8k-case-review-root", required=True)
    parser.add_argument("--n8k-summary-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n6b-root", required=True)
    parser.add_argument("--n7c6-root", required=True)
    parser.add_argument("--n8f1-root", required=True)
    parser.add_argument("--n8i-root", required=True)
    parser.add_argument("--n8j-root", required=True)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--plot-audit-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--case-review-dir", required=True)
    parser.add_argument("--summary-dir", required=True)
    parser.add_argument("--allow-rerun-missing-runtime", default="true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    del args.n8k_case_review_root, args.n8k_summary_root
    del args.n5b_root, args.n6b_root, args.n7c6_root, args.n8f1_root, args.n8i_root
    del args.clean_root, args.dual_root, args.build_dir, args.exe, args.allow_rerun_missing_runtime
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    data_bundle = load_real_plot_data(args.n8k_root, args.n8j_root)
    write_real_plot_data_load_report(out / "N8K2_REAL_PLOT_DATA_LOAD_REPORT.json", data_bundle["report"])
    materialization = materialize_real_plots(
        n8k_root=args.n8k_root,
        data_bundle=data_bundle,
        figure_output_dir=args.figure_output_dir,
        case_review_dir=args.case_review_dir,
        summary_dir=args.summary_dir,
    )
    write_real_plot_materialization_report(out / "N8K2_REAL_PLOT_MATERIALIZATION_REPORT.json", materialization)
    placeholder = detect_placeholder_plots(n8k_root=args.n8k_root, original_figure_root=args.n8k_figure_root, fixed_figure_root=args.figure_output_dir)
    write_placeholder_detection_report(out / "N8K2_PLACEHOLDER_PLOT_DETECTION_REPORT.json", placeholder)
    coverage = build_real_plot_coverage(n8k_root=args.n8k_root, materialization=materialization, placeholder_report=placeholder, data_report=data_bundle["report"])
    write_real_plot_coverage(out / "N8K2_REAL_PLOT_COVERAGE_REPORT.json", coverage)
    decision = build_real_plot_decision(coverage)
    write_real_plot_decision(out / "N8K2_BY2_REAL_PLOT_FIX_DECISION_REPORT.json", decision)
    write_json(out / "N8K2_REAL_TRAJECTORY_PLOT_REPORT.json", materialization["trajectory_report"])
    timeseries_entries = [item for item in materialization["generated"] if item.get("category") in {"02_position_errors", "03_velocity", "04_attitude", "05_consistency", "06_observation_quality", "07_compare", "08_summary_panels"} and str(item.get("filename", "")).endswith(".png")]
    write_json(
        out / "N8K2_REAL_TIMESERIES_PLOT_REPORT.json",
        {"stage": "N8K2", "generated_count": len(timeseries_entries), "all_real": all((item.get("applicable") is False) or item.get("real_data") for item in timeseries_entries), "paper_performance_claim": False, "outperform_final_v23_claim": False},
    )
    write_json(
        out / "N8K2_REAL_FACTOR_FEEDBACK_LEGGED_PLOT_REPORT.json",
        {
            "stage": "N8K2",
            "fgo_factor_generated_count": materialization["factor_report"]["fgo_factor_generated_count"],
            "feedback_generated_count": materialization["feedback_report"]["feedback_generated_count"],
            "legged_generated_count": materialization["legged_report"]["legged_generated_count"],
            "all_real": materialization["factor_report"]["all_real"] and materialization["feedback_report"]["all_real"] and materialization["legged_report"]["all_real"],
            "paper_performance_claim": False,
            "outperform_final_v23_claim": False,
        },
    )
    _write_case_review(out / "n8k2_by2_formal_ablation_real_plot_fix_case_review.md", decision, placeholder, coverage, materialization)
    summary = {
        "stage": "N8K2",
        "status": decision["status"],
        "recommended_next_stage": decision["recommended_next_stage"],
        "variant_count": data_bundle["report"]["variant_count"],
        "original_applicable_placeholder_count": placeholder["original_applicable_placeholder_count"],
        "fixed_applicable_placeholder_count": placeholder["fixed_applicable_placeholder_count"],
        "figures_generated": materialization["figures_generated"],
        "missing_count": coverage["missing_count"],
        "not_applicable_count": coverage["not_applicable_count"],
        "unresolved_missing_data_count": coverage["unresolved_missing_data_count"],
        "degradation_matrix_run": False,
        "algorithm_changes": False,
        "paper_performance_claim": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _write_case_review(path: Path, decision: dict[str, object], placeholder: dict[str, object], coverage: dict[str, object], materialization: dict[str, object]) -> None:
    path.write_text(
        "# N8K2 BY2 Formal Ablation Real Plot Fix Case Review\n\n"
        f"- decision: `{decision.get('status')}`\n"
        f"- original applicable placeholders: `{placeholder.get('original_applicable_placeholder_count')}`\n"
        f"- fixed applicable placeholders: `{placeholder.get('fixed_applicable_placeholder_count')}`\n"
        f"- generated figures: `{materialization.get('figures_generated')}`\n"
        f"- missing plots: `{coverage.get('missing_count')}`\n"
        f"- unresolved low-information plots: `{coverage.get('low_information_unresolved_count')}`\n"
        "- boundary: no algorithm changes, no degradation matrix, no trace/final_v23 tuning, no paper performance claim.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
