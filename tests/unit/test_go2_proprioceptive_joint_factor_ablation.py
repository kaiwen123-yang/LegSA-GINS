"""Unit tests for N7C6 joint factor ablation comparison.

中文说明：测试 N7C6 ablation comparison 输出键。
"""

from legsa_gins.go2_prior.go2_proprioceptive_joint_factor_ablation import compare_n7c6_joint_variants


def test_joint_factor_ablation_comparison_has_expected_keys():
    def row(variant):
        return {"variant_id": variant, "summary": {"horizontal_rmse_m": 1.0, "yaw_rmse_deg": 1.0, "roll_rmse_deg": 0.1, "pitch_rmse_deg": 0.1}}

    report = compare_n7c6_joint_variants(
        [row("baseline_no_go2_proprioceptive"), row("horizontal_only_fixed_1p0"), row("joint_rp1p6deg_hv1p0"), row("joint_rp1deg_hv1p0")]
    )
    assert "joint_rp1p6_minus_horizontal_only" in report["comparisons"]
    assert report["paper_performance_claim"] is False
