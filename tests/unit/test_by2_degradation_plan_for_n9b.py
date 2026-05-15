from legsa_gins.reporting.by2_degradation_plan_for_n9b import build_n9b_degradation_plan

# 中文说明：退化计划测试确认 N8K 只写计划不执行。


def test_by2_degradation_plan_is_plan_only():
    report = build_n9b_degradation_plan()
    assert report["plan_only"] is True
    assert report["degradation_matrix_run"] is False
    assert "combined_degradation" in report["n9b_extended_degradations"]
