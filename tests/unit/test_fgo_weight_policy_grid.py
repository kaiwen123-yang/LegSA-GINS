"""Tests for N8D weight policy grid.

中文说明：验证 N8D policy grid 包含正式 ablation 但候选仍 diagnostic-only。
"""

from legsa_gins.fgo.fgo_weight_policy_grid import FORMAL_ABLATION_VARIANTS, build_n8d_weight_policy_grid


def test_n8d_weight_policy_grid_has_required_boundaries() -> None:
    grid = build_n8d_weight_policy_grid()
    assert grid["formal_ablation_variants"] == FORMAL_ABLATION_VARIANTS
    assert len(grid["formal_ablation_variants"]) == 14
    assert grid["candidate_factors"]["foot_kinematic_velocity"] == "diagnostic_only"
    assert grid["no_smoothness_final_shortcut"]
    assert not grid["paper_performance_claim"]
