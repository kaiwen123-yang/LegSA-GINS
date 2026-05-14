#!/usr/bin/env python3
"""Run N8F legged candidate factor activation.

中文说明：所有输出均写入 runtime-only 目录；tracked docs/scripts 只保留 role
alias 和工程边界，不写本地绝对路径。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_contact_aware_weighting_factor import (
    summarize_contact_aware_weights,
    write_contact_aware_report,
    write_contact_weight_timeseries,
)
from legsa_gins.fgo.fgo_foot_kinematic_velocity_factor import (
    residuals_for_foot_kinematic_velocity,
    summarize_foot_kinematic_velocity_factor,
    write_factor_report,
    write_foot_factor_table,
)
from legsa_gins.fgo.fgo_legged_candidate_factor_contracts import build_legged_candidate_factor_contracts, write_contracts_report
from legsa_gins.fgo.fgo_legged_factor_ablation import build_n8f_comparison_report, write_ablation_report
from legsa_gins.fgo.fgo_legged_factor_activation_runner import run_n8f_legged_variants
from legsa_gins.fgo.fgo_legged_factor_dataset_builder import build_legged_factor_dataset, rows_to_vectors, write_factor_table_csv, write_json
from legsa_gins.fgo.fgo_legged_factor_jacobian_check import run_legged_factor_jacobian_checks, write_jacobian_check_report
from legsa_gins.fgo.fgo_n8f_decision import build_n8f_decision_report, write_decision_report
from legsa_gins.fgo.fgo_n8f_visual_plots import generate_n8f_figures
from legsa_gins.fgo.fgo_relative_odometry_between_factor import (
    residuals_for_relative_odometry_between,
    summarize_relative_odometry_between_factor,
    write_relative_odometry_report,
)
from legsa_gins.fgo.fgo_yawrate_between_factor import (
    residuals_for_yawrate_between,
    summarize_yawrate_between_factor,
    write_yawrate_report,
)


def _write_case_review(path: Path, payload: Mapping[str, Any]) -> None:
    decision = payload["decision"]
    comparison = payload["comparison"]
    contact = payload["contact"]
    foot = payload["foot"]
    yawrate = payload["yawrate"]
    relative = payload["relative"]
    lines = [
        "# N8F Legged Candidate Factor Case Review",
        "",
        "N8F formally activates legged candidate factors inside no-feedback FGO.",
        "",
        f"- decision: `{decision.get('status')}`",
        f"- recommended next stage: `{decision.get('recommended_next_stage')}`",
        f"- solved variants: `{comparison.get('solved_variant_count')}/{comparison.get('variant_count')}`",
        f"- contact rows: `{contact.get('rows')}`; scale p95: `{contact.get('scale_p95')}`",
        f"- foot factor rows: `{foot.get('factor_rows')}`; residual rows: `{foot.get('residual_rows')}`",
        f"- yaw-rate factor rows: `{yawrate.get('factor_rows')}`; residual rows: `{yawrate.get('residual_rows')}`",
        f"- relative odometry factor rows: `{relative.get('factor_rows')}`; residual rows: `{relative.get('residual_rows')}`",
        "",
        "Boundary: no FGO feedback, no EKF NAV substitution, no trace/final_v23 solver input or tuning, no Go2 truth claim, and no paper performance claim.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8e-root", required=True)
    parser.add_argument("--n8d-root", required=True)
    parser.add_argument("--n8c3-root", required=True)
    parser.add_argument("--n8b-root", required=True)
    parser.add_argument("--n8a2-root", required=True)
    parser.add_argument("--n7c5-root", required=True)
    parser.add_argument("--n7c6-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n6b-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--max-factor-rows", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.allow_run:
        raise SystemExit("--allow-run is required for N8F runtime generation")

    output_dir = Path(args.output_dir)
    figure_dir = Path(args.figure_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    dataset = build_legged_factor_dataset(
        n8b_root=args.n8b_root,
        n8a2_root=args.n8a2_root,
        n7c5_root=args.n7c5_root,
        n5b_root=args.n5b_root,
        max_factor_rows=args.max_factor_rows,
    )
    write_json(output_dir / "N8F_DATASET_MANIFEST.json", dataset.manifest)

    contact_report = summarize_contact_aware_weights(dataset.contact_rows)
    write_contact_aware_report(output_dir / "FGO_CONTACT_AWARE_WEIGHTING_REPORT.json", contact_report)
    write_contact_weight_timeseries(output_dir / "FGO_CONTACT_AWARE_WEIGHTING_TIMESERIES.csv", dataset.contact_rows)

    variant_report, variant_rows, factor_table_rows = run_n8f_legged_variants(dataset)
    write_json(output_dir / "N8F_LEGGED_FACTOR_ACTIVATION_VARIANT_SUMMARIES.json", variant_report)
    write_factor_table_csv(output_dir / "N8F_LEGGED_CANDIDATE_FACTOR_TABLE.csv", factor_table_rows)

    stack_rows = variant_rows.get("all_legged_candidate_stack") or next(iter(variant_rows.values()), [])
    stack_vectors = rows_to_vectors(stack_rows)
    foot_residual_rows = residuals_for_foot_kinematic_velocity(stack_vectors, dataset.foot_factor_rows)
    yawrate_residual_rows = residuals_for_yawrate_between(stack_vectors, dataset.yawrate_factor_rows)
    relative_residual_rows = residuals_for_relative_odometry_between(stack_vectors, dataset.relative_factor_rows)

    foot_report = summarize_foot_kinematic_velocity_factor(
        dataset.foot_factor_rows,
        foot_residual_rows,
        toggle_delta_rows=len(foot_residual_rows),
    )
    write_factor_report(output_dir / "FGO_FOOT_KINEMATIC_VELOCITY_FACTOR_REPORT.json", foot_report)
    write_foot_factor_table(output_dir / "FGO_FOOT_KINEMATIC_VELOCITY_FACTOR_TABLE.csv", dataset.foot_factor_rows)

    yawrate_report = summarize_yawrate_between_factor(
        dataset.yawrate_factor_rows,
        yawrate_residual_rows,
        toggle_delta_rows=len(yawrate_residual_rows),
    )
    write_yawrate_report(output_dir / "FGO_YAWRATE_BETWEEN_FACTOR_REPORT.json", yawrate_report)

    relative_report = summarize_relative_odometry_between_factor(
        dataset.relative_factor_rows,
        relative_residual_rows,
        toggle_delta_rows=len(relative_residual_rows),
    )
    write_relative_odometry_report(output_dir / "FGO_RELATIVE_ODOMETRY_BETWEEN_FACTOR_REPORT.json", relative_report)

    jacobian_report = run_legged_factor_jacobian_checks()
    write_jacobian_check_report(output_dir / "FGO_LEGGED_FACTOR_JACOBIAN_CHECK_REPORT.json", jacobian_report)
    contracts_report = build_legged_candidate_factor_contracts(
        contact_report=contact_report,
        foot_report=foot_report,
        yawrate_report=yawrate_report,
        relative_report=relative_report,
        jacobian_report=jacobian_report,
    )
    write_contracts_report(output_dir / "FGO_LEGGED_CANDIDATE_FACTOR_CONTRACTS_REPORT.json", contracts_report)

    comparison_report = build_n8f_comparison_report(variant_report)
    write_ablation_report(output_dir / "N8F_LEGGED_FACTOR_ACTIVATION_COMPARISON_REPORT.json", comparison_report)

    decision_report = build_n8f_decision_report(
        contact_report=contact_report,
        foot_report=foot_report,
        yawrate_report=yawrate_report,
        relative_report=relative_report,
        contracts_report=contracts_report,
        comparison_report=comparison_report,
    )
    write_decision_report(output_dir / "N8F_LEGGED_CANDIDATE_FACTOR_ACTIVATION_DECISION_REPORT.json", decision_report)

    figure_manifest = generate_n8f_figures(
        figure_output_dir=figure_dir,
        contact_timeseries=dataset.contact_rows,
        foot_residual_rows=foot_residual_rows,
        yawrate_residual_rows=yawrate_residual_rows,
        relative_residual_rows=relative_residual_rows,
        variant_report=variant_report,
        decision_report=decision_report,
    )
    write_json(output_dir / "N8F_FIGURE_MANIFEST.json", figure_manifest)

    _write_case_review(
        output_dir / "n8f_legged_candidate_factor_case_review.md",
        {
            "contact": contact_report,
            "foot": foot_report,
            "yawrate": yawrate_report,
            "relative": relative_report,
            "comparison": comparison_report,
            "decision": decision_report,
        },
    )

    print(
        json.dumps(
            {
                "stage": "N8F",
                "status": decision_report.get("status"),
                "recommended_next_stage": decision_report.get("recommended_next_stage"),
                "variant_count": variant_report.get("variant_count"),
                "figures": figure_manifest.get("figure_count_total"),
                "no_feedback": True,
                "paper_performance_claim": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
