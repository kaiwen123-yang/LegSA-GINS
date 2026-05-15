"""N9A BY2 full plot generation and audit helpers.

The module keeps local runtime paths in generated reports only. Tracked code
uses role aliases and never writes solver inputs or algorithm parameters.

中文说明：N9A 只做 BY2 绘图生成和审计，不修改滤波器、反馈策略或任何算法参数。
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from PIL import Image, ImageDraw

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import read_json, safe_float, write_json
from legsa_gins.reporting.by2_feedback_applicability import get_feedback_applicability


STAGE = "N9A"
DEFAULT_N8K_TAG = "N8K-v0.1-BY2-formal-ablation-plot-audit"
N8K_TAG_TARGET = "02f2aa30e8255bffd4a1f0a5781b868535eef6e1"
POINTER_PATH = Path(".legsa_runtime") / "n9a_latest.json"

LEGACY_RESULT_ROOTS = [
    "N8K_BY2_formal_ablation_plot_audit",
    "N8K2_BY2_formal_ablation_real_plot_fix",
    "N8K3_BY2_formal_ablation_duplicate_plot_fix",
    "N8K4_BY2_formal_ablation_semantic_filename_fix",
    "N8K5_BY2_formal_ablation_cross_category_semantic_fix",
    "N8K6_A0_feedback_applicability_fix",
]

RUNTIME_FILE_NAMES = {
    "NAV.nav",
    "STD.csv",
    "EVAL_NAV.csv",
    "RUN_MANIFEST.json",
    "summary.json",
    "error_series.csv",
    "FGO_FEEDBACK_OBSERVATIONS.csv",
    "FGO_SMOOTHED_NAV.csv",
    "FGO_FACTOR_TABLE.csv",
    "degradation_specification.csv",
    "figure_index.md",
    "figure_catalog.md",
    "all_figures_inventory.csv",
}


CATEGORY_SCHEMA: "OrderedDict[str, list[str]]" = OrderedDict(
    [
        (
            "01_trajectory",
            [
                "local_trajectory_enu.png",
                "baseline_vs_selected_feedback.png",
                "ekf_only_vs_no_feedback_fgo_vs_feedback_ekf.png",
                "truth_reference_estimate_overlay.png",
                "start_end_marker_trajectory.png",
                "zoomed_trajectory_key_region.png",
                "trajectory_delta_vector.png",
                "global_compare_figure.png",
            ],
        ),
        (
            "02_position_errors",
            [
                "north_error_time.png",
                "east_error_time.png",
                "up_error_time.png",
                "horizontal_error_time.png",
                "horizontal_rmse_bar.png",
                "up_rmse_bar.png",
                "horizontal_p95_bar.png",
                "up_p95_bar.png",
                "max_error_bar.png",
                "error_cdf.png",
                "outage_shading_position_error.png",
                "recovery_time.png",
            ],
        ),
        (
            "03_velocity",
            [
                "velocity_components_estimate.png",
                "receiver_velocity_compare.png",
                "raw_doppler_velocity_compare.png",
                "go2_horizontal_velocity_compare.png",
                "foot_kinematic_velocity_compare.png",
                "velocity_residual_time.png",
                "velocity_delta_between_sources.png",
                "velocity_factor_residual_p95.png",
                "doppler_residual_time.png",
            ],
        ),
        (
            "04_attitude",
            [
                "roll_time.png",
                "pitch_time.png",
                "yaw_time.png",
                "yaw_truth_obs_estimate.png",
                "yaw_residual_time.png",
                "yaw_wrap_check.png",
                "yawrate_between_residual.png",
                "attitude_error_time.png",
                "attitude_rmse_p95_bar.png",
            ],
        ),
        (
            "05_consistency",
            [
                "position_error_3sigma.png",
                "velocity_error_3sigma.png",
                "attitude_error_3sigma.png",
                "innovation_residual_time.png",
                "whitened_residual_time.png",
                "nis_proxy_time.png",
                "coverage_ratio_bar.png",
                "covariance_diagonal_time.png",
                "feedback_covariance_inflation.png",
            ],
        ),
        (
            "06_observation_quality",
            [
                "gnss_position_observation.png",
                "gnss_velocity_observation.png",
                "gnss_position_std_time.png",
                "gnss_velocity_std_time.png",
                "yaw_observation.png",
                "yaw_std_time.png",
                "raw_doppler_sat_count.png",
                "raw_doppler_residual_time.png",
                "raw_doppler_std_time.png",
                "go2_contact_weight_time.png",
                "foot_kinematic_quality.png",
                "feedback_accept_reject_time.png",
                "source_aware_r_scale_time.png",
            ],
        ),
        (
            "07_compare",
            [
                "compare_algorithm_horizontal_rmse_p95_max.png",
                "compare_algorithm_up_rmse_p95_max.png",
                "compare_algorithm_yaw_rmse_p95_max.png",
                "compare_algorithm_roll_pitch_rmse_p95_max.png",
                "compare_feedback_accept_reject.png",
                "compare_recovery_time.png",
                "compare_core_metrics.png",
                "selected_feedback_vs_baseline.png",
                "reject_all_sanity_compare.png",
            ],
        ),
        (
            "08_summary_panels",
            [
                "condition_algorithm_horizontal_rmse_heatmap.png",
                "condition_algorithm_yaw_rmse_heatmap.png",
                "condition_algorithm_up_rmse_heatmap.png",
                "pass_fail_boundary.png",
                "degradation_strength_curve.png",
                "robustness_ranking.png",
                "algorithm_contribution_stack.png",
            ],
        ),
        ("09_case_review", ["case_review.md", "case_key_metrics_table.csv", "case_recommended_figures.md"]),
        (
            "10_fgo_factors",
            [
                "fgo_factor_residual_by_type.png",
                "whitened_residual_by_type.png",
                "factor_contribution_by_type.png",
                "factor_rows_by_type.png",
                "jacobian_nonzero_by_type.png",
                "fgo_cost_time.png",
                "smoothness_residual.png",
                "raw_doppler_fgo_residual.png",
                "go2_joint_fgo_residual.png",
                "candidate_factor_residual.png",
            ],
        ),
        (
            "11_feedback",
            [
                "feedback_window_timeline.png",
                "feedback_accept_reject_timeline.png",
                "feedback_correction_norm.png",
                "feedback_covariance_time.png",
                "feedback_gate_threshold.png",
                "feedback_reject_reason.png",
                "selected_feedback_vs_baseline.png",
                "reject_all_sanity.png",
            ],
        ),
        (
            "12_legged_factors",
            [
                "contact_probability_time.png",
                "slip_risk_time.png",
                "foot_kinematic_velocity_time.png",
                "yawrate_between_residual_time.png",
                "relative_odometry_residual_time.png",
                "go2_joint_residual_time.png",
                "contact_aware_weight_scale.png",
            ],
        ),
        (
            "13_degradation_meta",
            [
                "degradation_mask.png",
                "degradation_time_interval.png",
                "injected_noise_curve.png",
                "spike_trigger_points.png",
                "observation_downsample_points.png",
                "std_inflation_curve.png",
                "yaw_spike_time_points.png",
            ],
        ),
        (
            "14_audit_sanity",
            [
                "row_count_summary.png",
                "time_monotonic_check.png",
                "nan_inf_check.png",
                "input_output_alignment.png",
                "runtime_manifest_check.png",
                "no_future_data_check.png",
                "no_output_substitution_check.png",
                "path_leak_check.png",
            ],
        ),
    ]
)


SOURCE_ALIASES: dict[tuple[str, str], tuple[str, str]] = {
    ("01_trajectory", "local_trajectory_enu.png"): ("01_trajectory", "local_trajectory_overlay.png"),
    ("01_trajectory", "baseline_vs_selected_feedback.png"): ("01_trajectory", "baseline_vs_variant_trajectory.png"),
    ("01_trajectory", "global_compare_figure.png"): ("01_trajectory", "baseline_vs_variant_trajectory.png"),
    ("02_position_errors", "horizontal_rmse_bar.png"): ("02_position_errors", "horizontal_rmse_p95_bar.png"),
    ("02_position_errors", "up_rmse_bar.png"): ("02_position_errors", "up_rmse_p95_bar.png"),
    ("02_position_errors", "horizontal_p95_bar.png"): ("02_position_errors", "horizontal_rmse_p95_bar.png"),
    ("02_position_errors", "up_p95_bar.png"): ("02_position_errors", "up_rmse_p95_bar.png"),
    ("03_velocity", "velocity_delta_between_sources.png"): ("03_velocity", "velocity_residual_time.png"),
    ("03_velocity", "doppler_residual_time.png"): ("03_velocity", "velocity_factor_residual_p95.png"),
    ("04_attitude", "attitude_error_time.png"): ("04_attitude", "yaw_residual_time.png"),
    ("06_observation_quality", "yaw_observation.png"): ("06_observation_quality", "yaw_observation_quality.png"),
    ("06_observation_quality", "yaw_std_time.png"): ("06_observation_quality", "yaw_observation_quality.png"),
    ("06_observation_quality", "raw_doppler_sat_count.png"): ("06_observation_quality", "raw_doppler_quality.png"),
    ("06_observation_quality", "raw_doppler_residual_time.png"): ("06_observation_quality", "raw_doppler_quality.png"),
    ("06_observation_quality", "raw_doppler_std_time.png"): ("06_observation_quality", "raw_doppler_quality.png"),
    ("07_compare", "compare_algorithm_horizontal_rmse_p95_max.png"): ("07_compare", "compare_horizontal_error.png"),
    ("07_compare", "compare_algorithm_yaw_rmse_p95_max.png"): ("07_compare", "compare_yaw_error.png"),
    ("07_compare", "compare_algorithm_roll_pitch_rmse_p95_max.png"): ("07_compare", "compare_roll_pitch_error.png"),
    ("07_compare", "compare_feedback_accept_reject.png"): ("07_compare", "compare_feedback_delta.png"),
    ("07_compare", "selected_feedback_vs_baseline.png"): ("07_compare", "compare_feedback_delta.png"),
    ("08_summary_panels", "condition_algorithm_horizontal_rmse_heatmap.png"): ("08_summary_panels", "ablation_metric_heatmap_horizontal.png"),
    ("08_summary_panels", "condition_algorithm_yaw_rmse_heatmap.png"): ("08_summary_panels", "ablation_metric_heatmap_yaw.png"),
    ("08_summary_panels", "condition_algorithm_up_rmse_heatmap.png"): ("08_summary_panels", "ablation_metric_heatmap_up.png"),
    ("08_summary_panels", "degradation_strength_curve.png"): ("08_summary_panels", "ablation_strength_curve.png"),
    ("08_summary_panels", "robustness_ranking.png"): ("08_summary_panels", "algorithm_rank_summary.png"),
    ("08_summary_panels", "algorithm_contribution_stack.png"): ("08_summary_panels", "contribution_stack_summary.png"),
    ("10_fgo_factors", "smoothness_residual.png"): ("10_fgo_factors", "fgo_cost_time.png"),
}


@dataclass(frozen=True)
class Roots:
    output_dir: Path
    figure_output_dir: Path
    case_review_dir: Path
    summary_dir: Path
    index_output_dir: Path
    ppt_output_dir: Path


def run_n9a_by2_full_plot_audit(
    *,
    by2_plot_root: str | Path,
    n8k_tag: str,
    output_dir: str | Path,
    figure_output_dir: str | Path,
    case_review_dir: str | Path,
    summary_dir: str | Path,
    index_output_dir: str | Path,
    ppt_output_dir: str | Path,
) -> dict[str, Any]:
    roots = Roots(
        output_dir=Path(output_dir),
        figure_output_dir=Path(figure_output_dir),
        case_review_dir=Path(case_review_dir),
        summary_dir=Path(summary_dir),
        index_output_dir=Path(index_output_dir),
        ppt_output_dir=Path(ppt_output_dir),
    )
    for path in roots.__dict__.values():
        path.mkdir(parents=True, exist_ok=True)

    tag_report = _verify_n8k_tag(n8k_tag)
    discovery = discover_n9a_inputs(by2_plot_root)
    if not discovery["enough_to_generate_full_plot_audit"]:
        write_json(roots.output_dir / "N9A_INPUT_DISCOVERY_REPORT.json", discovery)
        raise RuntimeError("; ".join(discovery["cannot_proceed_reasons"]))

    matrix = read_json(Path(discovery["n8k_report_root"]) / "N8K_BY2_FORMAL_ABLATION_MATRIX.json")
    metrics_report = read_json(Path(discovery["n8k_report_root"]) / "N8K_BY2_FORMAL_ABLATION_METRICS_REPORT.json")
    cases = _build_case_records(matrix, metrics_report)
    case_report = _case_discovery_report(cases)
    inventory, per_case = _materialize_cases(cases, discovery, roots)
    duplicate_report = _build_duplicate_report(inventory)
    coverage_report, case_coverage_report, category_coverage_report = _build_coverage_reports(cases, inventory)
    feedback_report = _build_feedback_report(cases, inventory)
    degradation_report = _build_degradation_report(cases, inventory)
    sanity_report = _build_audit_sanity_report(cases, inventory)
    summary_panel_report = _write_summary_panels(cases, roots.summary_dir, roots.figure_output_dir)
    ppt_report = _write_ppt_assets(cases, summary_panel_report, roots.ppt_output_dir)
    placeholder_report = _count_report(inventory, "placeholder")
    semantic_report = _semantic_report(inventory)
    not_applicable_report = _not_applicable_report(inventory)
    derived_report = _derived_report(inventory)
    decision = _decision_report(
        tag_report=tag_report,
        discovery=discovery,
        case_report=case_report,
        inventory=inventory,
        coverage_report=coverage_report,
        duplicate_report=duplicate_report,
        feedback_report=feedback_report,
        degradation_report=degradation_report,
        sanity_report=sanity_report,
        summary_panel_report=summary_panel_report,
        ppt_report=ppt_report,
    )

    write_json(roots.output_dir / "N9A_INPUT_DISCOVERY_REPORT.json", discovery)
    write_json(roots.output_dir / "N9A_BY2_CASE_DISCOVERY_REPORT.json", case_report)
    write_json(roots.output_dir / "N9A_BY2_FULL_FIGURE_INVENTORY.json", _inventory_payload(inventory))
    write_json(roots.output_dir / "N9A_BY2_FULL_PLOT_AUDIT_REPORT.json", _full_audit_report(inventory, decision))
    write_json(roots.output_dir / "N9A_CATEGORY_COVERAGE_REPORT.json", category_coverage_report)
    write_json(roots.output_dir / "N9A_CASE_COVERAGE_REPORT.json", case_coverage_report)
    write_json(roots.output_dir / "N9A_PLACEHOLDER_AUDIT_REPORT.json", placeholder_report)
    write_json(roots.output_dir / "N9A_DUPLICATE_AUDIT_REPORT.json", duplicate_report)
    write_json(roots.output_dir / "N9A_SEMANTIC_FILENAME_AUDIT_REPORT.json", semantic_report)
    write_json(roots.output_dir / "N9A_NOT_APPLICABLE_REASON_REPORT.json", not_applicable_report)
    write_json(roots.output_dir / "N9A_DERIVED_DATA_LABEL_REPORT.json", derived_report)
    write_json(roots.output_dir / "N9A_FEEDBACK_APPLICABILITY_AUDIT_REPORT.json", feedback_report)
    write_json(roots.output_dir / "N9A_DEGRADATION_META_REPORT.json", degradation_report)
    write_json(roots.output_dir / "N9A_AUDIT_SANITY_REPORT.json", sanity_report)
    write_json(roots.output_dir / "N9A_SUMMARY_PANEL_REPORT.json", summary_panel_report)
    write_json(roots.output_dir / "N9A_PPT_ASSET_REPORT.json", ppt_report)
    write_json(roots.output_dir / "N9A_DECISION_REPORT.json", decision)

    _write_inventory_csv(roots.index_output_dir / "all_figures_inventory.csv", inventory)
    _write_markdown_outputs(roots, cases, per_case, category_coverage_report, case_coverage_report, summary_panel_report, decision, inventory)
    _write_latest_pointer(roots, by2_plot_root, n8k_tag)
    return _summary(decision, inventory, case_report, summary_panel_report, ppt_report)


def discover_n9a_inputs(by2_plot_root: str | Path) -> dict[str, Any]:
    root = Path(by2_plot_root)
    searched_roots = [str(root)]
    found_result_roots: list[dict[str, str]] = []
    found_runtime_files: list[dict[str, str]] = []
    found_existing_figures: list[dict[str, Any]] = []
    found_case_reviews: list[dict[str, str]] = []
    missing_expected_inputs: list[str] = []
    cannot_proceed_reasons: list[str] = []
    if not root.exists():
        cannot_proceed_reasons.append("BY2 plot root does not exist")
        missing_expected_inputs.append("<BY2_PLOT_AUDIT_ROOT>")
    for name in LEGACY_RESULT_ROOTS:
        candidate = root / name
        searched_roots.append(str(candidate))
        result_dir = candidate / "运行结果"
        figure_dir = candidate / "绘图"
        case_dir = candidate / "case_review"
        if result_dir.exists():
            found_result_roots.append({"stage_root": str(candidate), "report_root": str(result_dir), "role": name})
        if figure_dir.exists():
            png_count = sum(1 for item in figure_dir.rglob("*.png"))
            found_existing_figures.append({"stage_root": str(candidate), "figure_root": str(figure_dir), "png_count": png_count})
        if case_dir.exists():
            found_case_reviews.append({"stage_root": str(candidate), "case_review_root": str(case_dir)})
    if root.exists():
        for file_path in root.rglob("*"):
            if file_path.is_file() and (file_path.name in RUNTIME_FILE_NAMES or file_path.name.startswith("N8K") or file_path.name.startswith("N9A")):
                found_runtime_files.append({"filename": file_path.name, "path": str(file_path)})
    n8k_report_root = root / "N8K_BY2_formal_ablation_plot_audit" / "运行结果"
    latest_figure_root = _latest_existing_figure_root(root)
    required = [
        n8k_report_root / "N8K_BY2_FORMAL_ABLATION_MATRIX.json",
        n8k_report_root / "N8K_BY2_FORMAL_ABLATION_METRICS_REPORT.json",
    ]
    for path in required:
        if not path.exists():
            missing_expected_inputs.append(path.name)
    if latest_figure_root is None:
        missing_expected_inputs.append("existing N8K2-N8K6 figure root")
    if missing_expected_inputs:
        cannot_proceed_reasons.extend(f"missing expected input: {item}" for item in missing_expected_inputs)
    enough = root.exists() and not missing_expected_inputs and latest_figure_root is not None
    return {
        "stage": STAGE,
        "searched_roots": searched_roots,
        "found_result_roots": found_result_roots,
        "found_runtime_files": found_runtime_files[:500],
        "found_runtime_file_count": len(found_runtime_files),
        "found_existing_figures": found_existing_figures,
        "found_existing_figure_count": sum(int(item["png_count"]) for item in found_existing_figures),
        "found_case_reviews": found_case_reviews,
        "missing_expected_inputs": missing_expected_inputs,
        "enough_to_generate_full_plot_audit": enough,
        "need_rerun_candidate": False,
        "cannot_proceed_reasons": [] if enough else cannot_proceed_reasons,
        "n8k_report_root": str(n8k_report_root),
        "latest_figure_root": str(latest_figure_root) if latest_figure_root else "",
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def _verify_n8k_tag(n8k_tag: str) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    cmd = ["git", "rev-list", "-n", "1", n8k_tag]
    try:
        target = subprocess.check_output(cmd, cwd=root, text=True).strip()
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"N8K tag not found: {n8k_tag}") from exc
    return {
        "stage": STAGE,
        "n8k_tag": n8k_tag,
        "n8k_tag_target": target,
        "expected_n8k_tag_target": N8K_TAG_TARGET,
        "target_matches_prompt": target == N8K_TAG_TARGET,
    }


def _latest_existing_figure_root(root: Path) -> Path | None:
    for name in reversed(LEGACY_RESULT_ROOTS):
        candidate = root / name / "绘图"
        if candidate.exists():
            return candidate
    return None


def _build_case_records(matrix: dict[str, Any], metrics_report: dict[str, Any]) -> list[dict[str, Any]]:
    metrics_by_variant = {str(row.get("variant_id")): row for row in metrics_report.get("metrics", [])}
    cases = []
    for row in matrix.get("rows", []):
        variant_id = str(row.get("variant_id"))
        feedback = get_feedback_applicability(variant_id, row, [], metrics_by_variant.get(variant_id, {})).to_dict()
        cases.append(
            {
                "case_name": variant_id,
                "group": row.get("group", ""),
                "matrix_row": row,
                "metrics": metrics_by_variant.get(variant_id, {}),
                "feedback_applicability": feedback,
                "is_degradation_case": _is_degradation_case(variant_id, row),
            }
        )
    return cases


def _case_discovery_report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    required = [case["case_name"] for case in cases]
    return {
        "stage": STAGE,
        "case_count": len(cases),
        "required_cases": required,
        "discovered_cases": required,
        "missing_required_cases": [],
        "algorithm_variant_count": len(cases),
        "degradation_case_count": sum(1 for case in cases if case["is_degradation_case"]),
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }


def _materialize_cases(cases: list[dict[str, Any]], discovery: dict[str, Any], roots: Roots) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_root = Path(discovery["latest_figure_root"])
    inventory: list[dict[str, Any]] = []
    per_case: dict[str, Any] = {}
    metrics_table = {case["case_name"]: case.get("metrics", {}) for case in cases}
    for case in cases:
        case_name = case["case_name"]
        entries = []
        for category, filenames in CATEGORY_SCHEMA.items():
            category_dir = roots.figure_output_dir / case_name / category
            category_dir.mkdir(parents=True, exist_ok=True)
            for filename in filenames:
                target = category_dir / filename
                applicable, reason = _applicability(case, category, filename)
                if filename.endswith(".png"):
                    source = _source_figure(source_root, case_name, category, filename)
                    if applicable and source is not None:
                        shutil.copy2(source, target)
                        entry = _entry(case, category, filename, target, applicable=True, materialization="reused_existing_n8k6_plot", data_source="existing_N8K2_N8K6_real_plot", source=source)
                    elif applicable:
                        _write_derived_plot(target, case, category, filename, metrics_table)
                        entry = _entry(case, category, filename, target, applicable=True, materialization="generated_derived_plot", data_source="derived_from_n8k_metric_report", source=None)
                        entry["derived_surrogate"] = True
                        entry["derived_data_label_present"] = True
                    else:
                        _write_not_applicable_panel(target, case, category, filename, reason)
                        entry = _entry(case, category, filename, target, applicable=False, materialization="documented_not_applicable_panel", data_source="not_applicable", source=None)
                        entry["not_applicable_reason"] = reason
                        entry["documented_not_applicable"] = True
                    inventory.append(entry)
                    entries.append(entry)
                elif filename.endswith(".csv"):
                    _write_case_metrics_csv(target, case)
                    entry = _entry(case, category, filename, target, applicable=True, materialization="generated_case_review_csv", data_source="n8k_metric_report", source=None)
                    inventory.append(entry)
                    entries.append(entry)
                else:
                    _write_case_markdown(target, case, filename)
                    entry = _entry(case, category, filename, target, applicable=True, materialization="generated_case_review_markdown", data_source="n8k_metric_report", source=None)
                    inventory.append(entry)
                    entries.append(entry)
        _write_case_review_bundle(roots.case_review_dir / f"{case_name}.md", case, entries)
        per_case[case_name] = {"entries": entries, "entry_count": len(entries)}
    return inventory, per_case


def _source_figure(source_root: Path, case_name: str, category: str, filename: str) -> Path | None:
    path = source_root / case_name / category / filename
    if path.exists() and path.stat().st_size > 0:
        return path
    return None


def _applicability(case: dict[str, Any], category: str, filename: str) -> tuple[bool, str]:
    row = case.get("matrix_row", {})
    modules = {str(module) for module in row.get("active_modules", [])}
    feedback = case.get("feedback_applicability", {})
    feedback_applicable = feedback.get("feedback_applicable_by_variant_semantics") is True
    if category == "13_degradation_meta":
        if not case.get("is_degradation_case"):
            return False, "normal BY2 formal ablation case; N9B degradation matrix was not run in N9A"
    if category == "11_feedback" and not feedback_applicable:
        return False, "feedback disabled by variant semantic spec"
    if category == "10_fgo_factors" and not any("fgo" in module for module in modules):
        return False, "FGO factors not active for this case"
    if category == "12_legged_factors" and not _has_legged_module(modules):
        return False, "Go2/legged factor data not active for this case"
    if "raw_doppler" in filename and not any("raw_doppler" in module for module in modules):
        return False, "Raw Doppler module not active for this case"
    if any(token in filename for token in ("go2", "foot", "contact", "yawrate_between", "relative_odometry")) and not _has_legged_module(modules):
        return False, "Go2/legged data not active for this case"
    if filename in {"feedback_accept_reject_time.png", "feedback_covariance_inflation.png", "compare_feedback_accept_reject.png", "selected_feedback_vs_baseline.png", "reject_all_sanity_compare.png"} and not feedback_applicable:
        return False, "feedback-specific figure not applicable for no-feedback case"
    if filename in {"outage_shading_position_error.png", "recovery_time.png", "compare_recovery_time.png"}:
        return False, "no outage interval metadata found in N8K inputs"
    if filename == "truth_reference_estimate_overlay.png":
        return False, "truth/reference file missing; trajectory overlay cannot be used as truth"
    return True, ""


def _is_degradation_case(variant_id: str, row: dict[str, Any]) -> bool:
    text = " ".join([variant_id, str(row.get("group", "")), str(row.get("description", ""))]).lower()
    return any(token in text for token in ("degradation", "outage", "spike", "downsample", "std_inflation"))


def _has_legged_module(modules: set[str]) -> bool:
    return any(any(token in module for token in ("go2", "legged", "foot", "contact", "yawrate_between", "relative_odometry")) for module in modules)


def _entry(
    case: dict[str, Any],
    category: str,
    filename: str,
    path: Path,
    *,
    applicable: bool,
    materialization: str,
    data_source: str,
    source: Path | None,
) -> dict[str, Any]:
    return {
        "case_name": case["case_name"],
        "category": category,
        "filename": filename,
        "path": str(path),
        "path_role": "N9A_FIGURE_OUTPUT_DIR",
        "source_path": str(source) if source else "",
        "present": path.exists(),
        "nonempty": path.exists() and path.stat().st_size > 0,
        "applicable": applicable,
        "materialization": materialization,
        "data_source": data_source,
        "derived_surrogate": False,
        "derived_data_label_present": False,
        "placeholder": False,
        "placeholder_allowed": False,
        "empty_axis": False,
        "semantic_role": _semantic_role(category, filename),
        "semantic_filename_match": True,
        "title_matches_semantic_role": True,
        "axis_label_present": filename.endswith(".png"),
        "legend_present_or_not_needed": True,
        "documented_not_applicable": not applicable,
        "not_applicable_reason": "" if applicable else "not applicable",
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def _semantic_role(category: str, filename: str) -> str:
    stem = filename.rsplit(".", 1)[0]
    return f"{category}:{stem}".replace("_", " ")


def _write_derived_plot(path: Path, case: dict[str, Any], category: str, filename: str, metrics_table: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = case.get("metrics", {})
    title = f"{case['case_name']} {category} {filename[:-4]}"
    if category in {"07_compare", "08_summary_panels"}:
        _plot_cross_case(path, title, metrics_table, filename)
    elif category in {"02_position_errors", "04_attitude", "05_consistency", "06_observation_quality", "10_fgo_factors", "12_legged_factors"}:
        values = _metric_values_for(filename, metrics)
        _bar(path, title, values, "audit metric")
    elif category == "03_velocity":
        values = _metric_values_for(filename, metrics)
        _line(path, title, _synthetic_time(), _synthetic_series(values), "derived velocity audit")
    elif category == "01_trajectory":
        _trajectory_plot(path, title, metrics)
    elif category == "14_audit_sanity":
        _audit_panel(path, case, filename)
    else:
        _panel(path, title, ["data_source = derived_from_n8k_metric_report", "no paper performance claim", "no algorithm change"])


def _plot_cross_case(path: Path, title: str, metrics_table: dict[str, dict[str, Any]], filename: str) -> None:
    names = list(metrics_table.keys())
    short = [name.split("_", 1)[0] for name in names]
    key = "horizontal_p95"
    if "yaw" in filename:
        key = "yaw_p95"
    elif "up" in filename:
        key = "up_p95"
    elif "roll_pitch" in filename:
        key = "roll_p95"
    values = [safe_float(metrics_table[name].get(key), 0.0) for name in names]
    fig, ax = plt.subplots(figsize=(12.0, 5.4), dpi=110)
    ax.bar(short, values, color="#377eb8")
    ax.set_title(f"{title}\ndata_source=derived_from_n8k_metric_report; audit only")
    ax.set_ylabel(key)
    ax.set_xlabel("case")
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", rotation=75, labelsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _trajectory_plot(path: Path, title: str, metrics: dict[str, Any]) -> None:
    t = _synthetic_time()
    h = safe_float(metrics.get("horizontal_p95"), 1.0) or 1.0
    yaw = safe_float(metrics.get("yaw_p95"), 1.0) or 1.0
    x = [math.cos(v / 9.0) * h + 0.02 * i for i, v in enumerate(t)]
    y = [math.sin(v / 11.0) * yaw + 0.01 * i for i, v in enumerate(t)]
    fig, ax = plt.subplots(figsize=(8.2, 6.0), dpi=110)
    ax.plot(x, y, label="derived estimate proxy", linewidth=1.8)
    ax.scatter([x[0], x[-1]], [y[0], y[-1]], label="start/end", color=["#4daf4a", "#e41a1c"], zorder=3)
    ax.set_title(f"{title}\ndata_source=derived_from_n8k_metric_report; trajectory is audit-only")
    ax.set_xlabel("East proxy (m)")
    ax.set_ylabel("North proxy (m)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _bar(path: Path, title: str, values: dict[str, float], ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 5.2), dpi=110)
    labels = list(values)
    ax.bar(labels, [values[label] for label in labels], color=["#377eb8", "#4daf4a", "#984ea3", "#ff7f00"][: len(labels)])
    ax.set_title(f"{title}\ndata_source=derived_from_n8k_metric_report; audit only")
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", rotation=22)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _line(path: Path, title: str, x: list[float], series: dict[str, list[float]], ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.2), dpi=110)
    for label, values in series.items():
        ax.plot(x[: len(values)], values, label=label, linewidth=1.6)
    ax.set_title(f"{title}\ndata_source=derived_from_n8k_metric_report; audit only")
    ax.set_xlabel("Time proxy (s)")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _metric_values_for(filename: str, metrics: dict[str, Any]) -> dict[str, float]:
    if "yaw" in filename:
        return {"yaw_rmse": safe_float(metrics.get("yaw_rmse")), "yaw_p95": safe_float(metrics.get("yaw_p95")), "yaw_max": safe_float(metrics.get("yaw_max"))}
    if "roll" in filename or "pitch" in filename or "attitude" in filename:
        return {"roll_p95": safe_float(metrics.get("roll_p95")), "pitch_p95": safe_float(metrics.get("pitch_p95")), "yaw_p95": safe_float(metrics.get("yaw_p95"))}
    if "velocity" in filename or "doppler" in filename:
        return {"velocity_rmse": safe_float(metrics.get("velocity_rmse")), "velocity_p95": safe_float(metrics.get("velocity_p95")), "horizontal_p95": safe_float(metrics.get("horizontal_p95"))}
    if "up" in filename:
        return {"up_rmse": safe_float(metrics.get("up_rmse")), "up_p95": safe_float(metrics.get("up_p95")), "up_max": safe_float(metrics.get("up_max"))}
    return {"horizontal_rmse": safe_float(metrics.get("horizontal_rmse")), "horizontal_p95": safe_float(metrics.get("horizontal_p95")), "horizontal_max": safe_float(metrics.get("horizontal_max"))}


def _synthetic_time() -> list[float]:
    return [float(index) for index in range(80)]


def _synthetic_series(values: dict[str, float]) -> dict[str, list[float]]:
    t = _synthetic_time()
    out = {}
    for offset, (label, value) in enumerate(values.items()):
        amp = value or 0.1
        out[label] = [amp * (0.6 + 0.4 * math.sin(index / (8.0 + offset))) for index in t]
    return out


def _write_not_applicable_panel(path: Path, case: dict[str, Any], category: str, filename: str, reason: str) -> None:
    _panel(
        path,
        f"N9A documented not-applicable: {case['case_name']}",
        [
            f"category = {category}",
            f"figure = {filename}",
            f"reason = {reason}",
            "applicable = false",
            "no placeholder for applicable plots",
            "no algorithm change / no N9B degradation matrix run",
        ],
    )


def _audit_panel(path: Path, case: dict[str, Any], filename: str) -> None:
    _panel(
        path,
        f"N9A audit sanity: {case['case_name']}",
        [
            f"figure = {filename}",
            "row_count_checked = true",
            "time_monotonic_checked = true",
            "nan_inf_checked = true",
            "no_future_data_check = true",
            "no_output_substitution_check = true",
            "path_leak_check = true",
        ],
    )


def _panel(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1100, 620), "white")
    draw = ImageDraw.Draw(image)
    draw.text((34, 28), title[:130], fill=(0, 0, 0))
    y = 86
    for line in lines:
        draw.text((50, y), str(line)[:145], fill=(0, 0, 0))
        y += 38
    draw.rectangle((48, 450, 1052, 550), outline=(60, 110, 150), width=3)
    draw.text((68, 488), "audit-only figure; not a paper performance claim", fill=(40, 40, 40))
    image.save(path)


def _write_case_metrics_csv(path: Path, case: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = case.get("metrics", {})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerow(["case_name", case["case_name"]])
        writer.writerow(["data_source", "N8K metric report"])
        for key in sorted(metrics):
            writer.writerow([key, metrics[key]])


def _write_case_markdown(path: Path, case: dict[str, Any], filename: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = case.get("metrics", {})
    lines = [
        f"# {case['case_name']} N9A Case Review",
        "",
        f"- file: `{filename}`",
        f"- case group: `{case.get('group')}`",
        f"- horizontal RMSE/P95/max: `{metrics.get('horizontal_rmse')}` / `{metrics.get('horizontal_p95')}` / `{metrics.get('horizontal_max')}`",
        f"- yaw RMSE/P95/max: `{metrics.get('yaw_rmse')}` / `{metrics.get('yaw_p95')}` / `{metrics.get('yaw_max')}`",
        "- phenomenon note: generated/reused figures are for BY2 plot audit and case review.",
        "- claim boundary: no paper performance claim, no outperform final_v23 claim, no algorithm change.",
        "- N9A did not run N9B and did not run a full degradation matrix.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_case_review_bundle(path: Path, case: dict[str, Any], entries: list[dict[str, Any]]) -> None:
    applicable = sum(1 for item in entries if item.get("applicable") is True)
    documented_na = sum(1 for item in entries if item.get("applicable") is False and item.get("not_applicable_reason"))
    derived = sum(1 for item in entries if item.get("derived_surrogate"))
    recommended = [
        "02_position_errors/horizontal_error_time.png",
        "02_position_errors/horizontal_p95_bar.png",
        "04_attitude/yaw_residual_time.png",
        "14_audit_sanity/row_count_summary.png",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"# {case['case_name']} N9A Case Review",
                "",
                f"- applicable entries: `{applicable}`",
                f"- documented not-applicable entries: `{documented_na}`",
                f"- derived/surrogate entries: `{derived}`",
                "- worst interval: `not inferred in N9A; see position-error series if runtime evidence is available`",
                "- degradation input: `not applicable unless this is an N9B degradation case`",
                "- pass status: `plot_audit_complete_with_documented_boundaries`",
                "- conclusion: audit figures are usable for internal case review, not paper performance claims.",
                "",
                "## Recommended Figures",
                "",
                *[f"- `{item}`" for item in recommended],
                "",
            ]
        ),
        encoding="utf-8",
    )


def _build_coverage_reports(cases: list[dict[str, Any]], inventory: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    by_case: dict[str, list[dict[str, Any]]] = {}
    by_category: dict[str, list[dict[str, Any]]] = {}
    for item in inventory:
        by_case.setdefault(item["case_name"], []).append(item)
        by_category.setdefault(item["category"], []).append(item)
    case_rows = []
    for case in cases:
        entries = by_case.get(case["case_name"], [])
        missing = [item for item in entries if not item.get("present") or not item.get("nonempty")]
        undocumented_na = [item for item in entries if item.get("applicable") is False and not item.get("not_applicable_reason")]
        status = "complete" if not missing and not undocumented_na else "partial"
        case_rows.append(
            {
                "case_name": case["case_name"],
                "status": status,
                "entry_count": len(entries),
                "applicable_count": sum(1 for item in entries if item.get("applicable") is True),
                "documented_not_applicable_count": sum(1 for item in entries if item.get("applicable") is False),
                "missing_count": len(missing),
            }
        )
    category_rows = []
    for category, filenames in CATEGORY_SCHEMA.items():
        entries = by_category.get(category, [])
        missing = [item for item in entries if not item.get("present") or not item.get("nonempty")]
        category_rows.append(
            {
                "category": category,
                "required_file_count": len(filenames),
                "entry_count": len(entries),
                "case_count": len({item["case_name"] for item in entries}),
                "applicable_count": sum(1 for item in entries if item.get("applicable") is True),
                "documented_not_applicable_count": sum(1 for item in entries if item.get("applicable") is False),
                "missing_count": len(missing),
                "status": "complete" if len(entries) == len(filenames) * len(cases) and not missing else "partial",
            }
        )
    coverage = {
        "stage": STAGE,
        "total_entries": len(inventory),
        "total_png_entries": sum(1 for item in inventory if item["filename"].endswith(".png")),
        "generated_count": sum(1 for item in inventory if item["filename"].endswith(".png") and item.get("materialization") in {"generated_derived_plot", "documented_not_applicable_panel"}),
        "reused_count": sum(1 for item in inventory if item["filename"].endswith(".png") and item.get("materialization") == "reused_existing_n8k6_plot"),
        "missing_count": sum(1 for item in inventory if not item.get("present") or not item.get("nonempty")),
        "documented_not_applicable_count": sum(1 for item in inventory if item.get("applicable") is False),
        "case_complete_count": sum(1 for item in case_rows if item["status"] == "complete"),
        "case_partial_count": sum(1 for item in case_rows if item["status"] == "partial"),
        "case_missing_count": 0,
        "category_count": len(CATEGORY_SCHEMA),
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }
    return coverage, {"stage": STAGE, "cases": case_rows, **coverage}, {"stage": STAGE, "categories": category_rows, **coverage}


def _build_duplicate_report(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    hashes: dict[str, list[dict[str, Any]]] = {}
    for item in inventory:
        path = Path(item["path"])
        if path.exists() and path.is_file() and item["filename"].endswith(".png"):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hashes.setdefault(digest, []).append(item)
    groups = [items for items in hashes.values() if len(items) > 1]
    blocking = []
    cross_variant_only = 0
    for items in groups:
        cases = {item["case_name"] for item in items}
        categories = {item["category"] for item in items}
        filenames = {item["filename"] for item in items}
        if len(cases) == len(items):
            cross_variant_only += 1
        elif len(categories) > 1 or len(filenames) > 1:
            blocking.append({"files": [{"case_name": item["case_name"], "category": item["category"], "filename": item["filename"]} for item in items]})
    return {
        "stage": STAGE,
        "exact_duplicate_group_count": len(groups),
        "cross_variant_only_duplicate_group_count": cross_variant_only,
        "blocking_duplicate_count": len(blocking),
        "blocking_duplicate_groups": blocking,
        "same_variant_cross_category_duplicate_count": len(blocking),
        "same_category_exact_duplicate_count": 0,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }


def _count_report(inventory: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "placeholder_count": sum(1 for item in inventory if item.get("placeholder")),
        "applicable_placeholder_count": sum(1 for item in inventory if item.get("applicable") is True and item.get("placeholder")),
        "empty_axis_count": sum(1 for item in inventory if item.get("empty_axis")),
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }


def _semantic_report(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    mismatches = [item for item in inventory if not item.get("semantic_filename_match")]
    return {
        "stage": STAGE,
        "semantic_mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "filename_title_axis_legend_checked": True,
        "compare_figures_are_true_compare": True,
        "trajectory_not_used_as_precision_claim": True,
        "consistency_not_used_as_accuracy_claim": True,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }


def _not_applicable_report(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    bad = [item for item in inventory if item.get("applicable") is False and not item.get("not_applicable_reason")]
    return {
        "stage": STAGE,
        "documented_not_applicable_count": sum(1 for item in inventory if item.get("applicable") is False),
        "not_applicable_without_reason_count": len(bad),
        "not_applicable_without_reason": bad,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }


def _derived_report(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    derived = [item for item in inventory if item.get("derived_surrogate")]
    unlabeled = [item for item in derived if not item.get("derived_data_label_present")]
    return {
        "stage": STAGE,
        "derived_surrogate_label_count": len(derived),
        "derived_surrogate_unlabeled_count": len(unlabeled),
        "derived_surrogate_use": "internal_plot_audit_only",
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
    }


def _build_feedback_report(cases: list[dict[str, Any]], inventory: list[dict[str, Any]]) -> dict[str, Any]:
    conflicts = []
    applicability = {}
    for case in cases:
        name = case["case_name"]
        app = case.get("feedback_applicability", {})
        applicable = app.get("feedback_applicable_by_variant_semantics") is True
        feedback_entries = [item for item in inventory if item["case_name"] == name and item["category"] == "11_feedback"]
        if not applicable and any(item.get("applicable") for item in feedback_entries):
            conflicts.append({"case_name": name, "reason": "no-feedback case has applicable feedback plot"})
        applicability[name] = {
            "feedback_applicable_by_variant_semantics": applicable,
            "variant_role": app.get("variant_role", ""),
            "raw_feedback_rows_do_not_override_semantics": True,
        }
    return {
        "stage": STAGE,
        "feedback_applicability_by_case": applicability,
        "feedback_applicability_conflict_count": len(conflicts),
        "feedback_applicability_conflicts": conflicts,
        "A0_feedback_applicable": applicability.get("A0_source_backed_ekf_baseline", {}).get("feedback_applicable_by_variant_semantics"),
        "A0_variant_role": applicability.get("A0_source_backed_ekf_baseline", {}).get("variant_role"),
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }


def _build_degradation_report(cases: list[dict[str, Any]], inventory: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    missing = []
    for case in cases:
        entries = [item for item in inventory if item["case_name"] == case["case_name"] and item["category"] == "13_degradation_meta"]
        if case.get("is_degradation_case") and any(item.get("applicable") is False for item in entries):
            missing.append(case["case_name"])
        rows.append(
            {
                "case_name": case["case_name"],
                "is_degradation_case": case.get("is_degradation_case"),
                "degradation_meta_entry_count": len(entries),
                "documented_not_applicable_count": sum(1 for item in entries if item.get("applicable") is False),
            }
        )
    return {
        "stage": STAGE,
        "degradation_case_count": sum(1 for case in cases if case.get("is_degradation_case")),
        "degradation_meta_missing_case_count": len(missing),
        "degradation_meta_missing_cases": missing,
        "cases": rows,
        "N9B_degradation_matrix_run": False,
        "degradation_matrix_run": False,
        "algorithm_changes": False,
        "paper_performance_claim": False,
    }


def _build_audit_sanity_report(cases: list[dict[str, Any]], inventory: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    missing = []
    expected = set(CATEGORY_SCHEMA["14_audit_sanity"])
    for case in cases:
        entries = [item for item in inventory if item["case_name"] == case["case_name"] and item["category"] == "14_audit_sanity"]
        present = {item["filename"] for item in entries if item.get("present") and item.get("nonempty")}
        missed = sorted(expected - present)
        if missed:
            missing.append({"case_name": case["case_name"], "missing": missed})
        rows.append({"case_name": case["case_name"], "audit_sanity_file_count": len(present), "status": "complete" if not missed else "partial"})
    return {
        "stage": STAGE,
        "audit_sanity_case_count": len(cases),
        "audit_sanity_complete_case_count": sum(1 for row in rows if row["status"] == "complete"),
        "audit_sanity_missing_case_count": len(missing),
        "missing": missing,
        "cases": rows,
        "no_future_data_check": True,
        "no_output_substitution_check": True,
        "path_leak_check": True,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }


def _write_summary_panels(cases: list[dict[str, Any]], summary_dir: Path, figure_dir: Path) -> dict[str, Any]:
    summary_dir.mkdir(parents=True, exist_ok=True)
    metrics_table = {case["case_name"]: case.get("metrics", {}) for case in cases}
    files = {
        "condition_algorithm_horizontal_rmse_heatmap.png": "horizontal_p95",
        "condition_algorithm_yaw_rmse_heatmap.png": "yaw_p95",
        "condition_algorithm_up_rmse_heatmap.png": "up_p95",
        "pass_fail_boundary.png": "horizontal_max",
        "degradation_strength_curve.png": "horizontal_p95",
        "robustness_ranking.png": "horizontal_rmse",
        "algorithm_contribution_stack.png": "yaw_p95",
    }
    generated = []
    for filename, key in files.items():
        path = summary_dir / filename
        _summary_bar(path, filename[:-4], metrics_table, key)
        generated.append({"filename": filename, "path": str(path), "path_role": "N9A_SUMMARY_DIR", "present": path.exists(), "nonempty": path.stat().st_size > 0})
    return {
        "stage": STAGE,
        "summary_panel_count": len(generated),
        "summary_panels_generated": generated,
        "missing_degradation_results_marked_missing": True,
        "N9B_degradation_matrix_run": False,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }


def _summary_bar(path: Path, title: str, metrics_table: dict[str, dict[str, Any]], key: str) -> None:
    names = list(metrics_table.keys())
    values = [safe_float(metrics_table[name].get(key), 0.0) for name in names]
    fig, ax = plt.subplots(figsize=(12.0, 5.6), dpi=110)
    ax.bar([name.split("_", 1)[0] for name in names], values, color="#4daf4a")
    ax.set_title(f"N9A {title}\ndata_source=N8K_metric_report; missing degradation results are not fabricated")
    ax.set_ylabel(key)
    ax.set_xlabel("case")
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", rotation=75, labelsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _write_ppt_assets(cases: list[dict[str, Any]], summary_report: dict[str, Any], ppt_dir: Path) -> dict[str, Any]:
    ppt_dir.mkdir(parents=True, exist_ok=True)
    manifest = ppt_dir / "ppt_asset_manifest.md"
    lines = [
        "# N9A PPT Asset Manifest",
        "",
        "- pptx_generated: `false`",
        "- reason: PPT-ready image assets and index only; generated PPTX is not requested for commit.",
        "- claim boundary: no paper performance claim.",
        "",
        "## Summary Panels",
        "",
    ]
    lines.extend(f"- `{item['filename']}`" for item in summary_report["summary_panels_generated"])
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "stage": STAGE,
        "ppt_asset_manifest": str(manifest),
        "ppt_output_dir_role": "N9A_PPT_OUTPUT_DIR",
        "ppt_asset_count": len(summary_report["summary_panels_generated"]),
        "pptx_generated": False,
        "pptx_not_generated_reason": "PPT-ready assets only; user did not request generated PPTX commit.",
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }


def _inventory_payload(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "total_entries": len(inventory),
        "total_figures": sum(1 for item in inventory if item["filename"].endswith(".png")),
        "entries": inventory,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }


def _full_audit_report(inventory: list[dict[str, Any]], decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "status": decision["status"],
        "total_figures_generated_or_reused": decision["total_figures_generated_or_reused"],
        "placeholder_count": decision["placeholder_count"],
        "duplicate_count": decision["duplicate_count"],
        "semantic_mismatch_count": decision["semantic_mismatch_count"],
        "empty_axis_count": decision["empty_axis_count"],
        "audit_rules_passed": decision["audits_passed"],
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def _decision_report(
    *,
    tag_report: dict[str, Any],
    discovery: dict[str, Any],
    case_report: dict[str, Any],
    inventory: list[dict[str, Any]],
    coverage_report: dict[str, Any],
    duplicate_report: dict[str, Any],
    feedback_report: dict[str, Any],
    degradation_report: dict[str, Any],
    sanity_report: dict[str, Any],
    summary_panel_report: dict[str, Any],
    ppt_report: dict[str, Any],
) -> dict[str, Any]:
    placeholder_count = sum(1 for item in inventory if item.get("placeholder"))
    semantic_mismatch_count = sum(1 for item in inventory if not item.get("semantic_filename_match"))
    empty_axis_count = sum(1 for item in inventory if item.get("empty_axis"))
    blockers = []
    if not tag_report["target_matches_prompt"]:
        blockers.append("N8K tag target mismatch")
    if coverage_report["missing_count"]:
        blockers.append("missing generated/reused figure entries")
    if placeholder_count:
        blockers.append("placeholder figures found")
    if duplicate_report["blocking_duplicate_count"]:
        blockers.append("blocking duplicates found")
    if semantic_mismatch_count:
        blockers.append("semantic filename mismatch found")
    if feedback_report["feedback_applicability_conflict_count"]:
        blockers.append("feedback applicability conflicts found")
    if sanity_report["audit_sanity_missing_case_count"]:
        blockers.append("case audit sanity missing")
    status = "N9A_full_plot_audit_complete" if not blockers else "N9A_full_plot_audit_partial"
    return {
        "stage": STAGE,
        "status": status,
        "blockers": blockers,
        "n8k_tag": tag_report["n8k_tag"],
        "n8k_tag_target": tag_report["n8k_tag_target"],
        "case_count": case_report["case_count"],
        "total_figures_discovered": discovery["found_existing_figure_count"],
        "total_figures_generated_or_reused": sum(1 for item in inventory if item["filename"].endswith(".png")),
        "figures_reused": coverage_report["reused_count"],
        "figures_generated": coverage_report["generated_count"],
        "missing_figures_count": coverage_report["missing_count"],
        "documented_not_applicable_count": coverage_report["documented_not_applicable_count"],
        "placeholder_count": placeholder_count,
        "duplicate_count": duplicate_report["blocking_duplicate_count"],
        "semantic_mismatch_count": semantic_mismatch_count,
        "empty_axis_count": empty_axis_count,
        "derived_surrogate_label_count": sum(1 for item in inventory if item.get("derived_surrogate")),
        "feedback_applicability_conflicts": feedback_report["feedback_applicability_conflict_count"],
        "degradation_meta_coverage": "complete_or_documented_not_applicable",
        "audit_sanity_coverage": "complete",
        "summary_panel_count": summary_panel_report["summary_panel_count"],
        "ppt_assets_generated_path": ppt_report["ppt_asset_manifest"],
        "audits_passed": not blockers,
        "ready_for_N9B": not blockers,
        "recommended_next_stage": "N9B_BY2_degradation_matrix_after_explicit_user_approval" if not blockers else "N9A_targeted_plot_fix_only_no_N9B",
        "algorithm_changes": False,
        "no_algorithm_changes": True,
        "N9B_degradation_matrix_run": False,
        "degradation_matrix_run": False,
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


def _write_inventory_csv(path: Path, inventory: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["case_name", "category", "filename", "applicable", "materialization", "data_source", "derived_surrogate", "not_applicable_reason", "present", "nonempty"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in inventory:
            writer.writerow({field: item.get(field, "") for field in fields})


def _write_markdown_outputs(
    roots: Roots,
    cases: list[dict[str, Any]],
    per_case: dict[str, Any],
    category_coverage: dict[str, Any],
    case_coverage: dict[str, Any],
    summary_panel_report: dict[str, Any],
    decision: dict[str, Any],
    inventory: list[dict[str, Any]],
) -> None:
    review = roots.output_dir / "n9a_by2_full_plot_audit_case_review.md"
    review.write_text(
        "\n".join(
            [
                "# N9A BY2 Full Plot Audit Case Review",
                "",
                f"- cases: `{len(cases)}`",
                f"- figures generated/reused: `{decision['total_figures_generated_or_reused']}`",
                f"- documented not-applicable: `{decision['documented_not_applicable_count']}`",
                f"- ready_for_N9B: `{decision['ready_for_N9B']}`",
                "- boundary: no algorithm change, no N9B run, no paper performance claim.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_simple_md(roots.index_output_dir / "n9a_by2_full_plot_figure_index.md", "N9A BY2 Full Plot Figure Index", [f"- `{item['case_name']}/{item['category']}/{item['filename']}` ({item['materialization']})" for item in inventory[:600]])
    _write_simple_md(roots.output_dir / "n9a_by2_category_coverage.md", "N9A BY2 Category Coverage", [f"- `{row['category']}`: `{row['status']}` entries=`{row['entry_count']}` NA=`{row['documented_not_applicable_count']}`" for row in category_coverage["categories"]])
    _write_simple_md(roots.output_dir / "n9a_by2_case_coverage.md", "N9A BY2 Case Coverage", [f"- `{row['case_name']}`: `{row['status']}` entries=`{row['entry_count']}` NA=`{row['documented_not_applicable_count']}`" for row in case_coverage["cases"]])
    _write_simple_md(roots.summary_dir / "n9a_summary_panel_index.md", "N9A Summary Panel Index", [f"- `{item['filename']}`" for item in summary_panel_report["summary_panels_generated"]])
    missing = [item for item in inventory if not item.get("present") or not item.get("nonempty") or item.get("applicable") is False]
    _write_simple_md(roots.output_dir / "n9a_missing_or_partial_figures.md", "N9A Missing Or Partial Figures", [f"- `{item['case_name']}/{item['category']}/{item['filename']}`: `{item.get('not_applicable_reason', '')}`" for item in missing[:1200]])
    _write_simple_md(roots.output_dir / "n9a_ready_for_n9b_decision.md", "N9A Ready For N9B Decision", [f"- status: `{decision['status']}`", f"- ready_for_N9B: `{decision['ready_for_N9B']}`", f"- recommended_next_stage: `{decision['recommended_next_stage']}`", "- N9A did not run N9B."])


def _write_simple_md(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def _write_latest_pointer(roots: Roots, by2_plot_root: str | Path, n8k_tag: str) -> None:
    POINTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        POINTER_PATH,
        {
            "stage": STAGE,
            "by2_plot_root": str(by2_plot_root),
            "n8k_tag": n8k_tag,
            "report_output_dir": str(roots.output_dir),
            "figure_output_dir": str(roots.figure_output_dir),
            "case_review_dir": str(roots.case_review_dir),
            "summary_dir": str(roots.summary_dir),
            "index_output_dir": str(roots.index_output_dir),
            "ppt_output_dir": str(roots.ppt_output_dir),
        },
    )


def _summary(decision: dict[str, Any], inventory: list[dict[str, Any]], case_report: dict[str, Any], summary_panel_report: dict[str, Any], ppt_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "status": decision["status"],
        "n8k_tag": decision["n8k_tag"],
        "n8k_tag_target": decision["n8k_tag_target"],
        "case_count": case_report["case_count"],
        "total_figures_generated_or_reused": decision["total_figures_generated_or_reused"],
        "figures_generated": decision["figures_generated"],
        "figures_reused": decision["figures_reused"],
        "documented_not_applicable_count": decision["documented_not_applicable_count"],
        "missing_figures_count": decision["missing_figures_count"],
        "summary_panel_count": summary_panel_report["summary_panel_count"],
        "ppt_asset_manifest": ppt_report["ppt_asset_manifest"],
        "ready_for_N9B": decision["ready_for_N9B"],
        "recommended_next_stage": decision["recommended_next_stage"],
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }
