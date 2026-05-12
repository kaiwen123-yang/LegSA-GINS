#!/usr/bin/env python3
"""Run N7B Go2 velocity/contact readiness diagnostics.

中文说明：所有真实数据路径只来自命令行参数；N7B 只生成 runtime-only reports
和 figures，不激活 Go2 velocity/yaw prior，不使用 trace/final_v23 output 作为
solver input。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_contact_velocity_readiness import run_go2_contact_velocity_readiness
from legsa_gins.go2_prior.go2_n7b_visual_plots import generate_n7b_visual_plots
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
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n5c-root", required=True)
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
        "# N7B Go2 velocity/contact readiness",
        "",
        "This report is diagnostic engineering evidence only.",
        "",
        f"- contact_rows: {reports['contact'].get('contact_rows')}",
        f"- contact_quality_status: {reports['contact'].get('recommended_contact_quality_status')}",
        f"- aligned_count_to_receiver_velocity: {reports['velocity'].get('aligned_count_to_receiver_velocity')}",
        f"- aligned_count_to_raw_doppler: {reports['velocity'].get('aligned_count_to_raw_doppler')}",
        f"- velocity_consistency_status: {reports['velocity'].get('consistency_status')}",
        f"- yaw_rate_consistency_status: {reports['yaw'].get('consistency_status')}",
        f"- decision_status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        "- Go2 position is not truth.",
        "- Go2 velocity is not truth.",
        "- Cross-source velocity comparison is not truth error.",
        "- contact thresholds are diagnostic defaults and are not trace tuned.",
        "- go2_velocity_prior_enabled: false",
        "- go2_yaw_prior_enabled: false",
        "- trace_solver_input: false",
        "- final_v23_output_solver_input: false",
        "- output_only_correction: false",
        "- bad_epoch_deletion_for_metric: false",
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
        raise SystemExit("--allow-run is required for N7B runtime execution")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    n7a_root = Path(args.n7a_root)
    go2_csv = n7a_root / "GO2_BODY_STATE_STANDARDIZED.csv"
    if not go2_csv.exists():
        raise FileNotFoundError(f"GO2_BODY_STATE_STANDARDIZED.csv missing under N7A root: {n7a_root}")
    go2_rows = read_standardized_csv(go2_csv)
    weak_prior_report = _read_json(n7a_root / "GO2_WEAK_PRIOR_BUILD_REPORT.json")

    clean_gnss = find_clean_gnss(args.clean_root)
    receiver_rows = load_receiver_velocity_rows(clean_gnss)
    factor_csv = find_factor_csv(args.n5b_root)
    raw_rows = load_raw_doppler_factor_rows(factor_csv)

    bundle = run_go2_contact_velocity_readiness(
        go2_rows=go2_rows,
        receiver_velocity_rows=receiver_rows,
        raw_doppler_rows=raw_rows,
        output_dir=out,
        n7a_weak_prior_report=weak_prior_report,
    )
    reports = {
        "contact": bundle["contact_report"],
        "velocity": bundle["velocity_report"],
        "motion": bundle["motion_report"],
        "yaw": bundle["yaw_report"],
    }
    figure_manifest: dict[str, Any] = {"required_figures_generated": False, "paper_performance_claim": False}
    if args.figure_output_dir:
        figure_manifest = generate_n7b_visual_plots(
            figure_output_dir=args.figure_output_dir,
            output_dir=out,
            contact_rows=bundle["contact_rows"],
            velocity_rows=bundle["velocity_rows"],
            motion_rows=bundle["motion_rows"],
            yaw_rows=bundle["yaw_rows"],
            reports=reports,
            decision=bundle["decision"],
        )
    _write_case_review(out / "n7b_go2_velocity_contact_case_review.md", reports, bundle["decision"])
    run_report = {
        "stage": "N7B_go2_velocity_contact_readiness",
        "input_roles": {
            "n7a_root": "N7A_go2_body_state_runtime_report_root",
            "n5b_root": "N5B_raw_doppler_runtime_report_root",
            "n5c_root": "N5C_raw_doppler_ablation_runtime_report_root",
            "n6b_root": "N6B_source_aware_policy_runtime_report_root",
            "clean_root": "clean_receiver_velocity_runtime_root",
        },
        "go2_row_count": len(go2_rows),
        "receiver_velocity_row_count": len(receiver_rows),
        "raw_doppler_row_count": len(raw_rows),
        "clean_gnss_runtime_path": str(clean_gnss) if clean_gnss else "",
        "raw_doppler_factor_runtime_path": str(factor_csv),
        "reports": reports,
        "decision": bundle["decision"],
        "figure_manifest": figure_manifest,
        "paper_performance_claim": False,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "fgo": False,
    }
    _write_json(out / "N7B_GO2_VELOCITY_CONTACT_RUN_REPORT.json", run_report)
    print(json.dumps({"reports": reports, "decision": bundle["decision"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
