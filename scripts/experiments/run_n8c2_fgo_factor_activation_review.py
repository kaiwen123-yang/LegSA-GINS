#!/usr/bin/env python3
"""Run N8C2 FGO factor activation and whitening review.

Runtime paths are accepted only as command-line inputs.  Tracked reports and
docs use role aliases instead of local absolute paths.

中文说明：runner 只接收 runtime 参数，不把本地绝对路径写入 tracked 文件。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_candidate_factor_real_contribution_review import build_candidate_factor_real_contribution_review
from legsa_gins.fgo.fgo_factor_activation_audit import build_factor_activation_audit, write_json_report
from legsa_gins.fgo.fgo_factor_toggle_integrity import build_factor_toggle_integrity
from legsa_gins.fgo.fgo_go2_joint_factor_activation_review import build_go2_joint_factor_activation_review
from legsa_gins.fgo.fgo_n8c2_decision import make_n8c2_decision
from legsa_gins.fgo.fgo_n8c2_visual_plots import generate_n8c2_figures
from legsa_gins.fgo.fgo_n8c_visual_loader import load_n8c_visual_inputs
from legsa_gins.fgo.fgo_raw_doppler_factor_activation_review import build_raw_doppler_factor_activation_review
from legsa_gins.fgo.fgo_raw_doppler_weight_sensitivity import run_raw_doppler_weight_sensitivity
from legsa_gins.fgo.fgo_residual_whitening_review import build_residual_whitening_review
from legsa_gins.fgo.fgo_smoothness_component_review import build_smoothness_component_review
from legsa_gins.fgo.fgo_yaw_convention_audit import read_json_report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8c-root", required=True)
    parser.add_argument("--n8b-root", required=True)
    parser.add_argument("--n8a2-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n7c6-root", required=True)
    parser.add_argument("--n7c5-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--run-weight-sensitivity", choices=["true", "false"], default="true")
    return parser.parse_args(argv)


def _write_case_review(
    path: Path,
    *,
    activation: dict[str, Any],
    whitening: dict[str, Any],
    smoothness: dict[str, Any],
    raw_doppler: dict[str, Any],
    go2: dict[str, Any],
    toggle: dict[str, Any],
    candidate: dict[str, Any],
    decision: dict[str, Any],
    figure_manifest: dict[str, Any],
) -> None:
    raw_row = next((row for row in activation.get("factor_activation_rows", []) if row.get("factor_type") == "RawDopplerVelocityFactor"), {})
    lines = [
        "# N8C2 FGO factor activation review",
        "",
        "Runtime role aliases:",
        "",
        "- N8C_REPORT_OUTPUT_DIR",
        "- N8B_REPORT_OUTPUT_DIR",
        "- N8A2_REPORT_OUTPUT_DIR",
        "- N5B_REPORT_OUTPUT_DIR",
        "- N7C6_REPORT_OUTPUT_DIR",
        "- N7C5_REPORT_OUTPUT_DIR",
        "- N8C2_REPORT_OUTPUT_DIR",
        "- N8C2_FIGURE_OUTPUT_DIR",
        "",
        f"- decision_status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- raw_doppler_classification: {raw_doppler.get('classification')}",
        f"- raw_doppler_direct_solver_residual_evidence: {raw_row.get('direct_solver_residual_evidence')}",
        f"- smoothness_dominance: {whitening.get('smoothness_dominance_classification')}",
        f"- smoothness_spike_component: {smoothness.get('component_causing_spikes')}",
        f"- go2_joint_classification: {go2.get('classification')}",
        f"- toggle_integrity: {toggle.get('status')}",
        f"- candidate_inactive_diagnostic_count: {len(candidate.get('inactive_diagnostic_factors', []))}",
        f"- figure_count: {figure_manifest.get('figure_count_total')}",
        "",
        "Boundaries:",
        "",
        "- Factor activation and residual whitening are engineering diagnostics.",
        "- Weight sensitivity is diagnostic only and does not select final weights by trace or final_v23.",
        "- FGO output remains no-feedback and does not replace EKF NAV.",
        "- Trace/final_v23 are not solver inputs.",
        "- Candidate factors are not formal factors in this stage.",
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

    manifest, data = load_n8c_visual_inputs(
        n8b_root=args.n8b_root,
        n8a2_root=args.n8a2_root,
        rerun_missing_timeseries=True,
    )
    reports = data["reports"]
    ekf_rows = data["ekf_rows"]
    rows_by_variant = data["rows_by_variant"]
    ablation_summary = data["ablation_summary"]
    if not ekf_rows or not rows_by_variant:
        raise SystemExit("N8C2 requires EKF rows and real no-feedback variant reruns")

    n8c_root = Path(args.n8c_root)
    n8c_contribution = read_json_report(n8c_root / "N8C_FACTOR_CONTRIBUTION_REVIEW_REPORT.json")
    n8c_decision = read_json_report(n8c_root / "N8C_NO_FEEDBACK_FGO_VISUAL_DECISION_REPORT.json")
    write_json_report(
        out / "N8C2_INPUT_MANIFEST.json",
        {
            "stage": "N8C2_fgo_factor_activation_review",
            "n8c_reports_found": bool(n8c_contribution or n8c_decision),
            "n8b_reports_found": manifest.get("n8b_reports_found"),
            "n8a2_reports_found": manifest.get("n8a2_reports_found"),
            "timeseries_rerun_performed_runtime_only": manifest.get("timeseries_rerun_performed_runtime_only"),
            "role_aliases": [
                "N8C_REPORT_OUTPUT_DIR",
                "N8B_REPORT_OUTPUT_DIR",
                "N8A2_REPORT_OUTPUT_DIR",
                "N5B_REPORT_OUTPUT_DIR",
                "N7C6_REPORT_OUTPUT_DIR",
                "N7C5_REPORT_OUTPUT_DIR",
                "N8C2_REPORT_OUTPUT_DIR",
                "N8C2_FIGURE_OUTPUT_DIR",
            ],
            "no_feedback": True,
            "output_substitution": False,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "paper_performance_claim": False,
        },
    )

    activation = build_factor_activation_audit(
        ekf_rows=ekf_rows,
        rows_by_variant=rows_by_variant,
        ablation_summary=ablation_summary,
        factor_weight_review=reports["n8b_factor_weight_review"],
        registry_report=reports["factor_registry"],
    )
    write_json_report(out / "FGO_FACTOR_ACTIVATION_AUDIT_REPORT.json", activation)

    whitening = build_residual_whitening_review(activation_report=activation)
    write_json_report(out / "FGO_RESIDUAL_WHITENING_REVIEW_REPORT.json", whitening)

    smoothness = build_smoothness_component_review(rows_by_variant=rows_by_variant)
    write_json_report(out / "FGO_SMOOTHNESS_COMPONENT_REVIEW_REPORT.json", smoothness)

    raw_initial = build_raw_doppler_factor_activation_review(
        activation_report=activation,
        whitening_report=whitening,
        n5b_root=args.n5b_root,
    )
    write_json_report(out / "FGO_RAW_DOPPLER_FACTOR_ACTIVATION_REVIEW.json", raw_initial)

    if args.run_weight_sensitivity == "true":
        sensitivity, sensitivity_rows = run_raw_doppler_weight_sensitivity(ekf_rows=ekf_rows)
    else:
        sensitivity, sensitivity_rows = (
            {
                "stage": "N8C2_fgo_factor_activation_review",
                "variants": [],
                "variant_count": 0,
                "all_required_variants_run": False,
                "weight_scan_diagnostic_only": True,
                "no_feedback": True,
                "output_substitution": False,
                "trace_solver_input": False,
                "final_v23_output_solver_input": False,
                "paper_performance_claim": False,
            },
            {},
        )
    write_json_report(out / "FGO_RAW_DOPPLER_WEIGHT_SENSITIVITY_REPORT.json", sensitivity)

    go2 = build_go2_joint_factor_activation_review(activation_report=activation)
    write_json_report(out / "FGO_GO2_JOINT_FACTOR_ACTIVATION_REVIEW.json", go2)

    toggle = build_factor_toggle_integrity(
        ablation_summary=ablation_summary,
        sensitivity_report=sensitivity,
        state_count=len(ekf_rows),
    )
    write_json_report(out / "FGO_FACTOR_TOGGLE_INTEGRITY_REPORT.json", toggle)

    raw_doppler = build_raw_doppler_factor_activation_review(
        activation_report=activation,
        whitening_report=whitening,
        toggle_integrity_report=toggle,
        n5b_root=args.n5b_root,
    )
    write_json_report(out / "FGO_RAW_DOPPLER_FACTOR_ACTIVATION_REVIEW.json", raw_doppler)

    candidate = build_candidate_factor_real_contribution_review(
        candidate_review=reports["n8b_candidate_review"],
        ablation_summary=ablation_summary,
        registry_report=reports["factor_registry"],
    )
    write_json_report(out / "FGO_CANDIDATE_FACTOR_REAL_CONTRIBUTION_REPORT.json", candidate)

    preview = make_n8c2_decision(
        activation_report=activation,
        whitening_report=whitening,
        smoothness_report=smoothness,
        raw_doppler_report=raw_doppler,
        toggle_report=toggle,
        figure_manifest={"figure_count_total": 0, "required_figures_nonempty": False},
    )
    figure_manifest = generate_n8c2_figures(
        figure_output_dir=figs,
        ekf_rows=ekf_rows,
        rows_by_variant=rows_by_variant,
        sensitivity_rows_by_variant=sensitivity_rows,
        activation_report=activation,
        whitening_report=whitening,
        smoothness_report=smoothness,
        sensitivity_report=sensitivity,
        toggle_report=toggle,
        decision_preview=preview,
    )
    write_json_report(out / "N8C2_FIGURE_MANIFEST.json", figure_manifest)

    decision = make_n8c2_decision(
        activation_report=activation,
        whitening_report=whitening,
        smoothness_report=smoothness,
        raw_doppler_report=raw_doppler,
        toggle_report=toggle,
        figure_manifest=figure_manifest,
    )
    write_json_report(out / "N8C2_FGO_FACTOR_ACTIVATION_DECISION_REPORT.json", decision)
    _write_case_review(
        out / "n8c2_factor_activation_case_review.md",
        activation=activation,
        whitening=whitening,
        smoothness=smoothness,
        raw_doppler=raw_doppler,
        go2=go2,
        toggle=toggle,
        candidate=candidate,
        decision=decision,
        figure_manifest=figure_manifest,
    )
    print(
        json.dumps(
            {
                "decision_status": decision.get("status"),
                "recommended_next_stage": decision.get("recommended_next_stage"),
                "raw_doppler_classification": raw_doppler.get("classification"),
                "smoothness_dominance_classification": whitening.get("smoothness_dominance_classification"),
                "toggle_integrity": toggle.get("status"),
                "figure_count_total": figure_manifest.get("figure_count_total"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
