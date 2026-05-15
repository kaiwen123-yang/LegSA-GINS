from legsa_gins.reporting.by2_formal_ablation_decision import build_n8k_decision

# 中文说明：决策测试覆盖 N8K 完成态和禁用退化矩阵边界。


def test_by2_formal_ablation_decision_passes_complete_audit():
    decision = build_n8k_decision(
        {"variant_count": 30, "completed_count": 30, "failed_count": 0},
        {"all_required_categories_complete": True, "total_png_figures_generated": 1, "missing_count": 0},
        {"all_checks_passed": True},
        {"degradation_matrix_run": False},
    )
    assert decision["status"] == "BY2_formal_ablation_plot_audit_complete"
    assert decision["degradation_matrix_run"] is False
