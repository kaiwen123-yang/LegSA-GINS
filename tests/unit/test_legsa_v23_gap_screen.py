"""中文说明：测试 N4H4D gap screen 分类。"""

from legsa_gins.evaluation.legsa_v23_gap_screen import screen_gap


def test_detects_update_count_zero():
    gap = screen_gap({"count": 10}, {"measurement_update_count": 0, "state_feedback_implemented": True})
    assert "measurement_update_count_zero" in gap["blocking_issues"]
    assert gap["recommended_next_stage"] == "N4H4D_update_trigger_fix"


def test_detects_yaw_divergence():
    gap = screen_gap(
        {"count": 10, "yaw_rmse_deg": 20.0},
        {"measurement_update_count": 5, "yaw_update_count": 5, "velocity_update_count": 5, "state_feedback_implemented": True},
    )
    assert "yaw_diverges_gt_10deg" in gap["blocking_issues"]
    assert "N4H4D_yaw_update_convention_fix" in gap["recommended_next_stages"]


def test_detects_time_mismatch_zero_alignment():
    gap = screen_gap(
        {"count": 0},
        {"measurement_update_count": 5, "yaw_update_count": 5, "velocity_update_count": 5, "state_feedback_implemented": True},
    )
    assert "aligned_count_zero" in gap["blocking_issues"]
    assert "N4H4D_output_evaluator_fix" in gap["recommended_next_stages"]
