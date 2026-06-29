from legsa_gins.degradation.yaw_time_resampler import interpolate_yaw_deg


def test_wrap_safe_interpolation_crosses_zero() -> None:
    rows = [{"time": 0.0, "yaw_deg": 359.0}, {"time": 1.0, "yaw_deg": 1.0}]
    assert abs(interpolate_yaw_deg(rows, 0.5) - 0.0) < 1.0e-9

