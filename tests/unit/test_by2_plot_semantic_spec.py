from legsa_gins.reporting.by2_plot_semantic_spec import SEMANTIC_SPECS

# 中文说明：semantic spec 固定重点文件名对应的语义角色。


def test_by2_plot_semantic_spec_maps_target_filenames():
    assert SEMANTIC_SPECS[("04_attitude", "yaw_residual_time.png")].expected_semantic_role == "yaw_residual_time_series"
    assert SEMANTIC_SPECS[("04_attitude", "yaw_wrap_check.png")].expected_semantic_role == "yaw_wrap_consistency_check"
    assert SEMANTIC_SPECS[("07_compare", "compare_horizontal_error.png")].expected_semantic_role == "horizontal_error_comparison"
    assert SEMANTIC_SPECS[("07_compare", "reject_all_sanity_compare.png")].documented_not_applicable_allowed is True
    assert SEMANTIC_SPECS[("11_feedback", "feedback_accept_reject_timeline.png")].expected_semantic_role == "feedback_accept_reject_timeline"
    assert SEMANTIC_SPECS[("03_velocity", "velocity_residual_time.png")].expected_semantic_role == "velocity_residual_time_series"
    assert SEMANTIC_SPECS[("07_compare", "compare_velocity_error.png")].expected_semantic_role == "velocity_error_comparison"
    assert SEMANTIC_SPECS[("06_observation_quality", "feedback_accept_reject_time.png")].expected_semantic_role == "feedback_observation_quality_timeline"
    assert SEMANTIC_SPECS[("07_compare", "compare_feedback_delta.png")].expected_semantic_role == "feedback_delta_comparison"
