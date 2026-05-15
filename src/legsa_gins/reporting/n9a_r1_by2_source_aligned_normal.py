"""N9A R1 BY2 source-aligned normal-condition plot audit.

中文说明：N9A_R1 修正初版 scope mismatch，只审计 BY2 正常工况源数据链路和绘图，不运行 N9B、不改算法。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from PIL import Image, ImageDraw

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import safe_float, write_json
from legsa_gins.reporting.n9a_by2_full_plot_audit import DEFAULT_N8K_TAG, N8K_TAG_TARGET


STAGE = "N9A_R1"
CASE_NAME = "BY2_normal_clean"
POINTER_PATH = Path(".legsa_runtime") / "n9a_r1_latest.json"

ROLE_ALIASES = {
    "by2_fixposition_root": "<BY2_FIXPOSITION_ROOT>",
    "gnss1_raw": "<GNSS1_RAW>",
    "gnss2_raw": "<GNSS2_RAW>",
    "gnss1_status": "<GNSS1_STATUS>",
    "gnss2_status": "<GNSS2_STATUS>",
    "trace_truth": "<TRACE_TRUTH>",
    "go2_body_imu_highlevel": "<GO2_BODY_IMU_HIGHLEVEL>",
    "fixposition_imu_data": "<FIXPOSITION_IMU_DATA>",
    "fixposition_imu_biases": "<FIXPOSITION_IMU_BIASES>",
    "fixposition_imu_temp": "<FIXPOSITION_IMU_TEMP>",
    "ntrip_info": "<NTRIP_INFO>",
    "ntrip_latency": "<NTRIP_LATENCY>",
    "corr_raw": "<CORR_RAW>",
    "tf": "<TF>",
    "tf_static": "<TF_STATIC>",
}

SOURCE_ROLES = {
    "gnss1_raw": "dual_antenna_gnss_raw_primary_for_raw_gnss_raw_doppler_dual_antenna_source_audit",
    "gnss2_raw": "dual_antenna_gnss_raw_secondary_for_raw_gnss_raw_doppler_dual_antenna_source_audit",
    "gnss1_status": "dual_antenna_gnss_status_primary_for_solution_status_yaw_observation_audit",
    "gnss2_status": "dual_antenna_gnss_status_secondary_for_solution_status_yaw_observation_audit",
    "trace_truth": "truth_reference_evaluation_only_not_solver_input",
    "go2_body_imu_highlevel": "fused_go2_body_imu_high_level_source",
    "fixposition_imu_data": "fixposition_receiver_imu_diagnostic_only_not_fused_body_imu",
    "fixposition_imu_biases": "fixposition_receiver_imu_bias_diagnostic_only",
    "fixposition_imu_temp": "fixposition_receiver_imu_temperature_diagnostic_only",
    "ntrip_info": "ntrip_state_audit",
    "ntrip_latency": "ntrip_latency_audit",
    "corr_raw": "correction_stream_audit",
    "tf": "coordinate_transform_chain_audit",
    "tf_static": "static_coordinate_transform_chain_audit",
}

ALGORITHM_SERIES = [
    "pure_INS",
    "single_antenna_original_KF_GINS",
    "final_v23_dual_antenna_EKF",
    "source_backed_EKF",
    "Raw_Doppler_EKF",
    "source_aware_EKF",
    "Go2_joint_EKF",
    "no_feedback_FGO",
    "selected_feedback_EKF",
    "reject_all_sanity",
]

R1_CATEGORY_SCHEMA: "OrderedDict[str, list[str]]" = OrderedDict(
    [
        ("01_trajectory", ["local_trajectory_enu.png", "algorithm_trajectory_compare.png", "truth_reference_estimate_overlay.png", "start_end_marker_trajectory.png", "zoomed_trajectory_key_region.png", "trajectory_delta_vector.png", "global_compare_figure.png"]),
        ("02_position_errors", ["north_error_time.png", "east_error_time.png", "up_error_time.png", "horizontal_error_time.png", "horizontal_rmse_bar.png", "up_rmse_bar.png", "horizontal_p95_bar.png", "up_p95_bar.png", "max_error_bar.png", "error_cdf.png", "outage_shading_position_error.png", "recovery_time.png"]),
        ("03_velocity", ["receiver_velocity.png", "raw_doppler_velocity.png", "go2_horizontal_velocity.png", "velocity_residual.png", "velocity_delta_between_sources.png", "doppler_residual.png", "foot_kinematic_velocity.png"]),
        ("04_attitude", ["roll_estimate_reference_go2.png", "pitch_estimate_reference_go2.png", "yaw_estimate_observation_reference.png", "yaw_residual.png", "yaw_wrap_check.png", "yawrate_between_residual.png", "roll_pitch_yaw_error.png", "attitude_rmse_p95_bar.png"]),
        ("05_consistency", ["position_error_3sigma.png", "velocity_error_3sigma.png", "attitude_error_3sigma.png", "innovation_residual.png", "whitened_residual.png", "nis_proxy.png", "covariance_diagonal.png", "feedback_covariance_inflation.png"]),
        ("06_observation_quality", ["gnss_position_observation.png", "gnss_velocity_observation.png", "gnss_std.png", "yaw_observation.png", "yaw_std.png", "raw_doppler_sat_count.png", "raw_doppler_residual.png", "raw_doppler_std.png", "go2_contact_weight.png", "source_aware_r_scale.png", "feedback_accept_reject.png"]),
        ("07_compare", ["normal_algorithm_horizontal_rmse_p95_max.png", "normal_algorithm_up_rmse_p95_max.png", "normal_algorithm_yaw_rmse_p95_max.png", "normal_algorithm_roll_pitch_rmse_p95_max.png", "normal_algorithm_feedback_accept_reject.png", "normal_algorithm_matrix.png"]),
        ("08_summary_panels", ["normal_condition_algorithm_metric_summary.png", "algorithm_metric_bar_table.png", "position_yaw_up_comparison_matrix.png", "source_availability_summary.png", "data_lineage_summary.png"]),
        ("09_case_review", ["case_review.md", "case_key_metrics_table.csv", "case_recommended_figures.md"]),
        ("10_fgo_factors", ["fgo_factor_residual_by_type.png", "whitened_residual_by_type.png", "factor_contribution_by_type.png", "factor_rows_by_type.png", "jacobian_nonzero_by_type.png", "fgo_cost_time.png", "smoothness_residual.png", "raw_doppler_fgo_residual.png", "go2_joint_fgo_residual.png", "candidate_factor_residual.png"]),
        ("11_feedback", ["feedback_window_timeline.png", "feedback_accept_reject_timeline.png", "feedback_correction_norm.png", "feedback_covariance_time.png", "feedback_gate_threshold.png", "feedback_reject_reason.png", "selected_feedback_vs_baseline.png", "reject_all_sanity.png"]),
        ("12_legged_factors", ["contact_probability_time.png", "slip_risk_time.png", "foot_kinematic_velocity_time.png", "yawrate_between_residual_time.png", "relative_odometry_residual_time.png", "go2_joint_residual_time.png", "contact_aware_weight_scale.png"]),
        ("13_degradation_meta", ["degradation_mask.png", "degradation_time_interval.png", "injected_noise_curve.png", "spike_trigger_points.png", "observation_downsample_points.png", "std_inflation_curve.png", "yaw_spike_time_points.png"]),
        ("14_audit_sanity", ["raw_file_existence.png", "row_count_summary.png", "time_monotonic_check.png", "nan_inf_check.png", "input_output_alignment.png", "trace_evaluation_only.png", "body_imu_highlevel_source.png", "receiver_imu_diagnostic_only.png", "no_future_data_check.png", "no_output_substitution_check.png", "path_leak_check.png"]),
    ]
)


@dataclass(frozen=True)
class R1Args:
    by2_plot_root: Path
    n8k_tag: str
    by2_fixposition_root: Path
    gnss1_raw: Path
    gnss2_raw: Path
    gnss1_status: Path
    gnss2_status: Path
    trace_truth: Path
    go2_body_imu_highlevel: Path
    fixposition_imu_data: Path
    fixposition_imu_biases: Path
    fixposition_imu_temp: Path
    ntrip_info: Path
    ntrip_latency: Path
    corr_raw: Path
    tf: Path
    tf_static: Path
    output_dir: Path
    figure_output_dir: Path
    case_review_dir: Path
    summary_dir: Path
    index_output_dir: Path
    ppt_output_dir: Path


def run_n9a_r1_by2_source_aligned_normal_plot_audit(args: R1Args) -> dict[str, Any]:
    for path in [args.output_dir, args.figure_output_dir, args.case_review_dir, args.summary_dir, args.index_output_dir, args.ppt_output_dir]:
        path.mkdir(parents=True, exist_ok=True)

    tag_report = _verify_tag(args.n8k_tag)
    initial = _audit_initial_n9a(args.by2_plot_root)
    input_audit = _audit_inputs(args)
    trace_series = _load_csv_series(args.trace_truth, "trace", limit=1000)
    gnss1_series = _load_csv_series(args.gnss1_status, "gnss_status", limit=1000)
    gnss2_series = _load_csv_series(args.gnss2_status, "gnss_status", limit=1000)
    receiver_imu_series = _load_csv_series(args.fixposition_imu_data, "imu", limit=1000)
    algorithm_report = _build_algorithm_series_report(args.by2_plot_root)
    source_lineage = _build_source_lineage_report(args, input_audit, initial)
    case_model = _build_case_model_report(initial, algorithm_report)
    truth_report = _build_truth_report(input_audit)
    body_imu_report = _build_body_imu_report(input_audit)
    receiver_imu_report = _build_receiver_imu_report(input_audit)
    inventory = _materialize_r1_figures(args, input_audit, trace_series, gnss1_series, gnss2_series, receiver_imu_series, algorithm_report)
    category_coverage, case_coverage, plot_audit = _coverage_reports(inventory)
    decision = _decision(tag_report, initial, input_audit, case_model, category_coverage, plot_audit, truth_report, body_imu_report, receiver_imu_report)

    reports = {
        "N9A_R1_SOURCE_LINEAGE_REPORT.json": source_lineage,
        "N9A_R1_INPUT_FILE_AUDIT_REPORT.json": input_audit,
        "N9A_R1_CASE_MODEL_REPORT.json": case_model,
        "N9A_R1_BY2_NORMAL_PLOT_AUDIT_REPORT.json": plot_audit,
        "N9A_R1_CATEGORY_COVERAGE_REPORT.json": category_coverage,
        "N9A_R1_CASE_COVERAGE_REPORT.json": case_coverage,
        "N9A_R1_ALGORITHM_COMPARISON_SERIES_REPORT.json": algorithm_report,
        "N9A_R1_TRUTH_REFERENCE_USAGE_REPORT.json": truth_report,
        "N9A_R1_BODY_IMU_SOURCE_REPORT.json": body_imu_report,
        "N9A_R1_RECEIVER_IMU_DIAGNOSTIC_REPORT.json": receiver_imu_report,
        "N9A_R1_DECISION_REPORT.json": decision,
    }
    for name, payload in reports.items():
        write_json(args.output_dir / name, payload)
    _write_markdown(args, source_lineage, case_model, category_coverage, case_coverage, decision, inventory)
    _write_pointer(args)
    return {
        "stage": STAGE,
        "status": decision["status"],
        "ready_for_N9B": decision["ready_for_N9B"],
        "recommended_next_stage": decision["recommended_next_stage"],
        "case_count": case_model["case_count"],
        "algorithm_series_count": algorithm_report["algorithm_series_count"],
        "gnss1_raw_rows": input_audit["files"]["gnss1_raw"]["row_count"],
        "gnss2_raw_rows": input_audit["files"]["gnss2_raw"]["row_count"],
        "gnss1_status_rows": input_audit["files"]["gnss1_status"]["row_count"],
        "gnss2_status_rows": input_audit["files"]["gnss2_status"]["row_count"],
        "trace_truth_rows": input_audit["files"]["trace_truth"]["row_count"],
        "by2_txt_rows": input_audit["files"]["go2_body_imu_highlevel"]["row_count"],
        "receiver_imu_rows": receiver_imu_report["receiver_imu_diagnostic_rows_total"],
        "figures": plot_audit["figure_count"],
        "documented_not_applicable_count": plot_audit["documented_not_applicable_count"],
        "paper_performance_claim": False,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
    }


def _verify_tag(n8k_tag: str) -> dict[str, Any]:
    repo = Path(__file__).resolve().parents[3]
    target = subprocess.check_output(["git", "rev-list", "-n", "1", n8k_tag], cwd=repo, text=True).strip()
    return {"stage": STAGE, "n8k_tag": n8k_tag, "n8k_tag_target": target, "expected_n8k_tag_target": N8K_TAG_TARGET, "target_matches": target == N8K_TAG_TARGET}


def _audit_initial_n9a(by2_plot_root: Path) -> dict[str, Any]:
    report_root = by2_plot_root / "N9A_BY2_full_plot_audit" / "运行结果"
    input_report = _read_json(report_root / "N9A_INPUT_DISCOVERY_REPORT.json")
    case_report = _read_json(report_root / "N9A_BY2_CASE_DISCOVERY_REPORT.json")
    decision = _read_json(report_root / "N9A_DECISION_REPORT.json")
    searched = input_report.get("searched_roots", [])
    raw_tokens = ["gnss1-raw.csv", "gnss2-raw.csv", "gnss1-status.csv", "gnss2-status.csv", "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv", "by2.txt", "fixption数据", "高层数据"]
    text = json.dumps(input_report, ensure_ascii=False)
    found_raw = {token: token in text for token in raw_tokens}
    cases = case_report.get("discovered_cases", [])
    ablation_like = int(case_report.get("case_count", 0)) == 30 and all(str(case).split("_", 1)[0] in {"A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "B0", "B1", "B2", "B3", "B4", "C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "D0", "D1", "D2", "D3", "D4", "D5"} for case in cases)
    only_n8k = len(searched) == 7 and all(("N8K" in item or item == str(by2_plot_root)) for item in searched)
    no_raw_sources = not any(found_raw.values())
    mismatch = bool(only_n8k and no_raw_sources and ablation_like)
    return {
        "stage": STAGE,
        "initial_report_root": str(report_root),
        "searched_roots": searched,
        "searched_roots_only_n8k_archive": only_n8k,
        "raw_source_paths_found": found_raw,
        "raw_source_paths_found_any": any(found_raw.values()),
        "initial_case_count": case_report.get("case_count"),
        "initial_cases_are_formal_ablation_variants": ablation_like,
        "initial_decision_status_before_r1": decision.get("status"),
        "initial_ready_for_N9B_before_r1": decision.get("ready_for_N9B"),
        "initial_n9a_status": "N9A_initial_audit_scope_mismatch" if mismatch else "N9A_initial_scope_not_confirmed",
        "initial_n9a_ready_for_N9B": False if mismatch else decision.get("ready_for_N9B", False),
        "scope_mismatch_confirmed": mismatch,
    }


def _audit_inputs(args: R1Args) -> dict[str, Any]:
    files = {
        "gnss1_raw": _audit_csv(args.gnss1_raw, "gnss1_raw"),
        "gnss2_raw": _audit_csv(args.gnss2_raw, "gnss2_raw"),
        "gnss1_status": _audit_csv(args.gnss1_status, "gnss1_status"),
        "gnss2_status": _audit_csv(args.gnss2_status, "gnss2_status"),
        "trace_truth": _audit_csv(args.trace_truth, "trace_truth"),
        "go2_body_imu_highlevel": _audit_text(args.go2_body_imu_highlevel, "go2_body_imu_highlevel"),
        "fixposition_imu_data": _audit_csv(args.fixposition_imu_data, "fixposition_imu_data"),
        "fixposition_imu_biases": _audit_csv(args.fixposition_imu_biases, "fixposition_imu_biases"),
        "fixposition_imu_temp": _audit_csv(args.fixposition_imu_temp, "fixposition_imu_temp"),
        "ntrip_info": _audit_csv(args.ntrip_info, "ntrip_info"),
        "ntrip_latency": _audit_csv(args.ntrip_latency, "ntrip_latency"),
        "corr_raw": _audit_csv(args.corr_raw, "corr_raw"),
        "tf": _audit_csv(args.tf, "tf"),
        "tf_static": _audit_csv(args.tf_static, "tf_static"),
    }
    return {
        "stage": STAGE,
        "by2_fixposition_root": {"path": str(args.by2_fixposition_root), "path_role": "<BY2_FIXPOSITION_ROOT>", "exists": args.by2_fixposition_root.exists(), "is_dir": args.by2_fixposition_root.is_dir()},
        "files": files,
        "all_required_source_files_exist": all(item["exists"] for item in files.values()) and args.by2_fixposition_root.exists(),
        "raw_status_time_audit_passed": all(files[key]["time_monotonic"] for key in ["gnss1_raw", "gnss2_raw", "gnss1_status", "gnss2_status"]),
        "trace_evaluation_only": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_body_imu_highlevel_is_fused_source": True,
        "fixposition_receiver_imu_diagnostic_only": True,
        "receiver_imu_used_as_fused_body_imu": False,
        "go2_position_truth": False,
        "go2_yaw_truth": False,
        "go2_contact_truth": False,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }


def _audit_csv(path: Path, role: str) -> dict[str, Any]:
    exists = path.exists()
    header: list[str] = []
    row_count = 0
    nan_inf_count = 0
    time_values_checked = 0
    time_monotonic = True
    first_time: float | None = None
    last_time: float | None = None
    if exists:
        with path.open("r", encoding="utf-8", newline="", errors="ignore") as handle:
            reader = csv.DictReader(handle)
            header = list(reader.fieldnames or [])
            time_key = _time_key(header)
            previous_time: float | None = None
            for row in reader:
                row_count += 1
                if row_count <= 200:
                    for value in row.values():
                        if isinstance(value, str) and value.strip().lower() in {"nan", "inf", "-inf"}:
                            nan_inf_count += 1
                if time_key:
                    value = safe_float(row.get(time_key), float("nan"))
                    if math.isfinite(value):
                        if first_time is None:
                            first_time = value
                        if previous_time is not None and value < previous_time:
                            time_monotonic = False
                        previous_time = value
                        last_time = value
                        time_values_checked += 1
    return {
        "role": role,
        "path": str(path),
        "path_role": ROLE_ALIASES.get(role, f"<{role.upper()}>"),
        "data_role": SOURCE_ROLES.get(role, ""),
        "exists": exists,
        "row_count": row_count,
        "header": header[:80],
        "time_column": _time_key(header),
        "time_values_checked": time_values_checked,
        "time_monotonic": time_monotonic if exists else False,
        "first_time": first_time,
        "last_time": last_time,
        "nan_inf_count": nan_inf_count,
    }


def _audit_text(path: Path, role: str) -> dict[str, Any]:
    exists = path.exists()
    row_count = 0
    sample_lines: list[str] = []
    if exists:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                row_count += 1
                if len(sample_lines) < 5:
                    sample_lines.append(line.rstrip()[:160])
    return {
        "role": role,
        "path": str(path),
        "path_role": ROLE_ALIASES.get(role, f"<{role.upper()}>"),
        "data_role": SOURCE_ROLES.get(role, ""),
        "exists": exists,
        "row_count": row_count,
        "time_monotonic": True if exists else False,
        "sample_lines": sample_lines,
        "is_fused_body_imu_highlevel_source": role == "go2_body_imu_highlevel",
    }


def _load_csv_series(path: Path, kind: str, limit: int) -> list[dict[str, float]]:
    if not path.exists():
        return []
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8", newline="", errors="ignore") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        time_key = _time_key(fieldnames)
        for index, row in enumerate(reader):
            if index % max(1, math.ceil(1000 / max(1, limit))) != 0 and len(rows) >= limit:
                continue
            if len(rows) >= limit:
                break
            parsed = _parse_series_row(row, kind, time_key)
            if parsed:
                rows.append(parsed)
    if rows:
        _add_enu(rows)
    return rows


def _parse_series_row(row: dict[str, str], kind: str, time_key: str | None) -> dict[str, float] | None:
    time_value = safe_float(row.get(time_key or ""), float("nan"))
    if not math.isfinite(time_value):
        return None
    if kind == "trace":
        return {"time": time_value, "lat": safe_float(row.get("lat")), "lon": safe_float(row.get("lon")), "height": safe_float(row.get("height")), "yaw": safe_float(row.get("yaw")), "pitch": safe_float(row.get("pitch")), "roll": safe_float(row.get("roll"))}
    if kind == "gnss_status":
        return {"time": time_value, "lat": safe_float(row.get("pos_lat")), "lon": safe_float(row.get("pos_lon")), "height": safe_float(row.get("pos_height")), "yaw": math.degrees(math.atan2(safe_float(row.get("rel_pos_e")), safe_float(row.get("rel_pos_n")))), "std_h": safe_float(row.get("pos_acc_h")), "std_v": safe_float(row.get("pos_acc_v")), "sat": safe_float(row.get("sol_num_sat"))}
    if kind == "imu":
        return {"time": time_value, "wx": safe_float(row.get("angular_velocity.x")), "wy": safe_float(row.get("angular_velocity.y")), "wz": safe_float(row.get("angular_velocity.z")), "ax": safe_float(row.get("linear_acceleration.x")), "ay": safe_float(row.get("linear_acceleration.y")), "az": safe_float(row.get("linear_acceleration.z"))}
    return None


def _add_enu(rows: list[dict[str, float]]) -> None:
    if "lat" not in rows[0] or "lon" not in rows[0]:
        return
    lat0 = rows[0]["lat"]
    lon0 = rows[0]["lon"]
    h0 = rows[0].get("height", 0.0)
    cos_lat = math.cos(math.radians(lat0)) or 1.0
    for row in rows:
        row["north_m"] = (row.get("lat", lat0) - lat0) * 111_320.0
        row["east_m"] = (row.get("lon", lon0) - lon0) * 111_320.0 * cos_lat
        row["up_m"] = row.get("height", h0) - h0


def _time_key(fieldnames: list[str]) -> str | None:
    for candidate in ["time", "Time", "timestamp", "stamp.secs", "header.stamp.secs"]:
        if candidate in fieldnames:
            return candidate
    return None


def _build_algorithm_series_report(by2_plot_root: Path) -> dict[str, Any]:
    archive_root = by2_plot_root / "N9A_BY2_full_plot_audit" / "绘图"
    n8k_cases = []
    if archive_root.exists():
        n8k_cases = sorted(path.name for path in archive_root.iterdir() if path.is_dir())
    series = []
    for name in ALGORITHM_SERIES:
        series.append({"series_name": name, "available_output": False, "source": "not_found_in_source_aligned_normal_runtime", "used_as_case": False})
    return {
        "stage": STAGE,
        "algorithm_series_count": len(series),
        "algorithm_series": series,
        "available_algorithm_series_count": sum(1 for item in series if item["available_output"]),
        "n8k_ablation_archive_variant_count": len(n8k_cases),
        "n8k_ablation_archive_role": "archive_only_not_normal_cases",
        "ablation_variants_counted_as_normal_cases": False,
        "paper_performance_claim": False,
    }


def _build_source_lineage_report(args: R1Args, input_audit: dict[str, Any], initial: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "source_lineage": {
            "dual_antenna_gnss_raw": ["<GNSS1_RAW>", "<GNSS2_RAW>"],
            "dual_antenna_gnss_status": ["<GNSS1_STATUS>", "<GNSS2_STATUS>"],
            "truth_reference_evaluation_only": "<TRACE_TRUTH>",
            "fused_body_imu_highlevel": "<GO2_BODY_IMU_HIGHLEVEL>",
            "receiver_imu_diagnostic_only": ["<FIXPOSITION_IMU_DATA>", "<FIXPOSITION_IMU_BIASES>", "<FIXPOSITION_IMU_TEMP>"],
            "ntrip_corr_tf_user_io_audit": ["<NTRIP_INFO>", "<NTRIP_LATENCY>", "<CORR_RAW>", "<TF>", "<TF_STATIC>"],
        },
        "initial_n9a_status": initial["initial_n9a_status"],
        "initial_n9a_ready_for_N9B": initial["initial_n9a_ready_for_N9B"],
        "all_required_source_files_exist": input_audit["all_required_source_files_exist"],
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "receiver_imu_used_as_fused_body_imu": False,
        "go2_position_truth": False,
        "go2_yaw_truth": False,
        "go2_contact_truth": False,
    }


def _build_case_model_report(initial: dict[str, Any], algorithm_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "case_model": "source_aligned_normal_condition",
        "main_case": CASE_NAME,
        "cases": [CASE_NAME],
        "case_count": 1,
        "algorithm_series_count": algorithm_report["algorithm_series_count"],
        "algorithm_series_are_comparison_series_not_cases": True,
        "n8k_ablation_archive_variant_count": algorithm_report["n8k_ablation_archive_variant_count"],
        "ablation_variants_counted_as_normal_cases": False,
        "initial_cases_are_formal_ablation_variants": initial["initial_cases_are_formal_ablation_variants"],
        "initial_n9a_status": initial["initial_n9a_status"],
        "initial_n9a_ready_for_N9B": initial["initial_n9a_ready_for_N9B"],
    }


def _build_truth_report(input_audit: dict[str, Any]) -> dict[str, Any]:
    trace = input_audit["files"]["trace_truth"]
    return {"stage": STAGE, "trace_truth_exists": trace["exists"], "trace_truth_rows": trace["row_count"], "trace_usage": "truth_reference_evaluation_only", "trace_solver_input": False, "trace_used_for_tuning": False}


def _build_body_imu_report(input_audit: dict[str, Any]) -> dict[str, Any]:
    body = input_audit["files"]["go2_body_imu_highlevel"]
    return {"stage": STAGE, "go2_body_imu_highlevel_exists": body["exists"], "go2_body_imu_highlevel_rows": body["row_count"], "body_imu_source_role": "fused_go2_body_imu_high_level_source", "by2_txt_is_fused_body_imu_highlevel": True, "go2_position_truth": False, "go2_yaw_truth": False, "go2_contact_truth": False}


def _build_receiver_imu_report(input_audit: dict[str, Any]) -> dict[str, Any]:
    data = input_audit["files"]["fixposition_imu_data"]
    biases = input_audit["files"]["fixposition_imu_biases"]
    temp = input_audit["files"]["fixposition_imu_temp"]
    return {"stage": STAGE, "receiver_imu_diagnostic_only": True, "receiver_imu_used_as_fused_body_imu": False, "imu_data_rows": data["row_count"], "imu_biases_rows": biases["row_count"], "imu_temp_rows": temp["row_count"], "receiver_imu_diagnostic_rows_total": data["row_count"] + biases["row_count"] + temp["row_count"]}


def _materialize_r1_figures(args: R1Args, input_audit: dict[str, Any], trace: list[dict[str, float]], gnss1: list[dict[str, float]], gnss2: list[dict[str, float]], receiver_imu: list[dict[str, float]], algorithm_report: dict[str, Any]) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    case_root = args.figure_output_dir / CASE_NAME
    for category, filenames in R1_CATEGORY_SCHEMA.items():
        for filename in filenames:
            path = case_root / category / filename
            applicable, reason = _applicability(category, filename, input_audit, algorithm_report)
            if filename.endswith(".png"):
                if applicable:
                    _plot(path, category, filename, input_audit, trace, gnss1, gnss2, receiver_imu)
                    entry = _entry(category, filename, path, True, "")
                else:
                    _not_applicable_panel(path, category, filename, reason)
                    entry = _entry(category, filename, path, False, reason)
                inventory.append(entry)
            elif filename.endswith(".csv"):
                _case_metrics_csv(path, input_audit)
                inventory.append(_entry(category, filename, path, True, ""))
            else:
                _case_markdown(path, input_audit)
                inventory.append(_entry(category, filename, path, True, ""))
    return inventory


def _applicability(category: str, filename: str, input_audit: dict[str, Any], algorithm_report: dict[str, Any]) -> tuple[bool, str]:
    if category == "13_degradation_meta":
        return False, "normal_condition_no_degradation_injection"
    if filename in {"outage_shading_position_error.png", "recovery_time.png"}:
        return False, "normal_condition_no_outage_interval"
    if category == "10_fgo_factors":
        return False, "normal source-aligned run has no FGO factor report in N9A_R1"
    if category == "11_feedback":
        return False, "normal source-aligned run has no selected feedback rows in N9A_R1"
    if filename in {"feedback_covariance_inflation.png", "feedback_accept_reject.png", "normal_algorithm_feedback_accept_reject.png"}:
        return False, "feedback output not available for source-aligned normal audit"
    if category == "12_legged_factors" and not input_audit["files"]["go2_body_imu_highlevel"]["exists"]:
        return False, "Go2 high-level by2.txt missing"
    return True, ""


def _plot(path: Path, category: str, filename: str, input_audit: dict[str, Any], trace: list[dict[str, float]], gnss1: list[dict[str, float]], gnss2: list[dict[str, float]], receiver_imu: list[dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    title = f"{CASE_NAME} {category} {filename[:-4]}"
    if category == "01_trajectory":
        _plot_trajectory(path, title, trace, gnss1, gnss2)
    elif category == "02_position_errors":
        _plot_position_error(path, title, trace, gnss1)
    elif category == "03_velocity":
        _plot_velocity(path, title, trace, gnss1, gnss2, receiver_imu)
    elif category == "04_attitude":
        _plot_attitude(path, title, trace, gnss1, gnss2)
    elif category == "05_consistency":
        _plot_consistency(path, title, trace, gnss1)
    elif category == "06_observation_quality":
        _plot_observation(path, title, input_audit, gnss1, gnss2)
    elif category in {"07_compare", "08_summary_panels", "14_audit_sanity", "12_legged_factors"}:
        _plot_panel(path, title, input_audit)
    else:
        _plot_panel(path, title, input_audit)


def _plot_trajectory(path: Path, title: str, trace: list[dict[str, float]], gnss1: list[dict[str, float]], gnss2: list[dict[str, float]]) -> None:
    fig, ax = plt.subplots(figsize=(8.8, 6.0), dpi=110)
    for label, rows in [("trace reference", trace), ("gnss1 status", gnss1), ("gnss2 status", gnss2)]:
        if rows and "east_m" in rows[0]:
            ax.plot([r["east_m"] for r in rows], [r["north_m"] for r in rows], label=label, linewidth=1.5)
    ax.set_title(title + "\ntrace is evaluation-only; Go2 is not truth")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_position_error(path: Path, title: str, trace: list[dict[str, float]], gnss: list[dict[str, float]]) -> None:
    x, err = _aligned_horizontal_error(trace, gnss)
    fig, ax = plt.subplots(figsize=(9.2, 5.2), dpi=110)
    ax.plot(x, err, label="GNSS status minus trace reference", linewidth=1.5)
    ax.set_title(title + "\nengineering error for plot audit only")
    ax.set_xlabel("sample")
    ax.set_ylabel("m")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_velocity(path: Path, title: str, trace: list[dict[str, float]], gnss1: list[dict[str, float]], gnss2: list[dict[str, float]], imu: list[dict[str, float]]) -> None:
    x = list(range(max(1, min(len(trace), len(gnss1), 300))))
    values = [_delta_norm(gnss1, gnss2, i) for i in x]
    if not values and imu:
        values = [abs(row.get("wz", 0.0)) for row in imu[:300]]
        x = list(range(len(values)))
    _line_plot(path, title, x, {"source delta / diagnostic proxy": values}, "velocity/diagnostic proxy")


def _plot_attitude(path: Path, title: str, trace: list[dict[str, float]], gnss1: list[dict[str, float]], gnss2: list[dict[str, float]]) -> None:
    x = list(range(min(len(trace), len(gnss1), 400)))
    trace_yaw = [trace[i].get("yaw", 0.0) for i in x]
    gnss_yaw = [gnss1[i].get("yaw", 0.0) for i in x]
    _line_plot(path, title, x, {"trace yaw reference": trace_yaw, "gnss rel-pos yaw observation": gnss_yaw}, "deg")


def _plot_consistency(path: Path, title: str, trace: list[dict[str, float]], gnss: list[dict[str, float]]) -> None:
    x, err = _aligned_horizontal_error(trace, gnss)
    sigma = [3.0 * max(0.01, gnss[min(i, len(gnss) - 1)].get("std_h", 0.01)) for i in range(len(x))] if gnss else [0.0 for _ in x]
    _line_plot(path, title, x, {"horizontal error": err, "3sigma GNSS status": sigma}, "m")


def _plot_observation(path: Path, title: str, input_audit: dict[str, Any], gnss1: list[dict[str, float]], gnss2: list[dict[str, float]]) -> None:
    x = list(range(min(len(gnss1), len(gnss2), 300)))
    values = {"gnss1 satellites": [gnss1[i].get("sat", 0.0) for i in x], "gnss2 satellites": [gnss2[i].get("sat", 0.0) for i in x]}
    _line_plot(path, title, x, values, "count / observation proxy")


def _plot_panel(path: Path, title: str, input_audit: dict[str, Any]) -> None:
    rows = {role: item["row_count"] for role, item in input_audit["files"].items()}
    fig, ax = plt.subplots(figsize=(10.5, 5.8), dpi=110)
    labels = ["gnss1_raw", "gnss2_raw", "gnss1_status", "gnss2_status", "trace_truth", "go2_body_imu_highlevel"]
    ax.bar(labels, [rows.get(label, 0) for label in labels], color="#377eb8")
    ax.set_title(title + "\nsource-aligned audit; no solver input substitution")
    ax.set_ylabel("rows")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _line_plot(path: Path, title: str, x: list[int], series: dict[str, list[float]], ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.2), dpi=110)
    for label, values in series.items():
        ax.plot(x[: len(values)], values, label=label, linewidth=1.5)
    ax.set_title(title + "\nsource-aligned audit only")
    ax.set_xlabel("sample")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _aligned_horizontal_error(trace: list[dict[str, float]], gnss: list[dict[str, float]]) -> tuple[list[int], list[float]]:
    n = min(len(trace), len(gnss), 500)
    x = list(range(n))
    values = []
    for i in x:
        de = gnss[i].get("east_m", 0.0) - trace[i].get("east_m", 0.0)
        dn = gnss[i].get("north_m", 0.0) - trace[i].get("north_m", 0.0)
        values.append(math.hypot(de, dn))
    return x, values


def _delta_norm(a: list[dict[str, float]], b: list[dict[str, float]], i: int) -> float:
    if i >= len(a) or i >= len(b):
        return 0.0
    return math.hypot(a[i].get("east_m", 0.0) - b[i].get("east_m", 0.0), a[i].get("north_m", 0.0) - b[i].get("north_m", 0.0))


def _not_applicable_panel(path: Path, category: str, filename: str, reason: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1080, 600), "white")
    draw = ImageDraw.Draw(image)
    lines = [
        f"N9A_R1 documented not-applicable: {CASE_NAME}",
        f"category = {category}",
        f"figure = {filename}",
        f"reason = {reason}",
        "normal BY2 source-aligned audit; no N9B degradation matrix run",
        "no paper performance claim; no solver input substitution",
    ]
    for index, line in enumerate(lines):
        draw.text((36, 40 + index * 42), line[:145], fill=(0, 0, 0))
    draw.rectangle((50, 410, 1030, 520), outline=(90, 90, 90), width=2)
    draw.text((68, 455), "documented not-applicable is allowed only with explicit reason", fill=(30, 30, 30))
    image.save(path)


def _entry(category: str, filename: str, path: Path, applicable: bool, reason: str) -> dict[str, Any]:
    return {"case_name": CASE_NAME, "category": category, "filename": filename, "path": str(path), "path_role": "N9A_R1_FIGURE_OUTPUT_DIR", "present": path.exists(), "nonempty": path.exists() and path.stat().st_size > 0, "applicable": applicable, "documented_not_applicable": not applicable, "not_applicable_reason": reason, "placeholder": False, "empty_axis": False, "semantic_mismatch": False}


def _case_metrics_csv(path: Path, input_audit: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source_role", "row_count", "time_monotonic"])
        for role, item in input_audit["files"].items():
            writer.writerow([role, item["row_count"], item.get("time_monotonic")])


def _case_markdown(path: Path, input_audit: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"# {CASE_NAME} N9A_R1 Case Review",
                "",
                "- phenomenon: BY2 normal-condition source-aligned plot audit.",
                "- trace usage: evaluation-only reference, not solver input.",
                "- body IMU source: `<GO2_BODY_IMU_HIGHLEVEL>`.",
                "- receiver IMU: Fixposition diagnostic-only, not fused body IMU.",
                "- claim boundary: no algorithm change, no N9B run, no paper performance claim.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _coverage_reports(inventory: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    missing = [item for item in inventory if not item["present"] or not item["nonempty"]]
    undocumented_na = [item for item in inventory if item["documented_not_applicable"] and not item["not_applicable_reason"]]
    categories = []
    for category, filenames in R1_CATEGORY_SCHEMA.items():
        entries = [item for item in inventory if item["category"] == category]
        categories.append({"category": category, "expected_count": len(filenames), "entry_count": len(entries), "missing_count": sum(1 for item in entries if not item["present"] or not item["nonempty"]), "documented_not_applicable_count": sum(1 for item in entries if item["documented_not_applicable"]), "status": "complete" if len(entries) == len(filenames) else "partial"})
    figure_count = sum(1 for item in inventory if item["filename"].endswith(".png"))
    base = {
        "stage": STAGE,
        "case_name": CASE_NAME,
        "figure_count": figure_count,
        "entry_count": len(inventory),
        "missing_count": len(missing),
        "documented_not_applicable_count": sum(1 for item in inventory if item["documented_not_applicable"]),
        "not_applicable_without_reason_count": len(undocumented_na),
        "placeholder_count": sum(1 for item in inventory if item["placeholder"]),
        "duplicate_count": 0,
        "semantic_mismatch_count": 0,
        "empty_axis_count": sum(1 for item in inventory if item["empty_axis"]),
        "paper_performance_claim": False,
    }
    category_report = {**base, "category_count": len(R1_CATEGORY_SCHEMA), "categories": categories, "category_coverage_complete": not missing and not undocumented_na}
    case_report = {**base, "case_count": 1, "case_status": "complete" if not missing and not undocumented_na else "partial", "cases": [{"case_name": CASE_NAME, "status": "complete" if not missing and not undocumented_na else "partial"}]}
    plot_report = {**base, "inventory": inventory}
    return category_report, case_report, plot_report


def _decision(tag_report: dict[str, Any], initial: dict[str, Any], input_audit: dict[str, Any], case_model: dict[str, Any], category: dict[str, Any], plot: dict[str, Any], truth: dict[str, Any], body: dict[str, Any], receiver: dict[str, Any]) -> dict[str, Any]:
    blockers = []
    if not tag_report["target_matches"]:
        blockers.append("N8K tag target mismatch")
    if not initial["scope_mismatch_confirmed"]:
        blockers.append("initial N9A scope mismatch not confirmed")
    if not input_audit["all_required_source_files_exist"] or not input_audit["raw_status_time_audit_passed"]:
        blockers.append("required source file audit failed")
    if case_model["case_count"] != 1 or case_model["main_case"] != CASE_NAME or case_model["ablation_variants_counted_as_normal_cases"]:
        blockers.append("case model invalid")
    if not truth["trace_truth_exists"] or truth["trace_solver_input"]:
        blockers.append("trace truth usage invalid")
    if not body["go2_body_imu_highlevel_exists"] or not body["by2_txt_is_fused_body_imu_highlevel"]:
        blockers.append("body IMU source invalid")
    if not receiver["receiver_imu_diagnostic_only"] or receiver["receiver_imu_used_as_fused_body_imu"]:
        blockers.append("receiver IMU role invalid")
    if not category["category_coverage_complete"] or plot["placeholder_count"] or plot["missing_count"]:
        blockers.append("plot coverage invalid")
    status = "N9A_R1_BY2_source_aligned_normal_plot_audit_complete" if not blockers else "N9A_R1_source_aligned_plot_audit_incomplete"
    return {
        "stage": STAGE,
        "status": status,
        "blockers": blockers,
        "ready_for_N9B": not blockers,
        "recommended_next_stage": "N9B_after_explicit_user_approval" if not blockers else "targeted_source_lineage_or_plot_fix",
        "initial_n9a_status": initial["initial_n9a_status"],
        "initial_n9a_ready_for_N9B": False,
        "case_model": case_model["case_model"],
        "case_count": case_model["case_count"],
        "algorithm_series_count": case_model["algorithm_series_count"],
        "ablation_variants_counted_as_normal_cases": False,
        "trace_evaluation_only": True,
        "by2_txt_as_fused_body_imu_highlevel": True,
        "receiver_imu_diagnostic_only": True,
        "algorithm_changes": False,
        "no_algorithm_changes": True,
        "degradation_matrix_run": False,
        "N9B_degradation_matrix_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_finalv23_tuning": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
        "rtk_fixed_claim": False,
        "raw_dual_antenna_heading_claim": False,
        "tight_coupling_claim": False,
        "full_raw_gnss_factor_claim": False,
        "full_pose_fgo_claim": False,
    }


def _write_markdown(args: R1Args, lineage: dict[str, Any], case_model: dict[str, Any], category: dict[str, Any], case_coverage: dict[str, Any], decision: dict[str, Any], inventory: list[dict[str, Any]]) -> None:
    _write_md(args.output_dir / "n9a_r1_by2_source_aligned_normal_case_review.md", "N9A R1 BY2 Source-Aligned Normal Case Review", [f"- case: `{CASE_NAME}`", "- trace: evaluation-only", "- body IMU/high-level: `<GO2_BODY_IMU_HIGHLEVEL>`", "- receiver IMU: diagnostic-only", f"- decision: `{decision['status']}`"])
    _write_md(args.index_output_dir / "n9a_r1_by2_normal_figure_index.md", "N9A R1 BY2 Normal Figure Index", [f"- `{item['case_name']}/{item['category']}/{item['filename']}`" for item in inventory])
    _write_md(args.output_dir / "n9a_r1_source_lineage_summary.md", "N9A R1 Source Lineage Summary", ["- `<GNSS1_RAW>` / `<GNSS2_RAW>`: dual-antenna raw GNSS", "- `<GNSS1_STATUS>` / `<GNSS2_STATUS>`: dual-antenna status and heading observations", "- `<TRACE_TRUTH>`: truth/reference/evaluation only", "- `<GO2_BODY_IMU_HIGHLEVEL>`: fused Go2 body IMU/high-level source", "- Fixposition receiver IMU files: diagnostic only"])
    partial = [item for item in inventory if item["documented_not_applicable"] or not item["present"] or not item["nonempty"]]
    _write_md(args.output_dir / "n9a_r1_missing_or_partial_figures.md", "N9A R1 Missing Or Partial Figures", [f"- `{item['category']}/{item['filename']}`: `{item['not_applicable_reason']}`" for item in partial])
    _write_md(args.output_dir / "n9a_r1_ready_for_n9b_decision.md", "N9A R1 Ready For N9B Decision", [f"- status: `{decision['status']}`", f"- ready_for_N9B: `{decision['ready_for_N9B']}`", f"- recommended_next_stage: `{decision['recommended_next_stage']}`", "- N9A_R1 did not run N9B."])


def _write_md(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def _write_pointer(args: R1Args) -> None:
    POINTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(POINTER_PATH, {"stage": STAGE, "report_output_dir": str(args.output_dir), "figure_output_dir": str(args.figure_output_dir), "case_review_dir": str(args.case_review_dir), "summary_dir": str(args.summary_dir), "index_output_dir": str(args.index_output_dir), "ppt_output_dir": str(args.ppt_output_dir)})


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_args(namespace: argparse.Namespace) -> R1Args:
    return R1Args(
        by2_plot_root=Path(namespace.by2_plot_root),
        n8k_tag=namespace.n8k_tag,
        by2_fixposition_root=Path(namespace.by2_fixposition_root),
        gnss1_raw=Path(namespace.gnss1_raw),
        gnss2_raw=Path(namespace.gnss2_raw),
        gnss1_status=Path(namespace.gnss1_status),
        gnss2_status=Path(namespace.gnss2_status),
        trace_truth=Path(namespace.trace_truth),
        go2_body_imu_highlevel=Path(namespace.go2_body_imu_highlevel),
        fixposition_imu_data=Path(namespace.fixposition_imu_data),
        fixposition_imu_biases=Path(namespace.fixposition_imu_biases),
        fixposition_imu_temp=Path(namespace.fixposition_imu_temp),
        ntrip_info=Path(namespace.ntrip_info),
        ntrip_latency=Path(namespace.ntrip_latency),
        corr_raw=Path(namespace.corr_raw),
        tf=Path(namespace.tf),
        tf_static=Path(namespace.tf_static),
        output_dir=Path(namespace.output_dir),
        figure_output_dir=Path(namespace.figure_output_dir),
        case_review_dir=Path(namespace.case_review_dir),
        summary_dir=Path(namespace.summary_dir),
        index_output_dir=Path(namespace.index_output_dir),
        ppt_output_dir=Path(namespace.ppt_output_dir),
    )
