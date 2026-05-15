from legsa_gins.reporting.by2_formal_ablation_spec import build_formal_ablation_matrix, build_formal_ablation_spec, formal_ablation_variants

# 中文说明：测试正式消融矩阵定义完整且不运行退化矩阵。


def test_by2_formal_ablation_spec_has_required_variants():
    variants = formal_ablation_variants()
    assert len(variants) == 30
    ids = {item.variant_id for item in variants}
    assert "A8_feedback_selected_conservative_gate" in ids
    assert "C9_selected_without_feedback" in ids
    spec = build_formal_ablation_spec({"n8j": "role"})
    matrix = build_formal_ablation_matrix(spec)
    assert matrix["completed_count"] == 30
    assert matrix["degradation_matrix_run"] is False
