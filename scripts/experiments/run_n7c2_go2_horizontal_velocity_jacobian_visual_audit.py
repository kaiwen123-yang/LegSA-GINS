#!/usr/bin/env python3
"""Run N7C2 Go2 horizontal velocity visual readability and Jacobian audit.

中文说明：N7C2 是 PR #38 的追加审计；只生成 runtime-only 报告和图片，不改
solver 数学、不调参、不 merge、不 tag、不进入 N8A。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_factor_jacobian_contract import (
    build_go2_factor_jacobian_contract_report,
    write_go2_factor_jacobian_contract_report,
)
from legsa_gins.go2_prior.go2_n7c2_decision import make_n7c2_decision, write_n7c2_decision
from legsa_gins.go2_prior.go2_n7c_visual_overlap_audit import (
    build_n7c2_visual_overlap_audit,
    load_n7c2_visual_source_data,
    write_n7c2_visual_overlap_audit,
)
from legsa_gins.go2_prior.go2_n7c_visual_readability_plots import (
    generate_n7c2_readability_figures,
    write_n7c2_figure_manifest,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n7c-root", required=True)
    parser.add_argument("--n7c1-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_case_review(path: str | Path, *, overlap: dict[str, Any], figures: dict[str, Any], jacobian: dict[str, Any], decision: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    status_counts = overlap.get("summary", {}).get("status_counts", {})
    lines = [
        "# N7C2 Go2 horizontal velocity Jacobian and visual readability audit",
        "",
        "N7C2 explains why several N7C/N7C1 curves are visually overlapped and records factor Jacobian contracts.",
        "",
        f"- overlap items: {overlap.get('summary', {}).get('item_count')}",
        f"- clearly separated: {status_counts.get('clearly_separated', 0)}",
        f"- mostly overlapped: {status_counts.get('mostly_overlapped', 0)}",
        f"- near identical: {status_counts.get('identical_or_near_identical', 0)}",
        f"- all overlaps explained: {overlap.get('summary', {}).get('all_overlaps_explained')}",
        f"- readability figures: {figures.get('figure_count_total')}",
        f"- readability figures nonempty: {figures.get('required_figures_nonempty')}",
        f"- active factor contracts: {jacobian.get('active_factor_contract_count')}",
        f"- Go2 horizontal H blocks: {jacobian.get('go2_horizontal_H_nonzero_blocks')}",
        f"- Go2 horizontal vertical derivative zero: {jacobian.get('go2_horizontal_vertical_derivative_zero')}",
        f"- toy finite difference status: {jacobian.get('toy_finite_difference_status')}",
        f"- decision status: {decision.get('status')}",
        f"- recommended next stage: {decision.get('recommended_next_stage')}",
        "",
        "Boundary: no solver math change, no tuning, no epoch deletion, no output-only correction, no Go2 vertical/yaw/position prior, no FGO, no paper performance claim, and no outperform-final_v23 claim.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.allow_run:
        raise SystemExit("N7C2 runner requires --allow-run because it writes runtime-only reports and figures")

    output_dir = Path(args.output_dir)
    figure_dir = Path(args.figure_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    source_data = load_n7c2_visual_source_data(args.n7c_root, args.n7c1_root)
    overlap = build_n7c2_visual_overlap_audit(source_data)
    figures = generate_n7c2_readability_figures(
        source_data=source_data,
        overlap_report=overlap,
        figure_output_dir=figure_dir,
    )
    overlap["summary"]["delta_zoom_generated"] = bool(figures.get("delta_zoom_figures_generated"))
    write_n7c2_visual_overlap_audit(output_dir / "N7C2_VISUAL_OVERLAP_AUDIT_REPORT.json", overlap)
    write_n7c2_figure_manifest(output_dir / "N7C2_FIGURE_MANIFEST.json", figures)

    jacobian = build_go2_factor_jacobian_contract_report()
    write_go2_factor_jacobian_contract_report(output_dir / "N7C2_FACTOR_JACOBIAN_CONTRACT_REPORT.json", jacobian)

    decision = make_n7c2_decision(
        overlap_report=overlap,
        figure_manifest=figures,
        jacobian_report=jacobian,
    )
    write_n7c2_decision(output_dir / "N7C2_JACOBIAN_VISUAL_DECISION_REPORT.json", decision)

    review = {
        "stage": "N7C2_go2_horizontal_velocity_jacobian_visual_audit",
        "visual_overlap": overlap,
        "figure_manifest": figures,
        "factor_jacobian_contract": jacobian,
        "decision": decision,
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }
    _write_json(output_dir / "N7C2_JACOBIAN_VISUAL_CASE_REVIEW.json", review)
    _write_case_review(
        output_dir / "n7c2_jacobian_visual_case_review.md",
        overlap=overlap,
        figures=figures,
        jacobian=jacobian,
        decision=decision,
    )
    print(
        json.dumps(
            {
                "decision": decision,
                "figure_count_total": figures.get("figure_count_total"),
                "required_figures_nonempty": figures.get("required_figures_nonempty"),
                "toy_finite_difference_status": jacobian.get("toy_finite_difference_status"),
                "go2_horizontal_H_nonzero_blocks": jacobian.get("go2_horizontal_H_nonzero_blocks"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
