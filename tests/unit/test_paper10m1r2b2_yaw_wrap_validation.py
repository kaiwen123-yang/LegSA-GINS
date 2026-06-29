from legsa_gins.degradation.yaw_wrap_validation import validate_yaw_wrap


def test_wrap_validation_passes_wrapped_sequence() -> None:
    result = validate_yaw_wrap([{"yaw_deg": "359.0"}, {"yaw_deg": "1.0"}])
    assert result["yaw_wrap_validation_status"] == "PASS"


def test_wrap_validation_rejects_out_of_range_yaw() -> None:
    result = validate_yaw_wrap([{"yaw_deg": "361.0"}])
    assert result["yaw_wrap_validation_status"] == "FAIL"

