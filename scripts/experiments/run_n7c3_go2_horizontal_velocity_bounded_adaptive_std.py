#!/usr/bin/env python3
"""Run N7C3 bounded adaptive Go2 horizontal velocity std policy.

中文说明：N7C3 只修改 Go2 horizontal velocity prior 的 row-wise R/std 和
update eligibility；不使用 trace/final_v23 输出调参，不启用 Go2 vertical/yaw/
position prior，不实现 FGO，不做 paper performance claim。
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

from legsa_gins.go2_prior.go2_horizontal_velocity_adaptive_ablation import (
    build_n7c3_bounded_adaptive_ablation_matrix,
    compare_n7c3_bounded_adaptive_variants,
    write_n7c3_ablation_artifacts,
)
from legsa_gins.go2_prior.go2_horizontal_velocity_bounded_adaptive_std import (
    BOUNDED_PRIOR_FIELDS,
    STD_VD_DISABLED,
    build_bounded_adaptive_go2_horizontal_velocity_priors,
    write_bounded_adaptive_prior_outputs,
)
from legsa_gins.go2_prior.go2_horizontal_velocity_confidence import (
    build_go2_horizontal_velocity_confidence,
    read_csv_rows,
    read_json,
    write_go2_horizontal_velocity_confidence_outputs,
)
from legsa_gins.go2_prior.go2_horizontal_velocity_activation_runner import run_n7c_horizontal_velocity_matrix
from legsa_gins.go2_prior.go2_horizontal_velocity_soft_gating import (
    build_go2_horizontal_velocity_soft_gating_report,
    write_go2_horizontal_velocity_soft_gating_report,
)
from legsa_gins.go2_prior.go2_n7c3_decision import make_n7c3_decision, write_n7c3_decision
from legsa_gins.go2_prior.go2_n7c3_visual_plots import generate_n7c3_visual_plots
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


def _write_prior_csv(path: str | Path, rows: list[dict[str, Any]]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BOUNDED_PRIOR_FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in BOUNDED_PRIOR_FIELDS} for row in rows])
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


def _fixed_std_rows(source_rows: list[dict[str, Any]], confidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_time = {round(float(row.get("time", 0.0) or 0.0), 6): row for row in confidence_rows}
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        time_value = float(row.get("time", 0.0) or 0.0)
        conf = by_time.get(round(time_value, 6), {})
        level = conf.get("confidence_level", "medium")
        rows.append(
            {
                "time": time_value,
                "vn": row.get("vn", 0.0),
                "ve": row.get("ve", 0.0),
                "vd": 0.0,
                "std_vn": 2.0,
                "std_ve": 2.0,
                "std_vd": STD_VD_DISABLED,
                "confidence": conf.get("confidence", ""),
                "confidence_level": level,
                "update_flag": "true",
                "reason_codes": "fixed_std_2mps_reference;no_trace_tuning;no_final_v23_tuning;go2_velocity_not_truth",
                "source_status": "active",
                "quality_flag": f"n7c3_fixed_{level}_confidence",
                "contact_model": row.get("contact_model", ""),
                "contact_label": row.get("contact_label", ""),
                "frame_candidate": row.get("frame_candidate", ""),
                "prior_policy": "n7c3_fixed_std_2mps_reference",
                "diagnostic_only": "false",
                "go2_velocity_truth_claim": "false",
            }
        )
    return rows


def _write_case_review(path: str | Path, *, std_report: dict[str, Any], comparison: dict[str, Any], decision: dict[str, Any], figures: dict[str, Any]) -> None:
    lines = [
        "# N7C3 bounded adaptive Go2 horizontal velocity std",
        "",
        "N7C3 replaces the over-wide coarse adaptive std idea with a literature-informed bounded soft-gating policy.",
        "",
        f"- decision: {decision.get('status')}",
        f"- max std: {decision.get('max_std')}",
        f"- std_vn p50/p95/max: {std_report.get('std_vn_p50')} / {std_report.get('std_vn_p95')} / {std_report.get('std_vn_max')}",
        f"- std_ve p50/p95/max: {std_report.get('std_ve_p50')} / {std_report.get('std_ve_p95')} / {std_report.get('std_ve_max')}",
        f"- update_count: {decision.get('update_count')}",
        f"- skip_count: {decision.get('skip_count')}",
        f"- clean adaptive-fixed delta: {decision.get('clean_bounded_adaptive_minus_fixed_horizontal_rmse_delta_m')}",
        f"- receiver stress adaptive-fixed delta: {decision.get('receiver_stress_bounded_adaptive_minus_fixed_horizontal_rmse_delta_m')}",
        f"- raw Doppler stress adaptive-fixed delta: {decision.get('raw_doppler_stress_bounded_adaptive_minus_fixed_horizontal_rmse_delta_m')}",
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
        raise SystemExit("--allow-run is required for N7C3 runtime execution")
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

    confidence_rows, confidence_report = build_go2_horizontal_velocity_confidence(
        prior_rows=source_rows,
        contact_probability_rows=contact_probability_rows,
        contact_probability_report=contact_probability_report,
        frame_equivalence_rows=frame_rows,
        frame_equivalence_report=frame_report,
        receiver_velocity_rows=receiver_rows,
        raw_doppler_rows=raw_rows,
    )
    write_go2_horizontal_velocity_confidence_outputs(
        output_dir=out,
        confidence_rows=confidence_rows,
        confidence_report=confidence_report,
    )

    adaptive_rows, std_report = build_bounded_adaptive_go2_horizontal_velocity_priors(
        source_prior_rows=source_rows,
        confidence_rows=confidence_rows,
    )
    adaptive_path, _std_report_path = write_bounded_adaptive_prior_outputs(output_dir=out, rows=adaptive_rows, report=std_report)
    fixed_rows = _fixed_std_rows(source_rows, confidence_rows)
    fixed_path = _write_prior_csv(out / "GO2_HORIZONTAL_VELOCITY_FIXED_STD_2MPS_PRIORS.csv", fixed_rows)
    high_rows, high_report = build_bounded_adaptive_go2_horizontal_velocity_priors(
        source_prior_rows=source_rows,
        confidence_rows=confidence_rows,
        policy_name="n7c3_high_confidence_only_bounded_diagnostic",
        high_confidence_only=True,
    )
    high_path, _ = write_bounded_adaptive_prior_outputs(
        output_dir=out,
        rows=high_rows,
        report={**high_report, "policy_name": "n7c3_high_confidence_only_bounded_diagnostic"},
        csv_name="GO2_HORIZONTAL_VELOCITY_HIGH_CONFIDENCE_ONLY_BOUNDED_PRIORS.csv",
        report_name="GO2_HORIZONTAL_VELOCITY_HIGH_CONFIDENCE_ONLY_BOUNDED_REPORT.json",
    )
    original_probability = Path(args.n7c_root) / "GO2_HORIZONTAL_VELOCITY_PROBABILITY_WEIGHTED_PRIORS_N7C.csv"
    if not original_probability.exists():
        original_probability = Path(args.n7b5_root) / "GO2_HORIZONTAL_VELOCITY_PROBABILITY_WEIGHTED_PRIORS_DIAGNOSTIC.csv"

    soft_gating_report = build_go2_horizontal_velocity_soft_gating_report(adaptive_rows)
    write_go2_horizontal_velocity_soft_gating_report(out / "GO2_HORIZONTAL_VELOCITY_SOFT_GATING_REPORT.json", soft_gating_report)

    matrix = build_n7c3_bounded_adaptive_ablation_matrix(
        output_dir=out,
        raw_doppler_factor_path=factor_csv,
        prior_paths={
            "fixed_std_2mps": fixed_path,
            "bounded_adaptive": adaptive_path,
            "high_confidence_only": high_path,
            "probability_weighted_original": original_probability,
        },
    )
    _runs, summaries = run_n7c_horizontal_velocity_matrix(
        matrix,
        clean_root=args.clean_root,
        exe=args.exe,
        output_dir=out,
        dual_reference=args.dual_root,
    )
    comparison = compare_n7c3_bounded_adaptive_variants(summaries, std_report)
    write_n7c3_ablation_artifacts(
        output_dir=out,
        matrix=matrix,
        variant_summaries=summaries,
        comparison_report=comparison,
    )
    preliminary = make_n7c3_decision(
        std_report=std_report,
        soft_gating_report=soft_gating_report,
        comparison_report=comparison,
        figure_manifest={},
    )
    figures = generate_n7c3_visual_plots(
        figure_output_dir=figs,
        output_dir=out,
        confidence_rows=confidence_rows,
        adaptive_prior_rows=adaptive_rows,
        comparison_report=comparison,
        decision=preliminary,
    )
    _write_json(out / "N7C3_FIGURE_MANIFEST.json", figures)
    decision = make_n7c3_decision(
        std_report=std_report,
        soft_gating_report=soft_gating_report,
        comparison_report=comparison,
        figure_manifest=figures,
    )
    write_n7c3_decision(out / "N7C3_BOUNDED_ADAPTIVE_STD_DECISION_REPORT.json", decision)
    _write_case_review(
        out / "n7c3_bounded_adaptive_std_case_review.md",
        std_report=std_report,
        comparison=comparison,
        decision=decision,
        figures=figures,
    )
    run_report = {
        "stage": "N7C3_go2_horizontal_velocity_bounded_adaptive_std",
        "input_roles": {
            "n7c_root": "N7C_runtime_report_root",
            "n7c1_root": "N7C1_runtime_report_root",
            "n7c2_root": "N7C2_runtime_report_root",
            "n7b5_root": "N7B5_runtime_report_root",
            "n7b4_root": "N7B4_runtime_report_root",
            "n5b_root": "N5B_raw_doppler_runtime_report_root",
            "n6b_root": "N6B_source_aware_runtime_report_root",
            "clean_root": "clean_receiver_velocity_runtime_root",
            "dual_root": "dual_reference_runtime_root",
            "output_dir": "N7C3_runtime_output_root",
            "figure_output_dir": "N7C3_runtime_figure_root",
        },
        "confidence": confidence_report,
        "bounded_adaptive_std": std_report,
        "soft_gating": soft_gating_report,
        "matrix": matrix,
        "variant_summaries": {"variants": summaries, "paper_performance_claim": False},
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
    _write_json(out / "N7C3_BOUNDED_ADAPTIVE_STD_RUN_REPORT.json", run_report)
    print(json.dumps({"std_report": std_report, "soft_gating": soft_gating_report, "decision": decision, "figures": figures}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
