"""Synthetic physical invariants only: no raw data, CILS, native or references."""
from dataclasses import replace
import math
import numpy as np
import pytest
from legsa_gins.paper_rebuild.carrier_phase.directed_motion import (
    DirectedMotionError, DirectedMotionPrior, qualify_directed_pair)


def rot(axis, angle):
    axis = np.asarray(axis, float)
    axis = axis / np.linalg.norm(axis)
    x, y, z = axis
    skew = np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])
    return np.eye(3) + math.sin(angle)*skew + (1-math.cos(angle))*(skew@skew)


def reflection_case():
    # R6 geometry, generated independently: x=.15 and a yz circle of radius sqrt(.1).
    length = .35
    radial = math.sqrt(length**2-.15**2)
    r = np.array([.15, 0., radial])
    d = rot([1., 0., 0.], math.pi/3)
    return r, d, np.diag([-1., 1., 1.]), np.array([0., 0., 1.])


def prior(r=None, d=None, q=None, g=None, eq=.001, ed=.002, **kwargs):
    rr, dd, _, gg = reflection_case()
    return DirectedMotionPrior(
        rr if r is None else r, dd if d is None else d,
        gg if g is None else g, gg if q is None else q, eq, ed,
        'SYNTHETIC_EXPLICIT_GEOMETRY', 'REGISTERED_DETERMINISTIC_TEST_BOUNDS',
        True, 'Exact constructed mounting and length, not real calibration', **kwargs)


def test_reflection_preserves_gram_and_height_but_reverses_signed_area():
    r, d, mirror, g = reflection_case()
    pair = np.array([r, d@r]); alias = pair@mirror.T
    np.testing.assert_allclose(pair@pair.T, alias@alias.T, atol=1e-16)
    np.testing.assert_allclose(pair@g, alias@g, atol=1e-16)
    area = float(g@np.cross(*pair)); wrong = float(g@np.cross(*alias))
    assert abs(area) > .01
    assert wrong == pytest.approx(-area)
    good = qualify_directed_pair(*pair, prior())
    bad = qualify_directed_pair(*alias, prior())
    assert good.status == 'FEASIBLE'
    assert bad.status == 'CONTRADICTION'
    assert bad.checks[0].consistent and bad.checks[1].consistent
    assert not bad.checks[2].consistent
    assert not good.integer_acceptance_defined and good.false_fix_probability is None


def test_physical_los_integer_alias_is_not_only_arbitrary_mirror():
    r, d, mirror, _ = reflection_case()
    lam = 299792458./1575420000.
    targets = []
    for y in [-.5, 0., .5]:
        x = -lam/.3
        targets.append([x, y, math.sqrt(1-x*x-y*y)])
    targets.append([0., .4, math.sqrt(1-.4**2)])
    targets = np.asarray(targets)
    np.testing.assert_allclose(np.linalg.norm(targets, axis=1), 1.)
    h = np.array([0., 0., 1.])-targets
    assert np.linalg.matrix_rank(h) == 3
    n = np.array([2, -3, 1, 4]); shift = np.array([1, 1, 1, 0])
    for b in [r, d@r]:
        np.testing.assert_allclose(lam*n+h@b, lam*(n+shift)+h@(mirror@b), atol=2e-16)


@pytest.mark.parametrize('d', [np.eye(3), rot([0., 1., 0.], 1e-7)])
def test_weak_excitation_unqualified(d):
    r = np.array([.35, 0., 0.])
    answer = qualify_directed_pair(r, d@r, prior(r=r, d=d))
    assert answer.status == 'UNQUALIFIED'
    assert answer.reason == 'DIRECTED_AREA_SIGN_UNRESOLVED'


def test_rotation_about_baseline_axis_gives_no_directional_qualification():
    r, _, _, _ = reflection_case()
    d = rot(r, .8)
    np.testing.assert_allclose(d@r, r, atol=1e-16)
    assert qualify_directed_pair(r, d@r, prior(r=r, d=d)).status == 'UNQUALIFIED'


@pytest.mark.parametrize('field', ['body_gravity_unit', 'navigation_gravity_unit'])
def test_unknown_gravity_is_not_filled_from_candidate(field):
    r, d, _, _ = reflection_case()
    answer = qualify_directed_pair(r, d@r, replace(prior(), **{field:None}))
    assert answer.status == 'UNQUALIFIED' and answer.reason == 'GRAVITY_UNKNOWN'


@pytest.mark.parametrize('field', ['gravity_angle_error_rad', 'rotation_angle_error_rad',
                                  'uncertainty_source_id'])
def test_missing_bounds_or_source_never_default_to_zero(field):
    r, d, _, _ = reflection_case()
    answer = qualify_directed_pair(r, d@r, replace(prior(), **{field:None}))
    assert answer.status == 'UNQUALIFIED'


def test_explicit_zero_bounds_need_justification():
    r, d, _, _ = reflection_case()
    p = prior(eq=0., ed=0.)
    assert qualify_directed_pair(r, d@r, p).reason == 'ZERO_ERROR_BOUND_UNJUSTIFIED'
    exact = replace(p, zero_error_justification='Known exact SO3 synthetic construction')
    assert qualify_directed_pair(r, d@r, exact).status == 'FEASIBLE'


def test_unknown_prior_and_withdrawal_restore_unqualified_state():
    r, d, _, _ = reflection_case()
    wrong_d = rot([1., 0., 0.], -math.pi/3)
    bad = prior(d=wrong_d)
    # Incorrect declared rotation domain can rule out the physical truth.
    assert qualify_directed_pair(r, d@r, bad).status == 'CONTRADICTION'
    assert qualify_directed_pair(r, d@r, replace(bad, qualified=False)).status == 'UNQUALIFIED'


def test_proper_so3_frame_changes_preserve_all_checks():
    r, d, _, g = reflection_case()
    p = prior()
    original = qualify_directed_pair(r, d@r, p)
    world = rot([1., 2., -1.], .71)
    nav = qualify_directed_pair(world@r, world@d@r,
                              replace(p, navigation_gravity_unit=world@g))
    body = rot([-1., 3., 1.], -.92)
    body_change = qualify_directed_pair(r, d@r, replace(p,
        body_baseline_m=body@r, body_gravity_unit=body@g,
        relative_rotation=body@d@body.T))
    for result in [nav, body_change]:
        assert result.status == original.status
        np.testing.assert_allclose([c.candidate_value for c in result.checks],
                                   [c.candidate_value for c in original.checks], atol=2e-16)
        np.testing.assert_allclose([c.nominal_value for c in result.checks],
                                   [c.nominal_value for c in original.checks], atol=2e-16)


def test_bound_contains_truth_for_fixed_finite_rotation_and_gravity_perturbations():
    # 5 axes x 5 axes x 3 edge/interior angles =75 deterministic bounded cases.
    # Generate R, q and D_true independently; never derive truth from the checks.
    r, d_nom, _, g = reflection_case()
    eq, ed = .02, .03
    axes = ([1.,0.,0.], [0.,1.,0.], [0.,0.,1.], [1.,2.,3.], [-2.,1.,1.])
    for a in axes:
        for b in axes:
            for fraction in [-1., 0., 1.]:
                world = rot(a, fraction*eq)
                q_true = world.T@g
                true_d = rot(b, fraction*ed)@d_nom
                p = prior(eq=eq, ed=ed)
                result = qualify_directed_pair(world@r, world@true_d@r, p)
                assert result.status == 'FEASIBLE'
                # Independently inspect the conservative analytic inequalities.
                h1 = g@(world@r); h2 = g@(world@true_d@r)
                tau = g@np.cross(world@r, world@true_d@r)
                assert abs(h1-g@r) <= 2*.35*math.sin(eq/2)+1e-15
                assert abs(h2-g@d_nom@r) <= 2*.35*(math.sin(eq/2)+math.sin(ed/2))+1e-15
                assert abs(tau-g@np.cross(r,d_nom@r)) <= 2*.35**2*(math.sin(eq/2)+math.sin(ed/2))+1e-15
                assert q_true@g >= math.cos(eq)-1e-15


def test_wide_uncertainty_must_not_use_nominal_signed_turn():
    r, d, _, _ = reflection_case()
    result = qualify_directed_pair(r, d@r, prior(eq=.8, ed=.8))
    assert result.reason == 'DIRECTED_AREA_SIGN_UNRESOLVED'
    assert not result.directed_sign_qualified


def test_height_contradiction_is_kept_when_directed_prior_is_qualified():
    r, d, _, _ = reflection_case()
    p = prior()
    # Rotate the physical pair away from the supplied gravity correspondence.
    wrong = rot([0., 1., 0.], .3)
    result = qualify_directed_pair(wrong@r, wrong@d@r, p)
    assert result.status == 'CONTRADICTION'
    assert not result.checks[0].consistent


@pytest.mark.parametrize('value', [-.1, math.pi+.01, float('nan'), float('inf'), True])
def test_invalid_error_bounds_rejected(value):
    with pytest.raises(DirectedMotionError):
        prior(eq=value)


def test_improper_rotation_units_lengths_and_silent_normalization_rejected():
    r, d, mirror, g = reflection_case()
    with pytest.raises(DirectedMotionError): prior(d=mirror)
    with pytest.raises(DirectedMotionError): prior(g=9.81*g)
    with pytest.raises(DirectedMotionError): qualify_directed_pair(r*1.001,d@r,prior())
    with pytest.raises(DirectedMotionError): replace(prior(),exact_geometry_justification='')


def test_input_arrays_copied_to_keep_bound_identity_stable():
    r, d, _, g = reflection_case()
    p = prior(r=r, d=d, q=g, g=g)
    before = qualify_directed_pair(r, d@r, p)
    r[:] = 0.; d[:] = 0.; g[:] = 0.
    after = qualify_directed_pair(p.body_baseline_m, p.relative_rotation@p.body_baseline_m, p)
    assert after == before
    assert not p.body_baseline_m.flags.writeable


def test_receiver_arrow_reversal_changes_both_mounting_and_candidates():
    r, d, _, _ = reflection_case()
    original = qualify_directed_pair(r, d@r, prior())
    reversed_pair = qualify_directed_pair(-r, -d@r, prior(r=-r))
    assert reversed_pair.status == original.status == 'FEASIBLE'
    assert reversed_pair.checks[0].candidate_value == pytest.approx(-original.checks[0].candidate_value)
    assert reversed_pair.checks[2].candidate_value == pytest.approx(original.checks[2].candidate_value)


def test_representation_tolerance_is_not_mistaken_for_exact_sensor_error():
    r, d, _, g = reflection_case()
    p = prior(g=g*(1+8e-13), eq=0., ed=0.,
              zero_error_justification='Synthetic exact limiting domain')
    result = qualify_directed_pair(r, d@r, p)
    assert result.status == 'FEASIBLE'
    assert all(c.arithmetic_margin > 0. for c in result.checks)
