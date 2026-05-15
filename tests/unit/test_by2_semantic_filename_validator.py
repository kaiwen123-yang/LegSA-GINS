from legsa_gins.reporting.by2_semantic_filename_validator import detect_n8k3_semantic_filename_mismatches, validate_semantic_filename_entries

# 中文说明：validator 必须能发现 N8K3 错位并接受 N8K4 修复后的角色。


def test_detect_n8k3_semantic_filename_mismatches():
    report = {
        "fixed_entries": [
            {"variant_id": "A", "category": "04_attitude", "filename": "yaw_residual_time.png", "semantic_fix": "yaw_wrap_consistency_panel"},
            {"variant_id": "A", "category": "07_compare", "filename": "compare_horizontal_error.png", "semantic_fix": "reject_all_compare_semantics"},
            {"variant_id": "A", "category": "11_feedback", "filename": "feedback_accept_reject_timeline.png", "semantic_fix": "feedback_reject_all_semantics"},
        ]
    }
    mismatches = detect_n8k3_semantic_filename_mismatches(report)
    assert len(mismatches) == 3


def test_validate_semantic_filename_entries_after_fix():
    entries = [
        {"variant_id": "A", "category": "04_attitude", "filename": "yaw_residual_time.png", "semantic_role": "yaw_residual_time_series", "title": "Yaw residual time series", "documented_not_applicable": False},
        {"variant_id": "A", "category": "04_attitude", "filename": "yaw_wrap_check.png", "semantic_role": "yaw_wrap_consistency_check", "title": "Yaw wrap consistency check", "documented_not_applicable": False},
        {"variant_id": "A", "category": "07_compare", "filename": "compare_horizontal_error.png", "semantic_role": "horizontal_error_comparison", "title": "Baseline horizontal error comparison", "documented_not_applicable": False},
        {"variant_id": "A", "category": "07_compare", "filename": "reject_all_sanity_compare.png", "semantic_role": "reject_all_sanity_compare", "title": "Reject-all sanity not applicable", "documented_not_applicable": True, "not_applicable_reason": "reject-all sanity only applies to feedback variants / no feedback rows"},
    ]
    assert validate_semantic_filename_entries(entries) == []


def test_validate_n8k5_cross_category_semantic_entries():
    entries = [
        {"variant_id": "A", "category": "07_compare", "filename": "compare_velocity_error.png", "semantic_role": "velocity_error_comparison", "title": "Compare baseline vs variant velocity error", "documented_not_applicable": False},
        {"variant_id": "A", "category": "06_observation_quality", "filename": "feedback_accept_reject_time.png", "semantic_role": "feedback_observation_quality_timeline", "title": "Feedback observation quality not applicable", "documented_not_applicable": True, "not_applicable_reason": "no feedback rows / feedback disabled for this variant"},
        {"variant_id": "A", "category": "07_compare", "filename": "compare_feedback_delta.png", "semantic_role": "feedback_delta_comparison", "title": "Feedback delta comparison not applicable", "documented_not_applicable": True, "not_applicable_reason": "feedback delta comparison only applies to feedback variants / no feedback rows"},
    ]
    assert validate_semantic_filename_entries(entries) == []


def test_validate_rejects_cross_category_role_leakage():
    entries = [
        {"variant_id": "A", "category": "07_compare", "filename": "compare_velocity_error.png", "semantic_role": "velocity_residual_time_series", "title": "Velocity residual time series", "documented_not_applicable": False},
        {"variant_id": "A", "category": "07_compare", "filename": "compare_feedback_delta.png", "semantic_role": "feedback_observation_quality_timeline", "title": "Feedback accept/reject timeline", "documented_not_applicable": False},
    ]
    mismatches = validate_semantic_filename_entries(entries)
    assert {item["reason"] for item in mismatches} >= {"semantic_role_mismatch", "compare_velocity_error_mapped_to_velocity_residual", "compare_feedback_delta_mapped_to_feedback_timeline"}
