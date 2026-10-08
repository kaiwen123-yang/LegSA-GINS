"""One causal support sequence against an uncompressed fixed-Jacobian history."""

from copy import deepcopy

import gtsam
import numpy as np
from gtsam.symbol_shorthand import X, V, B

from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch
from legsa_gins.paper_rebuild.joint_navigation.window import JointWindow, key_ordering


def full_history_solution(factors, anchor, keys):
    """Independent all-history QR, including every cross block and residual row."""
    linear = JointWindow._graph(factors).linearize(anchor)
    ordering = key_ordering(sorted(anchor.keys()))
    conditional, _ = gtsam.JacobianFactor(linear, ordering).eliminate(ordering)
    delta = conditional.solve(gtsam.VectorValues())
    root = np.linalg.solve(conditional.R(), np.diag(conditional.get_model().sigmas()))
    indices, cursor = {}, 0
    for key in sorted(anchor.keys()):
        size = len(delta.at(key))
        indices[key] = list(range(cursor, cursor+size))
        cursor += size
    selected = [column for key in keys for column in indices[key]]
    selected_root = root[selected]
    return delta, selected_root @ selected_root.T, float(linear.error(delta))


def test_future_separator_matches_complete_fixed_jacobian_history():
    branch = NavigationBranch(dict(baseline_body=[0., .25, 0.], gaussian_future_separator=True,
                                   foot_correlation_tau_s=2., foot_sigma=.04))
    branch.bootstrap_status = "INITIALIZED"
    branch.predictive_score, branch.predictive_row_count = 7.25, 11
    branch.integer_lineage = (("retained-carrier", 2),)
    points = dict(a=[.2, .15, -.35], b=[.2, -.15, -.35],
                  c=[-.2, .15, -.35], d=[-.2, -.15, -.35], a2=[.24, .16, -.34])
    identity = dict(a=0, b=1, c=2, d=3, a2=0)
    model = dict(group_id="observed_components", arc_ids=("a", "b", "c", "d"),
                 mode="common_translation_release")
    # Two initially disconnected pairs, a real bridge, asynchronous triples,
    # a long singleton, an external-only event, reunion and a new source token.
    sequence = [(0., "ab"), (.1, "cd"), (.2, "bc"), (.3, "abc"),
                (6.4, "b"), (6.6, ""), (6.8, "ab"),
                (7., ("a2", "b", "c")), (7.2, "c"), (7.4, ("a2", "c"))]
    anchor, history, readouts = gtsam.Values(), [], []
    nkey = gtsam.symbol("a", 0)
    saved_singleton_error = None
    exact_geometry_rows = 0
    for index, (time_s, arcs) in enumerate(sequence):
        branch.index, branch.time, branch.bias_key = index, time_s, B(index)
        new = gtsam.Values()
        pose = gtsam.Pose3(gtsam.Rot3.RzRyRx(.015*index, -.01*index, .02*index),
                          np.array([.03*index, -.01*index, 0.]))
        new.insert(X(index), pose)
        new.insert_vector(V(index), np.zeros(3))
        new.insert(B(index), gtsam.imuBias.ConstantBias())
        timestamps = {key: time_s for key in new.keys()}
        nav_noise = gtsam.noiseModel.Isotropic.Sigma(6, .2)
        velocity_noise = gtsam.noiseModel.Isotropic.Sigma(3, .1)
        bias_noise = gtsam.noiseModel.Isotropic.Sigma(6, .03)
        factors = [gtsam.PriorFactorPose3(X(index), pose.retract(np.array([.01, -.02, .01, .02, .01, -.01])), nav_noise),
                   gtsam.PriorFactorVector(V(index), np.ones(3)*.01*index, velocity_noise)]
        if index == 0:
            factors.append(gtsam.PriorFactorConstantBias(B(index), gtsam.imuBias.ConstantBias(), bias_noise))
            new.insert_vector(nkey, np.array([.2]))
            timestamps[nkey] = time_s
            branch.ambiguity_keys["retained-carrier"] = nkey
            factors.append(gtsam.PriorFactorVector(nkey, np.array([.5]), velocity_noise_dim1()))
        else:
            factors.extend([
                gtsam.BetweenFactorPose3(X(index-1), X(index),
                    anchor.atPose3(X(index-1)).between(pose), nav_noise),
                gtsam.BetweenFactorVector(V(index-1), V(index), np.zeros(3), velocity_noise),
                gtsam.BetweenFactorConstantBias(B(index-1), B(index), gtsam.imuBias.ConstantBias(), bias_noise)])
        feet = [dict(arc_id=arc, foot_id=identity[arc], force=120.,
                     point_body=np.asarray(points[arc])+np.array([.003*index, -.001*index, .002])) for arc in arcs]
        event = dict(time_s=time_s, feet=feet)
        if index == 8:
            event.update(active_support_arcs=("a2", "c"), support_state_source_time_s=time_s,
                         support_states=[dict(foot_id=0, arc_id="a2"), dict(foot_id=1, arc_id=None),
                                         dict(foot_id=2, arc_id="c"), dict(foot_id=3, arc_id=None)])
        branch._observe_support_lifecycle(event)
        branch._factor_seed_values = gtsam.Values(anchor)
        branch._support(feet, set(), [model], pose, X(index), new, timestamps, factors)
        branch._factor_seed_values = None
        anchor.insert(new)
        if index == 2:
            # Joining b/c transports d from its previous local component with
            # an exact point-coordinate row, preserving its existing AR chain.
            exact_geometry_rows = sum(isinstance(factor, gtsam.CustomFactor) and
                np.any(factor.noiseModel().sigmas() == 0.) for factor in factors)
            assert exact_geometry_rows > 0
        frozen = [gtsam.LinearContainerFactor(factor.linearize(anchor), anchor) for factor in factors]
        # Couple the retained ambiguity and navigation, then condition its
        # historical coordinate late in this same sequence.
        coupling = gtsam.JacobianFactor(X(index), np.array([[0., 0., .4, .2, 0., 0.]]),
                                        nkey, np.ones((1, 1)), np.array([.03*index]), velocity_noise_dim1())
        frozen.append(gtsam.LinearContainerFactor(coupling, anchor))
        if index == 7:
            late_integer = gtsam.JacobianFactor(nkey, np.ones((1, 1)), np.array([.1]),
                                                gtsam.noiseModel.Constrained.All(1))
            frozen.append(gtsam.LinearContainerFactor(late_integer, anchor))
        history.extend(frozen)
        branch.window.update(frozen, new, timestamps, time_s,
            retain_keys=branch._retained_keys(gaussian=True), gaussian_only=True, linearization_values=anchor)
        if index == 3:
            saved_singleton_error = deepcopy(branch.foot_error_history)
        if index in (4, 5):
            assert branch.foot_error_history == saved_singleton_error
            assert branch.window.values.exists(X(1))  # d's unseen latest AR
        stats = branch.compress_gaussian_history(event)
        keys = sorted(branch.window.values.keys())
        delta, covariance, objective = full_history_solution(history, anchor, keys)
        mean_error = max(np.max(np.abs(branch.window.linearization_delta.at(key)-delta.at(key))) for key in keys)
        covariance_error = np.max(np.abs(branch.window.joint_covariance(keys)-covariance))
        objective_error = abs(branch.window.error()-objective)
        np.testing.assert_allclose(mean_error, 0., atol=3e-9)
        np.testing.assert_allclose(covariance_error, 0., atol=3e-9)
        np.testing.assert_allclose(objective_error, 0., atol=3e-9)
        assert branch.window.values.exists(nkey)
        assert branch.predictive_score == 7.25 and branch.predictive_row_count == 11
        assert branch.integer_lineage == (("retained-carrier", 2),)
        if index == 7:
            assert stats["closed_support_arcs"] == ("a",)
            assert "a" not in branch.foot_error_history
            assert "a" not in branch.support_geometry["observed_components"]
        if index == 8:
            assert stats["closed_support_arcs"] == ("b", "d")
            assert set(branch.support_geometry["observed_components"]) == {"c"}
        if index == 5:
            assert not stats["closed_support_arcs"]
            checkpoint = branch.snapshot()
            branch.restore(checkpoint)
            np.testing.assert_allclose(branch.window.joint_covariance(keys), covariance, atol=3e-9)
        readouts.append(dict(event=index, retained_dimension=stats["retained_dimension"],
            full_dimension=int(anchor.dim()), mean_max_abs=float(mean_error),
            covariance_max_abs=float(covariance_error), objective_abs=float(objective_error)))
    assert readouts[-1]["retained_dimension"] < readouts[-1]["full_dimension"]//2
    return dict(events=len(sequence), exact_geometry_rows=int(exact_geometry_rows), readouts=readouts)


def velocity_noise_dim1():
    return gtsam.noiseModel.Isotropic.Sigma(1, .1)


if __name__ == "__main__":
    import json
    print(json.dumps(test_future_separator_matches_complete_fixed_jacobian_history(), indent=2))
