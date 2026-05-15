"""N8K BY2 ablation plot catalog."""

# 中文说明：图像目录列出必画项；不适用项必须有占位说明。

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json


PLOT_CATEGORIES: dict[str, list[str]] = {
    "01_trajectory": ["local_trajectory_overlay.png", "baseline_vs_variant_trajectory.png", "trajectory_delta_vector.png", "start_end_marker_trajectory.png", "zoomed_trajectory_key_region.png"],
    "02_position_errors": ["north_error_time.png", "east_error_time.png", "up_error_time.png", "horizontal_error_time.png", "horizontal_rmse_p95_bar.png", "up_rmse_p95_bar.png", "max_error_bar.png", "error_cdf.png"],
    "03_velocity": ["velocity_components_estimate.png", "receiver_velocity_compare.png", "raw_doppler_velocity_compare.png", "go2_horizontal_velocity_compare.png", "foot_kinematic_velocity_compare.png", "velocity_residual_time.png", "velocity_factor_residual_p95.png"],
    "04_attitude": ["roll_time.png", "pitch_time.png", "yaw_time.png", "yaw_truth_obs_estimate.png", "yaw_residual_time.png", "yaw_wrap_check.png", "yawrate_between_residual.png", "attitude_rmse_p95_bar.png"],
    "05_consistency": ["position_error_3sigma.png", "velocity_error_3sigma.png", "attitude_error_3sigma.png", "innovation_residual_time.png", "whitened_residual_time.png", "nis_proxy_time.png", "coverage_ratio_bar.png", "covariance_diagonal_time.png"],
    "06_observation_quality": ["gnss_position_observation.png", "gnss_velocity_observation.png", "gnss_position_std_time.png", "gnss_velocity_std_time.png", "yaw_observation_quality.png", "raw_doppler_quality.png", "go2_contact_weight_time.png", "foot_kinematic_quality.png", "feedback_accept_reject_time.png", "source_aware_r_scale_time.png"],
    "07_compare": ["compare_core_metrics.png", "compare_horizontal_error.png", "compare_yaw_error.png", "compare_roll_pitch_error.png", "compare_velocity_error.png", "compare_feedback_delta.png", "reject_all_sanity_compare.png"],
    "08_summary_panels": ["ablation_metric_heatmap_horizontal.png", "ablation_metric_heatmap_yaw.png", "ablation_metric_heatmap_up.png", "ablation_strength_curve.png", "algorithm_rank_summary.png", "contribution_stack_summary.png"],
    "09_case_review": ["case_review.md", "case_key_metrics_table.csv", "case_recommended_figures.md"],
    "10_fgo_factors": ["fgo_factor_residual_by_type.png", "whitened_residual_by_type.png", "factor_contribution_by_type.png", "factor_rows_by_type.png", "jacobian_nonzero_by_type.png", "fgo_cost_time.png", "raw_doppler_fgo_residual.png", "go2_joint_fgo_residual.png", "candidate_factor_residual.png"],
    "11_feedback": ["feedback_window_timeline.png", "feedback_accept_reject_timeline.png", "feedback_correction_norm.png", "feedback_covariance_time.png", "feedback_gate_threshold.png", "feedback_reject_reason.png", "selected_feedback_vs_baseline.png", "reject_all_sanity.png"],
    "12_legged_factors": ["contact_probability_time.png", "slip_risk_time.png", "foot_kinematic_velocity_time.png", "yawrate_between_residual_time.png", "relative_odometry_residual_time.png", "go2_joint_residual_time.png", "contact_aware_weight_scale.png"],
    "13_ablation_meta": ["active_module_list_panel.png", "variant_configuration_panel.png", "feedback_policy_panel.png", "factor_enable_disable_panel.png", "runtime_manifest_summary.png"],
    "14_audit_sanity": ["row_count_summary.png", "time_monotonic_check.png", "nan_inf_check.png", "input_output_alignment.png", "runtime_manifest_check.png", "no_future_data_check.png", "no_output_substitution_check.png"],
}


def build_plot_catalog(matrix: dict[str, Any]) -> dict[str, Any]:
    variants = []
    for row in matrix.get("rows", []):
        files = []
        for category, names in PLOT_CATEGORIES.items():
            for name in names:
                applicable, reason = _applicability(row, category, name)
                files.append({"category": category, "filename": name, "applicable": applicable, "not_applicable_reason": "" if applicable else reason})
        variants.append({"variant_id": row.get("variant_id"), "group": row.get("group"), "files": files})
    figure_count = sum(1 for variant in variants for item in variant["files"] if item["filename"].endswith(".png"))
    return {
        "stage": "N8K",
        "variant_count": len(variants),
        "category_count": len(PLOT_CATEGORIES),
        "png_figure_count_expected": figure_count,
        "categories": [{"category": key, "file_count": len(value)} for key, value in PLOT_CATEGORIES.items()],
        "variants": variants,
        "plot_output_role": "BY2_PLOT_AUDIT_ROOT/N8K_BY2_formal_ablation_plot_audit",
        "paper_performance_claim": False,
    }


def _applicability(row: dict[str, Any], category: str, filename: str) -> tuple[bool, str]:
    modules = set(row.get("active_modules", []))
    if category == "11_feedback" and row.get("feedback_mode") == "none":
        return False, "feedback disabled for this ablation variant"
    if category == "10_fgo_factors" and not any("fgo" in module for module in modules):
        return False, "FGO factors not active for this ablation variant"
    if category == "12_legged_factors" and not any(("go2" in module or "legged" in module or "foot" in module or "contact" in module) for module in modules):
        return False, "legged factors not active for this ablation variant"
    if "raw_doppler" in filename and not any("raw_doppler" in module for module in modules):
        return False, "raw Doppler module not active"
    return True, ""


def write_plot_catalog(path: str | Path, catalog: dict[str, Any]) -> None:
    write_json(path, catalog)
