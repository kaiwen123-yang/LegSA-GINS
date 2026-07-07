from legsa_gins.da_repro.yaw_frame_contract import (
    baseline_heading_from_enu,
    body_yaw_from_lateral_baseline,
    make_yaw_frame_contract,
    synthetic_contract_test,
    yaw_residual_deg,
)


def test_yaw_frame_contract_is_lateral_and_wrap_safe():
    contract = make_yaw_frame_contract()
    assert contract["baseline_heading_is_body_yaw"] is False
    assert contract["trace_rmse_selected_sign"] is False
    assert baseline_heading_from_enu(0.0, 1.0) == 0.0
    assert body_yaw_from_lateral_baseline(0.0) == 90.0
    assert yaw_residual_deg(1.0, 359.0) == 2.0
    assert synthetic_contract_test()["passed"] is True
