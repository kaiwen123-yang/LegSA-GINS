#!/usr/bin/env python3
"""Run N8C3 Raw Doppler FGO factor activation fix.

中文说明：runtime 路径只作为命令行参数使用，tracked 文件只记录 role alias。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_n8c3_decision import make_n8c3_decision
from legsa_gins.fgo.fgo_n8c3_visual_plots import generate_n8c3_figures
from legsa_gins.fgo.fgo_n8c_visual_loader import load_n8c_visual_inputs
from legsa_gins.fgo.fgo_raw_doppler_dataset_link import link_raw_doppler_to_fgo_epochs
from legsa_gins.fgo.fgo_raw_doppler_factor_contract import build_raw_doppler_factor_contract_report, write_json_report
from legsa_gins.fgo.fgo_raw_doppler_factor_fix import build_raw_doppler_fix_comparison_report, run_n8c3_raw_doppler_variants
from legsa_gins.fgo.fgo_raw_doppler_jacobian_check import build_raw_doppler_jacobian_check_report
from legsa_gins.fgo.fgo_raw_doppler_solver_injection import build_solver_injection_report
from legsa_gins.fgo.fgo_raw_doppler_toggle_regression import build_raw_doppler_toggle_regression_report
from legsa_gins.fgo.fgo_yaw_convention_fix import STATE_FIELDS, _f
from legsa_gins.fgo.fgo_yaw_convention_audit import read_json_report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8c2-root", required=True)
    parser.add_argument("--n8c-root", required=True)
    parser.add_argument("--n8b-root", required=True)
    parser.add_argument("--n8a2-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--run-rerun", choices=["true", "false"], default="true")
    return parser.parse_args(argv)


def _vectors_from_rows(rows: list[dict[str, Any]]) -> list[list[float]]:
    return [[_f(row.get(field)) for field in STATE_FIELDS] for row in rows]


def _write_case_review(
    path: Path,
    *,
    contract: dict[str, Any],
    dataset_link: dict[str, Any],
    solver_injection: dict[str, Any],
    toggle: dict[str, Any],
    variants: dict[str, Any],
    decision: dict[str, Any],
    figures: dict[str, Any],
) -> None:
    lines = [
        "# N8C3 Raw Doppler FGO factor fix",
        "",
        "Runtime role aliases:",
        "",
        "- N8C2_REPORT_OUTPUT_DIR",
        "- N8C_REPORT_OUTPUT_DIR",
        "- N8B_REPORT_OUTPUT_DIR",
        "- N8A2_REPORT_OUTPUT_DIR",
        "- N5B_REPORT_OUTPUT_DIR",
        "- N8C3_REPORT_OUTPUT_DIR",
        "- N8C3_FIGURE_OUTPUT_DIR",
        "",
        f"- contract_toy_passed: {contract.get('toy_passed')}",
        f"- source_epoch_count: {dataset_link.get('source_epoch_count')}",
        f"- aligned_factor_count: {dataset_link.get('aligned_factor_count')}",
        f"- factor_table_rows: {dataset_link.get('factor_table_rows')}",
        f"- appears_in_solver_residual_vector: {solver_injection.get('appears_in_solver_residual_vector')}",
        f"- residual_row_count: {solver_injection.get('residual_row_count')}",
        f"- jacobian_nonzero_count: {solver_injection.get('jacobian_nonzero_count')}",
        f"- residual_vector_dim_delta: {solver_injection.get('dim_delta')}",
        f"- toggle_regression_passed: {toggle.get('toggle_regression_passed')}",
        f"- real_solver_variant_count: {variants.get('variant_count')}",
        f"- decision_status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- figure_count: {figures.get('figure_count_total')}",
        "",
        "Boundaries:",
        "",
        "- Raw Doppler is injected into the no-feedback FGO residual/Jacobian assembly.",
        "- Weight sensitivity is diagnostic only.",
        "- FGO output does not feed back into EKF and does not replace EKF NAV.",
        "- Trace/final_v23 are not solver inputs and are not used for tuning.",
        "- No paper performance claim.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.allow_run:
        raise SystemExit("--allow-run is required")
    out = Path(args.output_dir)
    figs = Path(args.figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    manifest, data = load_n8c_visual_inputs(n8b_root=args.n8b_root, n8a2_root=args.n8a2_root, rerun_missing_timeseries=True)
    ekf_rows = data["ekf_rows"]
    if not ekf_rows:
        raise SystemExit("N8C3 requires N8A EKF state nodes through N8B/N8A2 inputs")
    n8c2_decision = read_json_report(Path(args.n8c2_root) / "N8C2_FGO_FACTOR_ACTIVATION_DECISION_REPORT.json")
    n8c_decision = read_json_report(Path(args.n8c_root) / "N8C_NO_FEEDBACK_FGO_VISUAL_DECISION_REPORT.json")
    write_json_report(
        out / "N8C3_INPUT_MANIFEST.json",
        {
            "stage": "N8C3_raw_doppler_fgo_factor_fix",
            "n8c2_decision_status": n8c2_decision.get("status"),
            "n8c_decision_status": n8c_decision.get("status"),
            "n8b_reports_found": manifest.get("n8b_reports_found"),
            "n8a2_reports_found": manifest.get("n8a2_reports_found"),
            "role_aliases": [
                "N8C2_REPORT_OUTPUT_DIR",
                "N8C_REPORT_OUTPUT_DIR",
                "N8B_REPORT_OUTPUT_DIR",
                "N8A2_REPORT_OUTPUT_DIR",
                "N5B_REPORT_OUTPUT_DIR",
                "N8C3_REPORT_OUTPUT_DIR",
                "N8C3_FIGURE_OUTPUT_DIR",
            ],
            "no_feedback": True,
            "output_substitution": False,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "paper_performance_claim": False,
        },
    )

    contract = build_raw_doppler_factor_contract_report()
    write_json_report(out / "FGO_RAW_DOPPLER_FACTOR_CONTRACT_REPORT.json", contract)

    raw_factors, dataset_link = link_raw_doppler_to_fgo_epochs(fgo_rows=ekf_rows, n5b_root=args.n5b_root)
    write_json_report(out / "FGO_RAW_DOPPLER_DATASET_LINK_REPORT.json", dataset_link)

    if args.run_rerun == "true":
        variant_report, rows_by_variant = run_n8c3_raw_doppler_variants(ekf_rows=ekf_rows, raw_factors=raw_factors)
    else:
        variant_report, rows_by_variant = (
            {
                "stage": "N8C3_raw_doppler_fgo_factor_fix",
                "variants": [],
                "variant_count": 0,
                "all_required_variants_run": False,
                "all_variants_real_solver_rerun": False,
                "no_feedback": True,
                "output_substitution": False,
                "trace_solver_input": False,
                "final_v23_output_solver_input": False,
                "paper_performance_claim": False,
            },
            {},
        )
    write_json_report(out / "N8C3_RAW_DOPPLER_RERUN_VARIANT_SUMMARIES.json", variant_report)

    variant_map = {row.get("variant"): row for row in variant_report.get("variants", [])}
    with_raw = variant_map.get("weak_yaw_smoothness_with_raw_fixed", {})
    without_raw = variant_map.get("raw_doppler_off_verified", {})
    solver_injection = build_solver_injection_report(with_raw_summary=with_raw, without_raw_summary=without_raw)
    write_json_report(out / "FGO_RAW_DOPPLER_SOLVER_INJECTION_REPORT.json", solver_injection)

    comparison = build_raw_doppler_fix_comparison_report(variant_report=variant_report)
    write_json_report(out / "N8C3_RAW_DOPPLER_FIX_COMPARISON_REPORT.json", comparison)

    solution_vectors = _vectors_from_rows(rows_by_variant.get("weak_yaw_smoothness_with_raw_fixed", []))
    jacobian = build_raw_doppler_jacobian_check_report(solution_vectors=solution_vectors, raw_factors=raw_factors)
    write_json_report(out / "FGO_RAW_DOPPLER_JACOBIAN_CHECK_REPORT.json", jacobian)

    toggle = build_raw_doppler_toggle_regression_report(
        ekf_rows=ekf_rows,
        raw_factors=raw_factors,
        with_raw_summary=with_raw,
        without_raw_summary=without_raw,
    )
    write_json_report(out / "FGO_RAW_DOPPLER_TOGGLE_REGRESSION_REPORT.json", toggle)

    preview = make_n8c3_decision(
        dataset_link_report=dataset_link,
        solver_injection_report=solver_injection,
        toggle_regression_report=toggle,
        variant_report=variant_report,
        figure_manifest={"figure_count_total": 0, "required_figures_nonempty": False},
    )
    figure_manifest = generate_n8c3_figures(
        figure_output_dir=figs,
        raw_factors=raw_factors,
        rows_by_variant=rows_by_variant,
        variant_report=variant_report,
        solver_injection_report=solver_injection,
        toggle_report=toggle,
        decision_preview=preview,
    )
    write_json_report(out / "N8C3_FIGURE_MANIFEST.json", figure_manifest)
    decision = make_n8c3_decision(
        dataset_link_report=dataset_link,
        solver_injection_report=solver_injection,
        toggle_regression_report=toggle,
        variant_report=variant_report,
        figure_manifest=figure_manifest,
    )
    write_json_report(out / "N8C3_RAW_DOPPLER_FGO_FACTOR_FIX_DECISION_REPORT.json", decision)
    _write_case_review(
        out / "n8c3_raw_doppler_factor_fix_case_review.md",
        contract=contract,
        dataset_link=dataset_link,
        solver_injection=solver_injection,
        toggle=toggle,
        variants=variant_report,
        decision=decision,
        figures=figure_manifest,
    )
    print(
        json.dumps(
            {
                "decision_status": decision.get("status"),
                "recommended_next_stage": decision.get("recommended_next_stage"),
                "aligned_factor_count": dataset_link.get("aligned_factor_count"),
                "appears_in_solver_residual_vector": solver_injection.get("appears_in_solver_residual_vector"),
                "residual_row_count": solver_injection.get("residual_row_count"),
                "jacobian_nonzero_count": solver_injection.get("jacobian_nonzero_count"),
                "residual_vector_dim_delta": solver_injection.get("dim_delta"),
                "figure_count_total": figure_manifest.get("figure_count_total"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
