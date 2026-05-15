from legsa_gins.reporting.n9a_by2_full_plot_audit import CATEGORY_SCHEMA, discover_n9a_inputs


# 中文说明：N9A 必须使用用户指定的 01-14 分类体系，不能回退到旧绘图目录。


def test_n9a_schema_has_unified_01_14_categories():
    assert list(CATEGORY_SCHEMA) == [
        "01_trajectory",
        "02_position_errors",
        "03_velocity",
        "04_attitude",
        "05_consistency",
        "06_observation_quality",
        "07_compare",
        "08_summary_panels",
        "09_case_review",
        "10_fgo_factors",
        "11_feedback",
        "12_legged_factors",
        "13_degradation_meta",
        "14_audit_sanity",
    ]
    assert "path_leak_check.png" in CATEGORY_SCHEMA["14_audit_sanity"]
    assert "degradation_mask.png" in CATEGORY_SCHEMA["13_degradation_meta"]


def test_n9a_input_discovery_fails_missing_root(tmp_path):
    report = discover_n9a_inputs(tmp_path / "missing")
    assert report["enough_to_generate_full_plot_audit"] is False
    assert "BY2 plot root does not exist" in report["cannot_proceed_reasons"]
