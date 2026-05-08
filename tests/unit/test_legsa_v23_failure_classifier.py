"""中文说明：N4H4D1 failure classifier 单元测试。"""

from legsa_gins.evaluation.legsa_v23_failure_classifier import classify_failure


def test_failure_classifier_prioritizes_config_before_yaw():
    decision = classify_failure(
        {"config_units_issue": True, "initatt_yaw_mismatch": True},
        {"first_epoch_time_alignment_issue": False},
        {"reject_reason_classification": ["yaw_convention_or_init_issue"]},
        {"recommended_issue_source": "likely_yaw_update_or_feedback_issue"},
    )
    assert decision["failure_classification"] == "config_unit_or_initialization_issue"
    assert decision["recommended_next_stage"] == "N4H4D_config_unit_fix"


def test_failure_classifier_maps_mechanization_source():
    decision = classify_failure(
        {},
        {"first_epoch_mechanization_jump_issue": True},
        {"reject_reason_classification": []},
        {"recommended_issue_source": "likely_mechanization_or_initialization_issue"},
    )
    assert decision["failure_classification"] == "mechanization_frame_or_gravity_issue"
    assert decision["recommended_next_stage"] == "N4H4D_mechanization_debug"

