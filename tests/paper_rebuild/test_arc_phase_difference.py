"""Independent synthetic qualification of the unfixed two-epoch contrast.

No raw files, evaluation reference, native solver or integer search is used.
The physical generator works in SD space and never calls the production
integer-design or path routines to create measurements/covariance oracles.
"""
from dataclasses import replace
import numpy as np
import pytest

from legsa_gins.paper_rebuild.carrier_phase.arc_relations import (
    SdArcNode, DdArcRelation,
)
from legsa_gins.paper_rebuild.carrier_phase.arc_phase_difference import (
    ArcPhaseDifferenceError, PhaseEpoch, PhaseArcContinuity, PhaseAttitudeState,
    build_phase_difference, difference_cross_covariance,
)

BASELINE = np.array([0.023, -0.347, 0.019])
BODY = "SYNTHETIC_BODY_FRD"
RNG_SEED = 20261007


def skew(v):
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def exp_rotation(v):
    v = np.asarray(v, float)
    angle = np.linalg.norm(v)
    if angle == 0:
        return np.eye(3)
    k = skew(v / angle)
    return np.eye(3) + np.sin(angle)*k + (1-np.cos(angle))*(k@k)


def node(sv, token="arc0", sig=0):
    return SdArcNode(f"0:{sv}:{sig}:0", token)


def oracle_wavelength(n):
    # Independent known GPS L1/L2 frequencies, not signal_spec/_wavelength.
    sig = int(n.signal.split(":")[2])
    return 299792458. / {0: 1575.42e6, 3: 1227.60e6}[sig]


def make_epoch(time, nodes, los, rotation, integers, *, pivot=0, errors=None,
               sd_cov=None, relations=None, epoch_id=None):
    nodes = tuple(nodes)
    if relations is None:
        relations = tuple(DdArcRelation(n, nodes[pivot]) for n in nodes
                          if n != nodes[pivot])
    relations = tuple(relations)
    index = {n: i for i, n in enumerate(nodes)}
    transform = np.zeros((len(relations), len(nodes)))
    for row, relation in enumerate(relations):
        transform[row, index[relation.target]] = 1.
        transform[row, index[relation.pivot]] = -1.
    if errors is None:
        errors = np.zeros(len(nodes))
    if sd_cov is None:
        sd_cov = np.diag(np.linspace(1., 2., len(nodes))*1e-4)
    baseline_ecef = rotation @ BASELINE
    # Define SD = receiver2 - receiver1 range/phase. Geometric SD is -u.b.
    sd_phase = np.array([
        -los[i] @ baseline_ecef + oracle_wavelength(n)*integers[n] + errors[i]
        for i, n in enumerate(nodes)
    ])
    geometry = -transform @ los
    epoch = PhaseEpoch(
        time, time + .03, epoch_id or f"epoch-{time}", f"generated-{time}",
        "rx1-right--rx2-left", "SYNTHETIC_GPS_SECONDS",
        "SD_RX2_RX1__DD_TARGET_PIVOT_METRES",
        f"own-epoch-geometry-{time}", f"latent-covariance-{time}",
        relations, transform @ sd_phase, geometry, transform @ sd_cov @ transform.T,
    )
    return epoch, transform


def fixture_epochs():
    nodes = tuple(node(i) for i in range(1, 6))
    # Five deliberately noncoplanar unit line-of-sight vectors.
    los0 = np.array([[.7, .2, .8], [-.4, .8, .3], [.1, -.9, .6],
                     [.9, -.1, -.3], [-.6, -.5, .8]])
    los0 /= np.linalg.norm(los0, axis=1)[:, None]
    los1 = los0 + np.array([[.01, -.02, .01], [.03, .01, -.04],
                            [-.01, .04, -.02], [.02, .02, .03],
                            [-.03, .01, .02]])
    los1 /= np.linalg.norm(los1, axis=1)[:, None]
    rot0 = exp_rotation([.1, -.2, .3])
    rot1 = exp_rotation([-.17, .14, .51])
    integers = dict(zip(nodes, [43, -17, 109, 8, -72]))
    e0, _ = make_epoch(100., nodes, los0, rot0, integers)
    e1, _ = make_epoch(100.8, nodes, los1, rot1, integers)
    return nodes, los0, los1, rot0, rot1, integers, e0, e1


def factor(e0, e1, *, continuous=None, continuity=None, **kwargs):
    if continuity is None:
        if continuous is None:
            continuous = tuple(set(e0.nodes) & set(e1.nodes))
        continuity = PhaseArcContinuity(
            e0.time_s, e1.time_s, e1.available_time_s,
            e0.receiver_pair_id, "whole-interval-physical-token-record", continuous)
    defaults = dict(
        covariance_mode="WORKING_ZERO_CROSS",
        covariance_source_id="declared-local-working-covariance",
        covariance_stack_m2=None,
        decision_available_time_s=max(e0.available_time_s, e1.available_time_s,
                                      continuity.available_time_s),
        baseline_body_m=BASELINE, body_frame_id=BODY,
        baseline_source_id="synthetic-rigid-installation")
    defaults.update(kwargs)
    return build_phase_difference(e0, e1, continuity, **defaults)


def state(epoch, rotation):
    return PhaseAttitudeState(
        epoch.time_s, epoch.available_time_s, rotation, BODY,
        f"synthetic-truth-linearization-{epoch.time_s}")


def test_constant_arbitrary_integers_cancel_with_moving_geometry(record_property):
    nodes, l0, l1, r0, r1, _, e0, e1 = fixture_epochs()
    first = factor(e0, e1)
    changed = dict(zip(nodes, [-203, 901, 7, -45, 156]))
    a, _ = make_epoch(e0.time_s, nodes, l0, r0, changed)
    b, _ = make_epoch(e1.time_s, nodes, l1, r1, changed)
    second = factor(a, b)
    # Direct SD oracle; no production F/A or graph is used.
    delta_sd = -l1 @ (r1 @ BASELINE) + l0 @ (r0 @ BASELINE)
    expected = np.array([delta_sd[i]-delta_sd[0] for i in range(1, len(nodes))])
    np.testing.assert_allclose(first.z_m, expected, atol=3e-14, rtol=0)
    np.testing.assert_allclose(second.z_m, expected, atol=1e-13, rtol=0)
    lin = first.linearize(state(e0, r0), state(e1, r1))
    np.testing.assert_allclose(lin.residual_m, 0., atol=3e-14, rtol=0)
    wrong_same_geometry = first.G0 @ ((r1-r0) @ BASELINE)
    assert np.linalg.norm(expected-wrong_same_geometry) > .001
    assert not first.integer_values_used
    assert not first.accepted_integer_measurement
    assert not first.covariance_calibrated
    assert not first.state_measurement_independence_established
    record_property("max_exact_model_residual_m", float(np.max(abs(lin.residual_m))))
    record_property("incorrect_frozen_geometry_error_norm_m",
                    float(np.linalg.norm(expected-wrong_same_geometry)))


def test_left_ecef_jacobian_finite_difference_and_baseline_gauges(record_property):
    _, _, _, r0, r1, _, e0, e1 = fixture_epochs()
    f = factor(e0, e1)
    lin = f.linearize(state(e0, r0), state(e1, r1))
    numerical = np.zeros_like(lin.prediction_jacobian_ecef_left)
    eps = 1e-7
    for axis in range(6):
        v = np.zeros(3); v[axis % 3] = eps
        plus = [r0, r1]; minus = [r0, r1]
        endpoint = axis // 3
        plus[endpoint] = exp_rotation(v) @ plus[endpoint]
        minus[endpoint] = exp_rotation(-v) @ minus[endpoint]
        fp = f.linearize(state(e0, plus[0]), state(e1, plus[1]))
        fm = f.linearize(state(e0, minus[0]), state(e1, minus[1]))
        numerical[:, axis] = (fp.prediction_m-fm.prediction_m)/(2*eps)
        np.testing.assert_allclose(
            (fp.residual_m-fm.residual_m)/(2*eps),
            lin.residual_jacobian_ecef_left[:, axis], atol=2e-9, rtol=0)
    error = np.max(abs(numerical-lin.prediction_jacobian_ecef_left))
    assert error < 2e-9
    h = lin.prediction_jacobian_ecef_left
    np.testing.assert_allclose(h @ np.r_[r0 @ BASELINE, np.zeros(3)], 0., atol=1e-16)
    np.testing.assert_allclose(h @ np.r_[np.zeros(3), r1 @ BASELINE], 0., atol=1e-16)
    assert lin.rank <= 4
    np.testing.assert_allclose(h @ lin.nullspace_ecef_left, 0., atol=1e-15)
    record_property("left_jacobian_max_abs_error", float(error))
    record_property("moving_two_pose_rank", lin.rank)


def test_static_same_geometry_has_common_rotation_gauge():
    nodes, l0, _, r0, _, ints, e0, _ = fixture_epochs()
    e1, _ = make_epoch(100.8, nodes, l0, r0, ints)
    f = factor(e0, e1)
    lin = f.linearize(state(e0, r0), state(e1, r0))
    np.testing.assert_allclose(f.z_m, 0., atol=1e-14)
    np.testing.assert_allclose(lin.prediction_jacobian_ecef_left @ np.vstack(
        [np.eye(3), np.eye(3)]), 0., atol=1e-16)
    assert lin.rank == 2
    assert lin.nullspace_ecef_left.shape == (6, 4)
    common = exp_rotation([.23, -.32, .14])
    other = f.linearize(state(e0, common@r0), state(e1, common@r0))
    np.testing.assert_allclose(other.prediction_m, 0., atol=1e-16)


def test_changed_geometry_is_not_falsely_given_common_rotation_gauge():
    _, _, _, r0, r1, _, e0, e1 = fixture_epochs()
    lin = factor(e0, e1).linearize(state(e0, r0), state(e1, r1))
    assert np.linalg.norm(lin.prediction_jacobian_ecef_left @
                          np.vstack([np.eye(3), np.eye(3)])) > .01


def test_pivot_reparameterization_preserves_observation_and_full_covariance():
    nodes, l0, l1, r0, r1, ints, e0, e1 = fixture_epochs()
    a, _ = make_epoch(100., nodes, l0, r0, ints, pivot=3)
    b, _ = make_epoch(100.8, nodes, l1, r1, ints, pivot=1)
    original, repivot = factor(e0, e1), factor(a, b)
    assert original.relations == repivot.relations
    np.testing.assert_allclose(original.z_m, repivot.z_m, atol=1e-14)
    np.testing.assert_allclose(original.G0, repivot.G0, atol=3e-16)
    np.testing.assert_allclose(original.G1, repivot.G1, atol=3e-16)
    np.testing.assert_allclose(original.covariance_m2, repivot.covariance_m2,
                               atol=5e-19, rtol=0)


def test_epoch_only_pivots_cancel_without_inheriting_their_integers():
    nodes, l0, l1, r0, r1, ints, e0, _ = fixture_epochs()
    new_pivot = node(9, token="new-at-second-epoch")
    nodes1 = nodes[1:] + (new_pivot,)
    los1 = np.vstack([l1[1:], [.3, .4, .866025403784]])
    i1 = {**ints, new_pivot: 753}
    e1, _ = make_epoch(100.8, nodes1, los1, r1, i1, pivot=4)
    f = factor(e0, e1, continuous=nodes[1:])
    assert len(f.relations) == 3
    assert all(nodes[0] not in (e.target, e.pivot) and new_pivot not in
               (e.target, e.pivot) for e in f.relations)
    assert np.all(f.physical_coefficients_m[:, f.physical_nodes.index(new_pivot)] == 0)
    changed, _ = make_epoch(100.8, nodes1, los1, r1,
                            {**i1, new_pivot: -999}, pivot=4)
    np.testing.assert_allclose(factor(e0, changed, continuous=nodes[1:]).z_m,
                               f.z_m, atol=1e-13)
    np.testing.assert_allclose(f.linearize(state(e0, r0), state(e1, r1)).residual_m,
                               0., atol=5e-14)


def test_partial_interval_break_is_removed_even_if_endpoint_tokens_match():
    nodes, _, _, r0, r1, _, e0, e1 = fixture_epochs()
    # The excluded node broke in the interval; matching endpoints are insufficient.
    f = factor(e0, e1, continuous=nodes[1:])
    assert len(f.relations) == 3
    assert all(nodes[0] not in (e.target, e.pivot) for e in f.relations)
    np.testing.assert_allclose(f.linearize(state(e0, r0), state(e1, r1)).residual_m,
                               0., atol=2e-14)


def test_full_break_new_tokens_and_empty_support_do_not_reuse_old_phase():
    nodes, l0, l1, r0, r1, ints, e0, e1 = fixture_epochs()
    for f in [factor(e0, e1, continuous=())]:
        assert f.status == "NO_CONTINUOUS_RELATIONS"
        assert f.z_m.shape == (0,)
        assert f.covariance_m2.shape == (0, 0)
        assert f.linearize(state(e0, r0), state(e1, r1)).rank == 0
    new_nodes = tuple(node(i+1, token="reacquired") for i in range(5))
    new_ints = dict(zip(new_nodes, [1, 2, 3, 4, 5]))
    reacquired, _ = make_epoch(100.8, new_nodes, l1, r1, new_ints)
    across = factor(e0, reacquired, continuous=new_nodes)
    assert len(across.relations) == 0
    later, _ = make_epoch(101.6, new_nodes, l0, r0, new_ints)
    fresh = factor(reacquired, later)
    assert len(fresh.relations) == 4
    np.testing.assert_allclose(fresh.linearize(
        state(reacquired, r1), state(later, r0)).residual_m, 0., atol=1e-15)


def test_disconnected_graphs_keep_only_common_connected_relations():
    nodes, l0, l1, r0, r1, ints, _, _ = fixture_epochs()
    rel0 = (DdArcRelation(nodes[1], nodes[0]), DdArcRelation(nodes[3], nodes[2]))
    rel1 = (DdArcRelation(nodes[1], nodes[0]), DdArcRelation(nodes[2], nodes[1]),
            DdArcRelation(nodes[4], nodes[3]))
    e0, _ = make_epoch(100., nodes, l0, r0, ints, relations=rel0)
    e1, _ = make_epoch(100.8, nodes, l1, r1, ints, relations=rel1)
    f = factor(e0, e1)
    assert f.relations == (DdArcRelation(nodes[1], nodes[0]),)


def test_signal_groups_wavelengths_are_separate_and_cross_group_dd_is_rejected():
    nodes = (node(1), node(2), node(1, sig=3), node(2, sig=3))
    los0 = np.array([[1., 0., 0.], [0., 1., 0.],
                      [1., 0., 0.], [0., 1., 0.]])
    los1 = los0 @ exp_rotation([.03, -.02, .01]).T
    ints = dict(zip(nodes, [7, -3, 54, 19]))
    relations = (DdArcRelation(nodes[1], nodes[0]), DdArcRelation(nodes[3], nodes[2]))
    r0, r1 = np.eye(3), exp_rotation([.1, -.1, .2])
    e0, _ = make_epoch(100., nodes, los0, r0, ints, relations=relations)
    e1, _ = make_epoch(100.8, nodes, los1, r1, ints, relations=relations)
    f = factor(e0, e1)
    assert len(f.relations) == 2
    np.testing.assert_allclose(f.linearize(state(e0, r0), state(e1, r1)).residual_m,
                               0., atol=1e-14)
    assert not np.isclose(oracle_wavelength(nodes[0]), oracle_wavelength(nodes[2]))
    with pytest.raises(ValueError, match="same exact group"):
        DdArcRelation(nodes[2], nodes[0])


def test_full_cross_time_covariance_matches_independent_sd_latent_oracle(record_property):
    nodes, l0, l1, r0, r1, ints, _, _ = fixture_epochs()
    rng = np.random.default_rng(RNG_SEED)
    latent = rng.normal(size=(10, 13)) * .002
    sd_stack_q = latent @ latent.T
    e0, t0 = make_epoch(100., nodes, l0, r0, ints, pivot=3,
                        sd_cov=sd_stack_q[:5, :5])
    e1, t1 = make_epoch(100.8, nodes, l1, r1, ints, pivot=1,
                        sd_cov=sd_stack_q[5:, 5:])
    mapping = np.zeros((8, 10)); mapping[:4, :5] = t0; mapping[4:, 5:] = t1
    joint = mapping @ sd_stack_q @ mapping.T
    # Exact marginal identity is part of the contract, with cross blocks from
    # the same latent model; explicit assignment avoids multiplication ULPs.
    joint[:4, :4] = e0.covariance_m2
    joint[4:, 4:] = e1.covariance_m2
    f = factor(e0, e1, covariance_mode="FULL_STACK", covariance_stack_m2=joint)
    canonical = np.zeros((4, 10))
    for row in range(4):
        canonical[row, 0] = 1
        canonical[row, row+1] = -1
        canonical[row, 5] = -1
        canonical[row, row+6] = 1
    expected = (canonical @ latent) @ (canonical @ latent).T
    np.testing.assert_allclose(f.covariance_m2, expected, atol=5e-19, rtol=1e-13)
    zero_cross = factor(e0, e1)
    assert np.linalg.norm(zero_cross.covariance_m2-expected) > 1e-5
    assert abs(expected[0, 1]) > 1e-6  # shared pivot/cross-signal not diagonal.
    record_property("covariance_max_abs_error_m2",
                    float(np.max(abs(f.covariance_m2-expected))))
    record_property("wrong_zero_cross_covariance_error_norm_m2",
                    float(np.linalg.norm(zero_cross.covariance_m2-expected)))


def shared_endpoint_fixture():
    nodes, l0, l1, r0, r1, ints, e0, e1 = fixture_epochs()
    e2, _ = make_epoch(101.6, nodes, l0, r0, ints)
    first, second = factor(e0, e1), factor(e1, e2)
    cross = np.zeros((8, 8))
    cross[4:, :4] = e1.covariance_m2
    return first, second, cross


def test_shared_endpoint_negative_cross_covariance_is_explicit():
    first, second, cross = shared_endpoint_fixture()
    got = difference_cross_covariance(first, second,
        source_cross_covariance_m2=cross, source_id="three-independent-sd-epochs")
    expected = -first.F1 @ first.epoch1.covariance_m2 @ second.F0.T
    np.testing.assert_allclose(got, expected, atol=1e-19)
    assert np.trace(got) < 0
    total = first.covariance_m2 + second.covariance_m2 + got + got.T
    direct = first.F0 @ first.epoch0.covariance_m2 @ first.F0.T + (
        second.F1 @ second.epoch1.covariance_m2 @ second.F1.T)
    np.testing.assert_allclose(total, direct, atol=1e-18)


def test_erased_shared_endpoint_or_conflicting_payload_is_rejected():
    first, second, cross = shared_endpoint_fixture()
    with pytest.raises(ArcPhaseDifferenceError, match="shared endpoint"):
        difference_cross_covariance(first, second,
            source_cross_covariance_m2=np.zeros_like(cross), source_id="incorrect")
    mutated = replace(second.epoch0, phase_m=second.epoch0.phase_m + .001)
    wrong = factor(mutated, second.epoch1)
    with pytest.raises(ArcPhaseDifferenceError, match="different payload"):
        difference_cross_covariance(first, wrong,
            source_cross_covariance_m2=cross, source_id="conflicting-source")


@pytest.mark.parametrize("which,cycle_step", [(0, 1.), (2, -.25)])
def test_hidden_target_or_pivot_step_has_template_but_is_not_detected(which, cycle_step):
    nodes, _, _, r0, r1, _, e0, e1 = fixture_epochs()
    f = factor(e0, e1)
    affected = nodes[which]
    row_step = np.array([
        oracle_wavelength(affected)*cycle_step*
        (int(e.target == affected)-int(e.pivot == affected))
        for e in e1.relations])
    contaminated = factor(e0, replace(e1, phase_m=e1.phase_m+row_step))
    template = f.fault_template_m_per_cycle(affected, endpoint=1)
    np.testing.assert_allclose(contaminated.z_m-f.z_m, cycle_step*template,
                               atol=5e-15)
    assert np.linalg.norm(contaminated.linearize(
        state(e0, r0), state(e1, r1)).residual_m) > .02
    # The false continuity claim cannot be detected by pure observation algebra.
    assert contaminated.status == "UNFIXED_ARC_PHASE_DIFFERENCE"
    assert not contaminated.accepted_integer_measurement
    np.testing.assert_allclose(f.fault_template_m_per_cycle(affected, endpoint=0),
                               -template, atol=1e-16)


def test_psd_singular_noise_is_preserved_without_floor_or_inversion():
    _, _, _, _, _, _, e0, e1 = fixture_epochs()
    e1 = replace(e1, covariance_m2=e0.covariance_m2)
    q = e0.covariance_m2
    joint = np.block([[q, q], [q, q]])
    f = factor(e0, e1, covariance_mode="FULL_STACK", covariance_stack_m2=joint)
    np.testing.assert_array_equal(f.covariance_m2, np.zeros((4, 4)))


@pytest.mark.parametrize("fault", [
    "time_scale", "receiver_pair", "phase_convention", "same_epoch_id",
    "reverse_time", "early_decision", "wrong_interval", "future_continuity",
])
def test_timing_identity_and_availability_fail_closed(fault):
    *_, e0, e1 = fixture_epochs()
    kwargs = {}
    if fault == "time_scale":
        e1 = replace(e1, time_scale_id="UTC-UNCONVERTED")
    elif fault == "receiver_pair":
        e1 = replace(e1, receiver_pair_id="other-receiver")
    elif fault == "phase_convention":
        e1 = replace(e1, phase_convention_id="CYCLES-NOT-METRES")
    elif fault == "same_epoch_id":
        e1 = replace(e1, epoch_id=e0.epoch_id)
    elif fault == "reverse_time":
        e0, e1 = e1, e0
    elif fault == "early_decision":
        kwargs["decision_available_time_s"] = e1.available_time_s - .001
    elif fault == "wrong_interval":
        kwargs["continuity"] = PhaseArcContinuity(
            99., e1.time_s, e1.available_time_s, e0.receiver_pair_id, "wrong", e0.nodes)
    elif fault == "future_continuity":
        kwargs["continuity"] = PhaseArcContinuity(
            e0.time_s, e1.time_s, e1.time_s+2., e0.receiver_pair_id, "late", e0.nodes)
        kwargs["decision_available_time_s"] = e1.time_s+1.
    with pytest.raises(ArcPhaseDifferenceError):
        factor(e0, e1, **kwargs)


def test_covariance_contract_rejects_missing_indefinite_or_changed_marginals():
    *_, e0, e1 = fixture_epochs()
    with pytest.raises(ArcPhaseDifferenceError, match="missing"):
        factor(e0, e1, covariance_mode="FULL_STACK")
    with pytest.raises(ArcPhaseDifferenceError, match="explicit"):
        factor(e0, e1, covariance_mode="IMPLICIT")
    with pytest.raises(ArcPhaseDifferenceError, match="positive semidefinite"):
        factor(e0, e1, covariance_mode="FULL_STACK", covariance_stack_m2=-np.eye(8))
    q = np.zeros((8, 8))
    q[:4, :4] = e0.covariance_m2; q[4:, 4:] = e1.covariance_m2
    q[0, 0] += .01
    with pytest.raises(ArcPhaseDifferenceError, match="marginals"):
        factor(e0, e1, covariance_mode="FULL_STACK", covariance_stack_m2=q)


def test_attitude_frame_and_actual_availability_are_checked():
    _, _, _, r0, r1, _, e0, e1 = fixture_epochs()
    f = factor(e0, e1)
    valid0, valid1 = state(e0, r0), state(e1, r1)
    for wrong in [replace(valid1, body_frame_id="WRONG_FLU"),
                  replace(valid1, time_s=e1.time_s-.01),
                  replace(valid1, available_time_s=f.decision_available_time_s+1.)]:
        with pytest.raises(ArcPhaseDifferenceError, match="endpoint/frame/availability"):
            f.linearize(valid0, wrong)
    with pytest.raises(ArcPhaseDifferenceError, match=r"SO\(3\)"):
        replace(valid1, matrix_body_to_ecef=np.diag([-1., 1., 1.]))


# Added only after the first 26 cases passed: historical-model geometry and
# unknown-cross conditional bound. The original cases remain in this file.
def test_geometry_only_preserves_missing_availability_and_does_not_admit():
    from legsa_gins.paper_rebuild.carrier_phase.arc_phase_difference import (
        build_phase_contrast_geometry,
    )
    *_, e0, e1 = fixture_epochs()
    c = PhaseArcContinuity(e0.time_s, e1.time_s, None, e0.receiver_pair_id,
                          "historical-full-interval-record", e0.nodes)
    g = build_phase_contrast_geometry(replace(e0, available_time_s=None),
                                     replace(e1, available_time_s=None), c)
    assert g.declared_available_time_s is None
    assert not g.navigation_admitted and not g.joint_covariance_known
    baseline = factor(e0, e1)
    np.testing.assert_array_equal(g.z_m, baseline.z_m)
    np.testing.assert_array_equal(g.G0, baseline.G0)
    np.testing.assert_array_equal(g.G1, baseline.G1)
    with pytest.raises(ArcPhaseDifferenceError, match="availability unknown"):
        build_phase_difference(replace(e0, available_time_s=None), e1, c,
            covariance_mode="WORKING_ZERO_CROSS", covariance_stack_m2=None,
            covariance_source_id="working-only", decision_available_time_s=e1.time_s+5,
            baseline_body_m=BASELINE, body_frame_id=BODY,
            baseline_source_id="known-synthetic-installation")


@pytest.mark.parametrize("cross_case", ["positive", "negative", "generic"])
def test_unknown_cross_bound_with_actual_joint_psd_and_extremes(cross_case):
    from legsa_gins.paper_rebuild.carrier_phase.arc_phase_difference import (
        build_phase_contrast_geometry, unknown_cross_difference_bound,
    )
    *_, e0, e1 = fixture_epochs()
    rng = np.random.default_rng(RNG_SEED+1)
    if cross_case in ("positive", "negative"):
        l = rng.normal(size=(4, 5))*.003
        latent = np.vstack([l, l if cross_case == "positive" else -l])
    else:
        latent = rng.normal(size=(8, 11))*.003
    q = latent @ latent.T
    e0 = replace(e0, covariance_m2=q[:4, :4])
    e1 = replace(e1, covariance_m2=q[4:, 4:])
    c = PhaseArcContinuity(e0.time_s, e1.time_s, e1.available_time_s,
                          e0.receiver_pair_id, "synthetic-known-continuity", e0.nodes)
    g = build_phase_contrast_geometry(e0, e1, c)
    bound = unknown_cross_difference_bound(g,
                  marginal_bound_source_id="exact-synthetic-latent-second-moments")
    actual = (g.observation_map@latent)@(g.observation_map@latent).T
    assert np.linalg.eigvalsh(bound.matrix_m2-actual).min() >= -2e-18
    assert not bound.is_covariance and not bound.calibrated
    assert not bound.cross_covariance_known
    if cross_case == "positive":
        np.testing.assert_allclose(actual, 0., atol=1e-30)
        assert np.trace(bound.matrix_m2) > 1e-4
    elif cross_case == "negative":
        np.testing.assert_allclose(actual, bound.matrix_m2, atol=5e-19, rtol=1e-14)


def test_geometry_only_empty_relations_does_not_invent_noise_or_delay():
    from legsa_gins.paper_rebuild.carrier_phase.arc_phase_difference import (
        build_phase_contrast_geometry, unknown_cross_difference_bound,
    )
    *_, e0, e1 = fixture_epochs()
    c = PhaseArcContinuity(e0.time_s, e1.time_s, None,
                          e0.receiver_pair_id, "known-full-break", ())
    g = build_phase_contrast_geometry(e0, e1, c)
    assert g.status == "NO_CONTINUOUS_RELATIONS"
    assert g.declared_available_time_s is None
    assert g.epoch0_covariance_contribution_m2.shape == (0, 0)
    assert unknown_cross_difference_bound(g, marginal_bound_source_id="synthetic").matrix_m2.shape == (0, 0)
