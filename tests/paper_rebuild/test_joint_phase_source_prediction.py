"""Consumption-free raw prediction checked by a joint future-observation graph."""

import gtsam
import numpy as np
from gtsam.symbol_shorthand import X, V, B

from legsa_gins.paper_rebuild.carrier_phase.arc_relations import DdArcRelation, SdArcNode
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock
from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch
from legsa_gins.paper_rebuild.joint_navigation.factors import source_ou_factor
from legsa_gins.paper_rebuild.joint_navigation.source_noise_likelihood import physical_source_incidence
from legsa_gins.paper_rebuild.joint_navigation.window import JointWindow, key_ordering


def fixture(gaussian):
    signals = tuple(f"0:{j}:0:0" for j in range(1, 5))
    labels = tuple(DdArcRelation(SdArcNode(signal, "arc0"), SdArcNode(signals[0], "arc0")).label
                   for signal in signals[1:])
    metadata = dict(baseline_body=[0., -.35, 0.], carrier_label_mode="physical_sd_arcs",
                    accel_bias_random_walk=0., gyro_bias_random_walk=0., gaussian_future_separator=True,
                    phase_noise_model=dict(white_sd_sigma_m=.007, beta_sd_sigma_m=.025, tau_s=.8))
    branch = NavigationBranch(metadata, use_foot=False)
    branch.index, branch.time, branch.bias_key = 0, 0., B(0)
    branch.bootstrap_status = "INITIALIZED"
    branch.ambiguity_keys = {label: gtsam.symbol("a", j) for j, label in enumerate(labels[:2])}
    branch.phase_beta_keys = {signals[0]: gtsam.symbol("e", 17), signals[1]: gtsam.symbol("e", 9)}
    branch.phase_beta_times = {signals[0]: -.3, signals[1]: -.1}
    branch.phase_beta_coordinates = {(signal, branch.phase_beta_times[signal]): key
                                    for signal, key in branch.phase_beta_keys.items()}
    anchor = gtsam.Values()
    anchor.insert(X(0), gtsam.Pose3(gtsam.Rot3.Ypr(.15, -.04, .02), np.array([.2, -.1, .3])))
    anchor.insert_vector(V(0), np.array([.1, .03, -.02]))
    anchor.insert(B(0), gtsam.imuBias.ConstantBias())
    for j, key in enumerate(branch.ambiguity_keys.values()):
        anchor.insert_vector(key, np.array([1.2-j]))
    for j, key in enumerate(branch.phase_beta_keys.values()):
        anchor.insert_vector(key, np.array([.012-.02*j]))
    keys = [X(0), V(0), B(0), *branch.ambiguity_keys.values(), *branch.phase_beta_keys.values()]
    sizes = [6, 3, 6, 1, 1, 1, 1]
    cuts = np.r_[0, np.cumsum(sizes)]
    sigma = np.r_[np.full(6, .04), np.full(3, .02), np.full(6, .004), [.2, .2, .02, .02]]
    loading = sigma*np.linspace(-.9, 1.2, sum(sizes))
    covariance = np.diag(sigma*sigma)+np.outer(loading, loading)
    target = np.r_[[.12, -.07, .09, .02, -.03, .01], [.02, -.01, .01],
                   np.full(6, .0005), [.13, -.08, .007, -.011]]

    def prior_error(_factor, values, jacobians):
        local = anchor.localCoordinates(values)
        if jacobians is not None:
            for j in range(len(keys)):
                jacobians[j] = np.asfortranarray(np.eye(sum(sizes))[:, cuts[j]:cuts[j+1]])
        return np.concatenate([local.at(key) for key in keys])-target

    prior = gtsam.CustomFactor(gtsam.noiseModel.Gaussian.Covariance(covariance), keys, prior_error)
    frozen = gtsam.LinearContainerFactor(prior.linearize(anchor), anchor)
    branch.window.update([frozen], anchor, {key: 0. for key in keys}, 0.,
                         gaussian_only=gaussian, linearization_values=anchor if gaussian else None)
    branch._current()
    # Third physical source has a supplied N coordinate but no previous beta;
    # the last DD integer is unknown and its phase row must remain excluded.
    block = EpochBlock(.2, np.arange(6)*.01, np.r_[np.zeros((3, 3)), .19*np.eye(3)],
                       np.r_[np.eye(3), np.eye(3)], np.diag([.06**2]*3+[.003**2]*3), labels)
    event = dict(time_s=.2, carrier=block, feet=[], gnss_position=np.array([.2, -.1, .3]),
                 gnss_velocity=np.array([.1, .03, -.02]),
                 imu=np.array([[.2, .1, .2, -9.7, .02, -.03, .08]]))
    return branch, event, signals


def future_observation_graph(branch, event, selected):
    """Integrate future X/V/beta and the unobserved raw Y in one independent QR.

    Actual ImuFactor and analytic raw-measurement Jacobians provide the oracle;
    no predict_external Jacobian/covariance is reused.
    """
    chart = gtsam.Values(branch.window.linearization_values if branch.window.gaussian_only else branch.window.values)
    old_pose, old_v, bias = chart.atPose3(X(0)), chart.atVector(V(0)), chart.atConstantBias(B(0))
    pim = branch._preintegrate(event, bias)
    predicted = pim.predict(gtsam.NavState(old_pose, old_v), bias)
    chart.insert(X(1), predicted.pose())
    chart.insert_vector(V(1), predicted.velocity())
    factors = list(branch.window.factors)
    factors.append(gtsam.ImuFactor(X(0), V(0), X(1), V(1), B(0), pim))
    block = event["carrier"]
    incidence = physical_source_incidence(block)
    D = incidence.D[selected]
    active = [j for j in range(D.shape[1]) if np.any(D[:, j])]
    D = D[:, active]
    beta_keys = []
    params = branch.phase_noise_model
    for j in active:
        signal, key = incidence.source_signals[j], gtsam.symbol("s", j)
        beta_keys.append(key)
        if signal in branch.phase_beta_keys:
            old = branch.phase_beta_keys[signal]
            dt = block.time_s-branch.phase_beta_times[signal]
            rho = np.exp(-dt/params["tau_s"])
            chart.insert_vector(key, rho*chart.atVector(old))
            factors.append(source_ou_factor(old, key, rho,
                params["beta_sd_sigma_m"]*np.sqrt(-np.expm1(-2.*dt/params["tau_s"]))))
        else:
            chart.insert_vector(key, np.zeros(1))
            factors.append(gtsam.PriorFactorVector(key, np.zeros(1),
                gtsam.noiseModel.Isotropic.Sigma(1, params["beta_sd_sigma_m"])))
    nkeys = list(branch.ambiguity_keys.values())
    A, design = block.A[np.ix_(selected, [0, 1])], block.B[selected]
    body = branch.baseline_body
    ykey = gtsam.symbol("y", 0)

    def observable(values):
        pose = values.atPose3(X(1))
        return np.r_[pose.translation(), values.atVector(V(1)),
            design@pose.rotation().rotate(body)+A@np.array([values.atVector(k)[0] for k in nkeys])+
            D@np.array([values.atVector(k)[0] for k in beta_keys])]

    y0 = observable(chart)
    chart.insert_vector(ykey, y0)
    measurement_keys = [X(1), V(1), *nkeys, *beta_keys, ykey]

    def measurement_error(_factor, values, jacobians):
        if jacobians is not None:
            pose, length = values.atPose3(X(1)), len(y0)
            bx, by, bz = body
            cross = np.array([[0., -bz, by], [bz, 0., -bx], [-by, bx, 0.]])
            hpose = np.zeros((length, 6))
            hpose[:3, 3:] = pose.rotation().matrix()
            hpose[6:, :3] = -design@pose.rotation().matrix()@cross
            jacobians[0] = np.asfortranarray(hpose)
            jacobians[1] = np.asfortranarray(np.r_[np.zeros((3, 3)), np.eye(3), np.zeros((len(selected), 3))])
            for j in range(len(nkeys)):
                jacobians[2+j] = np.asfortranarray(np.r_[np.zeros((6, 1)), A[:, j:j+1]])
            for j in range(len(beta_keys)):
                jacobians[2+len(nkeys)+j] = np.asfortranarray(np.r_[np.zeros((6, 1)), D[:, j:j+1]])
            jacobians[-1] = -np.eye(length, order="F")
        return observable(values)-values.atVector(ykey)

    q = np.diag([.05**2]*3+[.03**2]*3+[0.]*len(selected))
    raw_q = block.Q+params["white_sd_sigma_m"]**2*(incidence.D@incidence.D.T)
    q[6:, 6:] = raw_q[np.ix_(selected, selected)]
    factors.append(gtsam.CustomFactor(gtsam.noiseModel.Gaussian.Covariance(q), measurement_keys, measurement_error))
    linear = JointWindow._graph(factors).linearize(chart)
    order = [key for key in sorted(chart.keys()) if key != ykey]+[ykey]
    conditional, _ = gtsam.JacobianFactor(linear, key_ordering(order)).eliminate(key_ordering(order))
    delta = conditional.solve(gtsam.VectorValues())
    root = np.linalg.solve(conditional.R(), np.diag(conditional.get_model().sigmas()))
    observation_root = root[-len(y0):]
    return y0+delta.at(ykey), observation_root@observation_root.T


def test_phase_source_prediction_matches_joint_graph_and_physical_chart_restore():
    differences = []
    for gaussian in (False, True):
        branch, event, signals = fixture(gaussian)
        old_keys, old_times = dict(branch.phase_beta_keys), dict(branch.phase_beta_times)
        actual = branch.predict_external(event)
        expected_mean, expected_covariance = future_observation_graph(branch, event, [0, 1, 2, 3, 4])
        np.testing.assert_allclose(actual["predicted"], expected_mean, atol=2e-8, rtol=2e-7)
        np.testing.assert_allclose(actual["covariance"], expected_covariance, atol=2e-9, rtol=2e-6)
        assert actual["excluded_unknown_ambiguity_rows"] == [5]
        assert actual["new_phase_beta_signals"] == (signals[2],)
        assert actual["existing_phase_beta_signals"] == signals[:2]
        assert branch.phase_beta_keys == old_keys and branch.phase_beta_times == old_times
        restored = NavigationBranch(branch.metadata, use_foot=False)
        restored.restore(branch.snapshot())
        repeated = restored.predict_external(event)
        np.testing.assert_array_equal(repeated["predicted"], actual["predicted"])
        np.testing.assert_array_equal(repeated["covariance"], actual["covariance"])
        # Distinct local numeric keys must still use the same physical source
        # and epoch in the common chart, including beta-nuisance correlations.
        anchor = branch.export_linearization_anchor()
        for j, (identity, target) in enumerate(branch.phase_beta_coordinates.items()):
            source = gtsam.symbol("e", 101+j)
            anchor["values"].insert_vector(source, np.array([.123+j]))
            anchor["phase_beta_coordinates"][identity] = source
        mapped = restored._model_linearization_values(anchor)
        for j, target in enumerate(branch.phase_beta_coordinates.values()):
            np.testing.assert_array_equal(mapped.atVector(target), [.123+j])
        if gaussian:
            stats = restored.compress_gaussian_history(dict(time_s=0., feet=[]))
            assert stats["retained_phase_source_count"] == 2
            assert set(restored.phase_beta_keys.values()) <= set(restored.window.values.keys())
        differences.append(dict(gaussian=gaussian,
            mean_max_abs=float(np.max(np.abs(actual["predicted"]-expected_mean))),
            covariance_max_abs=float(np.max(np.abs(actual["covariance"]-expected_covariance)))))
    return differences


if __name__ == "__main__":
    import json
    print(json.dumps(test_phase_source_prediction_matches_joint_graph_and_physical_chart_restore(), indent=2))
