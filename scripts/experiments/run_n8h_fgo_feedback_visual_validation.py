#!/usr/bin/env python3
"""Run N8H FGO feedback EKF visual validation.

Runtime paths are command-line inputs only. Tracked outputs use role aliases and
do not record local absolute paths.

中文说明：运行 N8H 图像验证，不提交运行期报告或图像。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo_feedback.fgo_feedback_correction_review import build_correction_review, write_correction_review
from legsa_gins.fgo_feedback.fgo_feedback_gate_review import build_gate_review, write_gate_review
from legsa_gins.fgo_feedback.fgo_feedback_plot_semantic_guard import build_plot_semantic_guard, write_plot_semantic_guard
from legsa_gins.fgo_feedback.fgo_feedback_position_disabled_audit import (
    build_position_disabled_audit,
    write_position_disabled_audit,
)
from legsa_gins.fgo_feedback.fgo_feedback_variant_ablation_review import (
    build_variant_ablation_review,
    write_variant_ablation_review,
)
from legsa_gins.fgo_feedback.fgo_feedback_visual_decision import build_visual_decision_report, write_visual_decision_report
from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import load_n8h_visual_inputs, write_json, write_visual_input_manifest
from legsa_gins.fgo_feedback.fgo_feedback_visual_plots_final import generate_n8h_figures, write_plot_coverage_report


def _bool_arg(value: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"expected true/false, got {value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8g-root", required=True)
    parser.add_argument("--n8f1-root", required=True)
    parser.add_argument("--n8f-root", required=True)
    parser.add_argument("--n8e-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--rerun-missing-timeseries", type=_bool_arg, default=True)
    return parser.parse_args()


def run_n8h_feedback_visual_validation(
    *,
    n8g_root: str | Path,
    n8f1_root: str | Path,
    n8f_root: str | Path,
    n8e_root: str | Path,
    output_dir: str | Path,
    figure_output_dir: str | Path,
    allow_run: bool,
    rerun_missing_timeseries: bool,
) -> dict[str, Any]:
    del n8f1_root, n8f_root, n8e_root
    if not allow_run:
        raise RuntimeError("--allow-run is required for N8H runtime report generation")
    output_root = Path(output_dir)
    figure_root = Path(figure_output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    figure_root.mkdir(parents=True, exist_ok=True)

    bundle = load_n8h_visual_inputs(n8g_root)
    visual_manifest = dict(bundle.manifest)
    visual_manifest["rerun_missing_timeseries_requested"] = bool(rerun_missing_timeseries)
    if not visual_manifest.get("nav_eval_timeseries_found") and rerun_missing_timeseries:
        visual_manifest["rerun_missing_timeseries_performed"] = False
        visual_manifest["rerun_missing_timeseries_reason"] = "N8G runtime time series unavailable to N8H runner inputs"
    write_visual_input_manifest(output_root / "N8H_VISUAL_INPUT_MANIFEST.json", visual_manifest)

    position_audit = build_position_disabled_audit(bundle)
    variant_review = build_variant_ablation_review(bundle)
    gate_review = build_gate_review(bundle)
    correction_review = build_correction_review(bundle)
    semantic_guard = build_plot_semantic_guard(
        visual_manifest=visual_manifest,
        position_audit=position_audit,
        variant_review=variant_review,
    )

    write_position_disabled_audit(output_root / "FGO_FEEDBACK_POSITION_DISABLED_AUDIT_REPORT.json", position_audit)
    write_variant_ablation_review(output_root / "N8H_FEEDBACK_VARIANT_ABLATION_REVIEW.json", variant_review)
    write_gate_review(output_root / "FGO_FEEDBACK_GATE_VISUAL_REVIEW_REPORT.json", gate_review)
    write_correction_review(output_root / "FGO_FEEDBACK_CORRECTION_REVIEW_REPORT.json", correction_review)
    write_plot_semantic_guard(output_root / "N8H_PLOT_SEMANTIC_GUARD_REPORT.json", semantic_guard)

    provisional_decision = {"status": "pending_n8h_decision"}
    _, provisional_coverage = generate_n8h_figures(
        bundle=bundle,
        position_audit=position_audit,
        variant_review=variant_review,
        gate_review=gate_review,
        correction_review=correction_review,
        semantic_guard=semantic_guard,
        decision_report=provisional_decision,
        figure_output_dir=figure_root,
    )
    decision_report = build_visual_decision_report(
        visual_manifest=visual_manifest,
        position_audit=position_audit,
        variant_review=variant_review,
        gate_review=gate_review,
        correction_review=correction_review,
        semantic_guard=semantic_guard,
        plot_coverage=provisional_coverage,
    )
    figure_manifest, plot_coverage = generate_n8h_figures(
        bundle=bundle,
        position_audit=position_audit,
        variant_review=variant_review,
        gate_review=gate_review,
        correction_review=correction_review,
        semantic_guard=semantic_guard,
        decision_report=decision_report,
        figure_output_dir=figure_root,
    )
    write_plot_coverage_report(output_root / "N8H_PLOT_DATA_COVERAGE_REPORT.json", plot_coverage)
    write_json(output_root / "N8H_FIGURE_MANIFEST.json", figure_manifest)
    write_visual_decision_report(output_root / "N8H_FGO_FEEDBACK_VISUAL_DECISION_REPORT.json", decision_report)
    _write_case_review(output_root / "n8h_feedback_visual_case_review.md", decision_report, position_audit, variant_review, gate_review)

    summary = {
        "stage": "N8H",
        "status": decision_report["status"],
        "recommended_next_stage": decision_report["recommended_next_stage"],
        "report_output_role": "n8h_report_output_dir",
        "figure_output_role": "n8h_figure_output_dir",
        "figure_count": figure_manifest["figure_count_total"],
        "required_figures_nonempty": figure_manifest["all_required_figures_nonempty"],
        "position_disabled_status": position_audit["status"],
        "reject_all_sanity_passed": variant_review["reject_all_sanity_passed"],
        "gate_classification": gate_review["classification"],
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "no_future_data_feedback": True,
        "paper_performance_claim": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def _write_case_review(
    path: Path,
    decision: dict[str, Any],
    position: dict[str, Any],
    variant: dict[str, Any],
    gate: dict[str, Any],
) -> None:
    lines = [
        "# N8H FGO Feedback Visual Case Review",
        "",
        f"- decision: `{decision.get('status')}`",
        f"- recommended next stage: `{decision.get('recommended_next_stage')}`",
        f"- position-disabled audit: `{position.get('status')}`",
        f"- reject-all sanity passed: `{variant.get('reject_all_sanity_passed')}`",
        f"- gate classification: `{gate.get('classification')}`",
        "",
        "Boundary: FGO feedback remains an EKF update, not output substitution or direct NAV overwrite.",
        "Primary position feedback remains disabled; diagnostic PVA is reviewed separately.",
        "No trace/final_v23 tuning, no future-data feedback, and no paper performance claim.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    run_n8h_feedback_visual_validation(
        n8g_root=args.n8g_root,
        n8f1_root=args.n8f1_root,
        n8f_root=args.n8f_root,
        n8e_root=args.n8e_root,
        output_dir=args.output_dir,
        figure_output_dir=args.figure_output_dir,
        allow_run=args.allow_run,
        rerun_missing_timeseries=args.rerun_missing_timeseries,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
