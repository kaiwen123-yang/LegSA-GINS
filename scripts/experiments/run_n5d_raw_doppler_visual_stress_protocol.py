#!/usr/bin/env python3
"""Run N5D raw Doppler visual validation and velocity-stress protocol.

中文说明：真实路径只来自命令行参数；本 runner 只写 runtime-only 输出，不提交
图像或 NAV/STD/report artifacts。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.raw_gnss.raw_doppler_factor_diagnostics import analyze_raw_doppler_factor_csv
from legsa_gins.raw_gnss.raw_doppler_n5d_decision import make_n5d_decision, write_decision
from legsa_gins.raw_gnss.raw_doppler_stress_evaluator import evaluate_n5d_stress_pairs, write_report as write_stress_report
from legsa_gins.raw_gnss.raw_doppler_stress_matrix import build_n5d_stress_matrix, write_matrix
from legsa_gins.raw_gnss.raw_doppler_stress_runner import (
    load_existing_or_n5c_variant_summaries,
    run_n5d_stress_variants,
)
from legsa_gins.raw_gnss.raw_doppler_time_alignment import analyze_factor_time_alignment, read_first_column_times
from legsa_gins.raw_gnss.raw_doppler_velocity_comparison import compare_raw_doppler_velocity_to_receiver_velocity
from legsa_gins.raw_gnss.raw_doppler_visual_loader import (
    find_clean_gnss,
    find_factor_csv,
    load_n5d_visual_inputs,
    read_json,
    write_json,
)
from legsa_gins.raw_gnss.raw_doppler_visual_plots import generate_n5d_visual_plots
from legsa_gins.raw_gnss.raw_doppler_visual_sanity import build_visual_sanity_report, write_visual_sanity_report


def _str_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n5c-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--run-stress", default="true")
    return parser.parse_args(argv)


def _case_review(decision: dict[str, Any], sanity: dict[str, Any], stress_eval: dict[str, Any], path: Path) -> None:
    lines = [
        "# N5D raw Doppler visual/stress protocol",
        "",
        "This runtime report is diagnostic engineering evidence only.",
        "",
        f"- status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- visual_stress_candidate_passed: {sanity.get('visual_stress_candidate_passed')}",
        f"- stress_help_pair_count: {stress_eval.get('stress_help_pair_count')}",
        f"- stress_degrade_pair_count: {stress_eval.get('stress_degrade_pair_count')}",
        "- paper_performance_claim: false",
        "- proposed_factor_claim: false",
        "- no_outperform_final_v23_claim: true",
        "- final_v23_output_solver_input: false",
        "- trace_solver_input: false",
        "- output_only_correction: false",
        "- bad_epoch_deletion_for_metric: false",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    if not args.allow_run:
        raise RuntimeError("N5D protocol requires --allow-run")
    out = Path(args.output_dir)
    figs = Path(args.figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    factor_csv = find_factor_csv(args.n5b_root)
    clean_gnss = find_clean_gnss(args.clean_root)
    if clean_gnss is None:
        raise FileNotFoundError("clean GNSS input missing under clean root")
    factor_diag = analyze_raw_doppler_factor_csv(factor_csv)
    velocity_comp = compare_raw_doppler_velocity_to_receiver_velocity(factor_csv, clean_gnss)
    gnss_times = read_first_column_times(clean_gnss)
    time_align = analyze_factor_time_alignment(factor_csv, gnss_times, gnss_times, {"raw_doppler_update_count": 0})

    matrix = build_n5d_stress_matrix(factor_csv, out)
    write_matrix(matrix, out / "N5D_STRESS_MATRIX.json")

    if _str_bool(args.run_stress):
        _, variant_reports = run_n5d_stress_variants(
            matrix,
            clean_root=args.clean_root,
            exe=args.exe,
            build_dir=args.build_dir,
            output_dir=out,
            dual_reference=args.dual_root,
        )
    else:
        # 中文说明：toy/审计路径可复用 N5C summaries，不把它当真实 stress 结果。
        variant_reports = load_existing_or_n5c_variant_summaries(args.n5c_root)
        write_json(out / "N5D_STRESS_VARIANT_SUMMARIES.json", {"variants": variant_reports, "toy_or_reuse_only": True, "paper_performance_claim": False})

    plus_update_count = next(
        (int(row.get("raw_doppler_update_count", 0) or 0) for row in variant_reports if row.get("variant_id") == "baseline_plus_raw_doppler_r1"),
        0,
    )
    n5c_time_align = read_json(Path(args.n5c_root) / "RAW_DOPPLER_TIME_ALIGNMENT_REPORT.json")
    time_align = n5c_time_align or analyze_factor_time_alignment(
        factor_csv,
        gnss_times,
        gnss_times,
        {"raw_doppler_update_count": plus_update_count},
    )

    stress_eval = evaluate_n5d_stress_pairs(variant_reports)
    write_stress_report(stress_eval, out / "N5D_STRESS_PAIR_EVALUATION_REPORT.json")

    inputs = load_n5d_visual_inputs(
        factor_csv=factor_csv,
        clean_root=args.clean_root,
        n5c_root=args.n5c_root,
        variant_reports=variant_reports,
        dual_root=args.dual_root,
        factor_diag=factor_diag,
        velocity_comparison=velocity_comp,
        time_alignment=time_align,
    )
    first_manifest = generate_n5d_visual_plots(
        inputs,
        output_dir=out,
        figure_output_dir=figs,
        stress_eval=stress_eval,
    )
    sanity = build_visual_sanity_report(inputs=inputs, figure_manifest=first_manifest, stress_eval=stress_eval)
    write_visual_sanity_report(out / "N5D_VISUAL_SANITY_REPORT.json", sanity)
    decision = make_n5d_decision(sanity, stress_eval)
    write_decision(decision, out / "N5D_RAW_DOPPLER_VISUAL_STRESS_DECISION_REPORT.json")
    final_manifest = generate_n5d_visual_plots(
        inputs,
        output_dir=out,
        figure_output_dir=figs,
        stress_eval=stress_eval,
        visual_sanity=sanity,
        decision=decision,
    )
    _case_review(decision, sanity, stress_eval, out / "n5d_visual_case_review.md")
    _case_review(decision, sanity, stress_eval, figs / "08_case_review" / "n5d_visual_case_review.md")
    report = {
        "stage": "N5D_raw_doppler_visual_validation_and_velocity_stress_protocol",
        "factor_csv_found": True,
        "clean_gnss_found": True,
        "dual_reference_found": (Path(args.dual_root) / "KF_GINS_Navresult.nav").exists(),
        "n5c_reports_found": Path(args.n5c_root).exists(),
        "figure_count_total": final_manifest.get("figure_count_total", 0),
        "required_figures_generated": final_manifest.get("required_figures_generated", False),
        "visual_sanity": sanity,
        "stress_evaluation": stress_eval,
        "decision": decision,
        "factor_diagnostics": factor_diag,
        "velocity_comparison": velocity_comp,
        "time_alignment": time_align,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
    write_json(out / "N5D_RAW_DOPPLER_VISUAL_STRESS_REPORT.json", report)
    write_json(figs / "08_case_review" / "N5D_VISUAL_STRESS_REPORT.json", report)
    print(json.dumps(decision, indent=2, sort_keys=True))
    return report


def main(argv: list[str] | None = None) -> int:
    run_pipeline(parse_args(argv or sys.argv[1:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
