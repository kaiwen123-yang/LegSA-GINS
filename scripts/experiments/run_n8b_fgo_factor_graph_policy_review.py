#!/usr/bin/env python3
"""Run N8B FGO factor graph policy review.

中文说明：N8B 只审查 no-feedback FGO factor policy；真实重跑 policy
ablations，不使用 trace/final_v23 调权，不把 FGO 输出回写 EKF。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_candidate_factor_review import review_candidate_factors, write_candidate_factor_review
from legsa_gins.fgo.fgo_factor_weight_review import review_factor_weights, write_factor_weight_review
from legsa_gins.fgo.fgo_n8b_decision import make_n8b_decision, write_n8b_decision
from legsa_gins.fgo.fgo_n8b_visual_plots import generate_n8b_figures
from legsa_gins.fgo.fgo_policy_ablation_runner import build_policy_comparison_report, run_n8b_policy_ablations
from legsa_gins.fgo.fgo_policy_grid import build_n8b_policy_grid, write_policy_grid
from legsa_gins.fgo.fgo_smoothness_policy_review import review_smoothness_policy, write_smoothness_policy_review
from legsa_gins.fgo.fgo_yaw_convention_audit import read_csv_rows, read_json_report, write_json_report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8a2-root", required=True)
    parser.add_argument("--n8a-root", required=True)
    parser.add_argument("--n7c6-root", required=True)
    parser.add_argument("--n7c5-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def _write_case_review(
    path: Path,
    *,
    decision: dict[str, Any],
    smoothness: dict[str, Any],
    factors: dict[str, Any],
    candidates: dict[str, Any],
    ablations: dict[str, Any],
) -> None:
    lines = [
        "# N8B FGO factor graph policy review",
        "",
        "Runtime role aliases:",
        "",
        "- N8A2_REPORT_OUTPUT_DIR",
        "- N8A_REPORT_OUTPUT_DIR",
        "- N7C6_REPORT_OUTPUT_DIR",
        "- N7C5_REPORT_OUTPUT_DIR",
        "- N8B_REPORT_OUTPUT_DIR",
        "- N8B_FIGURE_OUTPUT_DIR",
        "",
        f"- decision_status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- recommended_smoothness_policy: {smoothness.get('recommended_policy')}",
        f"- suspect_factors: {', '.join(factors.get('suspect_factors', []))}",
        f"- candidate_factor_count: {len(candidates.get('candidate_factor_reviews', []))}",
        f"- real_solver_variant_count: {ablations.get('variant_count')}",
        "",
        "Boundaries:",
        "",
        "- Real no-feedback solver reruns are used for policy ablations.",
        "- Smoothness is not deleted as a final shortcut.",
        "- Candidate factors remain diagnostic unless promoted in a later stage.",
        "- Trace/final_v23 are not solver inputs and are not used for weight tuning.",
        "- FGO output does not feed back into EKF and does not replace EKF NAV.",
        "- No paper performance claim.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.allow_run:
        raise SystemExit("--allow-run is required")
    n8a2_root = Path(args.n8a2_root)
    n8a_root = Path(args.n8a_root)
    out = Path(args.output_dir)
    figs = Path(args.figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    ekf_rows = read_csv_rows(n8a_root / "N8A_EKF_STATE_NODES.csv")
    if not ekf_rows:
        raise SystemExit("N8A_EKF_STATE_NODES.csv is required for N8B real policy reruns")
    n8a2_decision = read_json_report(n8a2_root / "N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json")
    n8a2_comparison = read_json_report(n8a2_root / "N8A2_FGO_YAW_FIX_COMPARISON_REPORT.json")

    policy_grid = build_n8b_policy_grid()
    write_policy_grid(out / "N8B_FGO_POLICY_GRID.json", policy_grid)
    ablation_summary, rows_by_variant = run_n8b_policy_ablations(ekf_rows=ekf_rows, policy_grid=policy_grid)
    write_json_report(out / "N8B_FGO_POLICY_ABLATION_SUMMARIES.json", ablation_summary)
    comparison = build_policy_comparison_report(ablation_summary)
    comparison["n8a2_decision_status"] = n8a2_decision.get("status")
    comparison["n8a2_default_yaw_delta_wrapped_rmse_deg"] = n8a2_comparison.get("n8a2_default_yaw_delta_wrapped_rmse_deg")
    write_json_report(out / "N8B_FGO_POLICY_COMPARISON_REPORT.json", comparison)

    smoothness_review = review_smoothness_policy(ablation_summary)
    write_smoothness_policy_review(out / "FGO_SMOOTHNESS_POLICY_REVIEW_REPORT.json", smoothness_review)
    default_rows = rows_by_variant.get("default_active_stack_n8a2", [])
    factor_weight_review = review_factor_weights(
        ekf_rows=ekf_rows,
        default_fgo_rows=default_rows,
        ablation_summary=ablation_summary,
    )
    write_factor_weight_review(out / "FGO_FACTOR_WEIGHT_REVIEW_REPORT.json", factor_weight_review)
    candidate_review = review_candidate_factors(
        ablation_summary=ablation_summary,
        n7c6_available=Path(args.n7c6_root).exists(),
        n7c5_available=Path(args.n7c5_root).exists(),
    )
    write_candidate_factor_review(out / "FGO_CANDIDATE_FACTOR_REVIEW_REPORT.json", candidate_review)

    preview = make_n8b_decision(
        ablation_summary=ablation_summary,
        smoothness_review=smoothness_review,
        factor_weight_review=factor_weight_review,
        candidate_review=candidate_review,
        figure_manifest={"required_figures_generated": True, "required_figures_nonempty": True},
    )
    figure_manifest = generate_n8b_figures(
        figure_output_dir=figs,
        ekf_rows=ekf_rows,
        rows_by_variant=rows_by_variant,
        ablation_summary=ablation_summary,
        smoothness_review=smoothness_review,
        factor_weight_review=factor_weight_review,
        candidate_review=candidate_review,
        decision_preview=preview,
    )
    write_json_report(out / "N8B_FIGURE_MANIFEST.json", figure_manifest)
    decision = make_n8b_decision(
        ablation_summary=ablation_summary,
        smoothness_review=smoothness_review,
        factor_weight_review=factor_weight_review,
        candidate_review=candidate_review,
        figure_manifest=figure_manifest,
    )
    write_n8b_decision(out / "N8B_FGO_FACTOR_GRAPH_POLICY_DECISION_REPORT.json", decision)
    _write_case_review(
        out / "n8b_factor_graph_policy_case_review.md",
        decision=decision,
        smoothness=smoothness_review,
        factors=factor_weight_review,
        candidates=candidate_review,
        ablations=ablation_summary,
    )
    print(
        json.dumps(
            {
                "decision_status": decision.get("status"),
                "recommended_next_stage": decision.get("recommended_next_stage"),
                "recommended_smoothness_policy": smoothness_review.get("recommended_policy"),
                "variant_count": ablation_summary.get("variant_count"),
                "figure_count_total": figure_manifest.get("figure_count_total"),
                "best_safe_variant": comparison.get("best_safe_variant"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
