from legsa_gins.da_repro.yaw_frame_contract import synthetic_yaw_frame_checks, yaw_error_deg


def test_da3r2_yaw_frame_contract():
    assert all(row["passed"] == "true" for row in synthetic_yaw_frame_checks())
    assert abs(abs(yaw_error_deg(179.0, -179.0)) - 2.0) < 1e-9
