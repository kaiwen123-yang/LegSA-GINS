#!/usr/bin/env python3
"""Run N8A1 FGO yaw-delta, factor-policy, and visual sanity review.

中文说明：runner 只读取 N8A 运行时产物并生成 N8A1 审查报告。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_factor_ablation_review import run_factor_ablation_review
from legsa_gins.fgo.fgo_factor_policy_review import review_factor_policy
from legsa_gins.fgo.fgo_n8a1_decision import make_n8a1_decision, write_n8a1_decision
from legsa_gins.fgo.fgo_n8a1_visual_plots import generate_n8a1_figures
from legsa_gins.fgo.fgo_state_epoch_mapping_audit import audit_state_epoch_mapping
from legsa_gins.fgo.fgo_yaw_convention_audit import audit_yaw_convention, read_csv_rows, read_json_report, write_json_report
from legsa_gins.fgo.fgo_yaw_delta_diagnostics import diagnose_yaw_delta


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8a-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--run-ablation", choices=["true", "false"], default="true")
    return parser.parse_args(argv)


def _write_case_review(path: Path, decision: dict[str, Any], reports: dict[str, dict[str, Any]]) -> None:
    yaw = reports["yaw_convention"]
    state = reports["state_epoch"]
    factor = reports["factor_policy"]
    ablation = reports["ablation"]
    lines = [
        "# N8A1 FGO yaw-delta policy review",
        "",
        "Runtime role aliases:",
        "",
        "- N8A_REPORT_OUTPUT_DIR",
        "- N8A1_REPORT_OUTPUT_DIR",
        "- N8A1_FIGURE_OUTPUT_DIR",
        "",
        f"- decision_status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- yaw_unit_consistent: {yaw.get('yaw_unit_consistent')}",
        f"- yaw_wrap_consistent: {yaw.get('yaw_wrap_consistent')}",
        f"- yaw_residual_wrap_used: {yaw.get('yaw_residual_wrap_used')}",
        f"- yaw_delta_rmse_raw: {yaw.get('yaw_delta_rmse_raw')}",
        f"- yaw_delta_rmse_after_best_wrap: {yaw.get('yaw_delta_rmse_after_best_wrap')}",
        f"- epoch_count: {state.get('epoch_count')}",
        f"- state_dimension_per_epoch: {state.get('state_dimension_per_epoch')}",
        f"- state_count_interpretation: {state.get('state_count_interpretation')}",
        f"- candidate_factor_leak_suspect: {factor.get('candidate_factor_leak_suspect')}",
        f"- smoothness_weight_suspect: {factor.get('smoothness_weight_suspect')}",
        f"- yaw_factor_weight_suspect: {factor.get('yaw_factor_weight_suspect')}",
        f"- ablation_variant_count: {ablation.get('variant_count')}",
        f"- ablation_best_yaw_delta_variant: {ablation.get('best_yaw_delta_variant')}",
        "",
        "Boundaries:",
        "",
        "- FGO output remains no-feedback and does not replace EKF NAV.",
        "- Trace/final_v23 outputs are not FGO solver inputs.",
        "- Diagnostic ablations are not final weight selection.",
        "- Large FGO-vs-EKF yaw delta is diagnostic engineering evidence only.",
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
    fgo_rows = read_csv_rows(n8a_root / "N8A_FGO_DIAGNOSTIC_STATES.csv")
    dataset_report = read_json_report(n8a_root / "N8A_DATASET_REPORT.json")
    evaluation_report = read_json_report(n8a_root / "N8A_EVALUATION_REPORT.json")
    registry_report = read_json_report(n8a_root / "N8A_FACTOR_REGISTRY_REPORT.json")
    smoother_report = read_json_report(n8a_root / "N8A_NO_FEEDBACK_SMOOTHER_REPORT.json")

    yaw_convention = audit_yaw_convention(
        ekf_rows=ekf_rows,
        fgo_rows=fgo_rows,
        evaluation_report=evaluation_report,
        smoother_report=smoother_report,
    )
    write_json_report(out / "FGO_YAW_CONVENTION_AUDIT_REPORT.json", yaw_convention)
    state_epoch = audit_state_epoch_mapping(ekf_rows=ekf_rows, fgo_rows=fgo_rows, dataset_report=dataset_report)
    write_json_report(out / "FGO_STATE_EPOCH_MAPPING_AUDIT_REPORT.json", state_epoch)
    factor_policy = review_factor_policy(
        ekf_rows=ekf_rows,
        fgo_rows=fgo_rows,
        registry_report=registry_report,
        smoother_report=smoother_report,
        yaw_convention_report=yaw_convention,
    )
    write_json_report(out / "FGO_FACTOR_POLICY_REVIEW_REPORT.json", factor_policy)
    yaw_diagnostics = diagnose_yaw_delta(
        ekf_rows=ekf_rows,
        fgo_rows=fgo_rows,
        yaw_convention_report=yaw_convention,
        factor_policy_report=factor_policy,
    )
    write_json_report(out / "FGO_YAW_DELTA_DIAGNOSTICS_REPORT.json", yaw_diagnostics)
    if args.run_ablation == "true":
        ablation = run_factor_ablation_review(ekf_rows=ekf_rows, fgo_rows=fgo_rows)
    else:
        ablation = {
            "stage": "N8A1_fgo_yaw_delta_policy_review",
            "variant_count": 0,
            "variants": [],
            "diagnostic_only": True,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "paper_performance_claim": False,
        }
    write_json_report(out / "FGO_N8A1_ABLATION_REVIEW_REPORT.json", ablation)
    decision_preview = make_n8a1_decision(
        yaw_convention=yaw_convention,
        state_epoch_mapping=state_epoch,
        factor_policy=factor_policy,
        yaw_diagnostics=yaw_diagnostics,
        ablation=ablation,
        figures={"required_figures_generated": True, "required_figures_nonempty": True, "figure_count_total": 10},
    )
    figure_manifest = generate_n8a1_figures(
        figure_output_dir=figs,
        ekf_rows=ekf_rows,
        fgo_rows=fgo_rows,
        yaw_convention=yaw_convention,
        yaw_diagnostics=yaw_diagnostics,
        state_epoch_mapping=state_epoch,
        factor_policy=factor_policy,
        ablation=ablation,
        decision_preview=decision_preview,
    )
    write_json_report(out / "N8A1_FIGURE_MANIFEST.json", figure_manifest)
    decision = make_n8a1_decision(
        yaw_convention=yaw_convention,
        state_epoch_mapping=state_epoch,
        factor_policy=factor_policy,
        yaw_diagnostics=yaw_diagnostics,
        ablation=ablation,
        figures=figure_manifest,
    )
    write_n8a1_decision(out / "N8A1_FGO_YAW_DELTA_POLICY_DECISION_REPORT.json", decision)
    _write_case_review(
        out / "n8a1_fgo_yaw_delta_case_review.md",
        decision,
        {
            "yaw_convention": yaw_convention,
            "state_epoch": state_epoch,
            "factor_policy": factor_policy,
            "yaw_diagnostics": yaw_diagnostics,
            "ablation": ablation,
        },
    )
    print(
        json.dumps(
            {
                "decision_status": decision.get("status"),
                "recommended_next_stage": decision.get("recommended_next_stage"),
                "yaw_blocker": yaw_convention.get("blocker_status"),
                "epoch_count": state_epoch.get("epoch_count"),
                "ablation_variant_count": ablation.get("variant_count"),
                "figure_count_total": figure_manifest.get("figure_count_total"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
