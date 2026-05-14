"""N8B no-feedback FGO factor-policy grid.

中文说明：本模块只定义 N8B 诊断 policy 空间；不使用 trace/final_v23 调权。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SMOOTHNESS_POLICIES = [
    "default_smoothness",
    "weak_smoothness",
    "position_velocity_only_smoothness",
    "yaw_smoothness_weak",
    "no_yaw_smoothness",
    "no_smoothness_diagnostic_only",
]

GO2_POLICIES = [
    "go2_joint_on",
    "go2_joint_off",
    "go2_horizontal_only",
    "go2_rollpitch_only",
]

RAW_DOPPLER_POLICIES = [
    "raw_doppler_on",
    "raw_doppler_off",
    "raw_doppler_downweighted",
]

CANDIDATE_POLICIES = [
    "candidate_off_default",
    "foot_kinematic_diagnostic",
    "yawrate_between_diagnostic",
    "relative_odometry_diagnostic",
    "candidate_stack_diagnostic",
]


def build_n8b_policy_grid() -> dict[str, Any]:
    """Build the bounded policy grid used by N8B real reruns."""
    variants = [
        {
            "variant": "default_active_stack_n8a2",
            "smoothness_policy": "default_smoothness",
            "go2_policy": "go2_joint_on",
            "raw_doppler_policy": "raw_doppler_on",
            "candidate_policy": "candidate_off_default",
            "diagnostic_only": False,
            "smoothness_factor_deleted_for_metric": False,
        },
        {
            "variant": "weak_yaw_smoothness",
            "smoothness_policy": "yaw_smoothness_weak",
            "go2_policy": "go2_joint_on",
            "raw_doppler_policy": "raw_doppler_on",
            "candidate_policy": "candidate_off_default",
            "diagnostic_only": False,
            "smoothness_factor_deleted_for_metric": False,
        },
        {
            "variant": "position_velocity_only_smoothness",
            "smoothness_policy": "position_velocity_only_smoothness",
            "go2_policy": "go2_joint_on",
            "raw_doppler_policy": "raw_doppler_on",
            "candidate_policy": "candidate_off_default",
            "diagnostic_only": False,
            "smoothness_factor_deleted_for_metric": False,
        },
        {
            "variant": "no_yaw_smoothness_diagnostic",
            "smoothness_policy": "no_yaw_smoothness",
            "go2_policy": "go2_joint_on",
            "raw_doppler_policy": "raw_doppler_on",
            "candidate_policy": "candidate_off_default",
            "diagnostic_only": True,
            "smoothness_factor_deleted_for_metric": False,
        },
        {
            "variant": "no_smoothness_diagnostic",
            "smoothness_policy": "no_smoothness_diagnostic_only",
            "go2_policy": "go2_joint_on",
            "raw_doppler_policy": "raw_doppler_on",
            "candidate_policy": "candidate_off_default",
            "diagnostic_only": True,
            "smoothness_factor_deleted_for_metric": False,
        },
        {
            "variant": "go2_joint_off",
            "smoothness_policy": "default_smoothness",
            "go2_policy": "go2_joint_off",
            "raw_doppler_policy": "raw_doppler_on",
            "candidate_policy": "candidate_off_default",
            "diagnostic_only": True,
            "smoothness_factor_deleted_for_metric": False,
        },
        {
            "variant": "go2_horizontal_only",
            "smoothness_policy": "default_smoothness",
            "go2_policy": "go2_horizontal_only",
            "raw_doppler_policy": "raw_doppler_on",
            "candidate_policy": "candidate_off_default",
            "diagnostic_only": True,
            "smoothness_factor_deleted_for_metric": False,
        },
        {
            "variant": "raw_doppler_off",
            "smoothness_policy": "default_smoothness",
            "go2_policy": "go2_joint_on",
            "raw_doppler_policy": "raw_doppler_off",
            "candidate_policy": "candidate_off_default",
            "diagnostic_only": True,
            "smoothness_factor_deleted_for_metric": False,
        },
        {
            "variant": "raw_doppler_downweighted",
            "smoothness_policy": "default_smoothness",
            "go2_policy": "go2_joint_on",
            "raw_doppler_policy": "raw_doppler_downweighted",
            "candidate_policy": "candidate_off_default",
            "diagnostic_only": True,
            "smoothness_factor_deleted_for_metric": False,
        },
        {
            "variant": "candidate_foot_kinematic_diagnostic",
            "smoothness_policy": "default_smoothness",
            "go2_policy": "go2_joint_on",
            "raw_doppler_policy": "raw_doppler_on",
            "candidate_policy": "foot_kinematic_diagnostic",
            "diagnostic_only": True,
            "smoothness_factor_deleted_for_metric": False,
        },
        {
            "variant": "candidate_yawrate_between_diagnostic",
            "smoothness_policy": "default_smoothness",
            "go2_policy": "go2_joint_on",
            "raw_doppler_policy": "raw_doppler_on",
            "candidate_policy": "yawrate_between_diagnostic",
            "diagnostic_only": True,
            "smoothness_factor_deleted_for_metric": False,
        },
        {
            "variant": "candidate_relative_odometry_diagnostic",
            "smoothness_policy": "default_smoothness",
            "go2_policy": "go2_joint_on",
            "raw_doppler_policy": "raw_doppler_on",
            "candidate_policy": "relative_odometry_diagnostic",
            "diagnostic_only": True,
            "smoothness_factor_deleted_for_metric": False,
        },
        {
            "variant": "candidate_stack_diagnostic",
            "smoothness_policy": "default_smoothness",
            "go2_policy": "go2_joint_on",
            "raw_doppler_policy": "raw_doppler_on",
            "candidate_policy": "candidate_stack_diagnostic",
            "diagnostic_only": True,
            "smoothness_factor_deleted_for_metric": False,
        },
    ]
    return {
        "stage": "N8B_fgo_factor_graph_policy_review",
        "policy_dimensions": {
            "smoothness_policy": SMOOTHNESS_POLICIES,
            "go2_factor_policy": GO2_POLICIES,
            "raw_doppler_policy": RAW_DOPPLER_POLICIES,
            "candidate_factors": CANDIDATE_POLICIES,
        },
        "variants": variants,
        "variant_count": len(variants),
        "no_smoothness_is_diagnostic_only": True,
        "candidate_factors_are_diagnostic_only": True,
        "policy_selection_basis": "consistency_and_no_gross_degradation_gates_only",
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "fgo_output_feedback_to_ekf": False,
        "fgo_output_replaces_ekf_nav": False,
        "paper_performance_claim": False,
    }


def write_policy_grid(path: str | Path, grid: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(grid, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
