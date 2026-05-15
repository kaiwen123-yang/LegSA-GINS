from legsa_gins.reporting.by2_real_plot_decision import build_real_plot_decision

# 中文说明：决策逻辑要求 placeholder、缺失和重复模板全部清零才通过。


def test_real_plot_decision_passes():
    decision = build_real_plot_decision({"applicable_placeholder_count": 0, "unresolved_missing_data_count": 0, "missing_real_plot_count": 0, "duplicate_template_suspect_count": 0, "all_categories_complete": True})
    assert decision["status"] == "BY2_formal_ablation_real_plot_fix_complete"
