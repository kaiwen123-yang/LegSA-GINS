#!/usr/bin/env python3
"""Run N7B4 literature-informed Go2 contact/velocity diagnostics.

中文说明：真实路径只来自命令行参数；N7B4 所有 Go2 contact/velocity
activation 都是 diagnostic-only，不读取 trace/final_v23 output 调模型或阈值。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_contact_confidence_features import write_contact_confidence_features
from legsa_gins.go2_prior.go2_contact_probability_model import write_contact_probability_outputs
from legsa_gins.go2_prior.go2_literature_contact_review import write_literature_contact_review
from legsa_gins.go2_prior.go2_n7b4_decision import make_n7b4_decision, write_n7b4_decision
from legsa_gins.go2_prior.go2_n7b4_diagnostic_activation import run_n7b4_diagnostic_activation_variants
from legsa_gins.go2_prior.go2_n7b4_visual_plots import generate_n7b4_visual_plots
from legsa_gins.go2_prior.go2_probability_weighted_prior_builder import build_probability_weighted_diagnostic_priors
from legsa_gins.go2_prior.go2_velocity_frame_internal_external_score import write_velocity_frame_score
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
    parser.add_argument("--n7b3-root", required=True)
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
    lines = [
        "# N7B4 literature-informed Go2 contact/velocity diagnostics",
        "",
        "This report is diagnostic engineering evidence only.",
        "",
        f"- selected_contact_probability_model: {reports['contact_probability'].get('selected_contact_probability_model')}",
        f"- plausible_probability_models: {reports['contact_probability'].get('plausible_probability_models')}",
        f"- best_velocity_frame: {reports['frame_score'].get('best_candidate')}",
        f"- frame_status: {reports['frame_score'].get('frame_status')}",
        f"- probability_weighted_prior_epoch_count: {reports['prior_build'].get('epoch_count')}",
        f"- stable_with_updates: {reports['activation'].get('stable_with_updates')}",
        f"- diagnostic_degradation_detected: {reports['activation'].get('diagnostic_degradation_detected')}",
        f"- decision_status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        "- Contact probability is diagnostic, not truth.",
        "- Go2 velocity is not truth.",
        "- trace_solver_input: false",
        "- final_v23_output_solver_input: false",
        "- formal_go2_velocity_prior: false",
        "- formal_go2_yaw_prior: false",
        "- output_only_correction: false",
        "- paper_performance_claim: false",
        "- fgo: false",
    ]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if not args.allow_run:
        raise SystemExit("--allow-run is required for N7B4 runtime execution")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    go2_csv = Path(args.n7a_root) / "GO2_BODY_STATE_STANDARDIZED.csv"
    if not go2_csv.exists():
        raise FileNotFoundError(f"GO2_BODY_STATE_STANDARDIZED.csv missing under N7A root: {Path(args.n7a_root).name}")
    go2_rows = read_standardized_csv(go2_csv)
    clean_gnss = find_clean_gnss(args.clean_root)
    receiver_rows = load_receiver_velocity_rows(clean_gnss)
    factor_csv = find_factor_csv(args.n5b_root)
    raw_rows = load_raw_doppler_factor_rows(factor_csv)

    _review_path, literature_report = write_literature_contact_review(out)
    _features_csv, _features_report_path, feature_rows, features_report = write_contact_confidence_features(go2_rows, out)
    _prob_csv, _prob_report_path, probability_rows, probability_report = write_contact_probability_outputs(feature_rows, out)
    _frame_path, frame_score_report = write_velocity_frame_score(
        go2_rows=go2_rows,
        receiver_velocity_rows=receiver_rows,
        raw_doppler_rows=raw_rows,
        output_dir=out,
    )
    prior_paths, prior_build_report = build_probability_weighted_diagnostic_priors(
        go2_rows=go2_rows,
        frame_score_report=frame_score_report,
        probability_model_report=probability_report,
        probability_timeseries=probability_rows,
        output_dir=out,
    )
    activation_report, variant_summaries = run_n7b4_diagnostic_activation_variants(
        clean_root=args.clean_root,
        output_dir=out,
        exe=args.exe,
        raw_doppler_factor_path=factor_csv,
        prior_paths=prior_paths,
        allow_run=args.allow_run,
    )
    decision = make_n7b4_decision(
        contact_probability_report=probability_report,
        frame_score_report=frame_score_report,
        prior_build_report=prior_build_report,
        activation_report=activation_report,
    )
    write_n7b4_decision(decision, out / "N7B4_GO2_LITERATURE_CONTACT_VELOCITY_DECISION_REPORT.json")
    figure_manifest: dict[str, Any] = {"required_figures_generated": False, "paper_performance_claim": False}
    if args.figure_output_dir:
        figure_manifest = generate_n7b4_visual_plots(
            figure_output_dir=args.figure_output_dir,
            output_dir=out,
            feature_rows=feature_rows,
            probability_rows=probability_rows,
            probability_report=probability_report,
            frame_score_report=frame_score_report,
            prior_build_report=prior_build_report,
            activation_report=activation_report,
            variant_summaries=variant_summaries,
            decision=decision,
        )
    reports = {
        "literature": literature_report,
        "features": features_report,
        "contact_probability": probability_report,
        "frame_score": frame_score_report,
        "prior_build": prior_build_report,
        "activation": activation_report,
        "variant_summaries": variant_summaries,
    }
    _write_case_review(out / "n7b4_literature_contact_velocity_case_review.md", reports, decision)
    run_report = {
        "stage": "N7B4_literature_informed_contact_velocity",
        "input_roles": {
            "n7a_root": "N7A_go2_body_state_runtime_report_root",
            "n7b_root": "N7B_velocity_contact_runtime_report_root",
            "n7b2_root": "N7B2_contact_threshold_runtime_report_root",
            "n7b2a_root": "N7B2A_metric_contact_runtime_report_root",
            "n7b3_root": "N7B3_diagnostic_activation_runtime_report_root",
            "n5b_root": "N5B_raw_doppler_runtime_report_root",
            "n6b_root": "N6B_source_aware_policy_runtime_report_root",
            "clean_root": "clean_receiver_velocity_runtime_root",
            "output_dir": "N7B4_runtime_output_root",
            "figure_output_dir": "N7B4_runtime_figure_root",
        },
        "go2_row_count": len(go2_rows),
        "receiver_velocity_row_count": len(receiver_rows),
        "raw_doppler_row_count": len(raw_rows),
        "previous_stage_reports": {
            "n7b3_decision": _read_json(Path(args.n7b3_root) / "N7B3_GO2_CONTACT_VELOCITY_DIAGNOSTIC_DECISION_REPORT.json"),
            "n7b3_frame": _read_json(Path(args.n7b3_root) / "GO2_VELOCITY_FRAME_REVIEW_REPORT.json"),
            "n7b3_contact": _read_json(Path(args.n7b3_root) / "GO2_CONTACT_MODEL_COMPARISON_REPORT.json"),
        },
        "reports": reports,
        "decision": decision,
        "figure_manifest": figure_manifest,
        "paper_performance_claim": False,
        "diagnostic_only": True,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "formal_go2_velocity_prior": False,
        "formal_go2_yaw_prior": False,
        "fgo": False,
    }
    _write_json(out / "N7B4_GO2_LITERATURE_CONTACT_VELOCITY_RUN_REPORT.json", run_report)
    print(json.dumps({"reports": reports, "decision": decision}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
