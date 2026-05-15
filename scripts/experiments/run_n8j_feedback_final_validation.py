#!/usr/bin/env python3
"""Run N8J selected FGO feedback EKF final validation.

Runtime paths are command-line inputs only. Tracked files use role aliases and
must not record local absolute artifact paths.

中文说明：N8J 锁定 N8I selected policy 做最终验证，不再调 gate/covariance。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo_feedback.fgo_feedback_final_decision import build_final_decision_report, write_final_decision_report
from legsa_gins.fgo_feedback.fgo_feedback_final_evaluator import build_final_evaluation_report, write_final_evaluation_report
from legsa_gins.fgo_feedback.fgo_feedback_final_manifest import build_final_feedback_manifest, write_final_feedback_manifest
from legsa_gins.fgo_feedback.fgo_feedback_final_policy import build_selected_policy_report, write_selected_policy_report
from legsa_gins.fgo_feedback.fgo_feedback_final_runner import (
    build_final_comparison_report,
    build_final_variant_summaries,
    run_final_feedback_variants,
)
from legsa_gins.fgo_feedback.fgo_feedback_final_sanity import build_final_sanity_report, write_final_sanity_report
from legsa_gins.fgo_feedback.fgo_feedback_final_visual_plots import generate_final_validation_figures, write_final_figure_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8i-root", required=True)
    parser.add_argument("--n8h-root", required=True)
    parser.add_argument("--n8g-root", required=True)
    parser.add_argument("--n8f1-root", required=True)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args()


def run_n8j_feedback_final_validation(
    *,
    n8i_root: str | Path,
    n8h_root: str | Path,
    n8g_root: str | Path,
    n8f1_root: str | Path,
    clean_root: str | Path,
    dual_root: str | Path,
    build_dir: str | Path,
    exe: str | Path,
    output_dir: str | Path,
    figure_output_dir: str | Path,
    allow_run: bool,
    cwd: str | Path,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    figure_root = Path(figure_output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    figure_root.mkdir(parents=True, exist_ok=True)

    selected_policy = build_selected_policy_report(n8i_root)
    write_selected_policy_report(output_root / "N8J_SELECTED_FEEDBACK_POLICY_REPORT.json", selected_policy)
    bundle = run_final_feedback_variants(
        n8i_root=n8i_root,
        n8h_root=n8h_root,
        n8g_root=n8g_root,
        n8f1_root=n8f1_root,
        clean_root=clean_root,
        dual_root=dual_root,
        build_dir=build_dir,
        exe=exe,
        output_dir=output_root,
        allow_run=allow_run,
        cwd=cwd,
    )
    variant_summaries = build_final_variant_summaries(bundle)
    comparison_report = build_final_comparison_report(bundle)
    evaluation_report = build_final_evaluation_report(bundle)
    provisional_manifest = build_final_feedback_manifest(bundle=bundle, selected_policy=selected_policy, figure_manifest=None)
    provisional_figures = generate_final_validation_figures(
        bundle=bundle,
        selected_policy=selected_policy,
        variant_summaries=variant_summaries,
        evaluation_report=evaluation_report,
        final_manifest=provisional_manifest,
        sanity_report=None,
        decision_report=None,
        figure_output_dir=figure_root,
    )
    final_manifest = build_final_feedback_manifest(bundle=bundle, selected_policy=selected_policy, figure_manifest=provisional_figures)
    sanity_report = build_final_sanity_report(
        selected_policy=selected_policy,
        variant_summaries=variant_summaries,
        evaluation_report=evaluation_report,
        final_manifest=final_manifest,
        figure_manifest=provisional_figures,
    )
    decision_report = build_final_decision_report(
        selected_policy=selected_policy,
        final_manifest=final_manifest,
        sanity_report=sanity_report,
        comparison_report=comparison_report,
    )
    figure_manifest = generate_final_validation_figures(
        bundle=bundle,
        selected_policy=selected_policy,
        variant_summaries=variant_summaries,
        evaluation_report=evaluation_report,
        final_manifest=final_manifest,
        sanity_report=sanity_report,
        decision_report=decision_report,
        figure_output_dir=figure_root,
    )
    final_manifest = build_final_feedback_manifest(bundle=bundle, selected_policy=selected_policy, figure_manifest=figure_manifest)
    sanity_report = build_final_sanity_report(
        selected_policy=selected_policy,
        variant_summaries=variant_summaries,
        evaluation_report=evaluation_report,
        final_manifest=final_manifest,
        figure_manifest=figure_manifest,
    )
    decision_report = build_final_decision_report(
        selected_policy=selected_policy,
        final_manifest=final_manifest,
        sanity_report=sanity_report,
        comparison_report=comparison_report,
    )

    from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json

    write_json(output_root / "N8J_FINAL_FEEDBACK_VARIANT_SUMMARIES.json", variant_summaries)
    write_json(output_root / "N8J_FINAL_FEEDBACK_COMPARISON_REPORT.json", comparison_report)
    write_final_evaluation_report(output_root / "N8J_FINAL_FEEDBACK_EVALUATION_REPORT.json", evaluation_report)
    write_final_feedback_manifest(output_root / "N8J_FINAL_FEEDBACK_MANIFEST.json", final_manifest)
    write_final_sanity_report(output_root / "N8J_FINAL_FEEDBACK_SANITY_REPORT.json", sanity_report)
    write_final_decision_report(output_root / "N8J_FEEDBACK_FINAL_VALIDATION_DECISION_REPORT.json", decision_report)
    write_final_figure_manifest(output_root / "N8J_FIGURE_MANIFEST.json", figure_manifest)
    _write_case_review(output_root / "n8j_feedback_final_validation_case_review.md", decision_report, final_manifest, sanity_report)

    summary = {
        "stage": "N8J",
        "status": decision_report["status"],
        "recommended_next_stage": decision_report["recommended_next_stage"],
        "selected_policy_name": selected_policy["policy_name"],
        "accepted": final_manifest["accepted"],
        "rejected": final_manifest["rejected"],
        "runtime_outputs_generated": final_manifest["runtime_outputs_generated"],
        "figure_count": figure_manifest["figure_count_total"],
        "report_output_role": "n8j_report_output_dir",
        "figure_output_role": "n8j_figure_output_dir",
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "no_future_data_feedback": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def _write_case_review(path: Path, decision: dict[str, Any], manifest: dict[str, Any], sanity: dict[str, Any]) -> None:
    lines = [
        "# N8J Feedback Final Validation Case Review",
        "",
        f"- decision: `{decision.get('status')}`",
        f"- recommended next stage: `{decision.get('recommended_next_stage')}`",
        f"- selected policy: `{manifest.get('selected_policy_name')}`",
        f"- accepted/rejected: `{manifest.get('accepted')}` / `{manifest.get('rejected')}`",
        f"- runtime outputs generated: `{manifest.get('runtime_outputs_generated')}`",
        f"- sanity passed: `{sanity.get('all_checks_passed')}`",
        "",
        "Boundary: BY2 engineering validation only. FGO feedback remains EKF update, not output substitution.",
        "No trace/final_v23 tuning, no future-data feedback, no direct NAV overwrite, and no paper performance claim.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    run_n8j_feedback_final_validation(
        n8i_root=args.n8i_root,
        n8h_root=args.n8h_root,
        n8g_root=args.n8g_root,
        n8f1_root=args.n8f1_root,
        clean_root=args.clean_root,
        dual_root=args.dual_root,
        build_dir=args.build_dir,
        exe=args.exe,
        output_dir=args.output_dir,
        figure_output_dir=args.figure_output_dir,
        allow_run=args.allow_run,
        cwd=ROOT,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
