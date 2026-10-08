"""Finite support, one-use AR prediction, and shared-history reconstruction."""
from copy import deepcopy

import gtsam
import numpy as np

from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock
from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch
from legsa_gins.paper_rebuild.joint_navigation.window import key_ordering


def _events():
    events = []
    for index in range(9):
        timestamp = index*.1
        feet = [dict(arc_id=f"A{foot}", foot_id=foot, force=120.,
                     point_body=np.array([.2+.004*index, (-1.)**foot*.15, -.5]))
                for foot in range(2)]
        events.append(dict(time_s=timestamp, feet=feet,
            imu=np.array([[.1, .015, 0., -9.81, 0., 0., .008]]) if index else np.empty((0, 7)),
            gnss_position=np.array([.002*np.sin(index), 0., .5]), gnss_velocity=np.zeros(3),
            carrier=EpochBlock(timestamp, np.array([0., -.35, 0.]), np.empty((3, 0)),
                np.eye(3), np.eye(3)*.0004, ())))
    return events


def _metadata(sigma=.08, **changes):
    return dict(baseline_body=[0., -.35, 0.], lag_s=.35,
                accel_bias_random_walk=0., gyro_bias_random_walk=0.,
                gnss_position_sigma=.03, gnss_velocity_sigma=.03,
                support_prediction="foot_external",
                support_motion_model=dict(velocity_sigma_mps=sigma, tau_s=.6), **changes)


def _policy():
    return [dict(group_id="observed_A", arc_ids=("A0", "A1"), mode="finite_common_motion")]


def _density(residual, covariance):
    root = np.linalg.cholesky(covariance)
    whitened = np.linalg.solve(root, residual)
    return whitened@whitened+2*np.log(np.diag(root)).sum()+len(residual)*np.log(2*np.pi)


def test_joint_prediction_keeps_cross_information_and_does_not_score_birth():
    events = _events()
    branch = NavigationBranch(_metadata())
    for index, event in enumerate(events[:5]):
        branch.step(event, index, support_models=_policy())
    event = deepcopy(events[5])
    event["feet"].append(dict(arc_id="NEW2", foot_id=2, force=120., point_body=np.array([-.2, .15, -.5])))
    before_keys = tuple(branch.window.values.keys())
    joint = branch.predict_external(event, support_models=_policy())
    assert tuple(branch.window.values.keys()) == before_keys
    assert joint["excluded_contact_birth_arcs"] == ("NEW2",)
    assert joint["predicted_foot_arcs"] == ("A0", "A1")
    assert len(joint["row_ids"]) == 15
    external_rows = [i for i, row in enumerate(joint["row_ids"]) if not row.startswith("foot:")]
    foot_rows = [i for i, row in enumerate(joint["row_ids"]) if row.startswith("foot:")]
    branch.support_prediction = "external"
    external = branch.predict_external(event, support_models=_policy())
    branch.support_prediction = "foot_external"
    P = joint["covariance"]
    np.testing.assert_allclose(P[np.ix_(external_rows, external_rows)], external["covariance"], atol=2e-11)
    np.testing.assert_allclose(joint["innovation"][external_rows], external["innovation"], atol=1e-12)
    cross = P[np.ix_(foot_rows, external_rows)]
    assert np.linalg.norm(cross) > 1e-7
    Pee, Pff = P[np.ix_(external_rows, external_rows)], P[np.ix_(foot_rows, foot_rows)]
    re, rf = joint["innovation"][external_rows], joint["innovation"][foot_rows]
    foot_only = branch.predict_external(dict(event, gnss_position=None, gnss_velocity=None, carrier=None),
                                        support_models=_policy())
    assert len(foot_only["row_ids"]) == 6
    np.testing.assert_allclose(foot_only["innovation"], rf, atol=1e-12)
    np.testing.assert_allclose(foot_only["covariance"], Pff, atol=1e-11)
    gain = np.linalg.solve(Pee, cross.T).T
    conditional = _density(rf-gain@re, Pff-gain@cross.T)
    np.testing.assert_allclose(_density(joint["innovation"], P), _density(re, Pee)+conditional, atol=1e-9)
    assert abs(_density(rf, Pff)-conditional) > 1e-4
    # A new observation is not a repeated use of the previous AR noise: both
    # feet depend on their own previous expression and the same motion state.
    prior_keys = set(joint["prior_variable_keys"])
    assert all(set(expression.keys).issubset(prior_keys) for expression, _ in branch.foot_error_history.values())
    assert set(branch._motion_retained_keys()).issubset(prior_keys)

    # Independent graph calculation: append the actual IMU/OU transition
    # factors, marginalize their joint prior, and project the actual whitened
    # measurement Jacobians. This checks cross terms and AR noise against the
    # factors consumed by step, not a second copy of the prediction formula.
    graph_branch = NavigationBranch(_metadata())
    graph_branch.restore(branch.snapshot())
    old_factors = list(graph_branch.window.factors)
    graph_branch.step(events[5], 5, support_models=_policy(), defer_optimize=True)
    new_factors = graph_branch.window.factors[len(old_factors):]
    process, measured = [], []
    for factor in new_factors:
        symbols = {chr(gtsam.Symbol(key).chr()) for key in factor.keys()}
        (process if isinstance(factor, gtsam.ImuFactor) or symbols.issubset({"m", "u"}) else measured).append(factor)
    graph_branch.window.factors = old_factors+process
    observed_keys = list(dict.fromkeys(key for factor in measured for key in factor.keys()))
    graph_covariance = graph_branch.joint_covariance(observed_keys)
    measurement_graph = gtsam.NonlinearFactorGraph()
    for factor in measured:
        measurement_graph.push_back(factor)
    H, rhs = measurement_graph.linearize(graph_branch.window.values).jacobian(key_ordering(observed_keys))
    graph_predictive = np.eye(len(rhs))+H@graph_covariance@H.T
    whitening = np.zeros_like(P)
    whitening[:3, :3] = np.eye(3)/.03
    whitening[3:6, 3:6] = np.eye(3)/.03
    whitening[6:9, 6:9] = np.eye(3)/.02
    rho = np.exp(-.1/branch.foot_tau)
    whitening[9:, 9:] = np.eye(6)/(branch.foot_sigma*np.sqrt(1-rho*rho))
    np.testing.assert_allclose(whitening@P@whitening.T, graph_predictive, rtol=3e-6, atol=5e-7)
    np.testing.assert_allclose(whitening@joint["innovation"], rhs, atol=1e-8)


def test_finite_zero_limit_equals_fixed_and_checkpoint_reconstruction():
    events = _events()
    fixed = NavigationBranch(_metadata(0.))
    limit = NavigationBranch(_metadata(0.))
    finite = NavigationBranch(_metadata())
    for index, event in enumerate(events[:4]):
        fixed.step(event, index)
        limit.step(event, index, support_models=_policy())
        finite.step(event, index, support_models=_policy())
    for name in ("p", "v", "rpy_rad", "bias"):
        np.testing.assert_array_equal(fixed.current_output()[name], limit.current_output()[name])
    assert not limit.support_motion_states
    snapshot = finite.snapshot()
    replay = NavigationBranch(_metadata())
    replay.restore(snapshot)
    for index, event in enumerate(events[4:], 4):
        actual = finite.predict_external(event, support_models=_policy())
        repeated = replay.predict_external(event, support_models=_policy())
        assert actual["row_ids"] == repeated["row_ids"]
        np.testing.assert_allclose(actual["covariance"], repeated["covariance"], atol=1e-13)
        np.testing.assert_allclose(actual["innovation"], repeated["innovation"], atol=1e-13)
        finite.step(event, index, support_models=_policy())
        replay.step(event, index, support_models=_policy())
    for name in ("p", "v", "rpy_rad", "bias"):
        np.testing.assert_array_equal(finite.current_output()[name], replay.current_output()[name])


def test_shared_separator_retains_motion_and_closes_only_explicit_source_arcs():
    metadata = _metadata(gaussian_future_separator=True)
    events = _events()
    reference, conditional = NavigationBranch(metadata), NavigationBranch(metadata)
    for index, event in enumerate(events[:6]):
        if index == 3:
            event = {**event, "feet": []}  # Missing data do not reset the source.
        reference.step(event, index)
        conditional.step(event, index, support_models=_policy(),
                         linearization_anchor=reference.export_linearization_anchor())
        conditional.compress_gaussian_history(event)
        assert "observed_A" in conditional.support_motion_states
        assert all(conditional.window.values.exists(key) for key in conditional._motion_retained_keys())
        if index:
            prediction = conditional.predict_external(events[index+1], support_models=_policy())
            np.linalg.cholesky(prediction["covariance"])
    close = {**events[6], "feet": [], "active_support_arcs": ()}
    reference.step(close, 6)
    conditional.step(close, 6, support_models=_policy(),
                     linearization_anchor=reference.export_linearization_anchor())
    conditional.compress_gaussian_history(close)
    assert not conditional.support_motion_states
    assert not conditional.contact_keys
    assert not conditional.foot_error_history


if __name__ == "__main__":
    test_joint_prediction_keeps_cross_information_and_does_not_score_birth()
    test_finite_zero_limit_equals_fixed_and_checkpoint_reconstruction()
    test_shared_separator_retains_motion_and_closes_only_explicit_source_arcs()
    print("PASS: joint density, exact fixed limit, source-history reconstruction, shared separator")
