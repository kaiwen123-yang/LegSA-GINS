"""中文说明：测试 N8A2 yaw residual 合同。"""

from legsa_gins.fgo.fgo_yaw_residuals import (
    build_yaw_residual_contract_report,
    dual_yaw_residual_deg,
    yaw_rate_between_residual_deg,
    yaw_smoothness_residual_deg,
)


def test_yaw_residual_contract_examples() -> None:
    assert dual_yaw_residual_deg(1.0, 359.0) == 2.0
    assert yaw_smoothness_residual_deg(359.0, 1.0) == 2.0
    assert yaw_rate_between_residual_deg(359.0, 1.0, 1.0, 1.0) == 1.0


def test_yaw_residual_contract_report_boundaries() -> None:
    report = build_yaw_residual_contract_report()
    assert report["dual_yaw_wrap"] is True
    assert report["smoothness_wrap"] is True
    assert report["yaw_rate_wrap"] is True
    assert report["output_only_yaw_correction"] is False
