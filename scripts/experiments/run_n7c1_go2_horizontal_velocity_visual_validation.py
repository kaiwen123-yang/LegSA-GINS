#!/usr/bin/env python3
"""Run N7C1 Go2 horizontal velocity visual validation.

中文说明：N7C1 是 PR #38 的后置图像与 plotted-data coverage 审计；只生成
runtime-only 报告和图片，不修改 solver、不调参、不进入 N8A。
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_n7c_plot_coverage import write_n7c1_plot_coverage_report
from legsa_gins.go2_prior.go2_n7c_visual_decision import make_n7c1_visual_decision, write_n7c1_visual_decision
from legsa_gins.go2_prior.go2_n7c_visual_loader import load_n7c1_visual_inputs, write_n7c1_visual_input_manifest
from legsa_gins.go2_prior.go2_n7c_visual_plots import generate_n7c1_visual_figures
from legsa_gins.go2_prior.go2_n7c_visual_sanity import build_n7c1_visual_sanity_report, write_n7c1_visual_sanity_report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n7c-root", required=True)
    parser.add_argument("--n7b5-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n6b-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--rerun-missing-timeseries", default="true")
    return parser.parse_args(argv)


def _truthy(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.lower() in {"true", "1", "yes", "on"}


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _serializable_figure_manifest(figure_manifest: dict[str, Any]) -> dict[str, Any]:
    out = dict(figure_manifest)
    out["coverage"] = [asdict(row) for row in figure_manifest.get("coverage", [])]
    return out


def _write_case_review(path: str | Path, *, manifest: dict[str, Any], coverage: dict[str, Any], sanity: dict[str, Any], decision: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# N7C1 Go2 horizontal velocity visual validation",
        "",
        "N7C1 is visual validation and plotted-data coverage auditing for PR #38.",
        "",
        f"- N7C reports found: {all(manifest.get('n7c_reports_found', {}).values())}",
        f"- prior build report found: {manifest.get('prior_build_report_found')}",
        f"- baseline time series found: {manifest.get('baseline_timeseries_found')}",
        f"- main prior time series found: {manifest.get('main_prior_timeseries_found')}",
        f"- stress time series found: {manifest.get('stress_timeseries_found')}",
        f"- Go2 prior CSV found: {manifest.get('go2_prior_csv_found')}",
        f"- vertical disabled confirmed: {manifest.get('vertical_disabled_confirmed')}",
        f"- required figures generated: {coverage.get('required_figures_generated')}",
        f"- required figures nonempty: {coverage.get('required_figures_nonempty')}",
        f"- empty plot suspect count: {coverage.get('empty_plot_suspect_count')}",
        f"- clean no gross degradation visual: {sanity.get('clean_no_gross_degradation_visual')}",
        f"- update count matches report: {sanity.get('go2_horizontal_prior_update_count_matches_report')}",
        f"- stress variants visualized: {sanity.get('stress_variants_visualized')}",
        f"- decision status: {decision.get('status')}",
        f"- recommended next stage: {decision.get('recommended_next_stage')}",
        "",
        "Boundary: visual validation only; no solver math change, no tuning, no epoch deletion, no output-only correction, no Go2 vertical/yaw/position prior, no FGO, no paper performance claim, and no outperform-final_v23 claim.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.allow_run:
        raise SystemExit("N7C1 runner requires --allow-run because it writes runtime-only reports and figures")
    output_dir = Path(args.output_dir)
    figure_output_dir = Path(args.figure_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_output_dir.mkdir(parents=True, exist_ok=True)
    # 中文说明：build-dir/exe 只保留为 runtime contract 参数；N7C1 不重新编译或修改 solver。
    _ = (args.build_dir, args.exe)

    visual_inputs = load_n7c1_visual_inputs(
        n7c_root=args.n7c_root,
        n7b5_root=args.n7b5_root,
        n5b_root=args.n5b_root,
        n6b_root=args.n6b_root,
        dual_root=args.dual_root,
        rerun_missing_timeseries=_truthy(args.rerun_missing_timeseries),
    )
    manifest = visual_inputs["manifest"]
    write_n7c1_visual_input_manifest(output_dir / "N7C1_VISUAL_INPUT_MANIFEST.json", manifest)

    figure_manifest = generate_n7c1_visual_figures(visual_inputs=visual_inputs, figure_output_dir=figure_output_dir)
    serializable_manifest = _serializable_figure_manifest(figure_manifest)
    _write_json(output_dir / "N7C1_FIGURE_MANIFEST.json", serializable_manifest)

    case_dir = figure_output_dir / "07_case_review"
    _write_json(case_dir / "N7C1_FIGURE_MANIFEST.json", serializable_manifest)

    coverage_report = write_n7c1_plot_coverage_report(
        output_dir / "N7C1_PLOT_DATA_COVERAGE_REPORT.json",
        figure_manifest["coverage"],
    )
    _write_json(case_dir / "N7C1_PLOT_DATA_COVERAGE_REPORT.json", coverage_report)

    sanity_report = build_n7c1_visual_sanity_report(
        visual_inputs=visual_inputs,
        figure_manifest=figure_manifest,
        coverage_report=coverage_report,
    )
    write_n7c1_visual_sanity_report(output_dir / "N7C1_VISUAL_SANITY_REPORT.json", sanity_report)
    _write_json(case_dir / "N7C1_VISUAL_SANITY_REPORT.json", sanity_report)

    n7c_decision = visual_inputs["reports"].get("N7C_GO2_HORIZONTAL_VELOCITY_DECISION_REPORT.json", {})
    decision = make_n7c1_visual_decision(
        coverage_report=coverage_report,
        sanity_report=sanity_report,
        n7c_decision_report=n7c_decision,
    )
    write_n7c1_visual_decision(output_dir / "N7C1_GO2_HORIZONTAL_VELOCITY_VISUAL_DECISION_REPORT.json", decision)
    _write_json(case_dir / "N7C1_GO2_HORIZONTAL_VELOCITY_VISUAL_DECISION_REPORT.json", decision)

    validation_report = {
        "stage": "N7C1_go2_horizontal_velocity_visual_validation",
        "input_manifest": manifest,
        "figure_manifest": {
            "figure_count_total": serializable_manifest.get("figure_count_total"),
            "required_figures_generated": serializable_manifest.get("required_figures_generated"),
            "required_figures_nonempty": serializable_manifest.get("required_figures_nonempty"),
        },
        "coverage_passed": coverage_report.get("visual_validation_passed"),
        "visual_sanity_passed": sanity_report.get("visual_sanity_passed"),
        "decision": decision,
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "go2_vertical_velocity_prior_enabled": False,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "fgo": False,
    }
    _write_json(output_dir / "N7C1_VISUAL_VALIDATION_REPORT.json", validation_report)
    _write_json(case_dir / "N7C1_VISUAL_VALIDATION_REPORT.json", validation_report)
    _write_case_review(
        case_dir / "n7c1_visual_case_review.md",
        manifest=manifest,
        coverage=coverage_report,
        sanity=sanity_report,
        decision=decision,
    )
    print(
        json.dumps(
            {
                "decision": decision,
                "figure_count_total": serializable_manifest["figure_count_total"],
                "required_figures_generated": serializable_manifest["required_figures_generated"],
                "required_figures_nonempty": serializable_manifest["required_figures_nonempty"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
