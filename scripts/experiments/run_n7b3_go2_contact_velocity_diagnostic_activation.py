#!/usr/bin/env python3
"""Run N7B3 Go2 contact/velocity diagnostic-only activation attempt.

中文说明：真实路径只来自命令行参数；Go2 velocity/contact/yaw-rate 激活均为
diagnostic-only，不读取 trace/final_v23 output 调 frame/threshold，不实现 FGO。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_contact_model_candidates import write_contact_model_candidate_outputs
from legsa_gins.go2_prior.go2_contact_model_comparison import write_contact_model_comparison
from legsa_gins.go2_prior.go2_diagnostic_activation_runner import run_n7b3_diagnostic_activation_variants
from legsa_gins.go2_prior.go2_n7b3_decision import make_n7b3_decision, write_n7b3_decision
from legsa_gins.go2_prior.go2_n7b3_visual_plots import generate_n7b3_visual_plots
from legsa_gins.go2_prior.go2_velocity_frame_review import write_go2_velocity_frame_review
from legsa_gins.go2_prior.go2_velocity_prior_diagnostic_builder import build_go2_velocity_diagnostic_priors
from legsa_gins.go2_prior.go2_yaw_rate_prior_diagnostic_builder import build_go2_yaw_rate_diagnostic_prior
from legsa_gins.go2_state.go2_body_state_parser import read_standardized_csv
from legsa_gins.raw_gnss.raw_doppler_visual_loader import (
    find_clean_gnss,
    find_factor_csv,
    load_raw_doppler_factor_rows,
    load_receiver_velocity_rows,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n7a-root", required=True)
    parser.add_argument("--n7b-root", required=True)
    parser.add_argument("--n7b2-root", required=True)
    parser.add_argument("--n7b2a-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n6b-root", required=True)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", default="")
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_case_review(path: str | Path, reports: dict[str, Any], decision: dict[str, Any]) -> None:
    velocity_frame = reports["velocity_frame"]
    contact = reports["contact_model_comparison"]
    prior = reports["velocity_prior"]
    activation = reports["activation"]
    lines = [
        "# N7B3 Go2 contact/velocity diagnostic activation",
        "",
        "This report is diagnostic engineering evidence only.",
        "",
        f"- best_velocity_frame: {velocity_frame.get('best_candidate_by_cross_source_consistency')}",
        f"- frame_ambiguity_status: {velocity_frame.get('frame_ambiguity_status')}",
        f"- plausible_contact_models: {contact.get('plausible_models')}",
        f"- selected_diagnostic_contact_model: {contact.get('selected_diagnostic_contact_model')}",
        f"- prior_csv_generated: {prior.get('prior_csv_generated')}",
        f"- contact_gated_epoch_count: {prior.get('contact_gated_epoch_count')}",
        f"- stable_with_updates: {activation.get('stable_with_updates')}",
        f"- diagnostic_degradation_detected: {activation.get('diagnostic_degradation_detected')}",
        f"- decision_status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        "- Go2 position is not truth.",
        "- Go2 velocity is not truth.",
        "- Cross-source velocity comparison is not truth error.",
        "- Contact model thresholds are derived from Go2 fields only.",
        "- trace_solver_input: false",
        "- final_v23_output_solver_input: false",
        "- diagnostic_only: true",
        "- go2_velocity_prior_enabled: false",
        "- go2_yaw_prior_enabled: false",
        "- output_only_correction: false",
        "- paper_performance_claim: false",
        "- no_outperform_final_v23_claim: true",
        "- fgo: false",
    ]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if not args.allow_run:
        raise SystemExit("--allow-run is required for N7B3 runtime execution")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    n7a_root = Path(args.n7a_root)
    go2_csv = n7a_root / "GO2_BODY_STATE_STANDARDIZED.csv"
    if not go2_csv.exists():
        raise FileNotFoundError(f"GO2_BODY_STATE_STANDARDIZED.csv missing under N7A root: {n7a_root}")
    go2_rows = read_standardized_csv(go2_csv)
    clean_gnss = find_clean_gnss(args.clean_root)
    receiver_rows = load_receiver_velocity_rows(clean_gnss)
    factor_csv = find_factor_csv(args.n5b_root)
    raw_rows = load_raw_doppler_factor_rows(factor_csv)

    _frame_path, velocity_frame_report = write_go2_velocity_frame_review(
        go2_rows=go2_rows,
        receiver_velocity_rows=receiver_rows,
        raw_doppler_rows=raw_rows,
        output_dir=out,
    )
    _contact_csv, _contact_json, contact_rows, contact_candidate_report = write_contact_model_candidate_outputs(go2_rows, out)
    _comparison_path, contact_comparison_report = write_contact_model_comparison(
        candidate_timeseries=contact_rows,
        candidate_report=contact_candidate_report,
        go2_rows=go2_rows,
        receiver_velocity_rows=receiver_rows,
        raw_doppler_rows=raw_rows,
        velocity_frame_report=velocity_frame_report,
        output_dir=out,
    )
    velocity_prior_paths, velocity_prior_report = build_go2_velocity_diagnostic_priors(
        go2_rows=go2_rows,
        velocity_frame_report=velocity_frame_report,
        contact_model_comparison=contact_comparison_report,
        candidate_timeseries=contact_rows,
        output_dir=out,
    )
    yaw_rate_path, yaw_rate_report = build_go2_yaw_rate_diagnostic_prior(go2_rows=go2_rows, output_dir=out)
    activation_report, variant_summaries = run_n7b3_diagnostic_activation_variants(
        clean_root=args.clean_root,
        output_dir=out,
        exe=args.exe,
        raw_doppler_factor_path=factor_csv,
        velocity_prior_paths=velocity_prior_paths,
        yaw_rate_prior_path=yaw_rate_path,
        allow_run=args.allow_run,
    )
    decision = make_n7b3_decision(
        velocity_frame_report=velocity_frame_report,
        contact_model_report=contact_comparison_report,
        velocity_prior_report=velocity_prior_report,
        yaw_rate_prior_report=yaw_rate_report,
        activation_report=activation_report,
    )
    write_n7b3_decision(decision, out / "N7B3_GO2_CONTACT_VELOCITY_DIAGNOSTIC_DECISION_REPORT.json")

    figure_manifest: dict[str, Any] = {"required_figures_generated": False, "paper_performance_claim": False}
    if args.figure_output_dir:
        figure_manifest = generate_n7b3_visual_plots(
            figure_output_dir=args.figure_output_dir,
            output_dir=out,
            velocity_frame_report=velocity_frame_report,
            contact_candidate_report=contact_candidate_report,
            contact_candidate_rows=contact_rows,
            velocity_prior_report=velocity_prior_report,
            yaw_rate_report=yaw_rate_report,
            activation_report=activation_report,
            variant_summaries=variant_summaries,
            decision=decision,
        )
    reports = {
        "velocity_frame": velocity_frame_report,
        "contact_candidates": contact_candidate_report,
        "contact_model_comparison": contact_comparison_report,
        "velocity_prior": velocity_prior_report,
        "yaw_rate_prior": yaw_rate_report,
        "activation": activation_report,
        "variant_summaries": variant_summaries,
    }
    _write_case_review(out / "n7b3_contact_velocity_diagnostic_case_review.md", reports, decision)
    run_report = {
        "stage": "N7B3_go2_contact_velocity_diagnostic_activation",
        "input_roles": {
            "n7a_root": "N7A_go2_body_state_runtime_report_root",
            "n7b_root": "N7B_velocity_contact_runtime_report_root",
            "n7b2_root": "N7B2_contact_threshold_runtime_report_root",
            "n7b2a_root": "N7B2A_metric_contact_runtime_report_root",
            "n5b_root": "N5B_raw_doppler_runtime_report_root",
            "n6b_root": "N6B_source_aware_policy_runtime_report_root",
            "clean_root": "clean_receiver_velocity_runtime_root",
            "output_dir": "N7B3_runtime_output_root",
            "figure_output_dir": "N7B3_runtime_figure_root",
        },
        "go2_row_count": len(go2_rows),
        "receiver_velocity_row_count": len(receiver_rows),
        "raw_doppler_row_count": len(raw_rows),
        "n7b_prior_reports": {
            "n7b_decision": _read_json(Path(args.n7b_root) / "N7B_GO2_VELOCITY_CONTACT_DECISION_REPORT.json"),
            "n7b2_decision": _read_json(Path(args.n7b2_root) / "N7B2_GO2_CONTACT_THRESHOLD_DECISION_REPORT.json"),
            "n7b2a_decision": _read_json(Path(args.n7b2a_root) / "N7B2A_GO2_METRIC_CONTACT_DECISION_REPORT.json"),
        },
        "reports": reports,
        "decision": decision,
        "figure_manifest": figure_manifest,
        "paper_performance_claim": False,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "formal_go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "fgo": False,
    }
    _write_json(out / "N7B3_GO2_CONTACT_VELOCITY_DIAGNOSTIC_RUN_REPORT.json", run_report)
    print(json.dumps({"reports": reports, "decision": decision}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
