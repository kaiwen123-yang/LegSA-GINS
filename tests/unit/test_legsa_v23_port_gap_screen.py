"""中文说明：测试 R3 gap screen 的失败分类和下一阶段建议。"""

from legsa_gins.evaluation.legsa_v23_port_gap_screen import make_port_gap_screen


def test_detects_update_count_zero():
    gap = make_port_gap_screen(
        {"count": 10, "horizontal_rmse_m": 0.5},
        {"propagation_count": 10, "measurement_update_count": 0, "position_update_count": 0},
    )
    assert "measurement_update_count_zero" in gap["blocking_issues"]
    assert gap["recommended_next_stage"] == "N4H4R3_update_count_fix"


def test_detects_yaw_divergence():
    gap = make_port_gap_screen(
        {"count": 10, "yaw_rmse_deg": 30.0},
        {"propagation_count": 10, "measurement_update_count": 2, "position_update_count": 2},
    )
    assert "yaw_divergence_gt_10deg" in gap["blocking_issues"]
    assert gap["recommended_next_stage"] == "N4H4R3_filter_math_gap_fix"


def test_missing_input_recommends_config_fix():
    gap = make_port_gap_screen({"count": 0}, {}, {"clean_input_missing": True})
    assert "clean_input_missing" in gap["blocking_issues"]
    assert gap["recommended_next_stage"] == "N4H4R3_config_input_fix"
