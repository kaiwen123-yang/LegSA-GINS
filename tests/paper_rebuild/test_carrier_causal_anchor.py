"""Causal anchor state and independent finite-difference geometry checks.

Synthetic only; no original data, SPP, CILS, navigation solver, or reference.
"""
from types import SimpleNamespace
import numpy as np
import pytest

from legsa_gins.paper_rebuild.carrier_phase.causal_anchor import (
    AnchorPolicy, CausalRawCodeAnchor, pair_geometry_anchor_jacobian,
    dd_anchor_sensitivity,
)
from legsa_gins.paper_rebuild.horizontal_literature.reproduction_backend import pair_geometry

ANCHOR = np.array([-2171500., 4385500., 4076700.])
TARGET = (np.array([15600000., 20100000., 8000000.]),
          np.array([15600300., 20099900., 8000050.]))
PIVOT = (np.array([-12000000., 9000000., 21000000.]),
         np.array([-12000040., 9000120., 21000060.]))


def test_missing_initial_anchor_and_causal_hold():
    state = CausalRawCodeAnchor()
    missing = state.resolve(100., failure="SPP_RANK_DEFICIENT")
    assert not missing.available and missing.source_time_s is None
    assert missing.spp_failure == "SPP_RANK_DEFICIENT"
    point = ANCHOR.copy()
    current = state.resolve(100.2, point)
    point[:] = 0  # Caller mutation cannot rewrite the held anchor.
    assert current.available and not current.held and current.age_s == 0.
    held = state.resolve(103., failure="SPP_RANK_DEFICIENT")
    assert held.held and held.source_time_s == 100.2
    assert held.age_s == pytest.approx(2.8)
    assert held.assumed_error_radius_m == pytest.approx(114.)
    assert held.position_ecef_m == tuple(ANCHOR)
    assert not held.navigation_measurement
    assert held.assumption_label == "ENGINEERING_RADIUS_NOT_CALIBRATED_CONFIDENCE"


def test_age_boundary_expiration_and_new_success():
    state = CausalRawCodeAnchor()
    state.resolve(10., ANCHOR)
    assert state.resolve(30., failure="missing").held
    expired = state.resolve(30.000001, failure="missing")
    assert expired.status == "UNAVAILABLE_HOLD_TOO_OLD" and not expired.available
    assert expired.source_time_s == 10. and expired.age_s > 20
    renewed = state.resolve(31., ANCHOR + 3)
    assert renewed.source_time_s == 31. and renewed.age_s == 0.
    np.testing.assert_array_equal(renewed.position_ecef_m, ANCHOR + 3)


@pytest.mark.parametrize("time", [10., 9., float("nan"), float("inf")])
def test_future_interpolation_and_duplicate_calls_rejected(time):
    state = CausalRawCodeAnchor()
    state.resolve(10., ANCHOR)
    with pytest.raises(ValueError, match="STRICTLY_INCREASING"):
        state.resolve(time, ANCHOR + 1)
    held = state.resolve(11., failure="missing")
    assert held.source_time_s == 10. and held.age_s == 1.


@pytest.mark.parametrize("point", [[1., 2.], [1., 2., float("nan")], ["bad", 2., 3.]])
def test_invalid_current_position_does_not_overwrite_prior(point):
    state = CausalRawCodeAnchor()
    state.resolve(0., ANCHOR)
    bad = state.resolve(1., point)
    assert bad.status == "UNAVAILABLE_INVALID_CURRENT_ANCHOR"
    assert not bad.available and bad.source_time_s == 0.
    held = state.resolve(2., failure="missing")
    assert held.held and held.age_s == 2. and held.position_ecef_m == tuple(ANCHOR)


def test_conflicting_success_and_failure_do_not_advance_time():
    state = CausalRawCodeAnchor()
    with pytest.raises(ValueError, match="CONFLICT"):
        state.resolve(1., ANCHOR, failure="failed")
    assert state.resolve(1., ANCHOR).available


@pytest.mark.parametrize("field,value", [
    ("max_hold_age_s", -1), ("max_hold_age_s", float("inf")),
    ("initial_error_radius_m", -1), ("initial_error_radius_m", float("nan")),
    ("motion_bound_mps", -1), ("motion_bound_mps", float("inf")),
])
def test_invalid_policy(field, value):
    with pytest.raises(ValueError):
        AnchorPolicy(**{field: value})


def _pair(states, anchor):
    # Independent evaluation uses the actual existing pair_geometry function,
    # not the differentiated implementation under test.
    class Provider:
        def state(self, identity, week, tow, pseudorange):
            k = 0 if pseudorange == 21000000. else 1
            return SimpleNamespace(position_ecef_m=states[k], health=0,
                                   clock_bias_s=(k + 1) * 1e-5)
    epoch = SimpleNamespace(gps_week=2408, gps_tow_seconds=100.)
    measurements = [SimpleNamespace(identity="test", pseudorange_valid=True,
                                     pr_mes_m=p) for p in (21000000., 21000010.)]
    return pair_geometry(epoch, epoch, *measurements, Provider(), anchor)


@pytest.mark.parametrize("states", [TARGET, PIVOT])
def test_pair_gradient_matches_actual_four_rotation_geometry(states):
    result = pair_geometry_anchor_jacobian(*states, ANCHOR)
    base = _pair(states, ANCHOR)
    np.testing.assert_allclose(result.los1, base.los1, atol=1e-15)
    np.testing.assert_allclose(result.los2, base.los2, atol=1e-15)
    # A 100 m central step avoids subtractive range cancellation while its
    # relative distance to the satellite is < 1e-5.
    step = 100.
    numerical_g = []
    numerical_u = []
    for direction in np.eye(3):
        plus = _pair(states, ANCHOR + step * direction)
        minus = _pair(states, ANCHOR - step * direction)
        numerical_g.append((plus.known_sd_m - minus.known_sd_m) / (2 * step))
        numerical_u.append((plus.los2 - minus.los2) / (2 * step))
    np.testing.assert_allclose(result.known_sd_gradient, numerical_g, atol=8e-11, rtol=2e-5)
    np.testing.assert_allclose(result.los2_jacobian, np.asarray(numerical_u).T,
                               atol=2e-16, rtol=2e-8)


def test_dd_gradient_includes_own_transmit_state_term_and_baseline():
    one = pair_geometry_anchor_jacobian(*TARGET, ANCHOR)
    two = pair_geometry_anchor_jacobian(*PIVOT, ANCHOR)
    length = .35
    baseline = np.array([.1, -.2, .3]); baseline *= length / np.linalg.norm(baseline)
    sensitivity = dd_anchor_sensitivity(one, two, length_m=length)
    assert sensitivity.known_sd_coefficient > 10 * sensitivity.baseline_coefficient
    actual = sensitivity.gradient_at_baseline(baseline)
    numerical = []
    for direction in np.eye(3):
        def h(point):
            target, pivot = _pair(TARGET, point), _pair(PIVOT, point)
            return (target.known_sd_m - pivot.known_sd_m
                    - (target.los2 - pivot.los2) @ baseline)
        numerical.append((h(ANCHOR + 100 * direction) - h(ANCHOR - 100 * direction)) / 200)
    np.testing.assert_allclose(actual, numerical, atol=1.2e-10, rtol=2e-5)
    assert np.linalg.norm(actual) <= sensitivity.first_order_coefficient
    reverse = dd_anchor_sensitivity(two, one, length_m=length)
    np.testing.assert_allclose(reverse.gradient_at_baseline(baseline), -actual)
    assert reverse.first_order_coefficient == pytest.approx(sensitivity.first_order_coefficient)


def test_equal_receiver_transmit_states_cancel_known_sd_but_not_baseline():
    one = pair_geometry_anchor_jacobian(TARGET[0], TARGET[0], ANCHOR)
    two = pair_geometry_anchor_jacobian(PIVOT[0], PIVOT[0], ANCHOR)
    sensitivity = dd_anchor_sensitivity(one, two, length_m=.35)
    assert sensitivity.known_sd_coefficient == 0.
    assert sensitivity.baseline_coefficient > 0.
    assert sensitivity.first_order_coefficient == sensitivity.baseline_coefficient


def test_common_target_and_pivot_geometry_has_zero_sensitivity():
    one = pair_geometry_anchor_jacobian(*TARGET, ANCHOR)
    sensitivity = dd_anchor_sensitivity(one, one, length_m=.35)
    assert sensitivity.first_order_coefficient == 0.
    np.testing.assert_array_equal(sensitivity.gradient_at_baseline([.35, 0., 0.]), np.zeros(3))


@pytest.mark.parametrize("satellite", [[float("nan"), 1., 2.], [1., 2.], [1e9, 0., 0.]])
def test_invalid_geometry_rejected(satellite):
    with pytest.raises(ValueError):
        pair_geometry_anchor_jacobian(satellite, TARGET[1], ANCHOR)
