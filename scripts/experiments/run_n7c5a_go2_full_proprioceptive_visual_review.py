#!/usr/bin/env python3
"""Run N7C5A Go2 full proprioceptive visual review.

中文说明：N7C5A 只复核 N7C5 runtime 图像/数据覆盖；若无 visual blocker，
才建议进入 N7C6。所有图片与报告均为 runtime-only。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_full_proprioceptive_plot_coverage import (
    build_n7c5a_plot_data_coverage,
    write_n7c5a_plot_data_coverage,
)
from legsa_gins.go2_prior.go2_full_proprioceptive_visual_loader import load_n7c5_visual_inputs
from legsa_gins.go2_prior.go2_full_proprioceptive_visual_plots import generate_n7c5a_visual_review_plots
from legsa_gins.go2_prior.go2_full_proprioceptive_visual_sanity import (
    build_n7c5a_visual_sanity,
    write_n7c5a_visual_sanity,
)
from legsa_gins.go2_prior.go2_n7c5a_decision import make_n7c5a_visual_decision, write_n7c5a_visual_decision


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n7c5-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def _write_json(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _write_case_review(path: str | Path, *, coverage: dict[str, Any], sanity: dict[str, Any], decision: dict[str, Any]) -> None:
    lines = [
        "# N7C5A Go2 full proprioceptive visual review",
        "",
        f"- status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- figure_count: {decision.get('figure_count')}",
        f"- contact_rows_summary_only: {coverage.get('contact_rows_summary_only')}",
        f"- foot_kinematic_row_count: {coverage.get('foot_kinematic_row_count')}",
        f"- blocker_reasons: {sanity.get('blocker_reasons')}",
        "- Go2 body-state/contact/velocity/roll/pitch are observations, not truth.",
        "- No trace/final_v23 solver input, no FGO, no paper performance claim.",
    ]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.allow_run:
        raise SystemExit("--allow-run is required for N7C5A runtime execution")
    out = Path(args.output_dir)
    figs = Path(args.figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    inputs = load_n7c5_visual_inputs(args.n7c5_root)
    preview = {
        "status": "n7c5_visual_review_pending",
        "recommended_next_stage": "N7C6_go2_proprioceptive_joint_factor_if_passed",
    }
    figures = generate_n7c5a_visual_review_plots(figure_output_dir=figs, inputs=inputs, decision_preview=preview)
    _write_json(out / "N7C5A_FIGURE_MANIFEST.json", figures)
    inputs["figure_manifest"] = figures
    coverage = build_n7c5a_plot_data_coverage(inputs)
    write_n7c5a_plot_data_coverage(out / "N7C5A_PLOT_DATA_COVERAGE_REPORT.json", coverage)
    sanity = build_n7c5a_visual_sanity(inputs, figures, coverage)
    write_n7c5a_visual_sanity(out / "N7C5A_VISUAL_SANITY_REPORT.json", sanity)
    decision = make_n7c5a_visual_decision(sanity_report=sanity, coverage_report=coverage, figure_manifest=figures)
    write_n7c5a_visual_decision(out / "N7C5A_VISUAL_DECISION_REPORT.json", decision)
    _write_case_review(out / "n7c5a_visual_case_review.md", coverage=coverage, sanity=sanity, decision=decision)
    run_report = {
        "stage": "N7C5A_go2_full_proprioceptive_visual_review",
        "input_roles": {
            "n7c5_root": "N7C5_REPORT_OUTPUT_DIR",
            "output_dir": "N7C5A_REPORT_OUTPUT_DIR",
            "figure_output_dir": "N7C5A_FIGURE_OUTPUT_DIR",
        },
        "coverage": coverage,
        "sanity": sanity,
        "decision": decision,
        "figure_manifest": figures,
        "go2_not_truth": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "fgo": False,
    }
    _write_json(out / "N7C5A_VISUAL_REVIEW_RUN_REPORT.json", run_report)
    print(json.dumps({"coverage": coverage, "sanity": sanity, "decision": decision, "figures": figures}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
