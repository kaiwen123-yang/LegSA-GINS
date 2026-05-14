"""N8D FGO factor weight policy grid.

中文说明：定义 N8D 权重审查候选集合；策略筛选只允许 solver-visible diagnostics。
"""

from __future__ import annotations

from typing import Any


SMOOTHNESS_POLICIES = [
    "default_weak_yaw_from_N8B",
    "smoothness_balanced_low",
    "smoothness_balanced_mid",
    "yaw_smoothness_weaker",
    "process_like_position_velocity",
    "no_yaw_smoothness_diagnostic_only",
    "no_smoothness_diagnostic_only",
]

RAW_DOPPLER_POLICIES = [
    "raw_x0p5",
    "raw_x1",
    "raw_x2",
    "raw_x4",
    "raw_balanced_by_whitened_residual",
]

RECEIVER_VELOCITY_POLICIES = [
    "receiver_vel_x0p5",
    "receiver_vel_x1",
    "receiver_vel_x2",
    "receiver_vel_downweighted_raw_preserved",
    "receiver_vel_off_diagnostic_only",
]

GO2_JOINT_POLICIES = [
    "go2_joint_x0p5",
    "go2_joint_x1",
    "go2_joint_x2",
    "go2_joint_off_diagnostic_only",
]

DUAL_YAW_POLICIES = [
    "dual_yaw_x0p5",
    "dual_yaw_x1",
    "dual_yaw_x2",
    "dual_yaw_x4_diagnostic",
]

FORMAL_ABLATION_VARIANTS = [
    "ekf_baseline_no_fgo_reference",
    "n8b_weak_yaw_default",
    "balanced_policy_A",
    "balanced_policy_B",
    "conservative_policy",
    "raw_receiver_balanced_best",
    "go2_joint_weight_best",
    "dual_yaw_weight_best",
    "split_smoothness_best",
    "candidate_stack_diagnostic",
    "no_raw_doppler_diagnostic",
    "no_go2_joint_diagnostic",
    "no_dual_yaw_diagnostic",
    "no_smoothness_diagnostic",
]

RAW_RECEIVER_BALANCE_VARIANTS = [
    "receiver_vel_x1_raw_x1",
    "receiver_vel_x0p5_raw_x1",
    "receiver_vel_x1_raw_x2",
    "receiver_vel_x0p5_raw_x2",
    "receiver_vel_x0p5_raw_x4",
    "receiver_vel_off_raw_x1",
    "receiver_vel_off_raw_x2",
    "raw_off_receiver_x1",
]

GO2_JOINT_VARIANTS = [
    "go2_joint_x0p5",
    "go2_joint_x1",
    "go2_joint_x2",
    "go2_joint_x4_diagnostic",
    "go2_joint_off_diagnostic",
]

DUAL_YAW_VARIANTS = [
    "dual_yaw_x0p5",
    "dual_yaw_x1",
    "dual_yaw_x2",
    "dual_yaw_x4_diagnostic",
]


def _spec(
    variant: str,
    *,
    smoothness_scale: float = 1.0,
    yaw_smoothness_scale: float = 1.0,
    raw_scale: float = 1.0,
    raw_enabled: bool = True,
    receiver_velocity_scale: float = 1.0,
    receiver_velocity_enabled: bool = True,
    go2_joint_scale: float = 1.0,
    go2_joint_enabled: bool = True,
    dual_yaw_scale: float = 1.0,
    dual_yaw_enabled: bool = True,
    diagnostic_only: bool = False,
    candidate_stack_enabled: bool = False,
    policy_family: str = "formal_ablation",
) -> dict[str, Any]:
    return {
        "variant": variant,
        "policy_family": policy_family,
        "smoothness_scale": smoothness_scale,
        "yaw_smoothness_scale": yaw_smoothness_scale,
        "raw_doppler_weight_scale": raw_scale,
        "raw_doppler_enabled": raw_enabled,
        "receiver_velocity_scale": receiver_velocity_scale,
        "receiver_velocity_enabled": receiver_velocity_enabled,
        "go2_joint_scale": go2_joint_scale,
        "go2_joint_enabled": go2_joint_enabled,
        "dual_yaw_scale": dual_yaw_scale,
        "dual_yaw_enabled": dual_yaw_enabled,
        "diagnostic_only": diagnostic_only,
        "candidate_stack_enabled": candidate_stack_enabled,
        "smoothness_factor_deleted_for_metric": False,
        "no_smoothness_final_shortcut": True,
        "trace_weight_tuning": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }


def build_n8d_variant_specs() -> dict[str, dict[str, Any]]:
    """中文说明：给 runner 使用的可执行 variant spec，不是 trace/final_v23 网格调参。"""
    specs = {
        "ekf_baseline_no_fgo_reference": _spec(
            "ekf_baseline_no_fgo_reference",
            smoothness_scale=0.0,
            raw_enabled=False,
            receiver_velocity_enabled=False,
            go2_joint_enabled=False,
            dual_yaw_enabled=False,
            diagnostic_only=True,
        ),
        "n8b_weak_yaw_default": _spec("n8b_weak_yaw_default"),
        "balanced_policy_A": _spec(
            "balanced_policy_A",
            smoothness_scale=0.65,
            yaw_smoothness_scale=0.5,
            raw_scale=2.0,
            receiver_velocity_scale=0.75,
            go2_joint_scale=1.25,
            dual_yaw_scale=2.0,
        ),
        "balanced_policy_B": _spec(
            "balanced_policy_B",
            smoothness_scale=0.45,
            yaw_smoothness_scale=0.35,
            raw_scale=4.0,
            receiver_velocity_scale=0.5,
            go2_joint_scale=1.5,
            dual_yaw_scale=2.0,
        ),
        "conservative_policy": _spec(
            "conservative_policy",
            smoothness_scale=0.8,
            yaw_smoothness_scale=0.75,
            raw_scale=1.0,
            receiver_velocity_scale=1.0,
            go2_joint_scale=1.0,
            dual_yaw_scale=1.0,
        ),
        "raw_receiver_balanced_best": _spec(
            "raw_receiver_balanced_best",
            smoothness_scale=0.65,
            raw_scale=2.0,
            receiver_velocity_scale=0.5,
            go2_joint_scale=1.0,
            dual_yaw_scale=1.5,
        ),
        "go2_joint_weight_best": _spec("go2_joint_weight_best", go2_joint_scale=2.0),
        "dual_yaw_weight_best": _spec("dual_yaw_weight_best", yaw_smoothness_scale=0.5, dual_yaw_scale=2.0),
        "split_smoothness_best": _spec(
            "split_smoothness_best",
            smoothness_scale=0.55,
            yaw_smoothness_scale=0.35,
            raw_scale=2.0,
            receiver_velocity_scale=0.75,
            dual_yaw_scale=2.0,
        ),
        "candidate_stack_diagnostic": _spec(
            "candidate_stack_diagnostic",
            candidate_stack_enabled=True,
            diagnostic_only=True,
        ),
        "no_raw_doppler_diagnostic": _spec("no_raw_doppler_diagnostic", raw_enabled=False, raw_scale=0.0, diagnostic_only=True),
        "no_go2_joint_diagnostic": _spec("no_go2_joint_diagnostic", go2_joint_enabled=False, diagnostic_only=True),
        "no_dual_yaw_diagnostic": _spec("no_dual_yaw_diagnostic", dual_yaw_enabled=False, yaw_smoothness_scale=0.5, diagnostic_only=True),
        "no_smoothness_diagnostic": _spec(
            "no_smoothness_diagnostic",
            smoothness_scale=0.0,
            yaw_smoothness_scale=0.0,
            diagnostic_only=True,
        ),
        "receiver_vel_x1_raw_x1": _spec("receiver_vel_x1_raw_x1", policy_family="raw_receiver_balance"),
        "receiver_vel_x0p5_raw_x1": _spec(
            "receiver_vel_x0p5_raw_x1",
            receiver_velocity_scale=0.5,
            policy_family="raw_receiver_balance",
        ),
        "receiver_vel_x1_raw_x2": _spec(
            "receiver_vel_x1_raw_x2",
            raw_scale=2.0,
            policy_family="raw_receiver_balance",
        ),
        "receiver_vel_x0p5_raw_x2": _spec(
            "receiver_vel_x0p5_raw_x2",
            raw_scale=2.0,
            receiver_velocity_scale=0.5,
            policy_family="raw_receiver_balance",
        ),
        "receiver_vel_x0p5_raw_x4": _spec(
            "receiver_vel_x0p5_raw_x4",
            raw_scale=4.0,
            receiver_velocity_scale=0.5,
            policy_family="raw_receiver_balance",
        ),
        "receiver_vel_off_raw_x1": _spec(
            "receiver_vel_off_raw_x1",
            receiver_velocity_enabled=False,
            diagnostic_only=True,
            policy_family="raw_receiver_balance",
        ),
        "receiver_vel_off_raw_x2": _spec(
            "receiver_vel_off_raw_x2",
            raw_scale=2.0,
            receiver_velocity_enabled=False,
            diagnostic_only=True,
            policy_family="raw_receiver_balance",
        ),
        "raw_off_receiver_x1": _spec(
            "raw_off_receiver_x1",
            raw_enabled=False,
            raw_scale=0.0,
            diagnostic_only=True,
            policy_family="raw_receiver_balance",
        ),
        "go2_joint_x0p5": _spec("go2_joint_x0p5", go2_joint_scale=0.5, policy_family="go2_joint_weight"),
        "go2_joint_x1": _spec("go2_joint_x1", policy_family="go2_joint_weight"),
        "go2_joint_x2": _spec("go2_joint_x2", go2_joint_scale=2.0, policy_family="go2_joint_weight"),
        "go2_joint_x4_diagnostic": _spec(
            "go2_joint_x4_diagnostic",
            go2_joint_scale=4.0,
            diagnostic_only=True,
            policy_family="go2_joint_weight",
        ),
        "go2_joint_off_diagnostic": _spec(
            "go2_joint_off_diagnostic",
            go2_joint_enabled=False,
            diagnostic_only=True,
            policy_family="go2_joint_weight",
        ),
        "dual_yaw_x0p5": _spec("dual_yaw_x0p5", dual_yaw_scale=0.5, policy_family="dual_yaw_weight"),
        "dual_yaw_x1": _spec("dual_yaw_x1", policy_family="dual_yaw_weight"),
        "dual_yaw_x2": _spec("dual_yaw_x2", dual_yaw_scale=2.0, yaw_smoothness_scale=0.5, policy_family="dual_yaw_weight"),
        "dual_yaw_x4_diagnostic": _spec(
            "dual_yaw_x4_diagnostic",
            dual_yaw_scale=4.0,
            yaw_smoothness_scale=0.35,
            diagnostic_only=True,
            policy_family="dual_yaw_weight",
        ),
    }
    return specs


def build_n8d_weight_policy_grid() -> dict[str, Any]:
    specs = build_n8d_variant_specs()
    return {
        "stage": "N8D_fgo_factor_weight_policy_review",
        "smoothness_policies": SMOOTHNESS_POLICIES,
        "raw_doppler_policies": RAW_DOPPLER_POLICIES,
        "receiver_velocity_policies": RECEIVER_VELOCITY_POLICIES,
        "go2_joint_policies": GO2_JOINT_POLICIES,
        "dual_yaw_policies": DUAL_YAW_POLICIES,
        "formal_ablation_variants": FORMAL_ABLATION_VARIANTS,
        "raw_receiver_balance_variants": RAW_RECEIVER_BALANCE_VARIANTS,
        "go2_joint_variants": GO2_JOINT_VARIANTS,
        "dual_yaw_variants": DUAL_YAW_VARIANTS,
        "variant_specs": specs,
        "candidate_factors": {
            "foot_kinematic_velocity": "diagnostic_only",
            "yaw_rate_between": "diagnostic_only",
            "relative_odometry": "diagnostic_only",
            "contact_probability_weighting": "diagnostic_only",
        },
        "solver_visible_selection_inputs": [
            "whitened_residual_p50_p95_max",
            "dimension_normalized_residual",
            "factor_count",
            "nis_proxy",
            "finite_output",
            "no_gross_internal_inconsistency",
            "factor_activation_toggle_integrity",
        ],
        "evaluation_only_inputs": ["FGO_vs_EKF_delta", "FGO_vs_reference_metrics", "parity_to_final_v23"],
        "no_trace_finalv23_tuning": True,
        "no_feedback": True,
        "output_substitution": False,
        "smoothness_factor_deleted_for_metric": False,
        "no_smoothness_final_shortcut": True,
        "paper_performance_claim": False,
    }
