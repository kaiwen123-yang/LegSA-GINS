#!/usr/bin/env python3
"""Run N7C controlled Go2 horizontal velocity weak-prior activation.

中文说明：真实路径只来自命令行参数；N7C 只启用 vn/ve horizontal weak prior，
不使用 Go2 vertical/yaw/position prior，不实现 FGO，不做 paper performance claim。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_horizontal_velocity_ablation import (
    build_n7c_go2_horizontal_velocity_ablation_matrix,
    write_n7c_ablation_matrix,
)
from legsa_gins.go2_prior.go2_horizontal_velocity_activation_runner import (
    run_n7c_horizontal_velocity_matrix,
    write_n7c_reports,
)
from legsa_gins.go2_prior.go2_horizontal_velocity_prior_builder import (
    build_n7c_horizontal_velocity_weak_priors,
)
from legsa_gins.go2_prior.go2_horizontal_velocity_visual_plots import generate_n7c_visual_plots
from legsa_gins.go2_prior.go2_n7c_decision import make_n7c_decision, write_n7c_decision
from legsa_gins.raw_gnss.raw_doppler_visual_loader import find_factor_csv


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n7b5-root", required=True)
    parser.add_argument("--n7a-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n6b-root", required=True)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--run-stress", default="true")
    return parser.parse_args(argv)


def _truthy(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.lower() in {"true", "1", "yes", "on"}


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_case_review(path: str | Path, decision: dict[str, Any], prior_build: dict[str, Any], figure_manifest: dict[str, Any]) -> None:
    lines = [
        "# N7C Go2 horizontal velocity weak prior",
        "",
        "This report is engineering diagnostic evidence for controlled activation.",
        "",
        f"- status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- prior_epoch_count: {prior_build.get('epoch_count')}",
        f"- update_count: {decision.get('update_count')}",
        f"- reject_count: {decision.get('reject_count')}",
        f"- figures_generated: {figure_manifest.get('figure_count_total')}",
        "- measurement_components: vn, ve",
        "- Go2 vertical velocity prior: disabled",
        "- Go2 position prior: disabled",
        "- Go2 yaw prior: disabled",
        "- Go2 velocity is not truth.",
        "- trace_solver_input: false",
        "- final_v23_output_solver_input: false",
        "- no_outperform_final_v23_claim: true",
        "- output_only_correction: false",
        "- paper_performance_claim: false",
        "- fgo: false",
    ]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if not args.allow_run:
        raise SystemExit("--allow-run is required for N7C runtime execution")
    out = Path(args.output_dir)
    figs = Path(args.figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)
    factor_csv = find_factor_csv(args.n5b_root)
    prior_paths, prior_build_report = build_n7c_horizontal_velocity_weak_priors(
        n7b5_root=args.n7b5_root,
        output_dir=out,
    )
    matrix = build_n7c_go2_horizontal_velocity_ablation_matrix(
        output_dir=out,
        raw_doppler_factor_path=factor_csv,
        prior_paths=prior_paths,
        run_stress=_truthy(args.run_stress),
    )
    write_n7c_ablation_matrix(matrix, out / "N7C_GO2_HORIZONTAL_VELOCITY_ABLATION_MATRIX.json")
    _runs, summaries = run_n7c_horizontal_velocity_matrix(
        matrix,
        clean_root=args.clean_root,
        exe=args.exe,
        output_dir=out,
        dual_reference=args.dual_root,
    )
    variant_summaries = {"variants": summaries, "paper_performance_claim": False}
    comparison = write_n7c_reports(out, summaries)
    decision = make_n7c_decision(
        prior_build_report=prior_build_report,
        matrix=matrix,
        variant_summaries=variant_summaries,
        comparison_report=comparison,
    )
    write_n7c_decision(decision, out / "N7C_GO2_HORIZONTAL_VELOCITY_DECISION_REPORT.json")
    figure_manifest = generate_n7c_visual_plots(
        figure_output_dir=figs,
        output_dir=out,
        clean_root=args.clean_root,
        n5b_root=args.n5b_root,
        prior_build_report=prior_build_report,
        variant_summaries=variant_summaries,
        comparison_report=comparison,
        decision=decision,
    )
    _write_case_review(out / "n7c_go2_horizontal_velocity_case_review.md", decision, prior_build_report, figure_manifest)
    run_report = {
        "stage": "N7C_go2_horizontal_velocity_weak_prior",
        "input_roles": {
            "n7b5_root": "N7B5_runtime_report_root",
            "n7a_root": "N7A_go2_body_state_runtime_report_root",
            "n5b_root": "N5B_raw_doppler_runtime_report_root",
            "n6b_root": "N6B_source_aware_policy_runtime_report_root",
            "clean_root": "clean_receiver_velocity_runtime_root",
            "dual_root": "dual_final_v23_runtime_reference_root",
            "output_dir": "N7C_runtime_output_root",
            "figure_output_dir": "N7C_runtime_figure_root",
        },
        "prior_build": prior_build_report,
        "matrix": matrix,
        "variant_summaries": variant_summaries,
        "comparison": comparison,
        "decision": decision,
        "figure_manifest": figure_manifest,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "go2_velocity_truth_claim": False,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }
    _write_json(out / "N7C_GO2_HORIZONTAL_VELOCITY_RUN_REPORT.json", run_report)
    print(json.dumps({"prior_build": prior_build_report, "decision": decision, "figure_manifest": figure_manifest}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
