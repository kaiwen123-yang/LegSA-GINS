"""Tests for N8D smoothness policy.

中文说明：no_smoothness 只能保持 diagnostic-only。
"""

from legsa_gins.fgo.fgo_smoothness_weight_policy import build_smoothness_weight_policy_report


def test_smoothness_weight_policy_keeps_deletion_diagnostic_only() -> None:
    report = build_smoothness_weight_policy_report(
        n8c2_smoothness_report={"component_causing_spikes": "yaw_smoothness"},
        variant_report={"variants": [{"variant": "no_smoothness_diagnostic", "diagnostic_only": True, "smoothness_contribution_share": 0.0}]},
    )
    assert report["yaw_smoothness_still_suspect"]
    assert report["no_smoothness_final_shortcut"]
    assert "candidate_N8D2_process_factor_redesign" in report["recommendations"]
