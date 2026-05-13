"""Unit tests for N7C2 decision rules.

中文说明：验证图像可读性和 Jacobian 边界共同决定 N7C2 gate。
"""

from legsa_gins.go2_prior.go2_n7c2_decision import make_n7c2_decision


def _overlap():
    return {"summary": {"all_overlaps_explained": True}}


def _figures(**override):
    data = {"required_figures_generated": True, "required_figures_nonempty": True}
    data.update(override)
    return data


def _jacobian(**override):
    data = {
        "all_active_factor_contracts_present": True,
        "go2_horizontal_touches_only_horizontal_velocity": True,
        "go2_horizontal_vertical_derivative_zero": True,
        "go2_horizontal_position_prior_enabled": False,
        "go2_horizontal_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "go2_horizontal_H_nonzero_blocks": ["velocity_north", "velocity_east"],
        "toy_finite_difference_status": "toy_passed",
    }
    data.update(override)
    return data


def test_n7c2_decision_ready_when_visual_and_jacobian_pass():
    decision = make_n7c2_decision(overlap_report=_overlap(), figure_manifest=_figures(), jacobian_report=_jacobian())
    assert decision["status"] == "ready_to_merge_N7C_and_start_N8A"
    assert decision["paper_performance_claim"] is False
    assert decision["go2_velocity_truth_claim"] is False


def test_n7c2_decision_blocks_vertical_jacobian_touch():
    decision = make_n7c2_decision(
        overlap_report=_overlap(),
        figure_manifest=_figures(),
        jacobian_report=_jacobian(go2_horizontal_vertical_derivative_zero=False),
    )
    assert decision["status"] == "go2_horizontal_jacobian_boundary_failed"


def test_n7c2_decision_blocks_empty_figures_first():
    decision = make_n7c2_decision(
        overlap_report=_overlap(),
        figure_manifest=_figures(required_figures_nonempty=False),
        jacobian_report=_jacobian(go2_horizontal_vertical_derivative_zero=False),
    )
    assert decision["status"] == "visual_readability_not_ready"
