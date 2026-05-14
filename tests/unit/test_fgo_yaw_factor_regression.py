"""中文说明：测试 N8A2 yaw factor 回归报告。"""

from legsa_gins.fgo.fgo_yaw_factor_regression import build_yaw_factor_regression_report


def test_yaw_factor_regression_passes_wrap_cases() -> None:
    report = build_yaw_factor_regression_report()
    assert report["smoothness_359_1_pass"] is True
    assert report["dual_yaw_1_359_pass"] is True
    assert report["continuous_sequence_no_large_spike"] is True
    assert report["finite_residual_vector"] is True
    assert report["all_tests_passed"] is True
