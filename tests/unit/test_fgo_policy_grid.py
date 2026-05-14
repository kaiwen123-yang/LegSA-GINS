"""中文说明：测试 N8B policy grid 边界。"""

from legsa_gins.fgo.fgo_policy_grid import build_n8b_policy_grid


def test_n8b_policy_grid_has_required_boundaries() -> None:
    grid = build_n8b_policy_grid()
    assert grid["variant_count"] == 13
    assert grid["no_smoothness_is_diagnostic_only"]
    assert grid["candidate_factors_are_diagnostic_only"]
    assert not grid["trace_solver_input"]
    assert not grid["final_v23_output_solver_input"]
