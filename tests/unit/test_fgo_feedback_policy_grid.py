"""Unit tests for N8I feedback policy grid.

中文说明：策略网格必须包含 gate/cov/window/mode 消融，且禁止 trace/final_v23 调参。
"""

from legsa_gins.fgo_feedback.fgo_feedback_policy_grid import build_feedback_policy_grid, build_mode_ablation_specs


def test_policy_grid_contains_required_dimensions():
    report = build_feedback_policy_grid()
    assert "combined_conservative_gate" in report["dimensions"]["gate_policy"]
    assert "inflation_x4" in report["dimensions"]["covariance_inflation"]
    assert "window_10s_stride_1s" in report["dimensions"]["window_policy"]
    assert report["trace_solver_input"] is False
    assert report["final_v23_output_solver_input"] is False


def test_mode_ablation_specs_include_reject_all_and_pva():
    ids = {spec.policy_id for spec in build_mode_ablation_specs()}
    assert "reject_all_sanity" in ids
    assert "diagnostic_PVA" in ids
    assert "primary_hv_att_conservative_gate" in ids
