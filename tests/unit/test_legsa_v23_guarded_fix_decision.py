"""中文说明：N4H4D3 guarded fix decision 单元测试。"""

from legsa_gins.evaluation.legsa_v23_guarded_fix_decision import make_guarded_fix_decision


def test_guarded_fix_decision_pass_partial_and_no_improvement():
    audit = {"audit_status": "passed", "yaw_H_mapping_secondary_issue": True}
    passed = make_guarded_fix_decision(audit, {"summary": {"guarded_fix_parity_status": "passed"}, "gap_screen": {}})
    assert passed["recommended_next_stage"] == "N4H4E_visual_validation_for_legsa_v23_core"

    partial = make_guarded_fix_decision(
        audit,
        {
            "summary": {"guarded_fix_parity_status": "partial_improvement"},
            "gap_screen": {"gap_classification": ["mechanization_update"], "blocking_issues": ["yaw_diverges_gt_10deg"]},
        },
        {"multi_issue_or_coupled_issue": True},
    )
    assert partial["recommended_next_stage"] == "N4H4D4_remaining_yaw_or_update_fix"
    assert "D2_multi_issue_or_coupled_issue" in partial["blocking_issues"]

    failed = make_guarded_fix_decision(audit, {"summary": {"guarded_fix_parity_status": "no_improvement"}, "gap_screen": {}})
    assert failed["recommended_next_stage"] == "N4H4D4_revisit_mechanization_or_time_alignment"

    audit_failed = make_guarded_fix_decision({"audit_status": "failed"}, {"summary": {"guarded_fix_parity_status": "passed"}})
    assert audit_failed["recommended_next_stage"] == "N4H4D3_fix_source_backed_formula_implementation"

