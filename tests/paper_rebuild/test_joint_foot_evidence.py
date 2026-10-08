"""Joint source evidence and original foot-row scope in the actual controller."""
from types import SimpleNamespace

import gtsam
import numpy as np
from gtsam.symbol_shorthand import X, V, B
from scipy.stats import multivariate_normal

from legsa_gins.paper_rebuild.joint_navigation.navigator import JointNavigator


def _metadata():
    return dict(baseline_body=[0., -.35, 0.], support_prediction="foot_external",
                support_motion_model=dict(velocity_sigma_mps=.1, tau_s=.5),
                accel_bias_random_walk=0., gyro_bias_random_walk=0.,
                foot_sigma=.02, foot_correlation_tau_s=.5)


def test_joint_controller_density_equals_external_times_conditional_foot_density():
    navigator = JointNavigator(_metadata(), "U3", monitor_support=False)
    # Deliberately correlate both feet with each other and with external rows.
    loading = np.array([[1., .2, -.1], [.3, .6, .2], [-.2, .1, .8],
                        [.5, -.2, .1], [.3, .4, -.1], [-.1, .2, .5]])
    covariance = np.diag([.12, .2, .1, .08, .15, .13])+loading@loading.T
    innovation = np.array([.2, -.4, .1, .6, -.2, .3])
    identities = ("gnss_position:0.1:0", "gnss_position:0.1:1", "gnss_position:0.1:2",
                  "foot:a:0.1:0", "foot:b:0.1:0", "foot:b:0.1:1")
    predicted = dict(row_ids=identities, innovation=innovation, covariance=covariance)
    branch = SimpleNamespace(index=0, predictive_frontier=-1, predictive_score=4.25,
                             predictive_row_count=2, integer_lineage=(),
                             predict_external=lambda packet, **kwargs: predicted)
    navigator.branches = [branch]
    rows, _ = navigator._score_prediction(dict(time_s=.1, gnss_position=np.zeros(3), feet=[{}]), 1)
    joint = -2*multivariate_normal.logpdf(innovation, cov=covariance)
    external = -2*multivariate_normal.logpdf(innovation[:3], cov=covariance[:3, :3])
    gain = np.linalg.solve(covariance[:3, :3], covariance[:3, 3:]).T
    conditional_mean = gain@innovation[:3]
    conditional_covariance = covariance[3:, 3:]-gain@covariance[:3, 3:]
    conditional = -2*multivariate_normal.logpdf(innovation[3:], mean=conditional_mean,
                                                cov=conditional_covariance)
    np.testing.assert_allclose(joint, external+conditional, rtol=1e-14)
    np.testing.assert_allclose(branch.predictive_score, 4.25+joint, rtol=1e-14)
    blocks = navigator.last_prediction_blocks[0]
    np.testing.assert_allclose(blocks["external_marginal_negative_twice_log_density"], external)
    np.testing.assert_allclose(blocks["conditional_foot_negative_twice_log_density"], conditional)
    independent_sum = external-2*multivariate_normal.logpdf(innovation[3:], cov=covariance[3:, 3:])
    assert abs(joint-independent_sum) > .1
    assert rows == identities and branch.predictive_row_count == 8
    assert blocks["score_accumulations"] == 1


def _foot(arc, source_time):
    identity = {"a": 0, "b": 1, "c": 2}[arc]
    points = ([.2, .15, .4], [.2, -.15, .4], [-.2, .15, .4])
    return dict(arc_id=arc, foot_id=identity, force=120., source_time_s=source_time,
                point_body=np.asarray(points[identity])+np.array([.01*source_time, 0., 0.]))


def _initialized_controller(finite):
    policy = ([dict(group_id="observed", arc_ids=("a", "b", "c"), mode="finite_common_motion")]
              if finite else [])
    navigator = JointNavigator(_metadata(), "U3", monitor_support=False, support_models=policy)
    branch = navigator.branches[0]
    branch.index, branch.time, branch.bias_key = 0, 0., B(0)
    branch.bootstrap_status = "INITIALIZED"
    pose = gtsam.Pose3(gtsam.Rot3.RzRyRx(.1, -.05, .2), np.array([.2, .1, -.4]))
    values = gtsam.Values()
    values.insert(X(0), pose)
    values.insert_vector(V(0), np.array([.03, .01, 0.]))
    values.insert(B(0), gtsam.imuBias.ConstantBias())
    factors = [gtsam.PriorFactorPose3(X(0), pose, gtsam.noiseModel.Isotropic.Sigma(6, .05)),
               gtsam.PriorFactorVector(V(0), np.array([.03, .01, 0.]),
                                       gtsam.noiseModel.Isotropic.Sigma(3, .03)),
               gtsam.PriorFactorConstantBias(B(0), gtsam.imuBias.ConstantBias(),
                                             gtsam.noiseModel.Isotropic.Sigma(6, .003))]
    times = {X(0): 0., V(0): 0., B(0): 0.}
    branch._support([_foot("a", 0.), _foot("b", 0.)], set(), navigator.support_models,
                    pose, X(0), values, times, factors)
    branch.window.update(factors, values, times, 0.)
    branch._current()
    return navigator


def test_actual_foot_only_events_score_shared_original_rows_once_and_omit_birth():
    histories = []
    for finite in (False, True):
        navigator = _initialized_controller(finite)
        branch = navigator.branches[0]
        seen, total, row_count = [], 0., 0
        for index, (time_s, arcs) in enumerate(((.1, "abc"), (.2, "c"), (.3, "")), 1):
            packet = dict(time_s=time_s, imu=np.array([[.1, .1, -.2, -9.8, .01, -.02, .03]]),
                          carrier=None, gnss_position=None, gnss_velocity=None,
                          feet=[_foot(arc, time_s) for arc in arcs])
            prediction = branch.predict_external(packet, support_models=navigator.support_models)
            if index == 1:
                assert prediction["excluded_contact_birth_arcs"] == ("c",)
                assert prediction["predicted_foot_arcs"] == ("a", "b")
                assert len(prediction["row_ids"]) == 6
            elif index == 2:
                assert prediction["excluded_contact_birth_arcs"] == ()
                assert prediction["predicted_foot_arcs"] == ("c",)
            if prediction["row_ids"]:
                total += -2*multivariate_normal.logpdf(prediction["innovation"], cov=prediction["covariance"])
                row_count += len(prediction["row_ids"])
                seen.extend(prediction["row_ids"])
            rows, _ = navigator._advance(packet, index)
            assert rows == prediction["row_ids"]
            np.testing.assert_allclose(branch.predictive_score, total, rtol=2e-13, atol=1e-12)
            assert branch.predictive_row_count == row_count
        assert row_count == 9 and len(set(seen)) == len(seen)
        assert branch.predictive_frontier == 2  # IMU-only propagation adds no evidence.
        assert "c" in branch.contact_keys  # Its omitted birth still conditioned the graph.
        histories.append((seen, navigator.predictive_rows_fingerprint))
    assert histories[0] == histories[1]  # Proper alternatives compare identical raw rows.
