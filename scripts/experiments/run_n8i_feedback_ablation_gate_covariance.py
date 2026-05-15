#!/usr/bin/env python3
"""Run N8I FGO feedback ablation and gate/covariance policy review.

Runtime paths are command-line inputs only. Tracked files use role aliases and
must not record local absolute artifact paths.

中文说明：N8I 运行真实 EKF replay 消融；trace/final_v23 只允许 evaluation-only，
不能作为 feedback 调参输入。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo_feedback.fgo_feedback_attitude_spike_review import build_attitude_spike_review, write_attitude_spike_review
from legsa_gins.fgo_feedback.fgo_feedback_covariance_refinement import (
    build_covariance_refinement_report,
    write_covariance_refinement_report,
)
from legsa_gins.fgo_feedback.fgo_feedback_gate_policy_review import build_gate_policy_review, write_gate_policy_review
from legsa_gins.fgo_feedback.fgo_feedback_mode_ablation import build_feedback_mode_ablation, write_feedback_mode_ablation_reports
from legsa_gins.fgo_feedback.fgo_feedback_n8i_decision import build_n8i_decision_report, write_n8i_decision_report
from legsa_gins.fgo_feedback.fgo_feedback_n8i_visual_plots import generate_n8i_figures, write_n8i_figure_manifest
from legsa_gins.fgo_feedback.fgo_feedback_policy_ablation_runner import run_policy_ablation_matrix
from legsa_gins.fgo_feedback.fgo_feedback_policy_grid import build_feedback_policy_grid, write_policy_grid
from legsa_gins.fgo_feedback.fgo_feedback_window_policy_review import build_window_policy_review, write_window_policy_review


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8g-root", required=True)
    parser.add_argument("--n8h-root", required=True)
    parser.add_argument("--n8f1-root", required=True)
    parser.add_argument("--n8f-root", required=True)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args()


def run_n8i_feedback_ablation_gate_covariance(
    *,
    n8g_root: str | Path,
    n8h_root: str | Path,
    n8f1_root: str | Path,
    n8f_root: str | Path,
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

    policy_grid = build_feedback_policy_grid()
    write_policy_grid(output_root / "N8I_FEEDBACK_POLICY_GRID.json", policy_grid)
    bundle = run_policy_ablation_matrix(
        n8g_root=n8g_root,
        n8h_root=n8h_root,
        n8f1_root=n8f1_root,
        n8f_root=n8f_root,
        clean_root=clean_root,
        dual_root=dual_root,
        build_dir=build_dir,
        exe=exe,
        output_dir=output_root,
        allow_run=allow_run,
        cwd=cwd,
    )
    gate_review = build_gate_policy_review(bundle)
    covariance_review = build_covariance_refinement_report(bundle)
    window_review = build_window_policy_review(bundle)
    mode_summaries, mode_comparison = build_feedback_mode_ablation(bundle)
    attitude_spike_review = build_attitude_spike_review(bundle)

    write_gate_policy_review(output_root / "FGO_FEEDBACK_GATE_POLICY_REVIEW_REPORT.json", gate_review)
    write_covariance_refinement_report(output_root / "FGO_FEEDBACK_COVARIANCE_REFINEMENT_REPORT.json", covariance_review)
    write_window_policy_review(output_root / "FGO_FEEDBACK_WINDOW_POLICY_REVIEW_REPORT.json", window_review)
    write_feedback_mode_ablation_reports(output_root, mode_summaries, mode_comparison)
    write_attitude_spike_review(output_root / "FGO_FEEDBACK_ATTITUDE_SPIKE_REVIEW_REPORT.json", attitude_spike_review)

    provisional_decision = build_n8i_decision_report(
        policy_grid=policy_grid,
        gate_review=gate_review,
        covariance_review=covariance_review,
        window_review=window_review,
        mode_summaries=mode_summaries,
        mode_comparison=mode_comparison,
        attitude_spike_review=attitude_spike_review,
        figure_manifest=None,
    )
    provisional_manifest = generate_n8i_figures(
        bundle=bundle,
        gate_review=gate_review,
        covariance_review=covariance_review,
        window_review=window_review,
        mode_summaries=mode_summaries,
        attitude_spike_review=attitude_spike_review,
        decision_report=provisional_decision,
        figure_output_dir=figure_root,
    )
    decision_report = build_n8i_decision_report(
        policy_grid=policy_grid,
        gate_review=gate_review,
        covariance_review=covariance_review,
        window_review=window_review,
        mode_summaries=mode_summaries,
        mode_comparison=mode_comparison,
        attitude_spike_review=attitude_spike_review,
        figure_manifest=provisional_manifest,
    )
    figure_manifest = generate_n8i_figures(
        bundle=bundle,
        gate_review=gate_review,
        covariance_review=covariance_review,
        window_review=window_review,
        mode_summaries=mode_summaries,
        attitude_spike_review=attitude_spike_review,
        decision_report=decision_report,
        figure_output_dir=figure_root,
    )
    write_n8i_figure_manifest(output_root / "N8I_FIGURE_MANIFEST.json", figure_manifest)
    write_n8i_decision_report(output_root / "N8I_FEEDBACK_ABLATION_GATE_COVARIANCE_DECISION_REPORT.json", decision_report)
    _write_case_review(output_root / "n8i_feedback_ablation_case_review.md", decision_report, gate_review, covariance_review, window_review)

    summary = {
        "stage": "N8I",
        "status": decision_report["status"],
        "recommended_next_stage": decision_report["recommended_next_stage"],
        "selected_gate_policy": decision_report["selected_gate_policy"],
        "selected_covariance_policy": decision_report["selected_covariance_policy"],
        "selected_window_policy": decision_report["selected_window_policy"],
        "selected_feedback_policy": decision_report["selected_feedback_policy"],
        "figure_count": figure_manifest["figure_count_total"],
        "report_output_role": "n8i_report_output_dir",
        "figure_output_role": "n8i_figure_output_dir",
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "no_future_data_feedback": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def _write_case_review(
    path: Path,
    decision: dict[str, Any],
    gate: dict[str, Any],
    covariance: dict[str, Any],
    window: dict[str, Any],
) -> None:
    lines = [
        "# N8I Feedback Ablation Gate/Covariance Case Review",
        "",
        f"- decision: `{decision.get('status')}`",
        f"- recommended next stage: `{decision.get('recommended_next_stage')}`",
        f"- selected gate: `{decision.get('selected_gate_policy')}`",
        f"- selected covariance: `{decision.get('selected_covariance_policy')}`",
        f"- selected window: `{decision.get('selected_window_policy')}`",
        f"- gate classification: `{gate.get('classification')}`",
        f"- covariance policy: `{covariance.get('selected_covariance_policy')}`",
        f"- window policy: `{window.get('selected_window_policy')}`",
        "",
        "Boundary: FGO feedback remains an EKF update, not output substitution or direct NAV overwrite.",
        "Policy refinement uses solver-visible diagnostics only; trace/final_v23 are not tuning inputs.",
        "No future-data feedback and no paper performance claim.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    run_n8i_feedback_ablation_gate_covariance(
        n8g_root=args.n8g_root,
        n8h_root=args.n8h_root,
        n8f1_root=args.n8f1_root,
        n8f_root=args.n8f_root,
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
