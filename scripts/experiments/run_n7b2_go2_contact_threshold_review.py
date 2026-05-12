#!/usr/bin/env python3
"""Run N7B2 Go2 contact threshold/state refinement diagnostics.

中文说明：真实路径只来自命令行参数；阈值只由 Go2 field distributions 产生，
不使用 trace/final_v23 output 调阈值，不激活 Go2 velocity/yaw prior。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_contact_distribution import write_contact_distribution_report
from legsa_gins.go2_prior.go2_contact_state_v2 import write_contact_state_v2_outputs
from legsa_gins.go2_prior.go2_contact_threshold_review import write_contact_threshold_review
from legsa_gins.go2_prior.go2_contact_velocity_segment_review import write_contact_velocity_segment_review
from legsa_gins.go2_prior.go2_contact_window_smoother import write_contact_smoothing_outputs
from legsa_gins.go2_prior.go2_n7b2_decision import make_n7b2_decision, write_n7b2_decision
from legsa_gins.go2_prior.go2_n7b2_visual_plots import generate_n7b2_visual_plots
from legsa_gins.go2_state.go2_body_state_parser import read_standardized_csv
from legsa_gins.raw_gnss.raw_doppler_visual_loader import (
    find_clean_gnss,
    find_factor_csv,
    load_raw_doppler_factor_rows,
    load_receiver_velocity_rows,
    read_csv_rows,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n7a-root", required=True)
    parser.add_argument("--n7b-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n6b-root", required=True)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", default="")
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    loaded = json.loads(source.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_case_review(path: str | Path, reports: dict[str, dict[str, Any]], decision: dict[str, Any]) -> None:
    lines = [
        "# N7B2 Go2 contact threshold review",
        "",
        "This report is diagnostic engineering evidence only.",
        "",
        f"- field_quality_status: {reports['distribution'].get('field_quality_status')}",
        f"- v2_uncertain_ratio: {reports['contact_v2'].get('uncertain_ratio')}",
        f"- smoothing_uncertain_before: {reports['smoothing'].get('uncertain_ratio_before')}",
        f"- smoothing_uncertain_after: {reports['smoothing'].get('uncertain_ratio_after')}",
        f"- velocity_segment_readiness_status: {reports['velocity_segments'].get('readiness_status')}",
        f"- decision_status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        "- Go2 contact thresholds are derived from Go2 field distributions only.",
        "- Go2 velocity is not truth.",
        "- Contact-conditioned velocity comparison is not truth error.",
        "- trace_solver_input: false",
        "- final_v23_output_solver_input: false",
        "- go2_velocity_prior_enabled: false",
        "- go2_yaw_prior_enabled: false",
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
        raise SystemExit("--allow-run is required for N7B2 runtime execution")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    n7a_root = Path(args.n7a_root)
    n7b_root = Path(args.n7b_root)
    go2_csv = n7a_root / "GO2_BODY_STATE_STANDARDIZED.csv"
    if not go2_csv.exists():
        raise FileNotFoundError(f"GO2_BODY_STATE_STANDARDIZED.csv missing under N7A root: {n7a_root}")
    go2_rows = read_standardized_csv(go2_csv)
    n7b_contact_v1 = read_csv_rows(n7b_root / "GO2_CONTACT_STATE_TIMESERIES.csv")
    n7b_reports = {
        "contact": _read_json(n7b_root / "GO2_CONTACT_STATE_REPORT.json"),
        "velocity": _read_json(n7b_root / "GO2_VELOCITY_QUALITY_REPORT.json"),
        "decision": _read_json(n7b_root / "N7B_GO2_VELOCITY_CONTACT_DECISION_REPORT.json"),
    }
    clean_gnss = find_clean_gnss(args.clean_root)
    receiver_rows = load_receiver_velocity_rows(clean_gnss)
    factor_csv = find_factor_csv(args.n5b_root)
    raw_rows = load_raw_doppler_factor_rows(factor_csv)

    _dist_path, distribution_report = write_contact_distribution_report(go2_rows, out)
    _threshold_path, threshold_report = write_contact_threshold_review(distribution_report, out)
    _v2_csv, _v2_json, contact_v2_rows, contact_v2_report = write_contact_state_v2_outputs(go2_rows, threshold_report, out)
    _smooth_csv, _smooth_json, smoothed_rows, smoothing_report = write_contact_smoothing_outputs(contact_v2_rows, out)
    _seg_path, velocity_segment_report = write_contact_velocity_segment_review(
        go2_rows,
        out,
        receiver_velocity_rows=receiver_rows,
        raw_doppler_rows=raw_rows,
        contact_v2_rows=smoothed_rows,
        contact_v1_rows=n7b_contact_v1,
    )
    decision = make_n7b2_decision(
        distribution_report=distribution_report,
        contact_v2_report=contact_v2_report,
        smoothing_report=smoothing_report,
        velocity_segment_report=velocity_segment_report,
    )
    write_n7b2_decision(decision, out / "N7B2_GO2_CONTACT_THRESHOLD_DECISION_REPORT.json")
    reports = {
        "distribution": distribution_report,
        "threshold": threshold_report,
        "contact_v2": contact_v2_report,
        "smoothing": smoothing_report,
        "velocity_segments": velocity_segment_report,
    }
    figure_manifest: dict[str, Any] = {"required_figures_generated": False, "paper_performance_claim": False}
    if args.figure_output_dir:
        figure_manifest = generate_n7b2_visual_plots(
            figure_output_dir=args.figure_output_dir,
            output_dir=out,
            go2_rows=go2_rows,
            contact_v1_rows=n7b_contact_v1,
            contact_v2_rows=smoothed_rows,
            threshold_report=threshold_report,
            smoothing_report=smoothing_report,
            velocity_segment_report=velocity_segment_report,
            decision=decision,
        )
    _write_case_review(out / "n7b2_contact_threshold_case_review.md", reports, decision)
    run_report = {
        "stage": "N7B2_go2_contact_threshold_review",
        "input_roles": {
            "n7a_root": "N7A_go2_body_state_runtime_report_root",
            "n7b_root": "N7B_velocity_contact_runtime_report_root",
            "n5b_root": "N5B_raw_doppler_runtime_report_root",
            "n6b_root": "N6B_source_aware_policy_runtime_report_root",
            "clean_root": "clean_receiver_velocity_runtime_root",
        },
        "go2_row_count": len(go2_rows),
        "n7b_contact_v1_row_count": len(n7b_contact_v1),
        "receiver_velocity_row_count": len(receiver_rows),
        "raw_doppler_row_count": len(raw_rows),
        "clean_gnss_runtime_path": str(clean_gnss) if clean_gnss else "",
        "raw_doppler_factor_runtime_path": str(factor_csv),
        "n7b_reports": n7b_reports,
        "reports": reports,
        "decision": decision,
        "figure_manifest": figure_manifest,
        "paper_performance_claim": False,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }
    _write_json(out / "N7B2_GO2_CONTACT_THRESHOLD_RUN_REPORT.json", run_report)
    print(json.dumps({"reports": reports, "decision": decision}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
