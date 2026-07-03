from legsa_gins.external_literature.yaw_frame_contract import (
    baseline_heading_to_body_yaw_deg,
    body_yaw_to_lateral_baseline_heading_deg,
    synthetic_yaw_frame_checks,
    yaw_residual_deg,
)


def test_da2r2_synthetic_yaw_frame_contract():
    checks = synthetic_yaw_frame_checks()
    assert checks
    assert all(checks.values())
    assert baseline_heading_to_body_yaw_deg(270.0) == 0.0
    assert body_yaw_to_lateral_baseline_heading_deg(90.0) == 0.0
    assert yaw_residual_deg(179.0, -179.0) == -2.0
