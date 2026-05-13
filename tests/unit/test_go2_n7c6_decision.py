"""Unit tests for N7C6 decision.

中文说明：测试 N7C6 推荐默认策略决策。
"""

from legsa_gins.go2_prior.go2_n7c6_decision import make_n7c6_joint_factor_decision


def test_n7c6_decision_recommends_joint_when_neutral():
    comparison = {
        "comparisons": {
            "joint_rp1p6_minus_baseline": {"delta": {"horizontal_rmse_m": 0.0}},
            "joint_rp1p6_minus_horizontal_only": {"delta": {"horizontal_rmse_m": 0.0, "yaw_rmse_deg": 0.0, "roll_rmse_deg": 0.0, "pitch_rmse_deg": 0.0}},
            "joint_rp1deg_minus_horizontal_only": {"delta": {"horizontal_rmse_m": 0.2}},
        }
    }
    nis = {"variants": {"joint_rp1p6deg_hv1p0": {"overconfidence_flag": False}, "joint_rp1deg_hv1p0": {"overconfidence_flag": True}}}
    decision = make_n7c6_joint_factor_decision(
        comparison_report=comparison,
        nis_report=nis,
        figure_manifest={"figure_count_total": 12, "required_figures_generated": True, "required_figures_nonempty": True},
    )
    assert decision["status"] == "go2_proprioceptive_joint_factor_ready"
    assert decision["go2_vertical_velocity_prior_enabled"] is False
