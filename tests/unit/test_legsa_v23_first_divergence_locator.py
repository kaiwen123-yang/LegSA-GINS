from legsa_gins.evaluation.legsa_v23_first_divergence_locator import classify_first_divergence


"""中文说明：首次发散 locator 只分类诊断时序，不修改 solver 输出。"""


def test_first_divergence_category_before_update():
    report = classify_first_divergence(
        {"first_divergence_time": 1.0, "first_update_time": 2.0, "divergence_before_first_update": True}
    )
    assert report["first_divergence_category"] == "before_first_update"
