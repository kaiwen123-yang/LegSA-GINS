"""Tests for N8E final ablation matrix.

中文说明：验证 N8E 22 行矩阵和边界布尔值。
"""

from legsa_gins.fgo.fgo_final_ablation_matrix import build_final_engineering_ablation_matrix


def _stage_reports() -> dict:
    variants = [
        "ekf_baseline_no_fgo_reference",
        "n8b_weak_yaw_default",
        "conservative_policy",
        "candidate_stack_diagnostic",
        "no_raw_doppler_diagnostic",
        "no_go2_joint_diagnostic",
        "no_dual_yaw_diagnostic",
        "no_smoothness_diagnostic",
    ]
    return {
        "n5b_decision": {"status": "raw_doppler_frontend_active"},
        "n6b_decision": {"status": "ready_with_weak_stress_evidence"},
        "n7c6_decision": {"status": "go2_joint_factor_review_passed"},
        "n8a2_decision": {"status": "yaw_convention_fixed_foundation_ready"},
        "n8b_decision": {"status": "weak_yaw_smoothness_ready"},
        "n8c3_decision": {"status": "raw_doppler_active_consistent_or_dominated"},
        "n8d_decision": {"status": "raw_doppler_active_but_low_fgo_marginal_value", "raw_doppler_remains_low_marginal_value": True},
        "n8d_formal_matrix": {"best_solver_visible_balance_variant": "conservative_policy"},
        "n8d_variant_summaries": {
            "variants": [
                {
                    "variant": name,
                    "solve_status": "solved",
                    "horizontal_delta_rmse_m": 0.1,
                    "up_delta_rmse_m": 0.01,
                    "yaw_delta_wrapped_rmse_deg": 0.2,
                    "roll_delta_rmse_deg": 0.03,
                    "pitch_delta_rmse_deg": 0.04,
                    "diagnostic_only": "diagnostic" in name,
                }
                for name in variants
            ]
        },
        "n8d_raw_receiver": {
            "best_solver_visible_raw_receiver_balance": "receiver_vel_x0p5_raw_x1",
            "raw_doppler_remains_low_marginal_value": True,
            "variants": [{"variant": "receiver_vel_x0p5_raw_x1", "solve_status": "solved", "horizontal_delta_rmse_m": 0.2}],
        },
        "n8d_go2_policy": {
            "best_solver_visible_go2_joint_policy": "go2_joint_x2",
            "variants": [{"variant": "go2_joint_x2", "solve_status": "solved", "horizontal_delta_rmse_m": 0.3}],
        },
        "n8d_dual_yaw": {
            "best_solver_visible_dual_yaw_policy": "dual_yaw_x2",
            "variants": [{"variant": "dual_yaw_x2", "solve_status": "solved", "yaw_delta_wrapped_rmse_deg": 0.05}],
        },
    }


def test_n8e_final_ablation_matrix_has_required_groups() -> None:
    report = build_final_engineering_ablation_matrix(_stage_reports())
    assert report["matrix_complete"]
    assert report["row_count"] == 22
    assert report["group_counts"] == {
        "A_EKF_front_end_modules": 5,
        "B_no_feedback_FGO_modules": 7,
        "C_diagnostic_removals": 5,
        "D_candidate_factors": 5,
    }
    assert report["raw_doppler_fgo_active_but_low_marginal_value"]
    assert report["raw_doppler_low_marginal_value_is_not_failure"]
    assert report["no_fgo_feedback"]
    assert report["no_fgo_output_substitution"]
    assert report["no_trace_finalv23_solver_input_or_tuning"]
