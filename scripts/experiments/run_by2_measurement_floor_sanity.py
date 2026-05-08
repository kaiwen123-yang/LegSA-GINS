#!/usr/bin/env python3
"""Run N4H0 BY2 receiver-native measurement-floor sanity evaluation.

中文说明：本脚本不运行 LegSA filter，不生成 proposed solver 输出；它只把
receiver-native GNSS status 直接转成 EVAL_NAV-like rows，并与 trace evaluation-only
reference 做诊断对齐。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.datasets.by2.dual_antenna_heading_convention import (  # noqa: E402
    candidate_heading_offsets,
)
from legsa_gins.evaluation.case_review_report import FINAL_V23_CONTEXT  # noqa: E402
from legsa_gins.evaluation.measurement_floor import (  # noqa: E402
    compare_filter_trial_to_measurement_floor,
    evaluate_measurement_floor,
    load_receiver_status_standard,
    load_trace_eval_reference,
    make_direct_receiver_eval_nav,
    write_direct_receiver_eval_nav,
    write_json,
)
from legsa_gins.experiments.by2_filter_trial import write_toy_standardized_inputs  # noqa: E402
from legsa_gins.time_alignment.event_normalization import (  # noqa: E402
    add_algo_time_to_csv,
    make_event_normalization_report,
)


N4G_FILTER_CONTEXT = {
    "phase": "N4G",
    "candidate_name": "best_diagnostic_context_from_user",
    "horizontal_rmse_m": 14.86,
    "yaw_rmse_deg": 64.0,
    "context_only": True,
    "numerical_performance_claim": False,
}


def _standardize_inputs(args: argparse.Namespace, inputs_dir: Path) -> None:
    if args.toy:
        write_toy_standardized_inputs(inputs_dir)
        return
    from scripts.datasets.standardize_by2_inputs import standardize_by2_inputs

    standardize_by2_inputs(
        fix_root=args.fix_root,
        body_imu=args.body_imu,
        output_dir=inputs_dir,
        max_status_rows=args.max_status_rows,
        max_raw_rows=args.max_raw_rows,
        max_body_messages=args.max_body_messages,
    )


def _source_paths(inputs_dir: Path) -> dict[str, Path]:
    return {
        "gnss1": inputs_dir / "BY2_GNSS1_STATUS_STANDARD.csv",
        "gnss2": inputs_dir / "BY2_GNSS2_STATUS_STANDARD.csv",
    }


def _normalize_source(
    *,
    inputs_dir: Path,
    source_name: str,
    gnss_csv: Path,
    trace_csv: Path,
    end_margin_sec: float,
) -> tuple[Path, Path, dict[str, Any]]:
    event_report = make_event_normalization_report(
        go2_body_state_csv=inputs_dir / "BY2_GO2_BODY_STATE_DIAGNOSTIC.csv",
        gnss_status_csv=gnss_csv,
        trace_csv=trace_csv,
        end_margin_sec=end_margin_sec,
    )
    end_time = float(event_report["end_algo_time_sec"])
    gnss_start = float(event_report["gnss_formal_start_raw_time"] or 0.0)
    normalized_gnss = inputs_dir / f"BY2_{source_name.upper()}_STATUS_ALGO_TIME.csv"
    normalized_trace = inputs_dir / f"BY2_TRACE_REFERENCE_{source_name.upper()}_ALGO_TIME.csv"
    add_algo_time_to_csv(
        gnss_csv,
        normalized_gnss,
        raw_time_field="time_unix",
        start_time=gnss_start,
        end_algo_time_sec=end_time,
    )
    add_algo_time_to_csv(
        trace_csv,
        normalized_trace,
        raw_time_field="timestamp",
        start_time=gnss_start,
        end_algo_time_sec=end_time,
    )
    event_report.update(
        {
            "phase": "N4H0",
            "source_name": source_name,
            "trace_solver_input": False,
            "trace_evaluation_only": True,
            "trace_used_for_alignment": False,
            "proposed_solver_output": False,
            "numerical_performance_claim": False,
        }
    )
    return normalized_gnss, normalized_trace, event_report


def _evaluate_source(
    *,
    output_dir: Path,
    source_name: str,
    normalized_gnss: Path,
    normalized_trace: Path,
) -> dict[str, Any]:
    receiver_rows = load_receiver_status_standard(normalized_gnss)
    trace_rows = load_trace_eval_reference(normalized_trace)
    candidates: dict[str, Any] = {}
    for offset in candidate_heading_offsets():
        mode = str(offset["heading_offset_mode"])
        eval_nav = make_direct_receiver_eval_nav(
            receiver_rows,
            source_name=source_name,
            heading_offset_mode=mode,
        )
        if mode == "no_offset":
            eval_path = output_dir / f"{source_name.upper()}_MEASUREMENT_FLOOR_EVAL_NAV.csv"
        else:
            eval_path = output_dir / f"{source_name.upper()}_MEASUREMENT_FLOOR_EVAL_NAV_{mode}.csv"
        write_direct_receiver_eval_nav(eval_nav, eval_path)
        summary = evaluate_measurement_floor(eval_nav, trace_rows, max_dt=0.05)
        summary.update(
            {
                "source_name": source_name,
                "heading_offset_mode": mode,
                "heading_offset_deg": offset["heading_offset_deg"],
                "eval_nav": str(eval_path),
                "trace_solver_input": False,
                "proposed_solver_output": False,
            }
        )
        candidates[mode] = summary

    source_summary = {
        "phase": "N4H0",
        "source_name": source_name,
        "evaluation_role": "receiver_native_measurement_floor",
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "proposed_solver_output": False,
        "numerical_performance_claim": False,
        "heading_candidates": candidates,
    }
    write_json(output_dir / f"{source_name.upper()}_MEASUREMENT_FLOOR_SUMMARY.json", source_summary)
    return source_summary


def _metric_value(summary: dict[str, Any], field: str) -> float:
    value = summary.get(field)
    if isinstance(value, (int, float)):
        return float(value)
    return 1.0e99


def _find_best(all_candidates: dict[str, dict[str, Any]], metric: str) -> tuple[str, dict[str, Any]]:
    return min(all_candidates.items(), key=lambda item: _metric_value(item[1], metric))


def _make_case_review(path: Path, report: dict[str, Any], heading_report: dict[str, Any]) -> None:
    best_position = report["best_position_floor"]
    best_heading = report["best_heading_floor"]
    conclusion = report["comparison"]["conclusion"]
    lines = [
        "# BY2 measurement floor sanity case_review",
        "",
        "case_name: BY2_measurement_floor_sanity",
        "report_style_case_review: yes",
        "algorithm_line: receiver_native_measurement_floor",
        "proposed_solver_output: false",
        "numerical_performance_claim: false",
        "",
        "## Purpose",
        "- Evaluate direct receiver-native GNSS status against trace reference.",
        "- Distinguish input/evaluator issues from filter update or mechanization issues.",
        "- Keep trace evaluation-only and out of any solver input.",
        "",
        "## Benchmark Context",
        "- primary_benchmark: dual_final_v23_reference_context",
        f"- dual_final_v23 horizontal_rmse_m = {FINAL_V23_CONTEXT['dual_final_v23']['horizontal_rmse_m']}",
        f"- dual_final_v23 up_rmse_m = {FINAL_V23_CONTEXT['dual_final_v23']['up_rmse_m']}",
        f"- dual_final_v23 yaw_rmse_deg = {FINAL_V23_CONTEXT['dual_final_v23']['yaw_rmse_deg']}",
        f"- context_only_single_antenna horizontal_rmse_m = {FINAL_V23_CONTEXT['single_antenna']['horizontal_rmse_m']}",
        f"- context_only_single_antenna yaw_rmse_deg = {FINAL_V23_CONTEXT['single_antenna']['yaw_rmse_deg']}",
        f"- context_only_pure_ins horizontal_rmse_m = {FINAL_V23_CONTEXT['pure_ins']['horizontal_rmse_m']}",
        "",
        "## N4G Filter Context",
        f"- horizontal_rmse_m: {N4G_FILTER_CONTEXT['horizontal_rmse_m']}",
        f"- yaw_rmse_deg: {N4G_FILTER_CONTEXT['yaw_rmse_deg']}",
        "- context_only: true",
        "- ready_for_factor_stacking: false",
        "",
        "## Measurement Floor Metrics",
        f"- best_position_candidate: {best_position['candidate_name']}",
        f"- best_position_horizontal_rmse_m: {best_position['summary'].get('horizontal_rmse_m')}",
        f"- best_position_up_rmse_m: {best_position['summary'].get('up_rmse_m')}",
        f"- best_heading_candidate: {best_heading['candidate_name']}",
        f"- best_heading_yaw_rmse_deg: {best_heading['summary'].get('yaw_rmse_deg')}",
        f"- best_heading_yaw_p95_deg: {best_heading['summary'].get('yaw_p95_deg')}",
        "",
        "## Heading Candidate Summary",
    ]
    for name, summary in heading_report["candidate_summaries"].items():
        lines.append(
            f"- {name}: horizontal_rmse_m={summary.get('horizontal_rmse_m')}, "
            f"yaw_rmse_deg={summary.get('yaw_rmse_deg')}, count={summary.get('count')}"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            f"- measurement_floor_sanity_conclusion: {conclusion}",
            f"- likely_filter_issue: {str(report['comparison']['likely_filter_issue']).lower()}",
            f"- likely_input_or_evaluator_issue: {str(report['comparison']['likely_input_or_evaluator_issue']).lower()}",
            f"- likely_heading_convention_issue: {str(report['comparison']['likely_heading_convention_issue']).lower()}",
            f"- recommended_next_stage: {report['comparison']['recommended_next_stage']}",
            "",
            "## Claim Boundary",
            "- trace_solver_input: false",
            "- trace_evaluation_only: true",
            "- proposed_solver_output: false",
            "- output_only_correction: false",
            "- bad_epoch_deletion_for_metric: false",
            "- raw_doppler_claim: false",
            "- go2_prior_claim: false",
            "- source_aware_weighting_claim: false",
            "- fgo_smoother_claim: false",
            "- formal performance claim: false",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_measurement_floor(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    inputs_dir = output_dir / "inputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir.mkdir(parents=True, exist_ok=True)

    _standardize_inputs(args, inputs_dir)
    trace_csv = inputs_dir / "BY2_TRACE_REFERENCE_EVAL_ONLY.csv"
    source_reports: dict[str, Any] = {}
    event_reports: dict[str, Any] = {}
    all_candidates: dict[str, dict[str, Any]] = {}

    for source_name, gnss_csv in _source_paths(inputs_dir).items():
        if not gnss_csv.exists():
            continue
        normalized_gnss, normalized_trace, event_report = _normalize_source(
            inputs_dir=inputs_dir,
            source_name=source_name,
            gnss_csv=gnss_csv,
            trace_csv=trace_csv,
            end_margin_sec=args.end_margin_sec,
        )
        event_reports[source_name] = event_report
        source_summary = _evaluate_source(
            output_dir=output_dir,
            source_name=source_name,
            normalized_gnss=normalized_gnss,
            normalized_trace=normalized_trace,
        )
        source_reports[source_name] = source_summary
        for mode, summary in source_summary["heading_candidates"].items():
            all_candidates[f"{source_name}_{mode}"] = summary

    if not all_candidates:
        raise RuntimeError("No receiver status candidates were available.")

    best_position_name, best_position_summary = _find_best(all_candidates, "horizontal_rmse_m")
    best_heading_name, best_heading_summary = _find_best(all_candidates, "yaw_rmse_deg")
    combined_floor = dict(best_position_summary)
    combined_floor["yaw_rmse_deg"] = best_heading_summary.get("yaw_rmse_deg")
    combined_floor["yaw_p95_deg"] = best_heading_summary.get("yaw_p95_deg")
    comparison = compare_filter_trial_to_measurement_floor(N4G_FILTER_CONTEXT, combined_floor)

    heading_report = {
        "phase": "N4H0",
        "mounting": "transverse_dual_antenna",
        "candidate_offsets": candidate_heading_offsets(),
        "candidate_summaries": all_candidates,
        "best_heading_floor": {
            "candidate_name": best_heading_name,
            "summary": best_heading_summary,
        },
        "formal_heading_offset_selected": False,
        "trace_used_for_formal_selection": False,
        "heading_mounting_diagnostic_only": True,
        "numerical_performance_claim": False,
    }
    write_json(output_dir / "HEADING_FLOOR_CANDIDATE_REPORT.json", heading_report)

    report = {
        "phase": "N4H0",
        "case_name": "BY2_measurement_floor_sanity",
        "evaluation_role": "receiver_native_measurement_floor",
        "source_reports": source_reports,
        "event_reports": event_reports,
        "best_position_floor": {
            "candidate_name": best_position_name,
            "summary": best_position_summary,
        },
        "best_heading_floor": {
            "candidate_name": best_heading_name,
            "summary": best_heading_summary,
        },
        "n4g_filter_context": N4G_FILTER_CONTEXT,
        "comparison": comparison,
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "trace_used_for_alignment": False,
        "proposed_solver_output": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "raw_doppler_claim": False,
        "go2_prior_claim": False,
        "source_aware_weighting_claim": False,
        "fgo_smoother_claim": False,
        "numerical_performance_claim": False,
        "final_v23_reference_context_only": True,
    }
    write_json(output_dir / "MEASUREMENT_FLOOR_SANITY_REPORT.json", report)
    _make_case_review(output_dir / "measurement_floor_case_review.md", report, heading_report)
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-root", help="Local BY2 Fixposition root.")
    parser.add_argument("--body-imu", help="Local BY2 Go2 body-state text file.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-status-rows", type=int, default=None)
    parser.add_argument("--max-raw-rows", type=int, default=None)
    parser.add_argument("--max-body-messages", type=int, default=None)
    parser.add_argument("--end-margin-sec", type=float, default=5.0)
    parser.add_argument("--toy", action="store_true", help="Use toy standardized inputs.")
    args = parser.parse_args()
    if not args.toy and (not args.fix_root or not args.body_imu):
        parser.error("--fix-root and --body-imu are required unless --toy is used.")
    return args


def main() -> int:
    result = run_measurement_floor(_parse_args())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
