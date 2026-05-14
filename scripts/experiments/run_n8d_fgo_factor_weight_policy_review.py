#!/usr/bin/env python3
"""Run N8D no-feedback FGO factor weight policy review.

中文说明：runtime 路径只作为命令行参数使用；报告只记录 role alias。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_dual_yaw_weight_policy import run_dual_yaw_weight_policy
from legsa_gins.fgo.fgo_formal_ablation_matrix import (
    build_formal_ablation_matrix_report,
    build_n8d_comparison_report,
    run_n8d_weight_policy_variants,
)
from legsa_gins.fgo.fgo_go2_joint_weight_policy import run_go2_joint_weight_policy
from legsa_gins.fgo.fgo_n8c_visual_loader import load_n8c_visual_inputs
from legsa_gins.fgo.fgo_n8d_decision import make_n8d_decision
from legsa_gins.fgo.fgo_n8d_visual_plots import generate_n8d_figures
from legsa_gins.fgo.fgo_process_factor_policy_review import build_process_factor_policy_review
from legsa_gins.fgo.fgo_raw_doppler_dataset_link import link_raw_doppler_to_fgo_epochs
from legsa_gins.fgo.fgo_raw_doppler_factor_contract import write_json_report
from legsa_gins.fgo.fgo_raw_receiver_weight_balance import run_raw_receiver_weight_balance
from legsa_gins.fgo.fgo_smoothness_weight_policy import build_smoothness_weight_policy_report
from legsa_gins.fgo.fgo_weight_policy_grid import FORMAL_ABLATION_VARIANTS, build_n8d_weight_policy_grid
from legsa_gins.fgo.fgo_whitened_balance_policy import build_whitened_balance_policy_report
from legsa_gins.fgo.fgo_yaw_convention_audit import read_json_report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8c3-root", required=True)
    parser.add_argument("--n8c2-root", required=True)
    parser.add_argument("--n8c-root", required=True)
    parser.add_argument("--n8b-root", required=True)
    parser.add_argument("--n8a2-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n7c6-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def _write_case_review(
    path: Path,
    *,
    grid: dict[str, Any],
    balance: dict[str, Any],
    smoothness: dict[str, Any],
    raw_receiver: dict[str, Any],
    go2: dict[str, Any],
    dual_yaw: dict[str, Any],
    process: dict[str, Any],
    formal: dict[str, Any],
    decision: dict[str, Any],
    figures: dict[str, Any],
) -> None:
    lines = [
        "# N8D FGO factor weight policy review",
        "",
        "Runtime role aliases:",
        "",
        "- N8C3_REPORT_OUTPUT_DIR",
        "- N8C2_REPORT_OUTPUT_DIR",
        "- N8C_REPORT_OUTPUT_DIR",
        "- N8B_REPORT_OUTPUT_DIR",
        "- N8A2_REPORT_OUTPUT_DIR",
        "- N5B_REPORT_OUTPUT_DIR",
        "- N7C6_REPORT_OUTPUT_DIR",
        "- N8D_REPORT_OUTPUT_DIR",
        "- N8D_FIGURE_OUTPUT_DIR",
        "",
        f"- policy_grid_formal_variant_count: {len(grid.get('formal_ablation_variants', []))}",
        f"- smoothness_dominance_detected: {balance.get('smoothness_dominance_detected')}",
        f"- raw_receiver_best: {raw_receiver.get('best_solver_visible_raw_receiver_balance')}",
        f"- go2_best: {go2.get('best_solver_visible_go2_joint_policy')}",
        f"- dual_yaw_best: {dual_yaw.get('best_solver_visible_dual_yaw_policy')}",
        f"- process_factor_decision: {process.get('decision')}",
        f"- formal_matrix_best_balance: {formal.get('best_solver_visible_balance_variant')}",
        f"- decision_status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- figure_count: {figures.get('figure_count_total')}",
        "",
        "Boundaries:",
        "",
        "- Weight policy selection uses solver-visible diagnostics only.",
        "- Trace/final_v23 are not used for weight tuning and are not solver inputs.",
        "- FGO output does not feed back into EKF and does not replace EKF NAV.",
        "- Smoothness is not deleted as a final shortcut.",
        "- Candidate factors remain diagnostic-only.",
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
        raise SystemExit("N8D requires N8A EKF state nodes through N8B/N8A2 inputs")
    raw_factors, dataset_link = link_raw_doppler_to_fgo_epochs(fgo_rows=ekf_rows, n5b_root=args.n5b_root)
    n8c3_decision = read_json_report(Path(args.n8c3_root) / "N8C3_RAW_DOPPLER_FGO_FACTOR_FIX_DECISION_REPORT.json")
    n8c2_smoothness = read_json_report(Path(args.n8c2_root) / "FGO_SMOOTHNESS_COMPONENT_REVIEW_REPORT.json")
    n8c_decision = read_json_report(Path(args.n8c_root) / "N8C_NO_FEEDBACK_FGO_VISUAL_DECISION_REPORT.json")
    n7c6_decision = read_json_report(Path(args.n7c6_root) / "N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_DECISION_REPORT.json")
    write_json_report(
        out / "N8D_INPUT_MANIFEST.json",
        {
            "stage": "N8D_fgo_factor_weight_policy_review",
            "n8c3_decision_status": n8c3_decision.get("status"),
            "n8c_decision_status": n8c_decision.get("status"),
            "n7c6_decision_found": bool(n7c6_decision),
            "raw_doppler_aligned_factor_count": dataset_link.get("aligned_factor_count"),
            "n8b_reports_found": manifest.get("n8b_reports_found"),
            "n8a2_reports_found": manifest.get("n8a2_reports_found"),
            "role_aliases": [
                "N8C3_REPORT_OUTPUT_DIR",
                "N8C2_REPORT_OUTPUT_DIR",
                "N8C_REPORT_OUTPUT_DIR",
                "N8B_REPORT_OUTPUT_DIR",
                "N8A2_REPORT_OUTPUT_DIR",
                "N5B_REPORT_OUTPUT_DIR",
                "N7C6_REPORT_OUTPUT_DIR",
                "N8D_REPORT_OUTPUT_DIR",
                "N8D_FIGURE_OUTPUT_DIR",
            ],
            "no_feedback": True,
            "output_substitution": False,
            "trace_solver_input": False,
            "trace_weight_tuning": False,
            "final_v23_output_solver_input": False,
            "final_v23_weight_tuning": False,
            "paper_performance_claim": False,
        },
    )

    grid = build_n8d_weight_policy_grid()
    write_json_report(out / "N8D_FGO_WEIGHT_POLICY_GRID.json", grid)

    formal_variant_report, rows_by_variant = run_n8d_weight_policy_variants(
        ekf_rows=ekf_rows,
        raw_factors=raw_factors,
        variants=FORMAL_ABLATION_VARIANTS,
    )
    write_json_report(out / "N8D_FGO_WEIGHT_POLICY_VARIANT_SUMMARIES.json", formal_variant_report)
    formal_matrix = build_formal_ablation_matrix_report(formal_variant_report)
    write_json_report(out / "N8D_FORMAL_ENGINEERING_ABLATION_MATRIX.json", formal_matrix)
    comparison = build_n8d_comparison_report(formal_report=formal_matrix, variant_report=formal_variant_report)
    write_json_report(out / "N8D_FGO_WEIGHT_POLICY_COMPARISON_REPORT.json", comparison)

    balance = build_whitened_balance_policy_report(formal_variant_report)
    write_json_report(out / "FGO_WHITENED_BALANCE_POLICY_REPORT.json", balance)

    smoothness = build_smoothness_weight_policy_report(
        n8c2_smoothness_report=n8c2_smoothness,
        variant_report=formal_variant_report,
    )
    write_json_report(out / "FGO_SMOOTHNESS_WEIGHT_POLICY_REPORT.json", smoothness)

    raw_receiver, raw_receiver_rows = run_raw_receiver_weight_balance(ekf_rows=ekf_rows, raw_factors=raw_factors)
    write_json_report(out / "FGO_RAW_RECEIVER_WEIGHT_BALANCE_REPORT.json", raw_receiver)

    go2, go2_rows = run_go2_joint_weight_policy(ekf_rows=ekf_rows, raw_factors=raw_factors)
    write_json_report(out / "FGO_GO2_JOINT_WEIGHT_POLICY_REPORT.json", go2)

    dual_yaw, dual_rows = run_dual_yaw_weight_policy(ekf_rows=ekf_rows, raw_factors=raw_factors)
    write_json_report(out / "FGO_DUAL_YAW_WEIGHT_POLICY_REPORT.json", dual_yaw)

    process = build_process_factor_policy_review(smoothness_report=smoothness, balance_report=balance)
    write_json_report(out / "FGO_PROCESS_FACTOR_POLICY_REVIEW_REPORT.json", process)

    preview = make_n8d_decision(
        balance_report=balance,
        smoothness_report=smoothness,
        raw_receiver_report=raw_receiver,
        go2_report=go2,
        formal_matrix_report=formal_matrix,
        figure_manifest={"figure_count_total": 0, "required_figures_nonempty": False},
    )
    figure_manifest = generate_n8d_figures(
        figure_output_dir=figs,
        formal_variant_report=formal_variant_report,
        balance_report=balance,
        smoothness_report=smoothness,
        raw_receiver_report=raw_receiver,
        go2_report=go2,
        dual_yaw_report=dual_yaw,
        decision_preview=preview,
    )
    write_json_report(out / "N8D_FIGURE_MANIFEST.json", figure_manifest)

    decision = make_n8d_decision(
        balance_report=balance,
        smoothness_report=smoothness,
        raw_receiver_report=raw_receiver,
        go2_report=go2,
        formal_matrix_report=formal_matrix,
        figure_manifest=figure_manifest,
    )
    write_json_report(out / "N8D_FGO_WEIGHT_POLICY_DECISION_REPORT.json", decision)
    _write_case_review(
        out / "n8d_factor_weight_policy_case_review.md",
        grid=grid,
        balance=balance,
        smoothness=smoothness,
        raw_receiver=raw_receiver,
        go2=go2,
        dual_yaw=dual_yaw,
        process=process,
        formal=formal_matrix,
        decision=decision,
        figures=figure_manifest,
    )
    print(
        json.dumps(
            {
                "decision_status": decision.get("status"),
                "recommended_next_stage": decision.get("recommended_next_stage"),
                "formal_variant_count": formal_variant_report.get("variant_count"),
                "figure_count_total": figure_manifest.get("figure_count_total"),
                "best_balance": formal_matrix.get("best_solver_visible_balance_variant"),
                "raw_receiver_best": raw_receiver.get("best_solver_visible_raw_receiver_balance"),
                "go2_best": go2.get("best_solver_visible_go2_joint_policy"),
                "dual_yaw_best": dual_yaw.get("best_solver_visible_dual_yaw_policy"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    _ = rows_by_variant, raw_receiver_rows, go2_rows, dual_rows
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
