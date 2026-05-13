#!/usr/bin/env python3
"""Run N7C4 Go2 horizontal velocity prior strength calibration.

中文说明：N7C4 允许受控扫描 Go2 horizontal velocity prior 强度，但不使用
trace/final_v23 输出调参，不启用 Go2 垂向/yaw/position prior，不做论文性能声明。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_horizontal_velocity_activation_runner import run_n7c_horizontal_velocity_matrix
from legsa_gins.go2_prior.go2_horizontal_velocity_confidence import read_csv_rows, read_json
from legsa_gins.go2_prior.go2_horizontal_velocity_confidence_recalibration import (
    build_go2_horizontal_velocity_recalibrated_confidence,
    load_go2_source_aware_residual_rows,
    write_recalibrated_confidence_outputs,
)
from legsa_gins.go2_prior.go2_horizontal_velocity_nis_diagnostics import build_n7c4_nis_diagnostics
from legsa_gins.go2_prior.go2_horizontal_velocity_strength_ablation import (
    REQUIRED_N7C4_VARIANT_IDS,
    build_n7c4_strength_ablation_matrix,
    compare_n7c4_strength_variants,
    write_n7c4_strength_ablation_artifacts,
)
from legsa_gins.go2_prior.go2_horizontal_velocity_strength_calibration import (
    build_and_write_strength_priors,
)
from legsa_gins.go2_prior.go2_n7c4_decision import make_n7c4_strength_decision, write_n7c4_strength_decision
from legsa_gins.go2_prior.go2_n7c4_visual_plots import generate_n7c4_visual_plots
from legsa_gins.raw_gnss.raw_doppler_visual_loader import (
    find_clean_gnss,
    find_factor_csv,
    load_raw_doppler_factor_rows,
    load_receiver_velocity_rows,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n7c-root", required=True)
    parser.add_argument("--n7c1-root", required=True)
    parser.add_argument("--n7c2-root", required=True)
    parser.add_argument("--n7c3-root", required=True)
    parser.add_argument("--n7b5-root", required=True)
    parser.add_argument("--n7b4-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n6b-root", required=True)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def _write_json(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _source_prior_rows(n7c_root: str | Path, n7b5_root: str | Path) -> list[dict[str, Any]]:
    for path in [
        Path(n7c_root) / "GO2_HORIZONTAL_VELOCITY_WEAK_PRIORS.csv",
        Path(n7b5_root) / "GO2_HORIZONTAL_VELOCITY_PRIORS_DIAGNOSTIC.csv",
        Path(n7b5_root) / "GO2_HORIZONTAL_VELOCITY_PROBABILITY_WEIGHTED_PRIORS_DIAGNOSTIC.csv",
    ]:
        rows = read_csv_rows(path)
        if rows:
            return rows
    return []


def _read_prior_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_case_review(
    path: str | Path,
    *,
    confidence_report: dict[str, Any],
    prior_report: dict[str, Any],
    nis_report: dict[str, Any],
    comparison: dict[str, Any],
    decision: dict[str, Any],
    figures: dict[str, Any],
) -> None:
    lines = [
        "# N7C4 Go2 horizontal velocity strength calibration",
        "",
        "N7C4 scans fixed and recalibrated adaptive horizontal velocity prior strength.",
        "",
        f"- decision: {decision.get('status')}",
        f"- recommended_default_policy: {decision.get('recommended_default_policy')}",
        f"- confidence_counts: {confidence_report.get('confidence_counts')}",
        f"- fixed_1p0 clean horizontal delta: {decision.get('clean_fixed_1p0_minus_2p0_horizontal_rmse_delta_m')}",
        f"- fixed_1p0 NIS status: {decision.get('fixed_1p0_nis_status')}",
        f"- adaptive clean horizontal delta: {decision.get('clean_adaptive_minus_2p0_horizontal_rmse_delta_m')}",
        f"- adaptive NIS status: {decision.get('adaptive_nis_status')}",
        f"- figures generated: {figures.get('figure_count_total')}",
        "- Go2 velocity is not truth.",
        "- Vertical Go2 velocity, Go2 yaw prior, and Go2 position prior remain disabled.",
        "- No trace/final_v23 tuning, no output-only correction, no FGO, no paper performance claim.",
    ]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.allow_run:
        raise SystemExit("--allow-run is required for N7C4 runtime execution")
    out = Path(args.output_dir)
    figs = Path(args.figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    source_rows = _source_prior_rows(args.n7c_root, args.n7b5_root)
    contact_probability_rows = read_csv_rows(Path(args.n7b4_root) / "GO2_CONTACT_PROBABILITY_TIMESERIES.csv")
    contact_probability_report = read_json(Path(args.n7b4_root) / "GO2_CONTACT_PROBABILITY_MODEL_REPORT.json")
    frame_rows = read_csv_rows(Path(args.n7b5_root) / "GO2_FRAME_EQUIVALENCE_TIMESERIES.csv")
    frame_report = read_json(Path(args.n7b5_root) / "GO2_FRAME_EQUIVALENCE_REVIEW_REPORT.json")
    clean_gnss = find_clean_gnss(args.clean_root)
    receiver_rows = load_receiver_velocity_rows(clean_gnss)
    factor_csv = find_factor_csv(args.n5b_root)
    raw_rows = load_raw_doppler_factor_rows(factor_csv)
    residual_rows = load_go2_source_aware_residual_rows(args.n7c_root, args.n7c1_root, args.n7c3_root)

    confidence_rows, confidence_report = build_go2_horizontal_velocity_recalibrated_confidence(
        prior_rows=source_rows,
        contact_probability_rows=contact_probability_rows,
        contact_probability_report=contact_probability_report,
        frame_equivalence_rows=frame_rows,
        frame_equivalence_report=frame_report,
        receiver_velocity_rows=receiver_rows,
        raw_doppler_rows=raw_rows,
        residual_rows=residual_rows,
    )
    write_recalibrated_confidence_outputs(output_dir=out, confidence_rows=confidence_rows, confidence_report=confidence_report)

    prior_paths, prior_report = build_and_write_strength_priors(
        output_dir=out,
        source_prior_rows=source_rows,
        confidence_rows=confidence_rows,
    )
    matrix = build_n7c4_strength_ablation_matrix(output_dir=out, raw_doppler_factor_path=factor_csv, prior_paths=prior_paths)
    _runs, summaries = run_n7c_horizontal_velocity_matrix(
        matrix,
        clean_root=args.clean_root,
        exe=args.exe,
        output_dir=out,
        dual_reference=args.dual_root,
    )
    nis_report = build_n7c4_nis_diagnostics(output_dir=out, variant_ids=REQUIRED_N7C4_VARIANT_IDS)
    comparison = compare_n7c4_strength_variants(summaries, prior_report, nis_report)
    write_n7c4_strength_ablation_artifacts(output_dir=out, matrix=matrix, variant_summaries=summaries, comparison_report=comparison)
    preliminary = make_n7c4_strength_decision(
        confidence_report=confidence_report,
        prior_report=prior_report,
        nis_report=nis_report,
        comparison_report=comparison,
        figure_manifest={},
    )
    prior_rows_by_policy = {policy: _read_prior_csv(path) for policy, path in prior_paths.items()}
    figures = generate_n7c4_visual_plots(
        figure_output_dir=figs,
        output_dir=out,
        confidence_rows=confidence_rows,
        prior_rows_by_policy=prior_rows_by_policy,
        comparison_report=comparison,
        nis_report=nis_report,
        decision=preliminary,
    )
    _write_json(out / "N7C4_FIGURE_MANIFEST.json", figures)
    decision = make_n7c4_strength_decision(
        confidence_report=confidence_report,
        prior_report=prior_report,
        nis_report=nis_report,
        comparison_report=comparison,
        figure_manifest=figures,
    )
    write_n7c4_strength_decision(out / "N7C4_STRENGTH_CALIBRATION_DECISION_REPORT.json", decision)
    _write_case_review(
        out / "n7c4_strength_calibration_case_review.md",
        confidence_report=confidence_report,
        prior_report=prior_report,
        nis_report=nis_report,
        comparison=comparison,
        decision=decision,
        figures=figures,
    )
    run_report = {
        "stage": "N7C4_go2_horizontal_velocity_strength_calibration",
        "input_roles": {
            "n7c_root": "N7C_runtime_report_root",
            "n7c1_root": "N7C1_runtime_report_root",
            "n7c2_root": "N7C2_runtime_report_root",
            "n7c3_root": "N7C3_runtime_report_root",
            "n7b5_root": "N7B5_runtime_report_root",
            "n7b4_root": "N7B4_runtime_report_root",
            "n5b_root": "N5B_raw_doppler_runtime_report_root",
            "n6b_root": "N6B_source_aware_runtime_report_root",
            "clean_root": "clean_receiver_velocity_runtime_root",
            "dual_root": "dual_reference_runtime_root",
            "output_dir": "N7C4_runtime_output_root",
            "figure_output_dir": "N7C4_runtime_figure_root",
        },
        "confidence": confidence_report,
        "prior_strength": prior_report,
        "matrix": matrix,
        "variant_summaries": {"variants": summaries, "paper_performance_claim": False},
        "nis_diagnostics": nis_report,
        "comparison": comparison,
        "decision": decision,
        "figure_manifest": figures,
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "vertical_disabled": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }
    _write_json(out / "N7C4_STRENGTH_CALIBRATION_RUN_REPORT.json", run_report)
    print(json.dumps({"confidence": confidence_report, "prior_strength": prior_report, "nis": nis_report, "decision": decision, "figures": figures}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
