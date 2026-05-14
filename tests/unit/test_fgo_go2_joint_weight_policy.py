"""Tests for N8D Go2 joint weight policy.

中文说明：Go2 joint 权重审查不声明 Go2 truth。
"""

from legsa_gins.fgo.fgo_go2_joint_weight_policy import build_go2_joint_weight_policy_report


def test_go2_joint_weight_policy_no_truth_claim() -> None:
    report = build_go2_joint_weight_policy_report(
        {
            "variants": [
                {
                    "variant": "go2_joint_x1",
                    "finite_output": True,
                    "factor_balance": [{"factor_type": "Go2ProprioceptiveJointFactor", "contribution_share": 0.02}],
                }
            ]
        }
    )
    assert report["go2_joint_stable_low_marginal_value"]
    assert report["no_go2_truth_claim"]
