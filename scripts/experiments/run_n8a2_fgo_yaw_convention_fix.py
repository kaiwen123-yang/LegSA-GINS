#!/usr/bin/env python3
"""Run N8A2 FGO yaw convention / wrap fix.

中文说明：本 runner 重新运行 yaw-wrap-fixed no-feedback FGO；不回写 EKF，
不替换 EKF NAV，不使用 trace/final_v23 调权或作为 solver input。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_n8a2_decision import make_n8a2_decision, write_n8a2_decision
from legsa_gins.fgo.fgo_n8a2_visual_plots import generate_n8a2_figures
from legsa_gins.fgo.fgo_yaw_convention_audit import read_csv_rows, read_json_report, write_json_report
from legsa_gins.fgo.fgo_yaw_convention_fix import rows_to_dataset, run_yaw_wrap_fixed_variant, summarize_variant
from legsa_gins.fgo.fgo_yaw_factor_regression import build_yaw_factor_regression_report, write_yaw_factor_regression_report
from legsa_gins.fgo.fgo_yaw_residuals import build_yaw_residual_contract_report, write_yaw_residual_contract_report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8a-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--run-rerun", choices=["true", "false"], default="true")
    return parser.parse_args(argv)


def _comparison(reference: dict[str, Any], fixed_default: dict[str, Any]) -> dict[str, Any]:
    ref_wrapped = float(reference.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0)
    fixed_wrapped = float(fixed_default.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0)
    ref_horizontal = float(reference.get("horizontal_delta_rmse_m", 0.0) or 0.0)
    fixed_horizontal = float(fixed_default.get("horizontal_delta_rmse_m", 0.0) or 0.0)
    return {
        "stage": "N8A2_fgo_yaw_convention_fix",
        "n8a_reference_yaw_delta_raw_rmse_deg": reference.get("yaw_delta_raw_rmse_deg"),
        "n8a_reference_yaw_delta_wrapped_rmse_deg": ref_wrapped,
        "n8a2_default_yaw_delta_raw_rmse_deg": fixed_default.get("yaw_delta_raw_rmse_deg"),
        "n8a2_default_yaw_delta_wrapped_rmse_deg": fixed_wrapped,
        "yaw_delta_wrapped_improvement_deg": ref_wrapped - fixed_wrapped,
        "n8a_reference_residual_proxy_p95": reference.get("residual_proxy_p95"),
        "n8a2_default_residual_proxy_p95": fixed_default.get("residual_proxy_p95"),
        "n8a2_default_final_cost": fixed_default.get("final_cost"),
        "horizontal_delta_rmse_change_m": fixed_horizontal - ref_horizontal,
        "gross_degradation": fixed_horizontal > max(1.0, 2.0 * ref_horizontal + 0.25),
        "smoothness_factor_deleted": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_yaw_correction": False,
        "paper_performance_claim": False,
    }


def _write_case_review(path: Path, decision: dict[str, Any], comparison: dict[str, Any], variants: dict[str, Any]) -> None:
    lines = [
        "# N8A2 FGO yaw convention fix",
        "",
        "Runtime role aliases:",
        "",
        "- N8A_REPORT_OUTPUT_DIR",
        "- N8A2_REPORT_OUTPUT_DIR",
        "- N8A2_FIGURE_OUTPUT_DIR",
        "",
        f"- decision_status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- secondary_recommendation: {decision.get('secondary_recommendation')}",
        f"- n8a_reference_yaw_delta_wrapped_rmse_deg: {comparison.get('n8a_reference_yaw_delta_wrapped_rmse_deg')}",
        f"- n8a2_default_yaw_delta_wrapped_rmse_deg: {comparison.get('n8a2_default_yaw_delta_wrapped_rmse_deg')}",
        f"- yaw_delta_wrapped_improvement_deg: {comparison.get('yaw_delta_wrapped_improvement_deg')}",
        f"- variant_count: {variants.get('variant_count')}",
        "",
        "Boundaries:",
        "",
        "- FGO yaw residuals use shortest-angle wrapping.",
        "- Smoothness factor is retained; N8A2 does not pass by deleting it.",
        "- FGO output remains no-feedback and does not replace EKF NAV.",
        "- Trace/final_v23 outputs are not FGO solver inputs or weight-tuning inputs.",
        "- This is not output-only yaw correction.",
        "- No paper performance claim.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.allow_run:
        raise SystemExit("--allow-run is required")
    n8a_root = Path(args.n8a_root)
    out = Path(args.output_dir)
    figs = Path(args.figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    ekf_rows = read_csv_rows(n8a_root / "N8A_EKF_STATE_NODES.csv")
    original_fgo_rows = read_csv_rows(n8a_root / "N8A_FGO_DIAGNOSTIC_STATES.csv")
    n8a_smoother_report = read_json_report(n8a_root / "N8A_NO_FEEDBACK_SMOOTHER_REPORT.json")
    dataset = rows_to_dataset(ekf_rows)

    contract = build_yaw_residual_contract_report()
    write_yaw_residual_contract_report(out / "FGO_YAW_RESIDUAL_CONTRACT_REPORT.json", contract)
    regression = build_yaw_factor_regression_report()
    write_yaw_factor_regression_report(out / "FGO_YAW_FACTOR_REGRESSION_REPORT.json", regression)

    reference = summarize_variant(
        variant="original_n8a_for_reference",
        ekf_rows=ekf_rows,
        fgo_rows=original_fgo_rows,
        smoother_report=n8a_smoother_report,
        real_solver_rerun=False,
        notes="Existing N8A runtime output retained as before-fix reference.",
    )
    variants = [reference]
    fixed_rows = original_fgo_rows
    if args.run_rerun == "true":
        fixed_rows, _fixed_report, fixed_summary = run_yaw_wrap_fixed_variant(
            dataset,
            variant="yaw_wrap_fixed_default_active_stack",
            smoothness_weight=0.15,
            notes="Primary N8A2 rerun: smoothness retained, yaw residuals shortest-angle wrapped.",
        )
        variants.append(fixed_summary)
        _rows, _report, summary = run_yaw_wrap_fixed_variant(
            dataset,
            variant="yaw_wrap_fixed_no_smoothness_diagnostic",
            smoothness_weight=0.0,
            notes="Diagnostic-only rerun; not selected as N8A2 final and not used to delete smoothness.",
        )
        variants.append(summary)
        _rows, _report, summary = run_yaw_wrap_fixed_variant(
            dataset,
            variant="yaw_wrap_fixed_weak_smoothness_diagnostic",
            smoothness_weight=0.0375,
            notes="Diagnostic-only weak smoothness rerun; not trace/final_v23 tuned.",
        )
        variants.append(summary)
        _rows, _report, summary = run_yaw_wrap_fixed_variant(
            dataset,
            variant="yaw_wrap_fixed_candidate_stack_diagnostic",
            smoothness_weight=0.15,
            notes="Diagnostic-candidate stack request; N8A foundation has no active candidate equations, so rerun preserves no-feedback default equations.",
        )
        variants.append(summary)
    variant_summary = {
        "stage": "N8A2_fgo_yaw_convention_fix",
        "variant_count": len(variants),
        "variants": variants,
        "real_solver_reruns_performed": args.run_rerun == "true",
        "primary_variant": "yaw_wrap_fixed_default_active_stack",
        "smoothness_factor_deleted": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_yaw_correction": False,
        "paper_performance_claim": False,
    }
    write_json_report(out / "N8A2_FGO_RERUN_VARIANT_SUMMARIES.json", variant_summary)
    fixed_default = next((row for row in variants if row.get("variant") == "yaw_wrap_fixed_default_active_stack"), reference)
    comparison = _comparison(reference, fixed_default)
    write_json_report(out / "N8A2_FGO_YAW_FIX_COMPARISON_REPORT.json", comparison)

    preview = make_n8a2_decision(
        contract=contract,
        regression=regression,
        variant_summary=variant_summary,
        comparison=comparison,
        figures={"required_figures_generated": True, "required_figures_nonempty": True},
    )
    figure_manifest = generate_n8a2_figures(
        figure_output_dir=figs,
        ekf_rows=ekf_rows,
        original_fgo_rows=original_fgo_rows,
        fixed_fgo_rows=fixed_rows,
        variant_summary=variant_summary,
        comparison=comparison,
        decision_preview=preview,
    )
    write_json_report(out / "N8A2_FIGURE_MANIFEST.json", figure_manifest)
    decision = make_n8a2_decision(
        contract=contract,
        regression=regression,
        variant_summary=variant_summary,
        comparison=comparison,
        figures=figure_manifest,
    )
    write_n8a2_decision(out / "N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json", decision)
    _write_case_review(out / "n8a2_yaw_convention_fix_case_review.md", decision, comparison, variant_summary)
    print(
        json.dumps(
            {
                "decision_status": decision.get("status"),
                "recommended_next_stage": decision.get("recommended_next_stage"),
                "n8a_reference_wrapped_rmse": comparison.get("n8a_reference_yaw_delta_wrapped_rmse_deg"),
                "n8a2_default_wrapped_rmse": comparison.get("n8a2_default_yaw_delta_wrapped_rmse_deg"),
                "variant_count": variant_summary.get("variant_count"),
                "figure_count_total": figure_manifest.get("figure_count_total"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
