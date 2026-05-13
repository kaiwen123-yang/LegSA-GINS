from legsa_gins.go2_prior.go2_n7c6_final_decision import make_n7c6a_final_decision


def test_n7c6a_ready_decision() -> None:
    """中文说明：ready 状态必须同时满足语义、图像、NIS 和边界门禁。"""
    decision = make_n7c6a_final_decision(
        input_manifest={"n7c6_reports_all_found": True},
        semantic_report={"metric_semantic_status": "passed_with_runtime_replacements"},
        readability_report={"plot_label_readability_status": "passed_with_runtime_replacements"},
        figure_manifest={"required_figures_generated": True, "required_figures_nonempty": True},
        n7c6_decision={"status": "stronger_go2_proprioceptive_joint_factor_ready"},
        nis_report={"any_overconfidence": False, "any_stuck_at_cap": False},
    )
    assert decision["status"] == "ready_to_merge_PR38_and_start_N8A"
    assert decision["paper_performance_claim"] is False
