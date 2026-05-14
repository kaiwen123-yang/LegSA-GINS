"""N8D process factor policy review.

中文说明：当前只审查 process-factor 方向，不实现 IMU preintegration 或 paper claim。
"""

from __future__ import annotations

from typing import Any


def build_process_factor_policy_review(
    *,
    smoothness_report: dict[str, Any],
    balance_report: dict[str, Any],
) -> dict[str, Any]:
    smoothness_dominant = bool(smoothness_report.get("smoothness_still_dominant")) or bool(
        balance_report.get("smoothness_dominance_detected")
    )
    decision = "redesign_in_N8D2" if smoothness_dominant else "keep_current_smoothness_for_N8D"
    return {
        "stage": "N8D_fgo_factor_weight_policy_review",
        "candidates_reviewed": [
            "constant_velocity_process_factor",
            "position_propagation_p_k1_equals_p_k_plus_v_dt",
            "velocity_random_walk_factor",
            "yaw_random_walk_factor_with_wrap",
            "attitude_random_walk_factor",
            "imu_informed_preintegration_placeholder_future_only",
        ],
        "decision": decision,
        "keep_current_smoothness_for_N8D": True,
        "split_smoothness_recommended": True,
        "redesign_in_N8D2_recommended": smoothness_dominant,
        "future_imu_preintegration_not_claimed": True,
        "no_smoothness_deletion_final_shortcut": True,
        "trace_weight_tuning": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
        "no_feedback": True,
        "output_substitution": False,
    }
