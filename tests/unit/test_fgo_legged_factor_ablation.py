"""Unit tests for N8F comparison report.

中文说明：检查 comparison 能识别 candidate solver injection。
"""

from legsa_gins.fgo.fgo_legged_factor_ablation import build_n8f_comparison_report


def test_comparison_detects_candidate_injection() -> None:
    report = build_n8f_comparison_report(
        {
            "variants": [
                {"variant": "baseline", "solve_status": "solved", "finite_output": True, "candidate_solver_residual_dim": 0},
                {
                    "variant": "foot",
                    "solve_status": "solved",
                    "finite_output": True,
                    "foot_kinematic_velocity_enabled": True,
                    "candidate_solver_residual_dim": 2,
                },
            ]
        }
    )
    assert report["candidate_solver_injection_passed"] is True
    assert report["solved_variant_count"] == 2
