#!/usr/bin/env python3
"""Run N8E formal engineering ablation with caveats.

中文说明：runtime 路径只作为参数使用；报告只记录 role alias。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_caveat_report import build_caveat_report
from legsa_gins.fgo.fgo_claim_boundary_review import review_claim_boundaries
from legsa_gins.fgo.fgo_final_ablation_matrix import (
    build_final_engineering_ablation_matrix,
    read_json_report,
    write_ablation_summary_md,
    write_ablation_table_csv,
    write_json_report,
)
from legsa_gins.fgo.fgo_module_contribution_summary import build_module_contribution_summary
from legsa_gins.fgo.fgo_n8e_decision import make_n8e_decision
from legsa_gins.fgo.fgo_n8e_visual_plots import generate_n8e_figures


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n6b-root", required=True)
    parser.add_argument("--n7c6-root", required=True)
    parser.add_argument("--n8a2-root", required=True)
    parser.add_argument("--n8b-root", required=True)
    parser.add_argument("--n8c3-root", required=True)
    parser.add_argument("--n8d-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def _load_stage_reports(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    n5b = Path(args.n5b_root)
    n6b = Path(args.n6b_root)
    n7c6 = Path(args.n7c6_root)
    n8a2 = Path(args.n8a2_root)
    n8b = Path(args.n8b_root)
    n8c3 = Path(args.n8c3_root)
    n8d = Path(args.n8d_root)
    return {
        "n5b_decision": read_json_report(n5b / "N5B_RAW_DOPPLER_DECISION_REPORT.json"),
        "n5b_factor_comparison": read_json_report(n5b / "N5B_RAW_DOPPLER_FACTOR_COMPARISON_REPORT.json"),
        "n6b_decision": read_json_report(n6b / "N6B_SOURCE_AWARE_DECISION_REPORT.json"),
        "n6b_ablation": read_json_report(n6b / "N6B_SOURCE_AWARE_ABLATION_MATRIX.json"),
        "n7c6_decision": read_json_report(n7c6 / "N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_DECISION_REPORT.json"),
        "n7c6_ablation": read_json_report(n7c6 / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_ABLATION_MATRIX.json"),
        "n8a2_decision": read_json_report(n8a2 / "N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json"),
        "n8b_decision": read_json_report(n8b / "N8B_FGO_FACTOR_GRAPH_POLICY_DECISION_REPORT.json"),
        "n8c3_decision": read_json_report(n8c3 / "N8C3_RAW_DOPPLER_FGO_FACTOR_FIX_DECISION_REPORT.json"),
        "n8d_decision": read_json_report(n8d / "N8D_FGO_WEIGHT_POLICY_DECISION_REPORT.json"),
        "n8d_formal_matrix": read_json_report(n8d / "N8D_FORMAL_ENGINEERING_ABLATION_MATRIX.json"),
        "n8d_variant_summaries": read_json_report(n8d / "N8D_FGO_WEIGHT_POLICY_VARIANT_SUMMARIES.json"),
        "n8d_raw_receiver": read_json_report(n8d / "FGO_RAW_RECEIVER_WEIGHT_BALANCE_REPORT.json"),
        "n8d_go2_policy": read_json_report(n8d / "FGO_GO2_JOINT_WEIGHT_POLICY_REPORT.json"),
        "n8d_dual_yaw": read_json_report(n8d / "FGO_DUAL_YAW_WEIGHT_POLICY_REPORT.json"),
        "n8d_process": read_json_report(n8d / "FGO_PROCESS_FACTOR_POLICY_REVIEW_REPORT.json"),
    }


def _write_input_manifest(path: Path, stage_reports: dict[str, dict[str, Any]], dual_root_exists: bool) -> None:
    write_json_report(
        path,
        {
            "stage": "N8E_formal_engineering_ablation_with_caveat",
            "role_aliases": [
                "N5B_REPORT_OUTPUT_DIR",
                "N6B_REPORT_OUTPUT_DIR",
                "N7C6_REPORT_OUTPUT_DIR",
                "N8A2_REPORT_OUTPUT_DIR",
                "N8B_REPORT_OUTPUT_DIR",
                "N8C3_REPORT_OUTPUT_DIR",
                "N8D_REPORT_OUTPUT_DIR",
                "DUAL_FINAL_V23_ARTIFACT_ROOT",
                "N8E_REPORT_OUTPUT_DIR",
                "N8E_FIGURE_OUTPUT_DIR",
            ],
            "reports_loaded": sorted(name for name, report in stage_reports.items() if report),
            "missing_reports": sorted(name for name, report in stage_reports.items() if not report),
            "dual_root_role_available": bool(dual_root_exists),
            "no_feedback": True,
            "fgo_output_feedback_to_ekf": False,
            "fgo_output_substitution": False,
            "fgo_output_replaces_ekf_nav": False,
            "trace_solver_input": False,
            "trace_weight_tuning": False,
            "final_v23_output_solver_input": False,
            "final_v23_weight_tuning": False,
            "paper_performance_claim": False,
            "no_outperform_final_v23_claim": True,
        },
    )


def _write_case_review(
    path: Path,
    *,
    matrix: dict[str, Any],
    modules: dict[str, Any],
    caveats: dict[str, Any],
    claim: dict[str, Any],
    decision: dict[str, Any],
    figures: dict[str, Any],
) -> None:
    lines = [
        "# N8E formal engineering ablation with caveats",
        "",
        "Runtime role aliases:",
        "",
        "- N5B_REPORT_OUTPUT_DIR",
        "- N6B_REPORT_OUTPUT_DIR",
        "- N7C6_REPORT_OUTPUT_DIR",
        "- N8A2_REPORT_OUTPUT_DIR",
        "- N8B_REPORT_OUTPUT_DIR",
        "- N8C3_REPORT_OUTPUT_DIR",
        "- N8D_REPORT_OUTPUT_DIR",
        "- DUAL_FINAL_V23_ARTIFACT_ROOT",
        "- N8E_REPORT_OUTPUT_DIR",
        "- N8E_FIGURE_OUTPUT_DIR",
        "",
        f"- matrix_complete: {matrix.get('matrix_complete')}",
        f"- group_counts: {matrix.get('group_counts')}",
        f"- module_count: {modules.get('module_count')}",
        f"- caveats_present: {caveats.get('all_required_caveats_present')}",
        f"- claim_boundary: {claim.get('decision')}",
        f"- decision_status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- secondary_recommendation: {decision.get('secondary_recommendation')}",
        f"- figure_count: {figures.get('figure_count_total')}",
        "",
        "Boundary review:",
        "",
        "- Raw Doppler FGO active but low marginal value is a caveat, not a failure.",
        "- Candidate factors remain diagnostic-only unless promoted later.",
        "- FGO output is not fed back into EKF and does not replace EKF NAV.",
        "- Trace/final_v23 outputs are not solver input and are not used for tuning.",
        "- N8E is not a paper performance claim and does not claim outperform final_v23.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.allow_run:
        raise SystemExit("--allow-run is required")

    out = Path(args.output_dir)
    figs = Path(args.figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    stage_reports = _load_stage_reports(args)
    _write_input_manifest(out / "N8E_INPUT_MANIFEST.json", stage_reports, dual_root_exists=Path(args.dual_root).exists())

    matrix = build_final_engineering_ablation_matrix(stage_reports)
    write_json_report(out / "N8E_FINAL_ENGINEERING_ABLATION_MATRIX.json", matrix)
    write_ablation_table_csv(out / "N8E_FINAL_ENGINEERING_ABLATION_TABLE.csv", matrix)
    write_ablation_summary_md(out / "N8E_FINAL_ENGINEERING_ABLATION_SUMMARY.md", matrix)

    modules = build_module_contribution_summary(stage_reports=stage_reports, matrix_report=matrix)
    write_json_report(out / "N8E_MODULE_CONTRIBUTION_SUMMARY_REPORT.json", modules)

    caveats = build_caveat_report(matrix_report=matrix, module_summary=modules)
    write_json_report(out / "N8E_CAVEAT_REPORT.json", caveats)

    claim = review_claim_boundaries(docs_root=ROOT / "docs", report_root=out)
    write_json_report(out / "N8E_CLAIM_BOUNDARY_REVIEW_REPORT.json", claim)

    preview = make_n8e_decision(
        matrix_report=matrix,
        caveat_report=caveats,
        claim_boundary_report=claim,
        figure_manifest={"figure_count_total": 0, "required_figures_nonempty": False},
    )
    figures = generate_n8e_figures(
        figure_output_dir=figs,
        matrix_report=matrix,
        module_summary=modules,
        caveat_report=caveats,
        decision_preview=preview,
    )
    write_json_report(out / "N8E_FIGURE_MANIFEST.json", figures)

    decision = make_n8e_decision(
        matrix_report=matrix,
        caveat_report=caveats,
        claim_boundary_report=claim,
        figure_manifest=figures,
    )
    write_json_report(out / "N8E_FORMAL_ABLATION_WITH_CAVEAT_DECISION_REPORT.json", decision)
    _write_case_review(
        out / "n8e_formal_ablation_case_review.md",
        matrix=matrix,
        modules=modules,
        caveats=caveats,
        claim=claim,
        decision=decision,
        figures=figures,
    )

    print(
        json.dumps(
            {
                "decision_status": decision.get("status"),
                "recommended_next_stage": decision.get("recommended_next_stage"),
                "secondary_recommendation": decision.get("secondary_recommendation"),
                "matrix_complete": matrix.get("matrix_complete"),
                "group_counts": matrix.get("group_counts"),
                "module_count": modules.get("module_count"),
                "caveat_count": len(caveats.get("caveats", [])),
                "claim_boundary": claim.get("decision"),
                "figure_count_total": figures.get("figure_count_total"),
                "required_figures_nonempty": figures.get("required_figures_nonempty"),
                "raw_doppler_fgo_active_but_low_marginal_value": matrix.get(
                    "raw_doppler_fgo_active_but_low_marginal_value"
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
