"""case_review-style report writer for the N4F diagnostic trial.

中文说明：本报告只写 diagnostic case_review，不声明 final_v23 parity 或正式性能结论。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.target_gates import evaluate_target_gates


FINAL_V23_CONTEXT = {
    "dual_final_v23": {
        "horizontal_rmse_m": 0.353,
        "up_rmse_m": 0.818,
        "yaw_rmse_deg": 1.814,
        "roll_rmse_deg": 1.025,
        "pitch_rmse_deg": 1.524,
    },
    "single_antenna": {
        "horizontal_rmse_m": 38.947,
        "yaw_rmse_deg": 41.375,
    },
    "pure_ins": {
        "horizontal_rmse_m": 59240.252,
    },
}

REQUIRED_RUN_OUTPUTS = [
    "LegSA_NAV.nav",
    "LegSA_STD.csv",
    "EVAL_NAV.csv",
    "RUN_MANIFEST.json",
]


def _fmt(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _json_load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _file_has_nan(path: Path) -> bool:
    if not path.exists():
        return True
    return "nan" in path.read_text(encoding="utf-8", errors="ignore").lower()


def classify_trial(
    summary: dict[str, Any],
    *,
    run_dir: str | Path,
) -> dict[str, Any]:
    run_path = Path(run_dir)
    outputs_exist = all((run_path / name).exists() for name in REQUIRED_RUN_OUTPUTS)
    no_nan = all(not _file_has_nan(run_path / name) for name in REQUIRED_RUN_OUTPUTS)
    h_rmse = summary.get("horizontal_rmse_m")
    yaw_rmse = summary.get("yaw_rmse_deg")
    count = int(summary.get("count") or 0)

    runtime_pass = bool(outputs_exist and no_nan)
    comparable_generated = count > 100
    if isinstance(h_rmse, (int, float)) and h_rmse < FINAL_V23_CONTEXT["single_antenna"][
        "horizontal_rmse_m"
    ]:
        single_compare = "legsa_better_than_single_antenna"
    else:
        single_compare = "single_antenna_better_than_legsa"
    final_v23_close = bool(
        isinstance(h_rmse, (int, float))
        and isinstance(yaw_rmse, (int, float))
        and h_rmse <= 2.0
        and yaw_rmse <= 2.5
    )
    final_v23_oracle_level = bool(
        isinstance(h_rmse, (int, float))
        and isinstance(yaw_rmse, (int, float))
        and h_rmse <= 0.5
        and yaw_rmse <= 2.0
    )

    return {
        "runtime_pass": runtime_pass,
        "comparable_generated": comparable_generated,
        "single_antenna_comparison": single_compare,
        "final_v23_close": final_v23_close,
        "final_v23_oracle_level": final_v23_oracle_level,
        "diagnostic_comparable": bool(runtime_pass and comparable_generated),
        "evidence_status": summary.get("evidence_status", "insufficient_alignment"),
    }


def generate_case_review(
    *,
    output_path: str | Path,
    run_dir: str | Path,
    input_manifest_path: str | Path,
    trial_manifest_path: str | Path,
    summary_path: str | Path,
    event_report_path: str | Path | None = None,
    imu_report_path: str | Path | None = None,
    heading_report_path: str | Path | None = None,
    gate_report_path: str | Path | None = None,
    gap_screen_path: str | Path | None = None,
) -> dict[str, Any]:
    """Write the N4F case_review.md and return the classification."""

    output = Path(output_path)
    run_path = Path(run_dir)
    trial_manifest = Path(trial_manifest_path)
    summary = _json_load(Path(summary_path))
    classification = classify_trial(summary, run_dir=run_path)
    run_manifest = _json_load(run_path / "RUN_MANIFEST.json")
    trial_manifest_data = _json_load(trial_manifest)
    event_report = _json_load(Path(event_report_path)) if event_report_path else {}
    imu_report = _json_load(Path(imu_report_path)) if imu_report_path else {}
    heading_report = _json_load(Path(heading_report_path)) if heading_report_path else {}
    gate_report = (
        _json_load(Path(gate_report_path)) if gate_report_path else evaluate_target_gates(summary)
    )
    gap_screen = _json_load(Path(gap_screen_path)) if gap_screen_path else {}

    lines = [
        "# BY2_filter_core_trial case_review",
        "",
        "case_name: BY2_filter_core_trial",
        "report_style_case_review: yes",
        "comparable_status: diagnostic_comparable",
        "numerical_performance_claim: false",
        "",
        "## algorithm_lines_available",
        "- legsa_filter_core_trial",
        "- final_v23_nominal_reference_context",
        "",
        "## Input Files",
        "- LegSA_NAV.nav",
        "- LegSA_STD.csv",
        "- EVAL_NAV.csv",
        "- RUN_MANIFEST.json",
        "- BY2_INPUT_MANIFEST.json",
        "",
        "## Summary Metrics",
        f"- count: {_fmt(summary.get('count'))}",
        f"- evidence_status: {_fmt(summary.get('evidence_status'))}",
        f"- horizontal_rmse_m: {_fmt(summary.get('horizontal_rmse_m'))}",
        f"- horizontal_p95_m: {_fmt(summary.get('horizontal_p95_m'))}",
        f"- horizontal_max_m: {_fmt(summary.get('horizontal_max_m'))}",
        f"- up_rmse_m: {_fmt(summary.get('up_rmse_m'))}",
        f"- roll_rmse_deg: {_fmt(summary.get('roll_rmse_deg'))}",
        f"- pitch_rmse_deg: {_fmt(summary.get('pitch_rmse_deg'))}",
        f"- yaw_rmse_deg: {_fmt(summary.get('yaw_rmse_deg'))}",
        f"- yaw_p95_deg: {_fmt(summary.get('yaw_p95_deg'))}",
        "",
        "## Benchmark Context",
        "- primary_benchmark: dual_final_v23_reference_context",
        "- dual_final_v23 horizontal_rmse_m = 0.353",
        "- dual_final_v23 up_rmse_m = 0.818",
        "- dual_final_v23 yaw_rmse_deg = 1.814",
        "- dual_final_v23 roll_rmse_deg = 1.025",
        "- dual_final_v23 pitch_rmse_deg = 1.524",
        "- context_only_single_antenna horizontal_rmse_m = 38.947",
        "- context_only_single_antenna yaw_rmse_deg = 41.375",
        "- context_only_pure_ins horizontal_rmse_m = 59240.252",
        "",
        "## Diagnostic Classification",
        f"- runtime_pass: {str(classification['runtime_pass']).lower()}",
        f"- comparable_generated: {str(classification['comparable_generated']).lower()}",
        f"- single_antenna_comparison: {classification['single_antenna_comparison']}",
        f"- final_v23_close: {str(classification['final_v23_close']).lower()}",
        f"- final_v23_oracle_level: {str(classification['final_v23_oracle_level']).lower()}",
        f"- diagnostic_comparable: {str(classification['diagnostic_comparable']).lower()}",
        "",
        "## Claim Boundary",
        "- trace_solver_input: false",
        "- trace_used_for_alignment: false",
        "- trace_used_for_tuning: false",
        "- trace_evaluation_only: true",
        "- clock_sync_claim: false",
        "- physical_time_offset_claim: false",
        "- event_normalized_time_axis: true",
        "- output_only_correction: false",
        "- bad_epoch_deletion_for_metric: false",
        "- raw_doppler_claim: false",
        "- go2_prior_claim: false",
        "- source_aware_weighting_claim: false",
        "- fgo_smoother_claim: false",
        "- final_v23_reference_context_only: true",
        "",
        "## Runtime Manifest Check",
        f"- phase: {_fmt(run_manifest.get('phase'))}",
        f"- algorithm_name: {_fmt(run_manifest.get('algorithm_name'))}",
        f"- selected_receiver_source: {_fmt(trial_manifest_data.get('selected_receiver_source'))}",
        f"- body_imu_source: {_fmt(run_manifest.get('body_imu_source'))}",
        f"- receiver_imu_as_body_imu: {_fmt(run_manifest.get('receiver_imu_as_body_imu'))}",
        f"- imu_propagation_mode: {_fmt(run_manifest.get('imu_propagation_mode', trial_manifest_data.get('imu_propagation_mode')))}",
        f"- heading_offset_mode: {_fmt(run_manifest.get('heading_offset_mode', trial_manifest_data.get('heading_offset_mode')))}",
        "",
        "## Time Policy",
        "- hardware_clock_sync: false",
        "- time_axis: event_normalized_algo_time_sec",
        f"- go2_time_domain: {_fmt(event_report.get('go2_time_domain'))}",
        f"- gnss_time_domain: {_fmt(event_report.get('gnss_time_domain'))}",
        f"- go2_formal_start_raw_time: {_fmt(event_report.get('go2_formal_start_raw_time'))}",
        f"- gnss_formal_start_raw_time: {_fmt(event_report.get('gnss_formal_start_raw_time'))}",
        f"- end_algo_time_sec: {_fmt(event_report.get('end_algo_time_sec'))}",
        "- physical_time_offset_claim: false",
        "- trace evaluation-only: true",
        "",
        "## Unitree IMU Semantics",
        f"- quaternion_order: {_fmt(imu_report.get('quaternion_order'))}",
        f"- quaternion_rpy_consistency_status: {_fmt(imu_report.get('quaternion_rpy_consistency_status'))}",
        f"- accel_contains_gravity: {_fmt(imu_report.get('accel_contains_gravity'))}",
        f"- go2_body_frame: {_fmt(imu_report.get('go2_body_frame'))}",
        "- raw accelerometer direct dvel: deprecated diagnostic only",
        "",
        "## Heading Mounting",
        "- mounting: transverse_dual_antenna",
        "- receiver rel_pos heading: antenna baseline heading",
        "- body heading candidates: no_offset, plus90, minus90",
        f"- heading_offset_mode: {_fmt(trial_manifest_data.get('heading_offset_mode'))}",
        f"- formal_heading_offset_selected: {_fmt(heading_report.get('formal_heading_offset_selected', False))}",
        "",
        "## Target Gate",
        f"- target_gate_pass: {_fmt(gate_report.get('target_gate_pass'))}",
        f"- ready_for_factor_stacking: {_fmt(gate_report.get('ready_for_factor_stacking'))}",
        f"- horizontal_gate_m: {_fmt(gate_report.get('gates', {}).get('horizontal_rmse_m'))}",
        f"- up_gate_m: {_fmt(gate_report.get('gates', {}).get('up_rmse_m'))}",
        f"- yaw_gate_deg: {_fmt(gate_report.get('gates', {}).get('yaw_rmse_deg'))}",
        f"- roll_pitch_strict_gate_deg: 1.0",
        f"- roll_pitch_relaxed_gate_deg: 1.6",
        "",
        "## Gap Screen",
        f"- possible_time_domain_issue: {_fmt(gap_screen.get('possible_time_domain_issue'))}",
        f"- possible_imu_semantics_issue: {_fmt(gap_screen.get('possible_imu_semantics_issue'))}",
        f"- possible_heading_mounting_issue: {_fmt(gap_screen.get('possible_heading_mounting_issue'))}",
        f"- possible_full_mechanization_missing_issue: {_fmt(gap_screen.get('possible_full_mechanization_missing_issue'))}",
        f"- severe_horizontal_error: {_fmt(gap_screen.get('severe_horizontal_error'))}",
        f"- severe_vertical_error: {_fmt(gap_screen.get('severe_vertical_error'))}",
        f"- severe_yaw_error: {_fmt(gap_screen.get('severe_yaw_error'))}",
        f"- recommended_next_stage: {_fmt(gap_screen.get('recommended_next_stage'))}",
        "",
        "## Interpretation",
        "- This report is diagnostic-only and records whether the current filter core can run on BY2 real-data inputs.",
        "- Trace is used only by the evaluator to compute error_series and summary metrics.",
        "- The benchmark values are context for distance-to-baseline discussion, not tuning targets.",
    ]

    if summary.get("horizontal_rmse_m") is None or summary.get("yaw_rmse_deg") is None:
        lines.append("- Alignment is insufficient, so distance-to-baseline is not numerically judged.")
    else:
        h_gap = float(summary["horizontal_rmse_m"]) - FINAL_V23_CONTEXT["dual_final_v23"][
            "horizontal_rmse_m"
        ]
        yaw_gap = float(summary["yaw_rmse_deg"]) - FINAL_V23_CONTEXT["dual_final_v23"][
            "yaw_rmse_deg"
        ]
        if math.isfinite(h_gap) and math.isfinite(yaw_gap):
            lines.append(
                f"- distance_to_dual_final_v23_context: horizontal_gap_m={h_gap:.6f}, yaw_gap_deg={yaw_gap:.6f}"
            )

    lines.extend(
        [
            "",
            "## Diagnostic Gap Screen",
            f"- time_alignment_sufficient_for_evaluation: {str(classification['comparable_generated']).lower()}",
            f"- runtime_data_source_available: {str(classification['runtime_pass']).lower()}",
        ]
    )
    if not classification["comparable_generated"]:
        lines.append("- primary_gap_candidate: time_alignment_or_missing_reference_overlap")
    elif classification["single_antenna_comparison"] == "single_antenna_better_than_legsa":
        lines.append(
            "- primary_gap_candidate: current_filter_core_mechanization_heading_position_or_frame_consistency"
        )
    else:
        lines.append("- primary_gap_candidate: still_requires_manual_review_before_any_stronger_claim")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return classification
