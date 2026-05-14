#!/usr/bin/env python3
"""Run N8F1 legged candidate factor visual validation.

中文说明：N8F1 只做 runtime 图像验证和语义审查，不改 solver、不反馈 EKF。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_n8f_factor_signal_review import build_n8f_factor_signal_review, write_factor_signal_review
from legsa_gins.fgo.fgo_n8f_plot_coverage import build_n8f1_plot_coverage_report, write_plot_coverage_report
from legsa_gins.fgo.fgo_n8f_plot_semantic_guard import build_n8f_plot_semantic_guard, write_plot_semantic_guard
from legsa_gins.fgo.fgo_n8f_visual_loader import load_n8f_visual_inputs, write_json_report
from legsa_gins.fgo.fgo_n8f_visual_plots_final import generate_n8f1_visual_figures
from legsa_gins.fgo.fgo_n8f_visual_sanity import build_n8f_visual_sanity_report, write_visual_sanity_report
from legsa_gins.fgo.fgo_n8f1_decision import build_n8f1_decision_report, write_n8f1_decision_report


def _parse_bool(value: str) -> bool:
    return str(value).lower() in {"1", "true", "yes", "y"}


def _write_case_review(path: Path, payload: Mapping[str, Any]) -> None:
    decision = payload["decision"]
    signal = payload["signal"]
    lines = [
        "# N8F1 Legged Candidate Factor Visual Case Review",
        "",
        "N8F1 validates activated legged candidate FGO factors visually.",
        "",
        f"- decision: `{decision.get('status')}`",
        f"- recommended next stage: `{decision.get('recommended_next_stage')}`",
        f"- contact signal: `{signal.get('contact_aware_weighting', {}).get('signal_status')}`",
        f"- foot signal: `{signal.get('foot_kinematic_velocity', {}).get('signal_status')}`",
        f"- yawrate signal: `{signal.get('yawrate_between', {}).get('signal_status')}`",
        f"- relative odometry signal: `{signal.get('relative_odometry_between', {}).get('signal_status')}`",
        "",
        "Boundary: diagnostic engineering visual evidence only; no feedback, no substitution, no Go2 truth claim, no trace/final_v23 tuning, and no paper performance claim.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8f-root", required=True)
    parser.add_argument("--n8e-root", required=True)
    parser.add_argument("--n8d-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--rerun-missing-timeseries", default="true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.allow_run:
        raise SystemExit("--allow-run is required for N8F1 runtime generation")
    output_dir = Path(args.output_dir)
    figure_dir = Path(args.figure_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    visual_manifest, visual_data = load_n8f_visual_inputs(
        n8f_root=args.n8f_root,
        rerun_missing_timeseries=_parse_bool(args.rerun_missing_timeseries),
    )
    write_json_report(output_dir / "N8F1_VISUAL_INPUT_MANIFEST.json", visual_manifest)

    reports = visual_data["reports"]
    signal_report = build_n8f_factor_signal_review(
        reports=reports,
        contact_timeseries=visual_data["contact_timeseries"],
        foot_series=visual_data["foot_residual_series"],
        yawrate_series=visual_data["yawrate_residual_series"],
        relative_series=visual_data["relative_odometry_residual_series"],
        variants=visual_data["variants"],
    )
    figure_manifest, coverage_rows, semantic_labels = generate_n8f1_visual_figures(
        figure_output_dir=figure_dir,
        visual_data=visual_data,
        signal_preview=signal_report,
    )
    write_json_report(output_dir / "N8F1_FIGURE_MANIFEST.json", figure_manifest)
    coverage_report = build_n8f1_plot_coverage_report(
        figure_manifest=figure_manifest,
        coverage_rows=coverage_rows,
        n8f_reports=reports,
    )
    write_plot_coverage_report(output_dir / "N8F1_PLOT_DATA_COVERAGE_REPORT.json", coverage_report)
    write_factor_signal_review(output_dir / "N8F1_FACTOR_SIGNAL_REVIEW_REPORT.json", signal_report)
    semantic_report = build_n8f_plot_semantic_guard(figure_manifest=figure_manifest, semantic_labels=semantic_labels)
    write_plot_semantic_guard(output_dir / "N8F1_PLOT_SEMANTIC_GUARD_REPORT.json", semantic_report)
    sanity_report = build_n8f_visual_sanity_report(
        visual_manifest=visual_manifest,
        figure_manifest=figure_manifest,
        coverage_report=coverage_report,
        signal_report=signal_report,
        semantic_report=semantic_report,
        n8f_decision=reports.get("decision", {}),
    )
    write_visual_sanity_report(output_dir / "N8F1_VISUAL_SANITY_REPORT.json", sanity_report)
    decision_report = build_n8f1_decision_report(
        figure_manifest=figure_manifest,
        coverage_report=coverage_report,
        signal_report=signal_report,
        semantic_report=semantic_report,
        sanity_report=sanity_report,
    )
    write_n8f1_decision_report(output_dir / "N8F1_LEGGED_FACTOR_VISUAL_DECISION_REPORT.json", decision_report)
    _write_case_review(output_dir / "n8f1_visual_case_review.md", {"decision": decision_report, "signal": signal_report})

    print(
        json.dumps(
            {
                "stage": "N8F1",
                "status": decision_report.get("status"),
                "recommended_next_stage": decision_report.get("recommended_next_stage"),
                "figures": figure_manifest.get("figure_count_total"),
                "required_figures_nonempty": figure_manifest.get("required_figures_nonempty"),
                "no_feedback": True,
                "paper_performance_claim": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

