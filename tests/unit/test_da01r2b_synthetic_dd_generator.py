from legsa_gins.da_repro.synthetic_dd_generator import (
    BASELINE_LENGTH_M,
    BODY_YAW_CASES_DEG,
    baseline_enu_from_body_yaw,
    generate_synthetic_suite,
)
from legsa_gins.da_repro.yaw_frame_contract import baseline_heading_from_enu, body_yaw_from_lateral_baseline, yaw_residual_deg


def test_synthetic_generator_lateral_geometry_and_counts():
    cases = generate_synthetic_suite(noise_levels_m=(0.0,))
    assert len(cases) == len(BODY_YAW_CASES_DEG)
    for case in cases:
        assert len(case.rows) == 7
        length = sum(value * value for value in case.baseline_enu) ** 0.5
        assert abs(length - BASELINE_LENGTH_M) < 1.0e-9
        heading = baseline_heading_from_enu(case.baseline_east_m, case.baseline_north_m)
        body_yaw = body_yaw_from_lateral_baseline(heading, offset_deg=90.0)
        assert abs(yaw_residual_deg(body_yaw, case.body_yaw_deg)) < 1.0e-9
        assert not case.trace_used
        assert not case.cycle_slip


def test_baseline_enu_from_body_yaw_known_cases():
    east, north, up = baseline_enu_from_body_yaw(0.0)
    assert east < -0.35
    assert abs(north) < 1.0e-9
    assert up == 0.0
    east_90, north_90, _ = baseline_enu_from_body_yaw(90.0)
    assert abs(east_90) < 1.0e-9
    assert north_90 > 0.35
