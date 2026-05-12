#!/usr/bin/env python3
"""Run N6B1 source-aware LSIM/OIM visual validation.

中文说明：N6B1 是 N6B 后置图像检查，只生成 runtime-only 报告和图像；不修改
滤波器数学、不调参、不删除 epoch、不提交 figures。
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

from legsa_gins.source_aware.source_aware_n6b_plot_coverage import write_n6b1_plot_coverage_report
from legsa_gins.source_aware.source_aware_n6b_visual_decision import (
    make_n6b1_visual_decision,
    write_n6b1_visual_decision,
)
from legsa_gins.source_aware.source_aware_n6b_visual_loader import (
    load_n6b1_visual_inputs,
    write_n6b1_visual_input_manifest,
)
from legsa_gins.source_aware.source_aware_n6b_visual_plots import generate_n6b1_visual_figures
from legsa_gins.source_aware.source_aware_n6b_visual_sanity import (
    build_n6b1_visual_sanity_report,
    write_n6b1_visual_sanity_report,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n6b-root", required=True)
    parser.add_argument("--n5d1-root", required=True)
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
        "# N6B1 Source-Aware Visual Validation Case Review",
        "",
        "N6B1 is diagnostic-only visual validation after N6B table diagnostics.",
        "",
        f"- N6B reports found: {all(manifest.get('n6b_reports_found', {}).values())}",
        f"- Source-aware trace found: {manifest.get('source_aware_trace_found')}",
        f"- Clean time series found: {manifest.get('clean_time_series_found')}",
        f"- Stress time series found: {manifest.get('stress_time_series_found')}",
        f"- Required figures generated: {coverage.get('required_figures_generated')}",
        f"- Required figures nonempty: {coverage.get('required_figures_nonempty')}",
        f"- Empty plot suspect count: {coverage.get('empty_plot_suspect_count')}",
        f"- Clean no gross degradation visual: {sanity.get('clean_no_gross_degradation_visual')}",
        f"- Receiver position not slammed to cap: {sanity.get('receiver_position_not_slammed_to_cap')}",
        f"- Receiver velocity not slammed to cap: {sanity.get('receiver_velocity_not_slammed_to_cap')}",
        f"- Raw Doppler spike response visible: {sanity.get('raw_doppler_spike_response_visible')}",
        f"- Stress variants visualized: {sanity.get('stress_variants_visualized')}",
        f"- Decision status: {decision.get('status')}",
        f"- Recommended next stage: {decision.get('recommended_next_stage')}",
        "",
        "Boundary: no solver math change, no trace/final_v23 tuning, no Go2 prior, no FGO, no output-only correction, no epoch deletion, and no paper performance claim.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.allow_run:
        raise SystemExit("N6B1 runner requires --allow-run because it writes runtime-only reports and figures")
    output_dir = Path(args.output_dir)
    figure_output_dir = Path(args.figure_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_output_dir.mkdir(parents=True, exist_ok=True)

    visual_inputs = load_n6b1_visual_inputs(
        n6b_root=args.n6b_root,
        n5d1_root=args.n5d1_root,
        dual_root=args.dual_root,
        rerun_missing_timeseries=_truthy(args.rerun_missing_timeseries),
    )
    manifest = visual_inputs["manifest"]
    write_n6b1_visual_input_manifest(output_dir / "N6B1_VISUAL_INPUT_MANIFEST.json", manifest)

    figure_manifest = generate_n6b1_visual_figures(
        visual_inputs=visual_inputs,
        figure_output_dir=figure_output_dir,
    )
    serializable_manifest = _serializable_figure_manifest(figure_manifest)
    _write_json(output_dir / "N6B1_FIGURE_MANIFEST.json", serializable_manifest)
    case_dir = figure_output_dir / "07_case_review"
    _write_json(case_dir / "N6B1_FIGURE_MANIFEST.json", serializable_manifest)

    coverage_report = write_n6b1_plot_coverage_report(
        output_dir / "N6B1_PLOT_DATA_COVERAGE_REPORT.json",
        figure_manifest["coverage"],
    )
    _write_json(case_dir / "N6B1_PLOT_DATA_COVERAGE_REPORT.json", coverage_report)

    sanity_report = build_n6b1_visual_sanity_report(
        visual_inputs=visual_inputs,
        figure_manifest=figure_manifest,
        coverage_report=coverage_report,
    )
    write_n6b1_visual_sanity_report(output_dir / "N6B1_VISUAL_SANITY_REPORT.json", sanity_report)
    _write_json(case_dir / "N6B1_VISUAL_SANITY_REPORT.json", sanity_report)

    decision = make_n6b1_visual_decision(coverage_report=coverage_report, sanity_report=sanity_report)
    write_n6b1_visual_decision(output_dir / "N6B1_VISUAL_VALIDATION_DECISION_REPORT.json", decision)
    _write_json(case_dir / "N6B1_VISUAL_VALIDATION_DECISION_REPORT.json", decision)

    validation_report = {
        "stage": "N6B1_source_aware_visual_validation",
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
        "no_outperform_final_v23_claim": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "go2_prior": False,
        "fgo": False,
    }
    _write_json(output_dir / "N6B1_VISUAL_VALIDATION_REPORT.json", validation_report)
    _write_json(case_dir / "N6B1_VISUAL_VALIDATION_REPORT.json", validation_report)
    _write_case_review(
        case_dir / "n6b1_visual_case_review.md",
        manifest=manifest,
        coverage=coverage_report,
        sanity=sanity_report,
        decision=decision,
    )
    print(json.dumps({"decision": decision, "figure_count_total": serializable_manifest["figure_count_total"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
