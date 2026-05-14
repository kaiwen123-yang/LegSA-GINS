"""Unit tests for N8F1 factor signal review.

中文说明：检查新因子的 signal status 不会误写成性能结论。
"""

from legsa_gins.fgo.fgo_n8f_factor_signal_review import build_n8f_factor_signal_review


def test_signal_review_marks_active_factors_informative() -> None:
    report = build_n8f_factor_signal_review(
        reports={
            "contact_weighting": {"used_by_factor": ["FootKinematicVelocityFactor"]},
            "foot_kinematic": {"residual_rows": 2},
            "yawrate": {"residual_rows": 1, "wrap_boundary_test_passed": True},
            "relative_odometry": {"residual_rows": 2, "absolute_go2_position_factor": False},
            "comparison": {"gross_degradation_variants": [], "candidate_solver_injection_passed": True},
        },
        contact_timeseries=[{"contact_weight_scale": 1.0}, {"contact_weight_scale": 1.2}],
        foot_series=[{"residual_proxy": 0.1, "whitened_residual_proxy": 0.2}],
        yawrate_series=[{"residual_proxy": 0.1}],
        relative_series=[{"residual_proxy": 0.1}],
        variants=[
            {"foot_kinematic_velocity_enabled": True, "candidate_solver_residual_dim": 2},
            {"yawrate_between_enabled": True, "candidate_solver_residual_dim": 1},
            {"relative_odometry_between_enabled": True, "candidate_solver_residual_dim": 2},
        ],
    )
    assert report["all_new_factors_have_real_signal"] is True
    assert report["paper_performance_claim"] is False

