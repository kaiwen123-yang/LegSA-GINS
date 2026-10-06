import numpy as np
from legsa_gins.paper_rebuild.hext.hx05_leg_dr import kinematic_velocity, integrate


def test_rotational_cross_term_and_contact_selection():
    gyro = np.array([[0., 0., 2.]])
    feet = np.array([[[1., 0., 0.], [90., 90., 90.]]])
    speed = np.array([[[1., 0., 3.], [90., 90., 90.]]])
    np.testing.assert_array_equal(kinematic_velocity(gyro, feet, speed, np.array([[True, False]])), [[-1., -2., -3.]])


def test_gap_skips_both_adjacent_intervals_and_integrates_vertical():
    velocity = np.array([[1., 0., 2.], [3., 0., 4.], [np.nan]*3, [7., 0., 8.], [9., 0., 10.]])
    position, receipt = integrate(np.arange(5.), velocity)
    np.testing.assert_array_equal(position, [[0., 0., 0.], [2., 0., 3.], [2., 0., 3.], [2., 0., 3.], [10., 0., 12.]])
    assert receipt['unobserved_interval_count'] == 2
    assert receipt['unobserved_duration_s'] == 2


def test_no_contact_is_missing_velocity():
    result = kinematic_velocity(np.zeros((1, 3)), np.zeros((1, 4, 3)), np.zeros((1, 4, 3)), np.zeros((1, 4), bool))
    assert np.isnan(result).all()
